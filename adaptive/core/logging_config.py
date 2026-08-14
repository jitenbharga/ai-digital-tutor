"""
W8: optional structured (JSON) logging for aggregation (ELK / Loki / CloudWatch).

Enable with LOG_FORMAT=json; otherwise a readable text format is used. Level via
LOG_LEVEL (default INFO). Call configure_logging() once at startup.
"""
import json
import logging
import os


class JsonFormatter(logging.Formatter):
    """One JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Include any extra fields attached via logger.*(..., extra={...}).
        for k, v in record.__dict__.items():
            if k not in _RESERVED and not k.startswith("_"):
                payload.setdefault(k, v)
        return json.dumps(payload, default=str)


_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    if os.getenv("LOG_FORMAT", "").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
