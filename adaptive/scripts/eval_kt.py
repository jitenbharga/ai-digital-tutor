#!/usr/bin/env python3
"""
Offline evaluation of Knowledge Tracing models on interaction logs.

Splits interactions by student into train/test, evaluates BKT and DKT
predictions on the held-out portion.

Reports: AUC, accuracy, log-loss for each model.

Usage:
  python scripts/eval_kt.py
  python scripts/eval_kt.py --test-ratio 0.3
"""

import argparse
import asyncio
import logging
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adaptive.database import interactions_collection
from adaptive.core.knowledge_tracing.bkt import fit_params, predict_sequence, predict_correct, DEFAULT_PARAMS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("eval_kt")


def compute_auc(labels, scores):
    """Compute AUC via Mann-Whitney U statistic."""
    if not labels or not scores or len(labels) != len(scores):
        return 0.5

    pairs = list(zip(scores, labels))
    pairs.sort(key=lambda x: x[0])

    pos_count = sum(labels)
    neg_count = len(labels) - pos_count

    if pos_count == 0 or neg_count == 0:
        return 0.5

    # Count concordant pairs
    rank_sum = 0
    for i, (score, label) in enumerate(pairs):
        if label == 1:
            rank_sum += i + 1  # 1-indexed rank

    u = rank_sum - pos_count * (pos_count + 1) / 2
    auc = u / (pos_count * neg_count)
    return auc


def compute_accuracy(labels, scores, threshold=0.5):
    """Binary accuracy at given threshold."""
    if not labels:
        return 0.0
    correct = sum(1 for l, s in zip(labels, scores) if (s >= threshold) == (l == 1))
    return correct / len(labels)


def compute_logloss(labels, scores):
    """Binary cross-entropy (log loss)."""
    if not labels:
        return float("inf")
    eps = 1e-7
    ll = 0.0
    for l, s in zip(labels, scores):
        s = max(eps, min(1 - eps, s))
        if l == 1:
            ll -= math.log(s)
        else:
            ll -= math.log(1 - s)
    return ll / len(labels)


async def load_interactions():
    """Load all interactions grouped by student."""
    student_seqs = defaultdict(list)
    cursor = interactions_collection.find({}).sort("timestamp", 1)

    async for doc in cursor:
        sid = doc.get("student_id", "")
        skill = doc.get("skill_id", "")
        correct = bool(doc.get("correct", False))
        student_seqs[sid].append((skill, correct))

    return student_seqs


def evaluate_bkt(student_seqs, test_ratio=0.2):
    """Evaluate BKT predictions on held-out test portion."""
    all_labels = []
    all_scores = []

    for sid, seq in student_seqs.items():
        if len(seq) < 5:
            continue

        # Split: train on first (1-test_ratio), test on rest
        split = max(2, int(len(seq) * (1 - test_ratio)))
        train_seq = seq[:split]
        test_seq = seq[split:]

        if not test_seq:
            continue

        # Group train responses by skill and fit BKT params
        skill_responses = defaultdict(list)
        for skill, correct in train_seq:
            skill_responses[skill].append(correct)

        skill_params = {}
        for skill, responses in skill_responses.items():
            skill_params[skill] = fit_params(responses)

        # Run BKT on the full train sequence to get posterior states per skill
        skill_states = {}
        for skill, correct in train_seq:
            params = skill_params.get(skill, DEFAULT_PARAMS)
            from core.knowledge_tracing.bkt import _bkt_update
            p = skill_states.get(skill, params["p_L0"])
            p = _bkt_update(p, correct, params["p_G"], params["p_S"], params["p_T"])
            skill_states[skill] = p

        # Predict on test
        for skill, correct in test_seq:
            params = skill_params.get(skill, DEFAULT_PARAMS)
            p_known = skill_states.get(skill, params["p_L0"])
            p_correct = predict_correct(p_known, params["p_G"], params["p_S"])

            all_labels.append(int(correct))
            all_scores.append(p_correct)

            # Update state with observed response
            p_known = _bkt_update(p_known, correct, params["p_G"], params["p_S"], params["p_T"])
            skill_states[skill] = p_known

    return all_labels, all_scores


