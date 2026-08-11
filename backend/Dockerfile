# ============================================================
# AI Digital Tutor — Backend
# ============================================================
FROM python:3.11-slim AS backend

WORKDIR /app

# System deps for faiss-cpu (libomp) and general build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libomp-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ api/
COPY core/ core/
COPY config/ config/
COPY models/ models/
COPY routers/ routers/
COPY repositories/ repositories/
COPY services/ services/
COPY training/ training/
COPY utils/ utils/
COPY configs/ configs/
COPY content/ content/
COPY scripts/ scripts/
COPY tests/ tests/
# NOTE: auth_config.py, rate_limit.py are imported at startup by serve.py/auth.py
# and MUST be present or the app fails to import on first request.
COPY serve.py runtime.py database.py auth.py auth_config.py security.py dependencies.py rate_limit.py ./

# Bake the trained DQN checkpoint + its eval gate into the image so RL serving is
# available at boot. Render's disk is ephemeral, so these must ship in the image
# (not mounted). eval_results.json validates the DQN vs baselines; with both
# present and RL_ENABLED=true the tutor uses the DQN over all 36 actions.
COPY checkpoints/ checkpoints/
COPY eval_results.json ./

# SEC: run as a non-root user (least privilege). Own the app dir so the
# runtime can write checkpoints/logs if needed.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Container healthcheck hits the unauthenticated liveness probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)" || exit 1

# SEC-9: run one worker per CPU by default (override with UVICORN_WORKERS).
# NOTE: per-route rate limits (SEC-3) use slowapi's in-memory store, which is
# per-worker — set RATE_LIMIT_STORAGE_URI to a shared backend (e.g. Redis) in
# production so limits hold across workers. See SECURITY.md.
# Cloud Run injects $PORT (usually 8080); default 8000 for local runs.
# Default 1 worker: the app keeps in-memory state (LLM round-robin/cooldown,
# rate limits) that must stay consistent — FastAPI is async so one worker still
# serves many concurrent requests. Override with UVICORN_WORKERS if needed.
CMD ["sh", "-c", "uvicorn serve:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-1}"]
