"""KVN-01: CLI iskeleti çalışır (replay komutu KVN-06'da eklenecek)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app import cli


def test_version_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["version"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["app"] == "Kavun"
    assert payload["version"]


def test_check_command_fails_when_database_down(
    capsys: pytest.CaptureFixture[str], monkeypatch: Any
) -> None:
    monkeypatch.setattr(cli, "check_database", lambda: {"ok": False, "error": "OperationalError"})
    assert cli.main(["check"]) == 1
    assert json.loads(capsys.readouterr().out)["database"]["ok"] is False


def test_check_command_succeeds_when_database_up(
    capsys: pytest.CaptureFixture[str], monkeypatch: Any
) -> None:
    monkeypatch.setattr(cli, "check_database", lambda: {"ok": True})
    assert cli.main(["check"]) == 0
    assert json.loads(capsys.readouterr().out)["database"]["ok"] is True


def test_unknown_command_exits_with_error() -> None:
    with pytest.raises(SystemExit):
        cli.main(["bilinmeyen"])
