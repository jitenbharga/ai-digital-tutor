"""W8: metrics registry + structured-logging unit tests."""
import json
import logging
import sys


def test_metrics_record_and_render():
    from core import metrics

    metrics.record_request("GET", "/healthz", 200, 0.01)
    out = metrics.render()
    assert isinstance(out, bytes)
    if metrics.ENABLED:
        text = out.decode()
        assert "http_requests_total" in text
        assert "/healthz" in text


def test_metrics_record_never_raises():
    from core import metrics

    # No-op-safe whether or not prometheus-client is installed.
    metrics.record_request("POST", "/anything", 500, 0.5)


def test_json_formatter_emits_valid_json():
    from core.logging_config import JsonFormatter

    rec = logging.LogRecord("test.logger", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    obj = json.loads(JsonFormatter().format(rec))
    assert obj["level"] == "INFO"
    assert obj["logger"] == "test.logger"
    assert obj["msg"] == "hello world"
    assert "ts" in obj


def test_json_formatter_includes_exception():
    from core.logging_config import JsonFormatter

    try:
        raise ValueError("boom")
    except ValueError:
        rec = logging.LogRecord("t", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
        obj = json.loads(JsonFormatter().format(rec))
        assert "boom" in obj["exc"]
