"""
Bayesian Knowledge Tracing (BKT) — per-skill mastery estimation.

Standard BKT with four parameters per skill:
  p_L0   — prior probability of knowing the skill
  p_T    — probability of learning (transitioning from unknown -> known)
  p_G    — probability of guessing correctly despite not knowing
  p_S    — probability of slipping (answering wrong despite knowing)

Updates are Bayesian: after each observed response, the posterior P(known)
is computed via the standard BKT update equations.

Parameters are fit via grid-search MLE on historical interaction data.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("knowledge_tracing.bkt")

# Default BKT parameters (reasonable priors from literature)
DEFAULT_PARAMS = {
    "p_L0": 0.3,   # initial mastery probability
    "p_T": 0.1,    # learn rate per opportunity
    "p_G": 0.2,    # guess rate
    "p_S": 0.1,    # slip rate
}

# Grid for parameter fitting
_GRID = {
    "p_L0": [0.1, 0.2, 0.3, 0.4, 0.5],
    "p_T":  [0.05, 0.1, 0.15, 0.2, 0.3],
    "p_G":  [0.1, 0.15, 0.2, 0.25, 0.3],
    "p_S":  [0.05, 0.1, 0.15, 0.2],
}


def _bkt_update(p_known: float, correct: bool,
                p_G: float, p_S: float, p_T: float) -> float:
    """
    Single BKT posterior update.

    P(L_n | obs) = P(obs | L_n) * P(L_n) / P(obs)
    Then apply learning transition.
    """
    if correct:
        # P(correct | known) = 1 - p_S
        # P(correct | unknown) = p_G
        p_obs_known = 1.0 - p_S
        p_obs_unknown = p_G
    else:
        p_obs_known = p_S
        p_obs_unknown = 1.0 - p_G

    # Posterior before learning transition
    numerator = p_obs_known * p_known
    denominator = numerator + p_obs_unknown * (1.0 - p_known)

    if denominator < 1e-10:
        p_posterior = p_known
    else:
        p_posterior = numerator / denominator

    # Apply learning transition: unknown students may learn
    p_known_after = p_posterior + (1.0 - p_posterior) * p_T

    return max(0.0, min(1.0, p_known_after))


def predict_sequence(responses: List[bool], params: Dict[str, float]) -> List[float]:
    """
    Run BKT forward on a sequence of responses.
    Returns list of P(known) BEFORE each response (for prediction evaluation).
    """
    p = params["p_L0"]
    predictions = []

    for correct in responses:
        predictions.append(p)  # predict BEFORE observing
        p = _bkt_update(p, correct, params["p_G"], params["p_S"], params["p_T"])

    return predictions


def run_bkt(responses: List[bool], params: Optional[Dict[str, float]] = None) -> float:
    """
    Run BKT on a sequence of responses and return final P(known).
    """
    if params is None:
        params = DEFAULT_PARAMS.copy()

    p = params["p_L0"]
    for correct in responses:
        p = _bkt_update(p, correct, params["p_G"], params["p_S"], params["p_T"])

    return p


def predict_correct(p_known: float, p_G: float, p_S: float) -> float:
    """
    Predict P(correct) from current mastery estimate.
    P(correct) = P(known) * (1 - p_S) + P(unknown) * p_G
    """
    return p_known * (1.0 - p_S) + (1.0 - p_known) * p_G


def _log_likelihood(responses: List[bool], params: Dict[str, float]) -> float:
    """Compute log-likelihood of observed responses under BKT parameters."""
    p = params["p_L0"]
    ll = 0.0

    for correct in responses:
        p_correct = predict_correct(p, params["p_G"], params["p_S"])
        if correct:
            ll += math.log(max(p_correct, 1e-10))
        else:
            ll += math.log(max(1.0 - p_correct, 1e-10))
        p = _bkt_update(p, correct, params["p_G"], params["p_S"], params["p_T"])

    return ll


def fit_params(responses: List[bool]) -> Dict[str, float]:
    """
    Fit BKT parameters via grid-search MLE.
    Returns best parameter dict.
    """
    if len(responses) < 5:
        return DEFAULT_PARAMS.copy()

    best_ll = float("-inf")
    best_params = DEFAULT_PARAMS.copy()

    for p_L0 in _GRID["p_L0"]:
        for p_T in _GRID["p_T"]:
            for p_G in _GRID["p_G"]:
                for p_S in _GRID["p_S"]:
                    # Identifiability constraint: p_G + p_S < 1
                    if p_G + p_S >= 1.0:
                        continue
                    params = {"p_L0": p_L0, "p_T": p_T, "p_G": p_G, "p_S": p_S}
                    ll = _log_likelihood(responses, params)
                    if ll > best_ll:
                        best_ll = ll
                        best_params = params.copy()

    logger.info("BKT fit: LL=%.4f params=%s (n=%d)", best_ll, best_params, len(responses))
    return best_params
