"""
T1.1 — end-to-end learning-loop route test (mongomock + fake-LLM harness).

Exercises the core student journey through real handler + engine + persistence
code: start a subject, read the curriculum, complete/skip a node, generate a
quiz, submit an answer, get a tutor decision and a hint. The fixture starts the
subject once so each test is independent.
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
def flow():
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
            "student_id": "student_a", "concepts": {},
            "traits": {"knowledge": 0.5, "engagement": 0.5, "streak": 1},
        })
        await mockdb["users_collection"].insert_one({"username": "student_a", "role": "student"})
    H.run_async(seed())

    serve.app.dependency_overrides[get_current_user] = lambda: STUDENT
    client = TestClient(serve.app, raise_server_exceptions=False)
    client.post("/subjects/math/start", json={})   # establish curriculum + progress
    try:
        yield client
    finally:
        serve.app.dependency_overrides.pop(get_current_user, None)


class TestLearningLoop:
    def test_start_subject_is_idempotent(self, flow):
        assert flow.post("/subjects/math/start", json={}).status_code == 200

    def test_read_curriculum_map(self, flow):
        assert flow.get("/me/curriculum/math").status_code == 200

    def test_complete_node(self, flow):
        assert flow.post("/me/curriculum/math/node/n1/complete", json={}).status_code == 200

    def test_skip_node(self, flow):
        assert flow.post("/me/curriculum/math/node/n1/skip", json={}).status_code == 200

    def test_generate_quiz(self, flow):
        r = flow.post("/quiz/student_a", json={"topic": "algebra", "num_questions": 3})
        assert r.status_code == 200

    def test_submit_answer(self, flow):
        r = flow.post("/submit_answer", json={"student_id": "student_a", "answer": "4"})
        assert r.status_code == 200

    def test_tutor_decision(self, flow):
        r = flow.post("/tutor", json={"student_id": "student_a", "message": "help me"})
        assert r.status_code == 200

    def test_hint(self, flow):
        r = flow.post("/hint", json={"student_id": "student_a", "question": "2+2?", "concept": "math"})
        assert r.status_code == 200
