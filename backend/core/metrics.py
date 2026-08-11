"""
W8: Prometheus metrics. Import-safe — if prometheus-client isn't installed the
module degrades to no-ops so the app still runs.

Metrics are per-worker/per-process. In production, either scrape every worker or
run prometheus_client in multiprocess mode (PROMETHEUS_MULTIPROC_DIR) behind
gunicorn/uvicorn workers. Labels use the ROUTE TEMPLATE (e.g. /progress/{student_id}),
never the raw path, to keep cardinality bounded.
"""
import logging

log = logging.getLogger("metrics")

try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

    ENABLED = True
    _REQUESTS = Counter(
        "http_requests_total", "Total HTTP requests",
        ["method", "route", "status"],
    )
    _LATENCY = Histogram(
        "http_request_duration_seconds", "HTTP request latency (s)",
        ["method", "route"],
    )
except Exception:  # noqa: BLE001 — prometheus-client absent -> no-op metrics
    ENABLED = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


def record_request(method: str, route: str, status: int, duration_seconds: float) -> None:
    """Record one request. Safe to call whether or not prometheus-client exists."""
    if not ENABLED:
        return
    try:
        _REQUESTS.labels(method=method, route=route, status=str(status)).inc()
        _LATENCY.labels(method=method, route=route).observe(duration_seconds)
    except Exception as e:  # noqa: BLE001 — metrics must never break a request
        log.debug("metrics record failed: %s", e)


def render() -> bytes:
    """Return the Prometheus exposition payload (empty if disabled)."""
    if not ENABLED:
        return b"# prometheus-client not installed\n"
    return generate_latest()
