#!/usr/bin/env python3
"""
Offline DKT training on the interactions collection.

Reads interactions from MongoDB, builds per-student sequences,
trains an LSTM-based DKT model, and saves the checkpoint.

Usage:
  python training/train_dkt.py                       # defaults
  python training/train_dkt.py --epochs 50 --hidden 128
  python training/train_dkt.py --min-interactions 100  # require N rows
"""

import argparse
import asyncio
import logging
import os
import sys
from collections import defaultdict

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import interactions_collection
from core.knowledge_tracing.dkt import DKTModel, encode_interaction

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("train_dkt")


class InteractionDataset(Dataset):
    """Dataset of per-student interaction sequences."""

    def __init__(self, sequences, num_skills, max_seq_len=200):
        self.num_skills = num_skills
        self.max_seq_len = max_seq_len
        self.data = []  # list of (input_seq, target_seq, mask)

        for seq in sequences:
            if len(seq) < 2:
                continue
            # Truncate to max_seq_len
            seq = seq[-max_seq_len:]

            input_encoded = []
            targets = []
            for skill_idx, correct in seq:
                input_encoded.append(encode_interaction(skill_idx, correct, num_skills))
                target = [0.0] * num_skills
                target[skill_idx] = float(correct)
                targets.append(target)

            self.data.append({
                "input": input_encoded[:-1],    # all but last (input to predict next)
                "target": targets[1:],           # all but first (shifted by 1)
                "skill_idx": [s[0] for s in seq[1:]],  # which skill each target refers to
            })

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        return item


def collate_fn(batch):
    """Pad sequences to same length within a batch."""
    max_len = max(len(item["input"]) for item in batch)
    input_dim = len(batch[0]["input"][0]) if batch[0]["input"] else 1
    num_skills = len(batch[0]["target"][0]) if batch[0]["target"] else 1

    inputs_padded = []
    targets_padded = []
    masks = []
    skill_indices = []

    for item in batch:
        seq_len = len(item["input"])
        pad_len = max_len - seq_len

        inp = item["input"] + [[0.0] * input_dim] * pad_len
        tgt = item["target"] + [[0.0] * num_skills] * pad_len
        mask = [1.0] * seq_len + [0.0] * pad_len
        skills = item["skill_idx"] + [0] * pad_len

        inputs_padded.append(inp)
        targets_padded.append(tgt)
        masks.append(mask)
        skill_indices.append(skills)

    return {
        "input": torch.tensor(inputs_padded, dtype=torch.float32),
        "target": torch.tensor(targets_padded, dtype=torch.float32),
        "mask": torch.tensor(masks, dtype=torch.float32),
        "skill_idx": torch.tensor(skill_indices, dtype=torch.long),
    }


async def load_interactions():
    """Load all interactions from MongoDB, group by student."""
    student_seqs = defaultdict(list)
    skill_set = set()

    cursor = interactions_collection.find({}).sort("timestamp", 1)
    count = 0
    async for doc in cursor:
        sid = doc.get("student_id", "")
        skill = doc.get("skill_id", "")
        correct = bool(doc.get("correct", False))
        student_seqs[sid].append((skill, correct))
        skill_set.add(skill)
        count += 1

    logger.info("Loaded %d interactions, %d students, %d skills",
                count, len(student_seqs), len(skill_set))
    return student_seqs, sorted(skill_set)


