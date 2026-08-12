# ============================================================
# AI Digital Tutor — Root Dockerfile for Cloud Deployments (Render / Cloud Run)
# ============================================================
FROM python:3.11-slim AS backend

WORKDIR /app

# System deps for faiss-cpu (libomp) and general build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libomp-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps (cached layer)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ /app/

# Run as non-root appuser
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Container healthcheck hits the unauthenticated liveness probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)" || exit 1

# Start uvicorn server
CMD ["sh", "-c", "uvicorn serve:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-1}"]
