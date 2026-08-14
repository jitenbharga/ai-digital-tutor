"""
Deep Knowledge Tracing (DKT) — LSTM-based sequence model.

Input:  sequence of (skill_id, correct) pairs
Output: P(correct) for each skill at each timestep

The model learns a hidden student state from the full interaction sequence.
Training is done offline via training/train_dkt.py on the interactions collection.

At serving time, the trained model is loaded from a checkpoint and used to
predict mastery by feeding the student's interaction history through the LSTM.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
    _ModuleBase = nn.Module
except ImportError:
    torch = None
    nn = None
    HAS_TORCH = False
    _ModuleBase = object

logger = logging.getLogger("knowledge_tracing.dkt")


class DKTModel(_ModuleBase):
    """
    Standard DKT architecture (Piech et al., 2015).

    Input encoding: one-hot of (skill_id * 2 + correct) — 2*num_skills dims.
    Output: P(correct) for each skill — num_skills dims.
    """

    def __init__(self, num_skills: int, hidden_dim: int = 64, num_layers: int = 1):
        super().__init__()
        self.num_skills = num_skills
        self.input_dim = num_skills * 2  # (skill, correct) encoding
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=self.input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.0 if num_layers == 1 else 0.1,
        )
        self.output = nn.Linear(hidden_dim, num_skills)

    def forward(self, x: torch.Tensor, hidden=None):
        """
        Args:
            x: (batch, seq_len, input_dim) — one-hot encoded interactions
            hidden: optional (h, c) LSTM state

        Returns:
            logits: (batch, seq_len, num_skills) — raw scores before sigmoid
            hidden: updated LSTM state
        """
        lstm_out, hidden = self.lstm(x, hidden)
        logits = self.output(lstm_out)
        return logits, hidden

    def predict_proba(self, x: torch.Tensor, hidden=None):
        """Return P(correct) per skill per timestep."""
        logits, hidden = self.forward(x, hidden)
        return torch.sigmoid(logits), hidden


def encode_interaction(skill_idx: int, correct: bool, num_skills: int) -> List[float]:
    """
    One-hot encode a single interaction: skill * 2 + correct.
    Returns a vector of length num_skills * 2.
    """
    vec = [0.0] * (num_skills * 2)
    idx = skill_idx * 2 + int(correct)
    if 0 <= idx < len(vec):
        vec[idx] = 1.0
    return vec


class DKTPredictor:
    """
    Serving wrapper: loads a trained DKT checkpoint and predicts mastery.
    """

    def __init__(self, checkpoint_path: str = "checkpoints/dkt_model.pt"):
        self.checkpoint_path = checkpoint_path
        self.model: Optional[DKTModel] = None
        self.skill_to_idx: Dict[str, int] = {}
        self.num_skills = 0
        self._loaded = False

    def load(self) -> bool:
        """Load trained DKT model. Returns False if no checkpoint exists."""
        if not os.path.exists(self.checkpoint_path):
            logger.info("No DKT checkpoint at %s", self.checkpoint_path)
            return False

        try:
            # SEC (BUG-1/SEC-1): weights_only=True blocks arbitrary code execution
            # from a tampered checkpoint. Contents are tensors + plain metadata.
            checkpoint = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
            self.skill_to_idx = checkpoint["skill_to_idx"]
            self.num_skills = checkpoint["num_skills"]
            hidden_dim = checkpoint.get("hidden_dim", 64)
            num_layers = checkpoint.get("num_layers", 1)

            self.model = DKTModel(self.num_skills, hidden_dim, num_layers)
            self.model.load_state_dict(checkpoint["model_state"])
            self.model.eval()
            self._loaded = True
            logger.info("DKT model loaded: %d skills, hidden=%d", self.num_skills, hidden_dim)
            return True
        except Exception as e:
            logger.warning("Failed to load DKT checkpoint: %s", e)
            return False

    @property
    def is_available(self) -> bool:
        return self._loaded and self.model is not None

    @torch.no_grad()
    def predict_mastery(
        self, interactions: List[Tuple[str, bool]]
    ) -> Dict[str, float]:
        """
        Given a student's interaction sequence [(skill_name, correct), ...],
        return P(correct) for each seen skill.
        """
        if not self.is_available or not interactions:
            return {}

        # Encode sequence
        encoded = []
        for skill_name, correct in interactions:
            idx = self.skill_to_idx.get(skill_name)
            if idx is None:
                continue
            encoded.append(encode_interaction(idx, correct, self.num_skills))

        if not encoded:
            return {}

        x = torch.tensor([encoded], dtype=torch.float32)  # (1, seq_len, input_dim)
        probs, _ = self.model.predict_proba(x)

        # Extract final timestep predictions for each skill
        final_probs = probs[0, -1, :]  # (num_skills,)
        result = {}
        for skill_name, idx in self.skill_to_idx.items():
            result[skill_name] = round(final_probs[idx].item(), 4)

        return result

    def predict_skill(
        self, interactions: List[Tuple[str, bool]], target_skill: str
    ) -> Optional[float]:
        """Predict P(correct) for a specific skill."""
        if target_skill not in self.skill_to_idx:
            return None
        all_probs = self.predict_mastery(interactions)
        return all_probs.get(target_skill)
