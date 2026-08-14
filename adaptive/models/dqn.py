import random
import os
import logging

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    HAS_TORCH = True
    _ModuleBase = nn.Module
except ImportError:
    torch = None
    nn = None
    optim = None
    HAS_TORCH = False
    _ModuleBase = object

logger = logging.getLogger("rl.dqn")

from adaptive.models.replay_buffer import ReplayBuffer
from adaptive.utils.device import device
from adaptive.utils.state_vector import build_state_vector
from adaptive.utils.rl_metrics import RLMetrics


# ----------------------------------
# MODEL
# ----------------------------------

class DQN(_ModuleBase):

    def __init__(self, state_dim=16, action_dim=36):
        if HAS_TORCH:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(state_dim, 256), nn.ReLU(),
                nn.Linear(256, 256), nn.ReLU(),
                nn.Linear(256, 128), nn.ReLU(),
                nn.Linear(128, action_dim)
            )
        else:
            self.net = None

    def forward(self, x):
        if HAS_TORCH and self.net is not None:
            return self.net(x)
        return None


# ----------------------------------
# AGENT
# ----------------------------------

class DQNAgent:

    def __init__(self, action_space, db_collection=None, min_buffer=500):

        self.action_space = action_space

        # RL PARAMS
        self.gamma = 0.95
        self.epsilon = 1.0
        self.epsilon_decay = 0.999
        self.epsilon_min = 0.05

        # PERFORMANCE
        self.train_freq = 4
        self.min_buffer = min_buffer

        # MODELS
        if HAS_TORCH:
            self.model = DQN(state_dim=16, action_dim=len(action_space)).to(device)
            self.target_model = DQN(state_dim=16, action_dim=len(action_space)).to(device)
            self.target_model.load_state_dict(self.model.state_dict())
            self.target_model.eval()
            self.optimizer = optim.Adam(self.model.parameters(), lr=0.0003)
            self.loss_fn = nn.MSELoss()
        else:
            self.model = None
            self.target_model = None
            self.optimizer = None
            self.loss_fn = None

        self.replay_buffer = ReplayBuffer(20000, db_collection=db_collection)
        self.batch_size = 64

        self.target_update_freq = 500
        self.step_counter = 0

        # Observability
        self.metrics = RLMetrics()

    # ----------------------------------
    # STATE (NORMALIZED — uses shared helper)
    # ----------------------------------

    def get_state(self, student, kt_mastery: float = None):

        concept = student.get_current_concept()

        # Use KT-calibrated mastery if provided, else heuristic
        knowledge = kt_mastery if kt_mastery is not None else concept.knowledge

        vec = build_state_vector(
            knowledge=knowledge,
            learning_velocity=student.learning_velocity,
            confidence=student.confidence,
            concept_mastery=concept.concept_mastery,
            engagement=student.engagement,
            speed=student.speed,
            hint_dependency=student.hint_dependency,
            streak=student.streak,
            fatigue=student.fatigue,
            frustration=student.frustration,
            curiosity=student.curiosity,
            focus=student.focus,
            retention=student.retention,
            cognitive_load=student.cognitive_load,
            conversation_turns=getattr(student, "conversation_turns", 0),
            last_mode=getattr(student, "last_mode", 0),
        )

        if HAS_TORCH:
            return torch.tensor(vec, dtype=torch.float32, device=device)
        return vec

    # ----------------------------------
    # ACTION
    # ----------------------------------

    def get_action(self, student, explore=True, serve_epsilon=0.0, kt_mastery=None):
        state = self.get_state(student, kt_mastery=kt_mastery)

        if not HAS_TORCH or self.model is None:
            action_index = random.randrange(len(self.action_space))
            return action_index, self.action_space[action_index]

        if explore:
            eps = self.epsilon
        else:
            eps = serve_epsilon

        if random.random() < eps:
            action_index = random.randrange(len(self.action_space))
        else:
            with torch.no_grad():
                q_values = self.model(state)
                action_index = torch.argmax(q_values).item()

        return action_index, self.action_space[action_index]

    # ----------------------------------
    # STORE EXPERIENCE
    # ----------------------------------

    def store_transition(self, state, action, reward, next_state, done=False):
        if HAS_TORCH:
            st = torch.tensor(state, dtype=torch.float32)
            nst = torch.tensor(next_state, dtype=torch.float32)
        else:
            st = state
            nst = next_state

        self.replay_buffer.push(
            st,
            action,
            reward,
            nst,
            done
        )

    # ----------------------------------
    # TRAIN STEP (OPTIMIZED)
    # ----------------------------------

    def train_step(self):
        if not HAS_TORCH or self.model is None:
            return

        if len(self.replay_buffer) < self.min_buffer:
            return

        states, actions, rewards, next_states, dones = \
            self.replay_buffer.sample(self.batch_size)

        states = states.to(device)
        next_states = next_states.to(device)

        actions = torch.tensor(actions, device=device)
        rewards = torch.tensor(rewards, dtype=torch.float32, device=device)
        dones = torch.tensor(dones, dtype=torch.float32, device=device)

        # CURRENT Q
        q_values = self.model(states)
        q_value = q_values.gather(1, actions.unsqueeze(1)).squeeze()

        # DOUBLE DQN TARGET
        with torch.no_grad():
            next_actions = torch.argmax(self.model(next_states), dim=1)
            next_q = self.target_model(next_states)
            max_next_q = next_q.gather(1, next_actions.unsqueeze(1)).squeeze()

            target = rewards + self.gamma * max_next_q * (1 - dones)

        loss = self.loss_fn(q_value, target)

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()

        # RECORD LOSS
        self.metrics.record_loss(loss.item())

        # UPDATE TARGET
        self.step_counter += 1

        if self.step_counter % self.target_update_freq == 0:
            self.target_model.load_state_dict(self.model.state_dict())

        # EPSILON DECAY
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        # CHECKPOINT (full training state)
        if self.step_counter % 1000 == 0:
            self.save_checkpoint()

    # ----------------------------------
    # SAVE / LOAD FULL TRAINING STATE
    # ----------------------------------

    def save_checkpoint(self, path="checkpoints/dqn_model.pt"):
        if not HAS_TORCH or self.model is None:
            return
        os.makedirs(os.path.dirname(path) or "checkpoints", exist_ok=True)
        torch.save({
            "model": self.model.state_dict(),
            "target_model": self.target_model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "epsilon": self.epsilon,
            "step_counter": self.step_counter,
        }, path)
        print("Full checkpoint saved (step=%d, eps=%.4f)" % (self.step_counter, self.epsilon))

    def load_checkpoint(self, path="checkpoints/dqn_model.pt"):
        if not HAS_TORCH or self.model is None:
            return False
        """
        Load checkpoint. Supports both new (dict with keys) and old (bare state_dict) formats.
        Returns True if loaded successfully, False if file not found.
        """
        if not os.path.exists(path):
            print("WARNING: No checkpoint found. Starting fresh.")
            return False

        try:
            # SEC (BUG-1/SEC-1): weights_only=True uses Torch's restricted
            # unpickler, preventing arbitrary code execution from a tampered
            # checkpoint. torch is pinned >=2.0 (requirements.txt) so the kwarg is
            # always available. No weights_only=False fallback — that would re-open
            # the RCE hole. Checkpoints are produced only by our own training job;
            # if a legacy checkpoint fails to load, re-save it once via
            # scripts/reserialize_checkpoints.py. Fail closed on any load error.
            saved = torch.load(path, map_location=device, weights_only=True)

            if isinstance(saved, dict) and "model" in saved:
                # New format: full training state
                self.model.load_state_dict(saved["model"])
                self.target_model.load_state_dict(saved["target_model"])
                self.optimizer.load_state_dict(saved["optimizer"])
                self.epsilon = saved["epsilon"]
                self.step_counter = saved["step_counter"]
                self.model.eval()
                print(
                    "Loaded full checkpoint (step=%d, eps=%.4f)"
                    % (self.step_counter, self.epsilon)
                )
            else:
                # Old format: bare state_dict (backward compat)
                self.model.load_state_dict(saved)
                self.model.eval()
                print(
                    "WARNING: Loaded old-format checkpoint (weights only). "
                    "epsilon and step_counter reset to defaults. "
                    "Re-save to upgrade."
                )

            return True

        except RuntimeError as e:
            print("WARNING: Checkpoint incompatible (%s). Starting fresh." % e)
            os.rename(path, path + ".old")
            return False
