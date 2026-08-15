"""
Config-driven LLM model registry with two-tier routing, multi-key pools, and
round-robin load balancing.

Providers: Mistral + Groq only (Gemini/Google + HuggingFace dropped).

Keys — numbered, multiple per provider (load balancing):
    MISTRAL_API_KEY_1, MISTRAL_API_KEY_2, MISTRAL_API_KEY_3, ...
    GROQ_API_KEY_1,    GROQ_API_KEY_2,    GROQ_API_KEY_3,    ...
Legacy single names (MISTRAL_API_KEY / GROQ_API_KEY) are still honored and
appended, so old .env files keep working.

Two tiers (P3.1):
  - STRONG: question generation, explanation, Socratic probing, hints  → Mistral first
  - CHEAP:  grading, verification, classification, prereqs, quiz, KG    → Groq first (fast)

Load balancing: each provider owns a pool of one client per key. On every
build_models()/build_models_cheap() call the PRIMARY provider's pool is rotated
round-robin (thread-safe), so consecutive requests spread across keys → higher
aggregate rate-limit headroom + lower queueing latency. The secondary provider
is appended as the fallback tail, preserving call_llm's existing fallback loop.
"""

import itertools
import logging
import os
import threading
from typing import Dict, List, Optional, Tuple

import yaml

# Compat shim: some langchain-core versions call `langchain.verbose/debug/llm_cache`
# on the legacy `langchain` meta-package. If that package is a version where those
# module-level globals were removed, ChatMistralAI init raises
# "module 'langchain' has no attribute 'verbose'". Define them defensively.
try:
    import langchain as _lc
    for _attr, _val in (("verbose", False), ("debug", False), ("llm_cache", None)):
        if not hasattr(_lc, _attr):
            setattr(_lc, _attr, _val)
except Exception:
    pass

from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI

logger = logging.getLogger("llm_registry")


# ----------------------------------
# CONFIG LOADER
# ----------------------------------

_config_cache: Optional[Dict] = None
_config_lock = threading.Lock()


