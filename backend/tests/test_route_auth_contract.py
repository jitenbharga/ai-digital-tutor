"""
T1.2 — Authorization contract test.

Introspects EVERY registered API route and asserts that any route not on an
explicit PUBLIC allowlist declares an authentication guard in its dependency
tree. This turns "someone forgot the guard on a new endpoint" from a silent
security hole into a failing test.

Guard detection
---------------
The app's guards all resolve to ``dependencies.get_current_user`` somewhere in
their dependency subtree:
  * ``get_current_user``               — direct auth dependency
  * ``require_role(...)``              — inner _check Depends(get_current_user)
  * ``require_self_or_guardian(...)``  — inner _check Depends(get_current_user)
  * ``rate_limit.check_llm_budget``    — Depends(get_current_user)
So "a guard is present" == "get_current_user (or check_llm_budget) appears in the
route's recursive dependency tree". We match by object identity, which is robust
to the factory closures used by require_role / require_self_or_guardian.

Route enumeration
-----------------
Under Starlette 1.x, ``app.routes`` does not classically re-expose routes added
via ``include_router``, so we also walk each included router's own ``.routes``
(they carry fully-computed ``.dependant`` objects). Routes are de-duplicated by
(methods, path).
"""
import pytest
from fastapi.routing import APIRoute


# Paths allowed to have NO auth guard, each with a reason:
PUBLIC_PATHS = frozenset({
    # ── ops / health ──
    "/healthz",                 # liveness probe
    "/metrics",                 # Prometheus scrape (secured/internal-only in Phase 4)
    # ── unauthenticated auth flows (you cannot require a logged-in user to log in) ──
    "/login",
    "/signup",
    "/refresh",                 # consumes a refresh token, not an access token
    "/forgot-password",
    "/reset-password",
    "/verify-email",            # consumes an emailed one-time token
    "/verify-email/resend",     # public: an unverified user (can't log in yet) re-requests the link
    "/auth/google",             # Google sign-in: verifies a Google ID token, no prior session
    # ── SSE stream: authenticated via a one-time stream-ticket token in the query
    #    string (EventSource can't send Authorization headers), issued by the
    #    guarded /me/stream-ticket. Not a Depends() guard by design. ──
    "/tutor/stream",
    # ── FastAPI built-ins ──
    "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc",
})

# Included routers whose routes Starlette 1.x hides from app.routes. Must list
# EVERY router serve.py includes, otherwise the enumeration under-counts (and the
# >=130 sanity gate fails) whenever the installed Starlette hides include_router
# routes. Kept in sync with serve.py's app.include_router(...) calls.
_INCLUDED_ROUTER_ATTRS = (
    "auth_router", "extras_router", "notebook_router", "onboarding_router",
    "materials_router", "study_aids_router", "guardian_router", "review_router",
    "quiz_router", "gamification_router", "curriculum_router", "mastery_router",
    "tutor_router", "admin_router", "profile_router", "certificates_router",
    "social_router",
)


def _guard_ids():
    """Object ids of the callables that count as an auth guard."""
    import dependencies
    import rate_limit
    ids = {id(dependencies.get_current_user)}
    budget = getattr(rate_limit, "check_llm_budget", None)
    if budget is not None:
        ids.add(id(budget))
    return ids


def _dependency_calls(dependant):
    """Yield the .call of every (recursive) sub-dependency of a route."""
    for sub in dependant.dependencies:
        yield sub.call
        yield from _dependency_calls(sub)


def _is_guarded(route, guard_ids):
    return any(id(c) in guard_ids for c in _dependency_calls(route.dependant))


def _iter_api_routes():
    """All unique APIRoutes: app.routes + each included router's own routes."""
    import serve
    sources = list(serve.app.routes)
    for attr in _INCLUDED_ROUTER_ATTRS:
        router = getattr(serve, attr, None)
        if router is not None:
            sources += list(router.routes)
    seen = set()
    for r in sources:
        if not isinstance(r, APIRoute):
            continue
        key = (frozenset(r.methods), r.path)
        if key in seen:
            continue
        seen.add(key)
        yield r


@pytest.fixture(scope="module")
def app_smoke_env():
    """Engines build an LLM client at construction, so at least one provider key
    must exist for serve.py to import. LLM calls are never made by this test."""
    import os
    os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")
    os.environ.setdefault("GOOGLE_API_KEY", "test-dummy-key")
    os.environ.setdefault("ENVIRONMENT", "test")
    yield


@pytest.fixture(scope="module")
def app_built(app_smoke_env):
    """Import serve once (LLM/engine singletons) for the whole module."""
    import serve  # noqa: F401
    return serve.app


def test_every_nonpublic_route_declares_a_guard(app_built):
    guard_ids = _guard_ids()
    offenders = []
    checked = 0
    for route in _iter_api_routes():
        checked += 1
        if route.path in PUBLIC_PATHS:
            continue
        if not _is_guarded(route, guard_ids):
            offenders.append(f"{sorted(m for m in route.methods if m != 'HEAD')} {route.path}")
    # Sanity: we must have actually enumerated the full surface, not just a slice.
    assert checked >= 130, f"only enumerated {checked} routes — enumeration is incomplete"
    assert not offenders, (
        "These non-public routes declare no auth guard "
        "(add get_current_user/require_role/require_self_or_guardian/check_llm_budget, "
        "or add the path to PUBLIC_PATHS with a reason):\n  " + "\n  ".join(sorted(offenders))
    )


def test_guard_detection_bites(app_built):
    """Prove both directions: an unguarded route is flagged, a guarded one passes.

    This is the "fails if a guard is removed" proof — removing get_current_user
    from a route makes _is_guarded() return False, which the scan above reports
    as an offender.
    """
    from fastapi import FastAPI, Depends
    from dependencies import get_current_user

    probe = FastAPI()

    @probe.get("/leaky")
    def leaky():                       # no guard — simulates a forgotten Depends
        return {}

    @probe.get("/safe")
    def safe(user=Depends(get_current_user)):
        return {}

    guard_ids = _guard_ids()
    routes = {r.path: r for r in probe.routes if isinstance(r, APIRoute)}
    assert _is_guarded(routes["/safe"], guard_ids) is True
    assert _is_guarded(routes["/leaky"], guard_ids) is False
