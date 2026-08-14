import json
import os
import uuid
from contextvars import ContextVar
from database import client
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from auth import router as auth_router
from core.llm_telemetry import init_telemetry
from database import llm_calls_collection
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
import logging
logger = logging.getLogger(__name__)
# W8: opt-in structured/JSON logging for aggregation. Only reconfigures when
# LOG_FORMAT is set, so the default (uvicorn) logging is unchanged otherwise.
if os.getenv("LOG_FORMAT"):
    from core.logging_config import configure_logging
    configure_logging()

# -- Request-ID context var (accessible from any coroutine in the request) --
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request; echo it in the response."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request_id_ctx.set(rid)
        logger.info("req_start method=%s path=%s request_id=%s", request.method, request.url.path, rid)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        logger.info("req_end status=%d request_id=%s", response.status_code, rid)
        return response


# ── SEC-6: baseline security headers on every response ──
# CSP allows self + the CDN origins the SPA actually loads at runtime
# (cdn.jsdelivr.net for pyodide/tesseract/mermaid). 'wasm-unsafe-eval' + blob:
# worker-src are required by Pyodide; 'unsafe-inline' style covers the inline
# <style> block and Tailwind. tessdata origin is needed for OCR language data.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval' blob: "
    "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
    "worker-src 'self' blob:; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
    "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
    "https://tessdata.projectnaptha.com; "
    "frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard security headers to every response (SEC-6)."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault("Content-Security-Policy", _CSP)
        if os.getenv("ENVIRONMENT") == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """W8: record request count + latency per ROUTE TEMPLATE for /metrics.
    Labels use the matched route pattern (not the raw path) to bound cardinality."""

    async def dispatch(self, request: Request, call_next):
        import time as _t
        start = _t.perf_counter()
        response: Response = await call_next(request)
        try:
            route = request.scope.get("route")
            template = getattr(route, "path", None) or "unmatched"
            from core.metrics import record_request
            record_request(
                request.method, template, response.status_code, _t.perf_counter() - start
            )
        except Exception:  # noqa: BLE001 — metrics must never break a request
            pass
        return response


# -- Optional Sentry error tracking --
_sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.getenv("ENVIRONMENT", "development"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_RATE", "0.1")),
            integrations=[StarletteIntegration(), FastApiIntegration()],
        )
        logger.info("Sentry error tracking enabled (env=%s)", os.getenv("ENVIRONMENT", "development"))
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed — error tracking disabled")
    except Exception as e:
        # Bad/placeholder DSN (e.g. missing scheme) must NOT crash startup —
        # Sentry is optional telemetry. Degrade gracefully.
        logger.warning("SENTRY_DSN invalid or Sentry init failed (%s) — error tracking disabled", e)
else:
    logger.info("SENTRY_DSN not set — error tracking disabled (no-op)")


app = FastAPI(
    title="Digital Tutor API",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url=None,
)
# Shared limiter + LLM budget live in rate_limit.py so the extras router can
# reuse the SAME instance without a circular import (SEC-3).
from rate_limit import limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Centralized TutorError handler ─────────────────────────────
from core.exceptions import TutorError

@app.exception_handler(TutorError)
async def tutor_error_handler(request: Request, exc: TutorError):
    logger.error(
        "TutorError %s: %s (extra=%s) request_id=%s",
        exc.__class__.__name__, exc.detail, exc.extra,
        request_id_ctx.get("-"),
    )
    return Response(
        content=json.dumps({"detail": exc.detail, "error_type": exc.__class__.__name__}),
        status_code=exc.status_code,
        media_type="application/json",
    )

app.add_middleware(SlowAPIMiddleware)

# ── Global unhandled exception handler ─────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    rid = request_id_ctx.get("-")
    logger.exception("Unhandled exception request_id=%s: %s", rid, exc)
    return Response(
        content=json.dumps({"detail": "Internal server error", "request_id": rid}),
        status_code=500,
        media_type="application/json",
    )

_DEFAULT_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]
_raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] if _raw_origins else _DEFAULT_ORIGINS
# SEC-7: a wildcard origin is invalid with credentialed requests (and unsafe).
# Strip any "*" so cookies are only ever sent to the explicit origin list.
_origins = [o for o in _origins if o != "*"] or _DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    allow_credentials=True,
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MetricsMiddleware)  # W8: outermost — measures full request time

app.include_router(auth_router)

# ── Service 1 (Vercel Auth Gateway) / Service 2 (Render AI Engine) Split ──
from ai_proxy import proxy_router, AI_ENGINE_URL
if AI_ENGINE_URL:
    logger.info("Vercel Auth Gateway Mode active — Proxying AI requests to Render AI Engine (%s)", AI_ENGINE_URL)
    app.include_router(proxy_router)

from api.extras import router as extras_router  # memory, daily-session, code-feedback
app.include_router(extras_router)

