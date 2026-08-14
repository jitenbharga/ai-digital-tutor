"""
W5: short-TTL cache for the auth user lookup.

`get_current_user` runs on every authenticated request and previously hit Mongo
each time. This caches the user document per worker for a few seconds and is
invalidated whenever the user is written (password reset, email verify, create),
so staleness is bounded and correctness is preserved.

Per-worker in-memory by design: user docs change rarely, a 30s TTL cuts the vast
majority of reads, and there is no cross-worker consistency requirement (a write
invalidates only the writing worker's entry; others expire within TTL). Set
USER_CACHE_TTL_SECONDS=0 to disable, or back it with Redis later if needed.
"""
import os
import threading
import time

# Read at import; tests monkeypatch this attribute directly.
TTL_SECONDS = float(os.getenv("USER_CACHE_TTL_SECONDS", "30"))

_lock = threading.Lock()
_store: dict = {}  # username -> (expires_at_monotonic, user_doc)


def get(username: str):
    if TTL_SECONDS <= 0 or not username:
        return None
    now = time.monotonic()
    with _lock:
        item = _store.get(username)
        if item and item[0] > now:
            return item[1]
        if item:
            _store.pop(username, None)
    return None


def put(username: str, user_doc) -> None:
    # Never cache a miss (None) — an account may be created moments later.
    if TTL_SECONDS <= 0 or not username or user_doc is None:
        return
    with _lock:
        _store[username] = (time.monotonic() + TTL_SECONDS, user_doc)


def invalidate(username: str) -> None:
    if not username:
        return
    with _lock:
        _store.pop(username, None)


def clear() -> None:
    with _lock:
        _store.clear()
