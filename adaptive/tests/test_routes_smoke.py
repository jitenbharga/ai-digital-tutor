"""
T1.1 (breadth) — GET-surface smoke test.

Drives every fillable GET route against a seeded in-memory account (mongomock +
fake-LLM harness) and asserts it returns a *handled* status (no unhandled 5xx).
This is a correctness guarantee — "a fresh/seeded account never crashes a read
endpoint" — and it exercises a large slice of serve.py / api/extras.py.
"""
import os

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from tests import route_harness as H

STUDENT = {
    "username": "student_a", "role": "student", "linked_children": [],
    "grade": 8, "subjects": ["math"],
}
FILL = {"student_id": "student_a", "subject": "math", "topic": "algebra"}

# Routes intentionally skipped (reason in comment):
SKIP = {
    "/healthz",   # DB ping — MagicMock motor (503 by design here)
    "/metrics",   # Prometheus text, not user-scoped
    # retention_tracker caches its collection handle at module scope, which leaks
    # across test modules in a full-suite run; exercised directly elsewhere.
    "/me/retention",
    "/retention-summary",
    # routers/notebook.py binds `_notes_col = db["notes"]` at import (module scope),
    # so the harness can't rewire it to mongomock — the handle stays a MagicMock and
    # `async for` over its cursor raises. Works against a real DB; covered elsewhere.
    "/me/notebook",
}


@pytest.fixture(scope="module")
def seeded_client():
    os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")
    os.environ.setdefault("GOOGLE_API_KEY", "test-dummy-key")
    os.environ.setdefault("ENVIRONMENT", "test")
    import serve
    from dependencies import get_current_user
    from mongomock_motor import AsyncMongoMockClient

    mockdb = AsyncMongoMockClient()["t"]
    H.wire_mongomock(mockdb)
    H.install_fake_llm()

    async def seed():
        await mockdb["student_states_collection"].insert_one({
            "student_id": "student_a",
            "concepts": {"algebra": {"knowledge": 0.6}},
            "traits": {"knowledge": 0.6, "engagement": 0.5, "streak": 2},
        })
        await mockdb["users_collection"].insert_one({"username": "student_a", "role": "student"})
    H.run_async(seed())

    serve.app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(serve.app, raise_server_exceptions=False)
    try:
        yield client, serve.app
    finally:
        serve.app.dependency_overrides.pop(get_current_user, None)


def _fillable_get_paths(app):
    out = []
    for r in app.routes:
        if not isinstance(r, APIRoute) or "GET" not in r.methods:
            continue
        if r.path in SKIP:
            continue
        path = r.path
        for k, v in FILL.items():
            path = path.replace("{%s}" % k, v)
        if "{" in path:
            continue
        out.append(path)
    return out


def test_get_surface_has_no_unhandled_5xx(seeded_client):
    client, app = seeded_client
    paths = _fillable_get_paths(app)
    assert len(paths) >= 20, f"smoke should cover a broad slice; only {len(paths)} paths"
    bad = [(p, c) for p in paths for c in [client.get(p).status_code] if c >= 500]
    assert not bad, f"GET routes returned unhandled 5xx on a seeded account: {bad}"
