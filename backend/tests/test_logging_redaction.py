"""CLAUDE.md §2: credential'lar loglara asla yazılmaz."""

from __future__ import annotations

import pytest

from app.core.logging import (
    REDACTED_PLACEHOLDER,
    configure_logging,
    get_logger,
    redact_secrets,
)


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


def test_logs_go_to_stderr_not_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI stdout'u yalnızca komut çıktısı (JSON) taşır; log satırı stdout'u kirletmez."""
    configure_logging("INFO")
    get_logger("test").info("kavun.log_stream_check", value=1)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "kavun.log_stream_check" in captured.err


def test_logger_survives_a_swapped_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Akış kurulumda yakalanmaz: pytest stderr'i test başına değiştirir, logger kırılmaz."""
    configure_logging("INFO")
    log = get_logger("test")
    log.info("kavun.first")
    capsys.readouterr()  # akışı tüketip yenile

    log.info("kavun.second")
    assert "kavun.second" in capsys.readouterr().err