def train(
    sequences,
    num_skills,
    skill_to_idx,
    hidden_dim=64,
    num_layers=1,
    epochs=30,
    lr=0.001,
    batch_size=32,
    test_split=0.2,
    checkpoint_path="checkpoints/dkt_model.pt",
):
    """Train DKT model and save checkpoint."""

    # Convert skill names to indices
    indexed_seqs = []
    for seq in sequences:
        indexed = []
        for skill_name, correct in seq:
            idx = skill_to_idx.get(skill_name)
            if idx is not None:
                indexed.append((idx, correct))
        if len(indexed) >= 2:
            indexed_seqs.append(indexed)

    if not indexed_seqs:
        logger.error("No valid sequences to train on")
        return None

    # Train/test split
    split = int(len(indexed_seqs) * (1 - test_split))
    train_seqs = indexed_seqs[:split]
    test_seqs = indexed_seqs[split:]

    logger.info("Train: %d seqs, Test: %d seqs", len(train_seqs), len(test_seqs))

    train_ds = InteractionDataset(train_seqs, num_skills)
    test_ds = InteractionDataset(test_seqs, num_skills) if test_seqs else None

    if len(train_ds) == 0:
        logger.error("Training dataset is empty after processing")
        return None

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_fn)
    test_loader = DataLoader(test_ds, batch_size=batch_size, collate_fn=collate_fn) if test_ds and len(test_ds) > 0 else None

    model = DKTModel(num_skills, hidden_dim, num_layers)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.BCEWithLogitsLoss(reduction="none")

    best_test_loss = float("inf")

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        total_items = 0

        for batch in train_loader:
            optimizer.zero_grad()
            logits, _ = model(batch["input"])  # (B, T, num_skills)

            # Gather only the relevant skill's prediction at each timestep
            B, T, S = logits.shape
            skill_idx = batch["skill_idx"]  # (B, T)
            target = batch["target"]        # (B, T, S)
            mask = batch["mask"]            # (B, T)

            # Extract per-skill logits
            skill_logits = logits.gather(2, skill_idx.unsqueeze(2)).squeeze(2)  # (B, T)
            skill_targets = target.gather(2, skill_idx.unsqueeze(2)).squeeze(2)  # (B, T)

            loss = criterion(skill_logits, skill_targets)  # (B, T)
            loss = (loss * mask).sum() / mask.sum().clamp(min=1)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_loss += loss.item() * mask.sum().item()
            total_items += mask.sum().item()

        avg_train_loss = total_loss / max(total_items, 1)

        # Evaluate
        test_loss_str = "N/A"
        if test_loader:
            model.eval()
            test_loss_total = 0.0
            test_items = 0
            with torch.no_grad():
                for batch in test_loader:
                    logits, _ = model(batch["input"])
                    skill_idx = batch["skill_idx"]
                    target = batch["target"]
                    mask = batch["mask"]
                    skill_logits = logits.gather(2, skill_idx.unsqueeze(2)).squeeze(2)
                    skill_targets = target.gather(2, skill_idx.unsqueeze(2)).squeeze(2)
                    loss = criterion(skill_logits, skill_targets)
                    test_loss_total += (loss * mask).sum().item()
                    test_items += mask.sum().item()
            avg_test_loss = test_loss_total / max(test_items, 1)
            test_loss_str = f"{avg_test_loss:.4f}"

            if avg_test_loss < best_test_loss:
                best_test_loss = avg_test_loss

        if (epoch + 1) % 5 == 0 or epoch == 0:
            logger.info("Epoch %d/%d  train_loss=%.4f  test_loss=%s",
                        epoch + 1, epochs, avg_train_loss, test_loss_str)

    # Save checkpoint with training timestamp
    from datetime import datetime, timezone
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    checkpoint = {
        "model_state": model.state_dict(),
        "skill_to_idx": skill_to_idx,
        "num_skills": num_skills,
        "hidden_dim": hidden_dim,
        "num_layers": num_layers,
        "epochs_trained": epochs,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    torch.save(checkpoint, checkpoint_path)
    logger.info("DKT model saved to %s (trained_at=%s)", checkpoint_path, checkpoint["trained_at"])

    return model


async def main(args):
    student_seqs, skills = await load_interactions()

    total_interactions = sum(len(s) for s in student_seqs.values())
    if total_interactions < args.min_interactions:
        logger.warning("Only %d interactions (need %d). Skipping training.",
                       total_interactions, args.min_interactions)
        return

    skill_to_idx = {s: i for i, s in enumerate(skills)}
    sequences = list(student_seqs.values())

    train(
        sequences=sequences,
        num_skills=len(skills),
        skill_to_idx=skill_to_idx,
        hidden_dim=args.hidden,
        num_layers=args.layers,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        checkpoint_path=args.checkpoint,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train DKT on interaction logs")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--hidden", type=int, default=64)
    parser.add_argument("--layers", type=int, default=1)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--min-interactions", type=int, default=100)
    parser.add_argument("--checkpoint", default="checkpoints/dkt_model.pt")
    args = parser.parse_args()
    asyncio.run(main(args))
