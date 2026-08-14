"""
Feature flags loader — reads from configs/default.yaml.
Gate deferred features behind these flags so they can be re-enabled
once validated (see PHASE_WISE_IMPROVEMENT.md).
"""
import os
import yaml
from pathlib import Path

_config_path = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"

def _load() -> dict:
    try:
        with open(_config_path) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("features", {})
    except Exception:
        return {}

_flags = _load()

# --- Public flags ---
RL_ENABLED: bool = _flags.get("rl_enabled", False)
GAMIFICATION_ENABLED: bool = _flags.get("gamification_enabled", False)
QUESTS_ENABLED: bool = _flags.get("quests_enabled", False)
GUARDIAN_ENABLED: bool = _flags.get("guardian_enabled", False)
CERTIFICATES_ENABLED: bool = _flags.get("certificates_enabled", False)
DKT_ENABLED: bool = _flags.get("dkt_enabled", False)
VOICE_ENABLED: bool = _flags.get("voice_enabled", False)
LEADERBOARD_ENABLED: bool = _flags.get("leaderboard_enabled", False)

# Allow env overrides (e.g. RL_ENABLED=true)
def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")

RL_ENABLED = _env_bool("RL_ENABLED", RL_ENABLED)
GAMIFICATION_ENABLED = _env_bool("GAMIFICATION_ENABLED", GAMIFICATION_ENABLED)
QUESTS_ENABLED = _env_bool("QUESTS_ENABLED", QUESTS_ENABLED)
GUARDIAN_ENABLED = _env_bool("GUARDIAN_ENABLED", GUARDIAN_ENABLED)
CERTIFICATES_ENABLED = _env_bool("CERTIFICATES_ENABLED", CERTIFICATES_ENABLED)
DKT_ENABLED = _env_bool("DKT_ENABLED", DKT_ENABLED)
VOICE_ENABLED = _env_bool("VOICE_ENABLED", VOICE_ENABLED)
LEADERBOARD_ENABLED = _env_bool("LEADERBOARD_ENABLED", LEADERBOARD_ENABLED)

# Online RL training is OFF in production: models are trained locally and the
# trained checkpoint is shipped with the deploy. DQN still SERVES from the
# checkpoint; it just never updates its weights from live traffic.
RL_ONLINE_LEARNING = _env_bool("RL_ONLINE_LEARNING", RL_ENABLED)