# ── Extracted routers (decomposition of serve.py) ──
from routers.notebook import router as notebook_router
from routers.onboarding import router as onboarding_router
from routers.materials import router as materials_router
from routers.study_aids import router as study_aids_router
from routers.guardian import router as guardian_router
from routers.review import router as review_router
from routers.quiz import router as quiz_router
from routers.gamification import router as gamification_router
from routers.curriculum import router as curriculum_router
from routers.mastery import router as mastery_router
from routers.tutor import router as tutor_router
from routers.admin import router as admin_router
from routers.profile import router as profile_router
from routers.certificates import router as certificates_router
from routers.social import router as social_router
app.include_router(notebook_router)
app.include_router(onboarding_router)
app.include_router(materials_router)
app.include_router(study_aids_router)
app.include_router(guardian_router)
app.include_router(review_router)
app.include_router(quiz_router)
app.include_router(gamification_router)
app.include_router(curriculum_router)
app.include_router(mastery_router)
app.include_router(tutor_router)
app.include_router(admin_router)
app.include_router(profile_router)
app.include_router(certificates_router)
app.include_router(social_router)
# Re-export so extras' daily-session `from serve import get_progress_snapshot` resolves.
from routers.mastery import get_progress_snapshot
# Re-export quiz helpers so existing `from serve import _save_active_quiz, ...`
# call sites (materials, review, extras) and serve's own remaining tutor-group
# routes keep resolving after the quiz router extraction.
from routers.quiz import _save_active_quiz, _get_active_quiz, _get_quiz_engine

# ── Shared runtime singletons + cross-cutting helpers ──────────────
# Moved to runtime.py so every extracted router shares ONE tutor + engine
# instance. Re-exported here (imported into serve's namespace) so the existing
# lazy `from serve import tutor, review_engine, ...` call sites keep resolving.
from runtime import (
    tutor, Hint, graph_engine, review_engine, study_planner, challenge_engine,
    _concept_mastery, _require_feature, _FEATURE_EXPERIMENTS, _is_feature_on_for_user,
)

# Public surface re-exported for the routers/extras' lazy `from serve import X`
# call sites. Declared so these intentional re-exports are not treated as dead.
__all__ = [
    "app",
    "tutor", "Hint", "graph_engine", "review_engine", "study_planner",
    "challenge_engine", "_concept_mastery", "_require_feature",
    "_FEATURE_EXPERIMENTS", "_is_feature_on_for_user",
    "get_progress_snapshot", "_save_active_quiz", "_get_active_quiz",
    "_get_quiz_engine",
]


@app.api_route("/healthz", methods=["GET", "HEAD"])
async def healthz():
    """Liveness + readiness probe. Reports Mongo + the shared rate-limit store.
    Unauthenticated, cheap, safe to poll from load balancers / uptime checks."""
    mongo_ok = True
    try:
        await client.admin.command("ping")
    except Exception as e:
        mongo_ok = False
        logger.warning("healthz: mongo ping failed: %s", e)

    # W8: also surface the rate-limit store (True when using the in-memory store).
    store_ok = True
    try:
        from rate_limit import ping_rate_limit_store
        store_ok = ping_rate_limit_store()
    except Exception as e:
        store_ok = False
        logger.warning("healthz: rate-limit store check failed: %s", e)

    # Mongo is required; the rate-limit store degrades gracefully, so it's reported
    # but does not by itself flip the probe to 503.
    return Response(
        content=json.dumps({
            "status": "ok" if mongo_ok else "degraded",
            "mongo": mongo_ok,
            "rate_limit_store": store_ok,
        }),
        status_code=200 if mongo_ok else 503,
        media_type="application/json",
    )


@app.get("/metrics")
async def metrics():
    """W8: Prometheus metrics (text exposition). Per-worker — scrape each worker,
    or run prometheus_client in multiprocess mode behind multiple uvicorn workers."""
    from core.metrics import render, CONTENT_TYPE_LATEST
    return Response(content=render(), media_type=CONTENT_TYPE_LATEST)