def _load_config() -> Dict:
    """Load and cache configs/default.yaml. Thread-safe."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    with _config_lock:
        if _config_cache is not None:
            return _config_cache

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "configs",
            "default.yaml",
        )

        try:
            with open(config_path, "r") as f:
                _config_cache = yaml.safe_load(f) or {}
        except FileNotFoundError:
            _config_cache = {}

    return _config_cache


def get_llm_config() -> Dict:
    """Return the llm section of the config with defaults."""
    cfg = _load_config()
    llm = cfg.get("llm", {})
    return {
        "temperature": llm.get("temperature", 0.7),
        "max_retries": llm.get("max_retries", 2),
        "primary_model": llm.get("primary_model", "mistral"),
        "cache": llm.get("cache", {}),
        "retry": llm.get("retry", {}),
        "evaluator": llm.get("evaluator", {}),
        "routing": llm.get("routing", {}),
        "hedge": llm.get("hedge", {}),
    }


# ----------------------------------
# ROUTING CONFIG
# ----------------------------------

# Which engines use the cheap tier (everything else uses strong)
_DEFAULT_CHEAP_ENGINES = {
    "answer_evaluator",
    "answer_verifier",
    "leakage_guard",
    "prerequisite_engine",
    "knowledge_graph",
    "review_engine",
    "quiz_engine",
}


def get_tier_for_engine(engine_name: str) -> str:
    """Return 'cheap' or 'strong' based on engine routing config."""
    cfg = get_llm_config()
    routing = cfg.get("routing", {})
    cheap_engines = set(routing.get("cheap_engines", list(_DEFAULT_CHEAP_ENGINES)))
    return "cheap" if engine_name in cheap_engines else "strong"


# ----------------------------------
# MODEL METADATA
# ----------------------------------

# Base model label per provider (a "#<key-index>" suffix is appended per key).
# Groq: llama-3.3-70b-versatile was decommissioned 2026-08-16 → openai/gpt-oss-120b.
_PROVIDER_MODEL = {
    "mistral": ("Mistral-Large", "mistral-large-latest"),
    "groq": ("Groq-GPT-OSS-120B", "openai/gpt-oss-120b"),
}

# Estimated cost per 1K tokens (input) for telemetry — keyed by BASE label.
# Telemetry strips the "#<idx>" suffix before lookup.
MODEL_COST_PER_1K = {
    "Groq-GPT-OSS-120B": 0.00015,  # input $0.15/1M (Groq, cheap tier)
    "Mistral-Large": 0.00200,      # strong tier
}


# ----------------------------------
# KEY DISCOVERY
# ----------------------------------

_ENV_PREFIX = {"mistral": "MISTRAL_API_KEY", "groq": "GROQ_API_KEY"}


def _keys_for(provider: str) -> List[str]:
    """Collect all keys for a provider: numbered (_1.._N) + legacy single name.

    Order: numbered first (1,2,3,...), then the legacy single key if set and not
    already present. Blanks and duplicates are dropped.
    """
    prefix = _ENV_PREFIX.get(provider)
    if not prefix:
        return []

    keys: List[str] = []
    # Numbered: MISTRAL_API_KEY_1, _2, ... (stop at first gap after index 1)
    i = 1
    misses = 0
    while misses < 2 and i <= 20:  # tolerate one gap, cap at 20 keys
        val = (os.getenv(f"{prefix}_{i}") or "").strip()
        if val:
            if val not in keys:
                keys.append(val)
            misses = 0
        else:
            misses += 1
        i += 1

    # Legacy single name (backward compat)
    legacy = (os.getenv(prefix) or "").strip()
    if legacy and legacy not in keys:
        keys.append(legacy)

    return keys


def _make_client(provider: str, key: str, temperature: float, idx: int) -> Tuple[str, BaseChatModel]:
    base_label, model_id = _PROVIDER_MODEL[provider]
    label = f"{base_label}#{idx}"
    if provider == "mistral":
        return (label, ChatMistralAI(model=model_id, mistral_api_key=key, temperature=temperature))
    # groq
    return (label, ChatGroq(model=model_id, groq_api_key=key, temperature=temperature))


# ----------------------------------
# PROVIDER POOLS (singleton) + ROUND-ROBIN
# ----------------------------------

_pools: Dict[str, List[Tuple[str, BaseChatModel]]] = {}
_pools_lock = threading.Lock()
_rr_counters: Dict[str, "itertools.count"] = {}


def _get_pool(provider: str, temperature: float) -> List[Tuple[str, BaseChatModel]]:
    """Build (once) and return the client pool for a provider — one client per key."""
    if provider in _pools:
        return _pools[provider]
    with _pools_lock:
        if provider in _pools:
            return _pools[provider]
        keys = _keys_for(provider)
        pool = [_make_client(provider, k, temperature, i) for i, k in enumerate(keys, 1)]
        _pools[provider] = pool
        _rr_counters[provider] = itertools.count()
        if pool:
            logger.info("%s pool: %d key(s) -> %s", provider, len(pool), [m[0] for m in pool])
        return pool


def _rotate(provider: str, pool: List[Tuple[str, BaseChatModel]]) -> List[Tuple[str, BaseChatModel]]:
    """Round-robin rotate a provider pool so each call starts at the next key."""
    n = len(pool)
    if n <= 1:
        return list(pool)
    k = next(_rr_counters[provider]) % n
    return pool[k:] + pool[:k]


# ── Per-key 429 cooldown ──────────────────────────────────────────
# When a key returns 429, call_llm calls mark_cooldown() so that key is
# excluded from selection for a short window (config: retry.rate_limit_cooldown).
_cooldown: Dict[str, float] = {}


def mark_cooldown(label: str, seconds: float) -> None:
    """Mark a key label (e.g. 'Groq-GPT-OSS-120B#2') rate-limited for `seconds`."""
    import time as _t
    _cooldown[label] = _t.time() + max(float(seconds), 1.0)


def is_cooling(label: str) -> bool:
    import time as _t
    until = _cooldown.get(label)
    return until is not None and _t.time() < until


def _drop_cooling(
    models: List[Tuple[str, BaseChatModel]],
) -> List[Tuple[str, BaseChatModel]]:
    """Filter out keys currently in 429 cooldown. If ALL are cooling, keep the
    full list — trying a cooling key beats returning nothing."""
    alive = [m for m in models if not is_cooling(m[0])]
    return alive or models


def _compose(order: List[str], temperature: float) -> List[Tuple[str, BaseChatModel]]:
    """Build a tier's model list from an ordered provider list.

    First available provider = primary (round-robin rotated across its keys);
    remaining providers appended in order as the fallback tail.
    """
    blocks = [(name, _get_pool(name, temperature)) for name in order]
    blocks = [(name, pool) for name, pool in blocks if pool]  # drop providers w/o keys
    if not blocks:
        raise ValueError(
            "No API keys found. Set at least one of: "
            "MISTRAL_API_KEY_1.., GROQ_API_KEY_1.. (or legacy MISTRAL_API_KEY / GROQ_API_KEY)"
        )
    primary_name, primary_pool = blocks[0]
    models = _rotate(primary_name, primary_pool)
    for _, pool in blocks[1:]:
        models.extend(pool)
    return _drop_cooling(models)


# ----------------------------------
# PUBLIC BUILDERS
# ----------------------------------

def build_models() -> List[Tuple[str, BaseChatModel]]:
    """STRONG tier (question gen, explanation, Socratic, hints).

    Returns a round-robin-balanced, fallback-ordered model list. Called per
    request — the returned order rotates across keys for load balancing.
    """
    routing = get_llm_config().get("routing", {})
    temperature = get_llm_config()["temperature"]
    order = [p for p in routing.get("strong_order", ["mistral", "groq"]) if p in _ENV_PREFIX]
    return _compose(order or ["mistral", "groq"], temperature)


def build_models_cheap() -> List[Tuple[str, BaseChatModel]]:
    """CHEAP tier (grading, verification, classification). Groq first = fast."""
    routing = get_llm_config().get("routing", {})
    temperature = get_llm_config()["temperature"]
    order = [p for p in routing.get("cheap_order", ["groq", "mistral"]) if p in _ENV_PREFIX]
    return _compose(order or ["groq", "mistral"], temperature)


def build_models_for_engine(engine_name: str) -> List[Tuple[str, BaseChatModel]]:
    """Return the appropriate model list for a given engine name."""
    tier = get_tier_for_engine(engine_name)
    if tier == "cheap":
        return build_models_cheap()
    return build_models()
