# Backend Architecture (W4)

## Target layering

```
HTTP Router (FastAPI route handler — thin: parse, authz, shape response)
      │  calls
      ▼
Service (business logic / orchestration — no direct DB, no framework types)
      │  calls
      ▼
Repository (the ONLY code that touches a Mongo collection)
      │  calls
      ▼
Database (Motor collections in database.py)
```

Rule: **no layer reaches around the one below it.** Routers don't touch Mongo;
services don't `import database`; repositories are the single persistence seam.

## What exists today

| Layer | Modules |
|---|---|
| Repositories | `repositories/users.py` (`UserRepository`), `repositories/refresh_tokens.py` (`RefreshTokenRepository`) |
| Services | `services/token_service.py` (`TokenService` — issue/rotate token pairs) |
| Routers (migrated) | `auth.py` (signup/login/refresh/logout/reset/verify) and `dependencies.py` (`get_current_user`) now delegate all persistence to the repositories/services |
| Schemas | `api/schemas.py` (Pydantic request/response models) |

Repositories resolve their collection lazily (`import database; return database.X`)
so tests can point them at a fixture DB (`tests/integration/conftest.py::wire_db`).
The new layers have **100% test coverage** (`tests/integration/test_repositories.py`).

## Why serve.py / api/extras.py were NOT bulk-refactored this wave

`serve.py` (~110 routes) and `api/extras.py` (~42 routes) have **almost no
per-route test coverage**, and the unit-test stubs mock `slowapi`, which drops
rate-limited routes from the registered table — so a stub-based route-count check
can't reliably prove an extraction preserved behavior. Moving untested route
handlers blindly would violate "don't break working functionality" and "verify
after every extraction."

Two enabling fixes landed instead:
1. **Lazy tutor** (`serve.py`): the RL tutor now builds on first use, not at
   import — faster cold start, and the app module can be imported for smoke tests.
2. **App-import smoke test** (`tests/test_app_routes.py`, `RUN_APP_SMOKE=1`): runs
   in its own CI step (serve.py builds LLM singletons that would contaminate other
   tests) and asserts the app imports + registers its route table.

## Migration playbook for a serve.py / extras.py route group

Do this **per route group**, one at a time, each fully verified before the next:

1. **Add coverage first.** Write an E2E (Playwright) or API test that exercises
   the route group's happy path + key errors, so you can detect regressions.
   (The Wave 2 E2E harness boots the real stack — extend it here.)
2. **Extract the repository.** Move the group's Mongo access into a
   `repositories/<domain>.py` with the *identical* queries; unit-test it against
   `wire_db` (mongomock) to prove behavior parity.
3. **Extract the service.** Move business logic into `services/<domain>_service.py`
   using the repository; unit-test it.
4. **Thin the router.** Move the handlers into `routers/<domain>.py` (`APIRouter`),
   have them call the service, and `include_router` in `serve.py`. Change `@app.`
   → `@router.`; bring along any shared dependencies.
5. **Verify.** `RUN_APP_SMOKE=1 pytest tests/test_app_routes.py` (route table
   intact) + the group's E2E/API tests + `pytest tests/`. Only then move on.

Good first candidates (self-contained, lower shared-global coupling): chat
sessions (`/me/chats*`), mistakes notebook (`/me/mistakes*`), quiz history.

## Coverage ratchet

The backend coverage floor rose from **38% → 44%** as auth moved into tested
layers. As each serve.py group migrates with tests (step 1 above), raise the
`--cov-fail-under` floor in `.github/workflows/ci.yml` accordingly.
