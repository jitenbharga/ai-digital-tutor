"""
T1.3 — IDOR / negative-authorization tests.

For every ``/{student_id}`` route guarded by ``require_self_or_guardian``, prove
the authorization decision holds:
  * student B  -> 403 on student A's resource   (the IDOR that SEC-1 closed)
  * guardian NOT linked to the child -> 403
  * the owning student -> NOT rejected by the guard
  * a linked guardian  -> NOT rejected by the guard

Auth is injected with ``app.dependency_overrides[get_current_user]`` — no JWT or
users collection needed. The guard runs as a dependency (before the handler), so
denied cases return 403 without touching the database. Allowed cases fall through
to the handler; we only assert they are *not* 403 (the handler may 4xx/5xx under
the stubbed DB — that still proves the guard let the request through).

This locks in dependencies.py::require_self_or_guardian.
"""
import os

import pytest
from fastapi.testclient import TestClient

# Every route whose dependency tree includes require_self_or_guardian("student_id").
SELF_SCOPED_ROUTES = [
    ("GET", "/challenge/{sid}"),
    ("GET", "/gamification/{sid}"),
    ("GET", "/knowledge-graph/{sid}"),
    ("GET", "/progress/{sid}"),
    ("POST", "/quiz/{sid}"),
    ("POST", "/quiz/{sid}/submit"),
    ("GET", "/report/{sid}"),
    ("GET", "/review/{sid}"),
    ("GET", "/study-plan/{sid}"),
]

STUDENT_A = {"username": "student_a", "role": "student", "linked_children": []}
STUDENT_B = {"username": "student_b", "role": "student", "linked_children": []}
GUARDIAN_LINKED = {"username": "guardian_g", "role": "guardian", "linked_children": ["student_a"]}
GUARDIAN_UNLINKED = {"username": "guardian_h", "role": "guardian", "linked_children": ["student_z"]}


@pytest.fixture(scope="module")
def route_client():
    os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")
    os.environ.setdefault("GOOGLE_API_KEY", "test-dummy-key")
    os.environ.setdefault("ENVIRONMENT", "test")
    import serve
    from dependencies import get_current_user

    app = serve.app
    client = TestClient(app, raise_server_exceptions=False)

    def as_user(user):
        app.dependency_overrides[get_current_user] = lambda: user

    yield client, as_user
    app.dependency_overrides.pop(get_current_user, None)


def _call(client, method, path):
    # Send an empty JSON body for POSTs so body-parsing never preempts the guard.
    return client.request(method, path, json={} if method == "POST" else None)


@pytest.mark.parametrize("method,tmpl", SELF_SCOPED_ROUTES)
def test_other_student_gets_403(route_client, method, tmpl):
    client, as_user = route_client
    as_user(STUDENT_B)
    r = _call(client, method, tmpl.format(sid="student_a"))
    assert r.status_code == 403, (
        f"{method} {tmpl}: student B must be forbidden from student A's resource, got {r.status_code}"
    )


@pytest.mark.parametrize("method,tmpl", SELF_SCOPED_ROUTES)
def test_unlinked_guardian_gets_403(route_client, method, tmpl):
    client, as_user = route_client
    as_user(GUARDIAN_UNLINKED)
    r = _call(client, method, tmpl.format(sid="student_a"))
    assert r.status_code == 403, (
        f"{method} {tmpl}: guardian not linked to the child must be 403, got {r.status_code}"
    )


@pytest.mark.parametrize("method,tmpl", SELF_SCOPED_ROUTES)
def test_owner_is_not_blocked_by_guard(route_client, method, tmpl):
    client, as_user = route_client
    as_user(STUDENT_A)
    r = _call(client, method, tmpl.format(sid="student_a"))
    assert r.status_code != 403, (
        f"{method} {tmpl}: the owning student must pass the guard, got 403"
    )


def test_linked_guardian_is_not_blocked_by_guard(route_client):
    client, as_user = route_client
    as_user(GUARDIAN_LINKED)
    r = _call(client, "GET", "/progress/student_a")
    assert r.status_code != 403