@app.on_event("startup")
async def startup():
    try:
        await client.server_info()
        logger.info("MongoDB connected")
        # W5: in production, indexes are created by scripts/migrate_indexes.py as a
        # deploy step (set AUTO_ENSURE_INDEXES=0). Dev keeps auto-ensure for
        # convenience. Either way, failures now log at ERROR (no longer swallowed).
        if os.getenv("AUTO_ENSURE_INDEXES", "1") != "0":
            from database import ensure_indexes
            await ensure_indexes()
        else:
            logger.info("AUTO_ENSURE_INDEXES=0 — run scripts/migrate_indexes.py at deploy")
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}")
        logger.warning("Running in degraded mode — DB-dependent features will error on use")

    # SEC H-4: verify the shared rate-limit store (Redis) is reachable if one is
    # configured. Non-fatal: slowapi keeps working, but we log loudly so a
    # misconfigured store is visible instead of silently degrading to per-worker.
    try:
        from rate_limit import ping_rate_limit_store
        if not ping_rate_limit_store():
            logger.warning(
                "Rate-limit store configured but unreachable — limits may not be "
                "shared across workers until connectivity is restored."
            )
    except Exception as e:
        logger.warning(f"Rate-limit store check skipped: {e}")

    # Load persisted replay buffer transitions from MongoDB
    try:
        await tutor.load_replay_buffer()
    except Exception as e:
        logger.warning(f"Replay buffer load skipped: {e}")

    # Initialize LLM telemetry with MongoDB persistence
    try:
        telemetry = init_telemetry(db_collection=llm_calls_collection)
        await telemetry.start_flush_loop()
        logger.info("LLM telemetry initialized")
    except Exception as e:
        logger.warning(f"Telemetry init skipped: {e}")

    # P4: Ensure RL-vs-rule A/B experiment exists
    try:
        from core.ab_experiment import ensure_rl_experiment
        await ensure_rl_experiment()
    except Exception as e:
        logger.warning(f"AB experiment init skipped: {e}")

    # P5: Ensure per-feature delight experiments exist
    try:
        from core.ab_experiment import get_experiment_manager
        exp_mgr = get_experiment_manager()
        _delight_experiments = [
            ("gamification_v1", "P5: Gamification (XP, streaks, badges) vs no gamification"),
            ("leaderboard_v1", "P5: Weekly leaderboard vs no leaderboard"),
            ("certificates_v1", "P5: Mastery certificates vs no certificates"),
        ]
        for exp_id, desc in _delight_experiments:
            existing = await exp_mgr.get_experiment(exp_id)
            if not existing:
                await exp_mgr.create_experiment(
                    experiment_id=exp_id,
                    description=desc,
                    arms=["control", "treatment"],
                    traffic_pct=1.0,
                    win_conditions={
                        "primary_metric": "day7_retention",
                        "min_effect_size": 0.1,
                        "significance_level": 0.05,
                    },
                    min_sample_size=30,
                )
        logger.info("Delight feature experiments initialized")
    except Exception as e:
        logger.warning(f"Delight experiments init skipped: {e}")





















# -- P4: A/B Experiment endpoints --











# -- C4: Gamification (feature-flagged) --









# -- E11: Daily Quests --





# -- P5: Leaderboard (feature-flagged) --





# -- P5: Reminders --









# -- P5: Retention --





# ======================================================================
# TEACHER DASHBOARD — REMOVED.
# The teacher role was deprecated and has been removed end-to-end. Parental
# oversight is served by the consent-based Guardian flow (see /guardian/*).
# Legacy teacher/admin accounts are converted to students by
# scripts/migrate_roles.py.
# ======================================================================


# ----------------------------------
# ONBOARDING
# ----------------------------------

# ONBOARDING — moved to routers/onboarding.py


# ----------------------------------
# E5: LEARNING PATH & DAILY PLAN
# ----------------------------------









# -- E6: Mastery Dashboard History --



# -- E9: Student Preferences (language, reading level, accessibility) --





# -- Profile (view + edit display name / goal / interests) --





# -- Feature flags endpoint (P1.1) --



# -- E7: Certificates (feature-flagged) --







# -- C6: PDF Report (enhanced for E7) --





# -- Quiz endpoints --



# ── Active quizzes live in MongoDB (survives restarts, works multi-worker) ──


















# =====================================================
# N1: ASK-ANYTHING — bring your own problem
# =====================================================



# =====================================================
# N8: HIGHLIGHT-TO-ASK — scoped Q&A about a selected span
# =====================================================




# =====================================================
# N2: EXPLAIN-AGAIN — explain differently on demand
# =====================================================



# ======================================================================
# N10: CURRICULUM MAP — Canonical tree + per-user progress
# ======================================================================















# ======================================================================
# N3: RESUME — Track + return last active session
# ======================================================================





# ======================================================================
# CHAT PERSISTENCE — Multi-session chat history per student
# ----------------------------------------------------------------------
# Each chat is its own document keyed by `chat_id`. A topic can have many
# chats. Starting a "New Chat" creates a fresh chat_id; the previous one is
# preserved (never deleted), so students can reopen any old chat and resume
# exactly where it ended.
# ======================================================================





















# ── Backward-compat: old per-topic endpoints (map to newest chat of a topic) ──







# ======================================================================
# N4: REVIEW-DUE — Lightweight count of due topics
# ======================================================================



# ======================================================================
# N9: QUIZ HISTORY — Persist results + history endpoint
# ======================================================================





# ======================================================================
# N5: MISTAKES NOTEBOOK — List + resolve
# ======================================================================







# ======================================================================
# STUDY BUDDY — pair with a friend; a shared streak counts days BOTH studied.
# Reuses the retention `active_days` log. Healthy peer motivation, no leaderboard.
# ======================================================================











# ============================================================
# N13: PROJECT-BASED LEARNING
# ============================================================











# ============================================================
# N7: PROGRESS SNAPSHOT
# ============================================================



# ============================================================
# N11: DEEPER-LEARNING REFERENCES
# ============================================================









# ============================================================
# N12: PERSONAL NOTEBOOK — moved to routers/notebook.py
