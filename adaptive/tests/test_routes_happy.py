"""
T1.1 (template) â€” happy-path route tests via mongomock-motor + dependency_overrides.

This is the reusable pattern for driving serve's routes toward the 80% coverage
target: wire an in-memory async Mongo into every loaded module's collection
handles, inject the current user with dependency_overrides, seed only what a
route reads, and assert the real response. Extend group by group (quiz,
curriculum, gamification, mastery, materials, ...).

Runs fully in-process â€” no torch/LLM/real Mongo. Routes that call the LLM are
out of scope for this template (they need a fake-LLM seam); these cover the
read/query surface.
"""
import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

STUDENT = {
    "username": "student_a", "role": "student", "linked_children": [],
    "grade": 8, "subjects": ["math"],
}


def _run(coro):
    """Drive an async coroutine (for seeding mongomock) on a throwaway loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _wire_all_collections(mockdb):
    """Point EVERY loaded module's `*_collection` / `students_col` handle at the
    in-memory db. Modules bind these at import (`from database import X`), so a
    single database-level patch isn't enough â€” we patch every importer."""
    patched = 0
    for module in list(sys.modules.values()):
        ns = getattr(module, "__dict__", None)
        if not ns:
            continue
        for attr in list(ns.keys()):
            if attr.endswith("_collection") or attr == "students_col":
                try:
                    setattr(module, attr, mockdb[attr])
                    patched += 1
                except Exception:
                    pass
    return patched


@pytest.fixture(scope="module")
def _env():
    os.environ.setdefault("MISTRAL_API_KEY_1", "test-dummy-key")
    os.environ.setdefault("GROQ_API_KEY_1", "test-dummy-key")
    os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture
def api(_env):
    """Yield (client, mockdb). Fresh in-memory db per test; user = STUDENT."""
    import serve
    from adaptive.dependencies import get_current_user
    from mongomock_motor import AsyncMongoMockClient

    mockdb = AsyncMongoMockClient()["t"]
    _wire_all_collections(mockdb)
    serve.app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(serve.app, raise_server_exceptions=False)
    try:
        yield client, mockdb
    finally:
        serve.app.dependency_overrides.pop(get_current_user, None)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ read routes that need no seed â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestReadRoutesNoSeed:
    def test_subjects_lists_all(self, api):
        client, _ = api
        r = client.get("/subjects")
        assert r.status_code == 200
        subjects = r.json()["subjects"]
        assert len(subjects) >= 1
        assert {"id", "title", "started"} <= set(subjects[0])
        assert all(s["started"] is False for s in subjects)  # nothing started yet

    def test_profile_returns_current_user(self, api):
        client, _ = api
        r = client.get("/me/profile")
        assert r.status_code == 200

    def test_preferences_ok(self, api):
        client, _ = api
        assert client.get("/me/preferences").status_code == 200

    def test_features_flags_ok(self, api):
        client, _ = api
        r = client.get("/me/features")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ read routes exercised with seeded data â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestReadRoutesWithSeed:
    def test_progress_self_after_seeding_state(self, api):
        client, db = api
        _run(db["student_states_collection"].insert_one({
            "student_id": "student_a",
            "concepts": {"algebra": {"knowledge": 0.7}},
            "traits": {"knowledge": 0.6, "engagement": 0.5, "streak": 3},
        }))
        r = client.get("/progress/student_a")
        assert r.status_code == 200

    def test_subjects_marks_started_after_progress_row(self, api):
        client, db = api
        # /subjects marks a subject 'started' if a curriculum_progress row exists.
        subj = client.get("/subjects").json()["subjects"][0]["id"]
        _run(db["curriculum_progress_collection"].insert_one(
            {"user_id": "student_a", "subject_id": subj}))
        after = {s["id"]: s["started"] for s in client.get("/subjects").json()["subjects"]}
        assert after[subj] is True


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ empty-state contract (404 when absent) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestEmptyStateContract:
    @pytest.mark.parametrize("path", ["/me/gamification", "/gamification/student_a"])
    def test_missing_gamification_state_is_404_not_500(self, api, path):
        client, _ = api
        # No state seeded â†’ a clean 404 (handled), never an unhandled 500.
        assert client.get(path).status_code == 404
