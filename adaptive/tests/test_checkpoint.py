"""
Test that DQN checkpoint saves and restores full training state.

Acceptance criteria:
- epsilon round-trips through save/load
- step_counter round-trips through save/load
- Old-format (bare state_dict) checkpoints load with a warning (backward compat)
"""

import os
import tempfile
import torch
import pytest

# These tests exercise real save/load round-trips and need genuine torch.
# When torch is only the lightweight conftest stub, skip instead of erroring.
pytestmark = pytest.mark.skipif(
    getattr(torch, "__stub__", False),
    reason="real torch not installed — checkpoint round-trip tests skipped",
)

# Minimal action space for testing (don't need all 36)
TEST_ACTION_SPACE = [(0, 0, 0.2), (0, 0, 0.4), (0, 0, 0.6)]


@pytest.fixture
def tmp_checkpoint(tmp_path):
    return str(tmp_path / "test_model.pt")


def _make_agent():
    """Create a DQNAgent without importing the full app stack."""
    # We need to import with the project on sys.path
    import sys
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from models.dqn import DQNAgent
    return DQNAgent(action_space=TEST_ACTION_SPACE)


class TestCheckpointRoundTrip:

    def test_epsilon_preserved(self, tmp_checkpoint):
        """Epsilon must survive save/load cycle."""
        agent = _make_agent()

        # Simulate training: decay epsilon
        agent.epsilon = 0.42
        agent.step_counter = 5000

        agent.save_checkpoint(tmp_checkpoint)

        # Create a fresh agent (epsilon=1.0 by default)
        agent2 = _make_agent()
        assert agent2.epsilon == 1.0  # default

        agent2.load_checkpoint(tmp_checkpoint)
        assert agent2.epsilon == pytest.approx(0.42)

    def test_step_counter_preserved(self, tmp_checkpoint):
        """step_counter must survive save/load cycle."""
        agent = _make_agent()
        agent.step_counter = 12345
        agent.epsilon = 0.1

        agent.save_checkpoint(tmp_checkpoint)

        agent2 = _make_agent()
        assert agent2.step_counter == 0  # default

        agent2.load_checkpoint(tmp_checkpoint)
        assert agent2.step_counter == 12345

    def test_optimizer_state_preserved(self, tmp_checkpoint):
        """Optimizer state should be restored so learning continues seamlessly."""
        agent = _make_agent()

        # Do a fake backward pass to populate optimizer state
        dummy_input = torch.randn(1, 16)
        output = agent.model(dummy_input)
        loss = output.sum()
        loss.backward()
        agent.optimizer.step()

        agent.epsilon = 0.33
        agent.step_counter = 999

        agent.save_checkpoint(tmp_checkpoint)

        agent2 = _make_agent()
        agent2.load_checkpoint(tmp_checkpoint)

        # Check optimizer has state (not empty)
        assert len(agent2.optimizer.state) > 0

    def test_target_model_preserved(self, tmp_checkpoint):
        """Target model weights should match after load."""
        agent = _make_agent()

        # Diverge target from model
        with torch.no_grad():
            for p in agent.model.parameters():
                p.add_(torch.randn_like(p) * 0.1)

        # Don't sync target — they should differ
        agent.epsilon = 0.5
        agent.step_counter = 100
        agent.save_checkpoint(tmp_checkpoint)

        agent2 = _make_agent()
        agent2.load_checkpoint(tmp_checkpoint)

        # Model weights should match
        for p1, p2 in zip(agent.model.parameters(), agent2.model.parameters()):
            assert torch.allclose(p1, p2)

        # Target weights should match (and differ from model)
        for p1, p2 in zip(agent.target_model.parameters(), agent2.target_model.parameters()):
            assert torch.allclose(p1, p2)

    def test_old_format_backward_compat(self, tmp_checkpoint):
        """Old-format checkpoint (bare state_dict) should load weights only."""
        agent = _make_agent()

        # Save in OLD format (bare state_dict)
        torch.save(agent.model.state_dict(), tmp_checkpoint)

        agent2 = _make_agent()
        result = agent2.load_checkpoint(tmp_checkpoint)

        assert result is True
        # Epsilon should stay at default (1.0) since old format has no epsilon
        assert agent2.epsilon == 1.0
        assert agent2.step_counter == 0

    def test_missing_checkpoint(self, tmp_checkpoint):
        """Missing file should return False, not crash."""
        agent = _make_agent()
        result = agent.load_checkpoint("/nonexistent/path/model.pt")
        assert result is False
        # Agent should still be functional
        assert agent.epsilon == 1.0
