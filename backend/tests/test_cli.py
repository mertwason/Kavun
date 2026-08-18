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


def _last_json(output: str) -> Any:
    """CLI çıktısındaki son JSON satırını çözer.

    `local` ortamında structlog konsola da yazdığı için stdout karışık olabilir;
    komutun kendi çıktısı her zaman son JSON satırıdır.
    """
    for line in reversed([line for line in output.splitlines() if line.strip()]):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise AssertionError(f"Çıktıda JSON yok: {output!r}")


def test_normalize_and_replay_commands(
    capsys: pytest.CaptureFixture[str], monkeypatch: Any, db_session: Session
) -> None:
    """`normalize` ve `replay` komutları uçtan uca çalışır (spec §3.2)."""
    import json as json_module
    from datetime import UTC, datetime
    from pathlib import Path

    from sqlalchemy import select

    from app.core.context import system_scope
    from app.models.enums import ChannelCode
    from app.models.identity import Channel, Store
    from app.seeds.base import seed_base
    from app.services.sync import record_raw_events

    monkeypatch.setattr(cli, "SessionLocal", lambda: _NonClosingSession(db_session))

    with system_scope():
        seed_base(db_session)
        channel = db_session.scalar(select(Channel).where(Channel.code == ChannelCode.TRENDYOL))
        assert channel is not None
        store = db_session.scalar(select(Store).where(Store.channel_id == channel.id))
        assert store is not None
        fixture = Path(__file__).parent / "fixtures" / "trendyol" / "orders_page0.json"
        payloads = json_module.loads(fixture.read_text(encoding="utf-8"))["content"]
        record_raw_events(
            db_session,
            store,
            "order",
            [(str(item["orderNumber"]), item) for item in payloads],
            fetched_at=datetime.now(UTC),
        )

    assert cli.main(["normalize"]) == 0
    assert _last_json(capsys.readouterr().out)["orders_created"] == 2

    assert cli.main(["replay", "--channel", "trendyol", "--dry-run"]) == 0
    dry = _last_json(capsys.readouterr().out)
    assert dry["dry_run"] is True and dry["processed_events"] == 2

    assert cli.main(["replay", "--channel", "trendyol", "--from", "2026-01-01"]) == 0
    replayed = _last_json(capsys.readouterr().out)
    assert replayed["processed_events"] == 2
    assert replayed["orders_created"] == 2


def test_generate_key_command(capsys: pytest.CaptureFixture[str]) -> None:
    """`generate-key` geçerli bir Fernet anahtarı basar."""
    from cryptography.fernet import Fernet

    assert cli.main(["generate-key"]) == 0
    key = capsys.readouterr().out.strip().splitlines()[-1]
    assert Fernet(key).decrypt(Fernet(key).encrypt(b"x")) == b"x"
