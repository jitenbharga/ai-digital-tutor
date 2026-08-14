"""
In-memory TTL cache for LLM responses.

Keys are hashed from (engine_name, topic, difficulty, coarse_profile_bucket, prompt_version).
Continuous traits are bucketed (rounded to 0.1) so the cache actually hits.
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

from adaptive.core.llm_registry import get_llm_config

logger = logging.getLogger("llm_cache")


class LLMCache:
    """Thread-safe in-memory TTL cache with LRU eviction."""

    def __init__(self, max_size: int = 512, ttl_seconds: int = 600):
        self._cache: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

        # Stats
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if exists and not expired, else None."""
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                logger.debug("cache_miss key=%s", key[:16])
                return None

            ts, value = self._cache[key]
            if time.time() - ts > self.ttl_seconds:
                # Expired
                del self._cache[key]
                self.misses += 1
                logger.debug("cache_expired key=%s", key[:16])
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self.hits += 1
            logger.debug("cache_hit key=%s", key[:16])
            return value

    def put(self, key: str, value: Any) -> None:
        """Store value with current timestamp."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = (time.time(), value)
            else:
                # Evict oldest if at capacity
                while len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)
                self._cache[key] = (time.time(), value)

    def stats(self) -> Dict:
        """Return cache statistics."""
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / max(1, total), 3),
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
        }


# ----------------------------------
# CACHE KEY BUILDER
# ----------------------------------

def _bucket(value: float, precision: float = 0.1) -> float:
    """Round a continuous trait to the nearest bucket."""
    return round(round(value / precision) * precision, 2)


def build_cache_key(
    engine_name: str,
    topic: str,
    difficulty: str = "",
    profile_bucket: Optional[Dict[str, float]] = None,
    prompt_version: str = "v1",
    extra: Optional[Dict[str, str]] = None,
) -> str:
    """
    Build a deterministic cache key from engine inputs.

    Continuous profile traits are bucketed to 0.1 precision so near-identical
    students share cache entries.
    """
    key_parts = {
        "engine": engine_name,
        "topic": topic.strip().lower(),
        "difficulty": difficulty.strip().lower(),
        "prompt_version": prompt_version,
    }

    if profile_bucket:
        # Bucket all continuous traits
        bucketed = {k: _bucket(v) for k, v in sorted(profile_bucket.items())}
        key_parts["profile"] = bucketed

    if extra:
        key_parts["extra"] = extra

    raw = json.dumps(key_parts, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


# ----------------------------------
# SINGLETON INSTANCE
# ----------------------------------

_cache_instance: Optional[LLMCache] = None
_cache_lock = threading.Lock()


def get_llm_cache() -> Optional[LLMCache]:
    """
    Return the shared LLM cache instance, or None if caching is disabled.
    Config-driven from configs/default.yaml llm.cache section.
    """
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    with _cache_lock:
        if _cache_instance is not None:
            return _cache_instance

        cfg = get_llm_config()
        cache_cfg = cfg.get("cache", {})

        if not cache_cfg.get("enabled", True):
            return None

        _cache_instance = LLMCache(
            max_size=cache_cfg.get("max_size", 512),
            ttl_seconds=cache_cfg.get("ttl_seconds", 600),
        )

    return _cache_instance
