"""Yapılandırılmış loglama (structlog) — JSON çıktısı, secret redaksiyonu."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import Any

import structlog

# Log kayıtlarında asla görünmemesi gereken alan adları (spec §3.6).
REDACTED_KEYS = frozenset(
    {
        "password",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "encrypted_payload",
        "kavun_encryption_key",
        "jwt_secret",
        "credentials",
    }
)

REDACTED_PLACEHOLDER = "***"


def redact_secrets(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Hassas anahtarları maskeler; iç içe dict'lerde de çalışır."""
    for key in list(event_dict):
        if key.lower() in REDACTED_KEYS:
            event_dict[key] = REDACTED_PLACEHOLDER
        elif isinstance(event_dict[key], dict):
            event_dict[key] = redact_secrets(_logger, _method_name, dict(event_dict[key]))
    return event_dict


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    """structlog'u yapılandırır. Tüm servisler (api, worker, cli) bunu çağırır."""
    logging.basicConfig(format="%(message)s", level=getattr(logging, level))
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_secrets,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Bağlı logger döndürür."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
