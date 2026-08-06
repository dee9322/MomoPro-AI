"""Structured application logging with secret redaction."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

_SECRET_RE = re.compile(r"(?i)(api[_-]?key|secret|token|authorization|signature|password)")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if _SECRET_RE.search(str(k)) else _safe(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if context:
            payload["context"] = _safe(context)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    root = logging.getLogger("momopro")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    root.setLevel(level)
    return root


def log_event(category: str, message: str, *, level: int = logging.INFO, **context: Any) -> None:
    logger = configure_logging().getChild(category.lower())
    logger.log(level, message, extra={"context": context})
