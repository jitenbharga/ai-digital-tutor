"""
T1.1 â€” mutation + LLM-backed route tests (mongomock + fake-LLM harness).

Exercises write endpoints and the LLM-backed learning routes end-to-end with a
deterministic fake LLM (route_harness.install_fake_llm), so quiz generation / ask
run their real engine + handler code without a provider.
"""
import os

import pytest
from fastapi.testclient import TestClient

from tests import route_harness as H

STUDENT = {
    "username": "student_a", "role": "student", "linked_children": [],
    "grade": 8, "subjects": ["math"],
}


@pytest.fixture(scope="module")
def api():
    os.environ.setdefault("MISTRAL_API_KEY_1", "test-dummy-key")
    os.environ.setdefault("GROQ_API_KEY_1", "test-dummy-key")
    os.environ.setdefault("ENVIRONMENT", "test")
    import serve
    from adaptive.dependencies import get_current_user
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
        yield client
    finally:
        serve.app.dependency_overrides.pop(get_current_user, None)


class TestLLMBackedRoutes:
    def test_ask_returns_200(self, api):
        r = api.post("/ask", json={"question": "explain fractions"})
        assert r.status_code == 200

    def test_quiz_generate_returns_200(self, api):
        r = api.post("/quiz/student_a", json={"topic": "algebra", "num_questions": 3})
        assert r.status_code == 200


class TestMutationRoutes:
    def test_update_preferences(self, api):
        assert api.put("/me/preferences", json={"tone": "friendly"}).status_code == 200

    def test_update_reminder_prefs(self, api):
        assert api.put("/me/reminder-prefs", json={"enabled": True}).status_code == 200

    def test_mark_reminders_read(self, api):
        assert api.post("/me/reminders/read-all", json={}).status_code == 200


class TestSocialRoutes:
    def test_buddy_invite(self, api):
        assert api.post("/me/buddy/invite", json={}).status_code == 200

    def test_create_and_list_chats(self, api):
        assert api.post("/me/chats", json={"title": "chat1"}).status_code == 200
        assert api.get("/me/chats").status_code == 200


class TestChatLifecycle:
    """Create a saved chat, read it, re-save, delete â€” all via the API."""

    def test_chat_lifecycle(self, api):
        r = api.post("/me/chats", json={"title": "c1"})
        assert r.status_code == 200
        cid = r.json().get("chat_id") or r.json().get("id")
        assert api.get(f"/me/chats/{cid}").status_code == 200
        assert api.post(f"/me/chats/{cid}/save", json={}).status_code == 200
        assert api.delete(f"/me/chats/{cid}").status_code == 200

    def test_chat_save_by_topic(self, api):
        body = {"topic": "algebra", "messages": [{"role": "user", "content": "hi"}]}
        assert api.post("/me/chat/save", json=body).status_code == 200


class TestCurriculumRoutes:
    """Curriculum-tree generation runs via the fake LLM (nodes schema)."""

    def test_start_subject(self, api):
        assert api.post("/subjects/math/start", json={}).status_code == 200

    def test_get_curriculum_map(self, api):
        assert api.get("/me/curriculum/math").status_code == 200

    def test_diagnose_topic(self, api):
        assert api.get("/me/diagnose/algebra").status_code == 200

    def test_exam_readiness(self, api):
        assert api.get("/me/exam-readiness/math").status_code == 200


class TestNotFoundContract:
    """Mutations on non-existent resources return a clean 404, not a 5xx."""

    def test_resolve_unknown_mistake_404(self, api):
        assert api.post("/me/mistakes/does-not-exist/resolve", json={}).status_code == 404

    def test_complete_unknown_quest_404(self, api):
        assert api.post("/me/quests/does-not-exist/complete", json={}).status_code == 404
