"""
Smoke test: the FastAPI app imports and registers a substantial route table.

Importing serve.py builds+caches LLM models in a process-global singleton, which
would contaminate the isolated engine tests. So this is SKIPPED by default and
run in its own process (RUN_APP_SMOKE=1) — e.g. a dedicated CI step. It still
guards against wholesale import breakage (the W4 lazy-tutor change, a bad
refactor). slowapi is mocked here, so rate-limited routes like /login drop out;
we assert un-limited core routes + a floor rather than an exact count.
"""
import os

import pytest


@pytest.mark.skipif(
    os.getenv("RUN_APP_SMOKE") != "1",
    reason="imports serve.py (LLM/engine singleton side effects); run standalone",
)
def test_app_imports_and_registers_routes(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-dummy-key")

    from serve import app

    paths = {getattr(r, "path", None) for r in app.routes}
    paths.discard(None)

    for expected in ("/healthz", "/tutor", "/submit_answer", "/ask"):
        assert expected in paths, f"missing core route {expected}"

    assert len(paths) > 50, f"only {len(paths)} routes registered — import likely broke"
