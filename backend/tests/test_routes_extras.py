"""
T1.1 — api/extras.py route coverage (memory, daily-session, materials,
flashcards, notifications, feynman, guardian/admin guards).

Uses the shared mongomock + fake-LLM harness. Covers reads, mutations, the
not-found contract, and role-guard rejections for a plain student.
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
        yield client
    finally:
        serve.app.dependency_overrides.pop(get_current_user, None)


class TestExtrasReads:
    @pytest.mark.parametrize("path", [
        "/me/feynman/history",
        "/me/flashcards/due",
        "/me/materials",
        "/me/memory",
        "/me/next-exam",
        "/me/notifications",
        "/me/progress-card.pdf",
    ])
    def test_read_returns_200(self, api, path):
        assert api.get(path).status_code == 200


class TestExtrasMutations:
    def test_daily_session(self, api):
        assert api.post("/me/daily-session", json={}).status_code == 200

    def test_flashcards_sync(self, api):
        assert api.post("/me/flashcards/sync", json={}).status_code == 200

    def test_notifications_prefs_put(self, api):
        assert api.put("/me/notifications/prefs", json={}).status_code == 200

    def test_notifications_read_all(self, api):
        assert api.post("/me/notifications/read-all", json={}).status_code == 200

    def test_practice_weak_spots(self, api):
        assert api.post("/me/practice/weak-spots", json={}).status_code == 200


class TestExtrasNotFound:
    def test_delete_unknown_material_404(self, api):
        assert api.delete("/me/materials/does-not-exist").status_code == 404

    def test_quiz_unknown_material_404(self, api):
        assert api.post("/me/materials/does-not-exist/quiz", json={}).status_code == 404


class TestExtrasRoleGuards:
    """A plain student is forbidden from admin- and guardian-only extras routes."""

    @pytest.mark.parametrize("path", [
        "/admin/content-quality",
        "/admin/llm-usage",
        "/guardian/digest/prefs",
    ])
    def test_student_forbidden_403(self, api, path):
        assert api.get(path).status_code == 403


class TestExtrasPostBodies:
    """POST routes with JSON bodies (LLM-backed study aids)."""

    def test_quick_recap(self, api):
        assert api.post("/me/recap", json={"topic": "algebra"}).status_code == 200

    def test_content_report(self, api):
        assert api.post("/content-report", json={"question": "2+2=5?", "quiz_id": "q1"}).status_code == 200

    def test_cheatsheet(self, api):
        assert api.post("/me/cheatsheet", json={"topic": "algebra"}).status_code == 200

    def test_cheatsheet_smart(self, api):
        assert api.post("/me/cheatsheet/smart", json={"topic": "algebra"}).status_code == 200

    def test_exam_plan(self, api):
        body = {"exam_date": "2026-12-01", "subject": "math", "topics": ["algebra"]}
        assert api.post("/me/exam-plan", json=body).status_code == 200

    def test_mock_test(self, api):
        assert api.post("/me/mock-test", json={"subject": "math", "num_questions": 3}).status_code == 200

    def test_recap_missing_topic_is_400(self, api):
        # Handler validates the body — empty topic is a clean 400, not a 5xx.
        assert api.post("/me/recap", json={}).status_code == 400


# A valid 1x1 PNG so the image validator passes before the (faked) vision call.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000100056cf9a40000000049454e44ae426082"
)


class TestVisionRoutes:
    """solution-check / step-check upload an image; the vision model is faked."""

    def test_solution_check(self, api):
        r = api.post(
            "/me/solution-check",
            files={"image": ("s.png", _PNG_1x1, "image/png")},
            data={"question": "2+2?", "topic": "math"},
        )
        assert r.status_code == 200

    def test_step_check(self, api):
        r = api.post(
            "/me/step-check",
            files={"image": ("s.png", _PNG_1x1, "image/png")},
            data={"problem": "solve 2x=4", "step_text": "x=2"},
        )
        assert r.status_code == 200


class TestMaterialsLifecycle:
    """Upload a study material, then read / ask / quiz / delete it end-to-end."""

    def test_material_lifecycle(self, api):
        up = api.post(
            "/me/materials",
            files={"file": ("ch1.txt", b"Algebra basics. Solve x+2=4 gives x=2. Fractions are parts of a whole.", "text/plain")},
            data={"title": "Chapter 1", "subject": "math"},
        )
        assert up.status_code == 200
        mid = up.json()["material_id"]

        assert api.get("/me/materials").status_code == 200
        assert api.post(f"/me/materials/{mid}/ask", json={"question": "what is x?"}).status_code == 200
        assert api.post(f"/me/materials/{mid}/quiz", json={"num_questions": 3}).status_code == 200
        assert api.delete(f"/me/materials/{mid}").status_code == 200
