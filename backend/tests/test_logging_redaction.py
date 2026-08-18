"""CLAUDE.md §2: credential'lar loglara asla yazılmaz."""

from __future__ import annotations

from app.core.logging import REDACTED_PLACEHOLDER, redact_secrets


def test_top_level_secrets_are_redacted() -> None:
    event = {"event": "store.sync", "api_key": "AKIA123", "store_id": 7}
    result = redact_secrets(None, "info", event)
    assert result["api_key"] == REDACTED_PLACEHOLDER
    assert result["store_id"] == 7


def test_nested_secrets_are_redacted() -> None:
    event = {"event": "store.connect", "payload": {"API_SECRET": "s3cr3t", "seller_id": "12345"}}
    result = redact_secrets(None, "info", event)
    assert result["payload"]["API_SECRET"] == REDACTED_PLACEHOLDER
    assert result["payload"]["seller_id"] == "12345"


def test_encryption_key_is_redacted() -> None:
    event = {"kavun_encryption_key": "abc", "jwt_secret": "def"}
    result = redact_secrets(None, "info", event)
    assert result == {
        "kavun_encryption_key": REDACTED_PLACEHOLDER,
        "jwt_secret": REDACTED_PLACEHOLDER,
    }
