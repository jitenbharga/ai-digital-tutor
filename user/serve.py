import sys
import os
import types

_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)

if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

if "user" not in sys.modules or not hasattr(sys.modules["user"], "__path__"):
    user_mod = types.ModuleType("user")
    user_mod.__path__ = [_current_dir]
    user_mod.__file__ = os.path.join(_current_dir, "__init__.py")
    sys.modules["user"] = user_mod

import json
import uuid
from contextvars import ContextVar
try:
    from user.database import client
except ImportError:
    from database import client
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
try:
    from user.auth import router as auth_router
except ImportError:
    from auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
import logging

logger = logging.getLogger(__name__)

if os.getenv("LOG_FORMAT"):
    try:
        from user.core.logging_config import configure_logging
    except ImportError:
        from core.logging_config import configure_logging
    configure_logging()

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request_id_ctx.set(rid)
        logger.info("req_start method=%s path=%s request_id=%s", request.method, request.url.path, rid)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        logger.info("req_end status=%d request_id=%s", response.status_code, rid)
        return response


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
    async def dispatch(self, request: Request, call_next):
        import time as _t
        start = _t.perf_counter()
        response: Response = await call_next(request)
        try:
            route = request.scope.get("route")
            template = getattr(route, "path", None) or "unmatched"
            from user.core.metrics import record_request
            record_request(
                request.method, template, response.status_code, _t.perf_counter() - start
            )
        except Exception:
            pass
        return response


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
        logger.warning("SENTRY_DSN invalid or Sentry init failed (%s) — error tracking disabled", e)
else:
    logger.info("SENTRY_DSN not set — error tracking disabled (no-op)")


app = FastAPI(
    title="Digital Tutor Auth Gateway",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url=None,
)

from user.rate_limit import limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from user.core.exceptions import TutorError

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
app.add_middleware(MetricsMiddleware)

app.include_router(auth_router)

try:
    from user.ai_proxy import proxy_router
except ImportError:
    from ai_proxy import proxy_router

if ADAPTIVE_ENGINE_URL := os.getenv("ADAPTIVE_ENGINE_URL", "").strip():
    logger.info("Auth Gateway Mode active — Proxying AI requests to Adaptive Engine (%s)", ADAPTIVE_ENGINE_URL)
    app.include_router(proxy_router)

@app.api_route("/", methods=["GET", "HEAD"])
@app.api_route("/healthz", methods=["GET", "HEAD"])
async def healthz():
    mongo_ok = True
    try:
        await client.admin.command("ping")
    except Exception as e:
        mongo_ok = False
        logger.warning("healthz: mongo ping failed: %s", e)

    store_ok = True
    try:
        try:
            from user.rate_limit import ping_rate_limit_store
        except ImportError:
            from rate_limit import ping_rate_limit_store
        store_ok = ping_rate_limit_store()
    except Exception as e:
        store_ok = False
        logger.warning("healthz: rate-limit store check failed: %s", e)

    return Response(
        content=json.dumps({
            "status": "ok" if mongo_ok else "degraded",
            "service": "user-auth-api",
            "mongo": mongo_ok,
            "rate_limit_store": store_ok,
        }),
        status_code=200 if mongo_ok else 503,
        media_type="application/json",
    )


@app.get("/metrics")
async def metrics():
    try:
        from user.core.metrics import render, CONTENT_TYPE_LATEST
    except ImportError:
        from core.metrics import render, CONTENT_TYPE_LATEST
    return Response(content=render(), media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
async def startup():
    try:
        await client.server_info()
        logger.info("MongoDB connected")
        if os.getenv("AUTO_ENSURE_INDEXES", "1") != "0":
            from user.database import ensure_indexes
            await ensure_indexes()
        else:
            logger.info("AUTO_ENSURE_INDEXES=0 — run scripts/migrate_indexes.py at deploy")
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}")
        logger.warning("Running in degraded mode — DB-dependent features will error on use")

    try:
        from user.rate_limit import ping_rate_limit_store
        if not ping_rate_limit_store():
            logger.warning(
                "Rate-limit store configured but unreachable — limits may not be "
                "shared across workers until connectivity is restored."
            )
    except Exception as e:
        logger.warning(f"Rate-limit store check skipped: {e}")