def evaluate_dkt(student_seqs, test_ratio=0.2):
    """Evaluate DKT predictions on held-out test portion."""
    try:
        from core.knowledge_tracing.dkt import DKTPredictor
    except ImportError:
        return [], []

    dkt = DKTPredictor()
    if not dkt.load():
        logger.warning("No DKT checkpoint found, skipping DKT eval")
        return [], []

    all_labels = []
    all_scores = []

    for sid, seq in student_seqs.items():
        if len(seq) < 5:
            continue

        split = max(2, int(len(seq) * (1 - test_ratio)))
        train_seq = seq[:split]
        test_seq = seq[split:]

        if not test_seq:
            continue

        # Build context from training portion, predict on test
        context = list(train_seq)
        for skill, correct in test_seq:
            p = dkt.predict_skill(context, skill)
            if p is not None:
                all_labels.append(int(correct))
                all_scores.append(p)
            context.append((skill, correct))

    return all_labels, all_scores


async def main(args):
    student_seqs = await load_interactions()
    total = sum(len(s) for s in student_seqs.values())
    logger.info("Loaded %d students, %d total interactions", len(student_seqs), total)

    if total < 10:
        logger.warning("Not enough interactions for meaningful evaluation")
        return

    print("\n" + "=" * 60)
    print("Knowledge Tracing Evaluation Report")
    print("=" * 60)

    # BKT
    bkt_labels, bkt_scores = evaluate_bkt(student_seqs, args.test_ratio)
    if bkt_labels:
        bkt_auc = compute_auc(bkt_labels, bkt_scores)
        bkt_acc = compute_accuracy(bkt_labels, bkt_scores)
        bkt_ll = compute_logloss(bkt_labels, bkt_scores)
        print(f"\nBKT (Bayesian Knowledge Tracing)")
        print(f"  Test samples: {len(bkt_labels)}")
        print(f"  AUC:          {bkt_auc:.4f}")
        print(f"  Accuracy:     {bkt_acc:.4f}")
        print(f"  Log-loss:     {bkt_ll:.4f}")
        print(f"  Base rate:    {sum(bkt_labels)/len(bkt_labels):.4f}")
    else:
        print("\nBKT: Insufficient data for evaluation")

    # DKT
    dkt_labels, dkt_scores = evaluate_dkt(student_seqs, args.test_ratio)
    if dkt_labels:
        dkt_auc = compute_auc(dkt_labels, dkt_scores)
        dkt_acc = compute_accuracy(dkt_labels, dkt_scores)
        dkt_ll = compute_logloss(dkt_labels, dkt_scores)
        print(f"\nDKT (Deep Knowledge Tracing)")
        print(f"  Test samples: {len(dkt_labels)}")
        print(f"  AUC:          {dkt_auc:.4f}")
        print(f"  Accuracy:     {dkt_acc:.4f}")
        print(f"  Log-loss:     {dkt_ll:.4f}")
        print(f"  Base rate:    {sum(dkt_labels)/len(dkt_labels):.4f}")
    else:
        print("\nDKT: No trained model or insufficient data")

    # Random baseline
    if bkt_labels:
        base_rate = sum(bkt_labels) / len(bkt_labels)
        baseline_ll = compute_logloss(bkt_labels, [base_rate] * len(bkt_labels))
        print(f"\nRandom Baseline")
        print(f"  AUC:          0.5000")
        print(f"  Accuracy:     {max(base_rate, 1-base_rate):.4f}")
        print(f"  Log-loss:     {baseline_ll:.4f}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate KT models")
    parser.add_argument("--test-ratio", type=float, default=0.2)
    args = parser.parse_args()
    asyncio.run(main(args))
