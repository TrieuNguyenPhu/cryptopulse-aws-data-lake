"""Structured JSON logging with mandatory secret redaction."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, TextIO

REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "coingecko_api_key",
        "secret",
        "token",
        "x_cg_demo_api_key",
    }
)
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)(x[-_]cg[-_]demo[-_]api[-_]key|authorization|coingecko_api_key)"
    r"(\s*[=:]\s*)([^\s&,]+)"
)
_STANDARD_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)


class Redactor:
    """Recursively remove known secrets and secret-bearing fields."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self._secrets = tuple(sorted({value for value in secrets if value}, key=len, reverse=True))

    def redact(self, value: Any, *, key: str | None = None) -> Any:
        normalized_key = key.lower().replace("-", "_") if key else None
        if normalized_key in _SENSITIVE_KEYS:
            return REDACTED
        if isinstance(value, Mapping):
            return {
                str(item_key): self.redact(item, key=str(item_key))
                for item_key, item in value.items()
            }
        if isinstance(value, tuple):
            return tuple(self.redact(item) for item in value)
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, str):
            redacted = value
            for secret in self._secrets:
                redacted = redacted.replace(secret, REDACTED)
            return _KEY_VALUE_PATTERN.sub(rf"\1\2{REDACTED}", redacted)
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return self.redact(str(value))


class SecretRedactionFilter(logging.Filter):
    """Sanitize a log record before any formatter or handler sees it."""

    def __init__(self, redactor: Redactor) -> None:
        super().__init__()
        self._redactor = redactor

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redactor.redact(record.msg)
        record.args = self._redactor.redact(record.args)
        for key in tuple(record.__dict__):
            if key not in _STANDARD_RECORD_FIELDS:
                record.__dict__[key] = self._redactor.redact(record.__dict__[key], key=key)
        return True


class JsonFormatter(logging.Formatter):
    """Render a redacted log record as one compact JSON object."""

    def __init__(self, redactor: Redactor) -> None:
        super().__init__()
        self._redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        document: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": self._redactor.redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS:
                document[key] = self._redactor.redact(value, key=key)
        if record.exc_info:
            document["exception"] = self._redactor.redact(self.formatException(record.exc_info))
        return json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def configure_json_logging(
    *,
    logger: logging.Logger | None = None,
    level: int = logging.INFO,
    secrets: Iterable[str] = (),
    stream: TextIO | None = None,
) -> logging.Logger:
    """Install one JSON handler and its mandatory redaction filter."""

    target = logging.getLogger() if logger is None else logger
    redactor = Redactor(secrets)
    handler = logging.StreamHandler(stream)
    handler.addFilter(SecretRedactionFilter(redactor))
    handler.setFormatter(JsonFormatter(redactor))
    target.handlers.clear()
    target.addHandler(handler)
    target.setLevel(level)
    target.propagate = False
    return target
