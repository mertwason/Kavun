"""KVN-01: CLI iskeleti çalışır (replay komutu KVN-06'da eklenecek)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.orm import Session

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


def test_seed_commands_run_against_database(
    capsys: pytest.CaptureFixture[str], monkeypatch: Any, db_session: Session
) -> None:
    """`seed`, `seed-demo` ve `wipe-demo` uçtan uca çalışır."""
    monkeypatch.setattr(cli, "SessionLocal", lambda: _NonClosingSession(db_session))

    assert cli.main(["seed"]) == 0
    assert json.loads(capsys.readouterr().out)["brands"]

    assert cli.main(["seed-demo"]) == 0
    counts = json.loads(capsys.readouterr().out)["counts"]
    assert counts["products"] > 0

    assert cli.main(["wipe-demo"]) == 0
    assert json.loads(capsys.readouterr().out)["deleted_rows"] > 0


class _NonClosingSession:
    """Test oturumunu CLI'a ödünç verir; `with` bloğu çıkışında kapatmaz."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, *exc_info: object) -> None:
        return None
