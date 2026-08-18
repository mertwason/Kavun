"""Kavun komut satırı arayüzü.

Komutlar: `version`, `check`, `generate-key`, `seed`, `seed-demo`, `wipe-demo`,
`normalize`, `replay`.

Replay (spec §3.2): normalize tablolar silinip ham olaylardan yeniden üretilir.

    python -m app.cli replay --channel trendyol --from 2026-08-01
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.crypto import generate_key
from app.core.db import SessionLocal, check_database
from app.main import API_VERSION
from app.models.enums import ChannelCode
from app.seeds.base import seed_base
from app.seeds.demo import seed_demo, wipe_demo
from app.services.normalize import normalize_pending, replay


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Kavun CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Sürüm bilgisini yazdırır")
    sub.add_parser("check", help="Ayarları ve DB bağlantısını doğrular")
    sub.add_parser("seed", help="Çekirdek veriyi kurar (tenant, marka, kanal, mağaza)")
    sub.add_parser("seed-demo", help="Demo tenant'ını gerçekçi örnek veriyle doldurur")
    sub.add_parser("wipe-demo", help="Demo tenant'ını ve tüm verisini siler")
    sub.add_parser("generate-key", help="Yeni bir KAVUN_ENCRYPTION_KEY üretir")

    normalize = sub.add_parser("normalize", help="İşlenmemiş ham olayları normalize eder")
    normalize.add_argument("--store", help="Yalnızca bu mağaza (UUID)")
    normalize.add_argument("--limit", type=int, default=5000, help="En fazla kaç olay")

    replay_parser = sub.add_parser(
        "replay", help="Normalize veriyi ham olaylardan yeniden üretir (spec §3.2)"
    )
    replay_parser.add_argument("--channel", help="Kanal kodu (ör. trendyol)")
    replay_parser.add_argument("--store", help="Yalnızca bu mağaza (UUID)")
    replay_parser.add_argument("--from", dest="since", help="Başlangıç tarihi (YYYY-AA-GG)")
    replay_parser.add_argument("--to", dest="until", help="Bitiş tarihi (YYYY-AA-GG, hariç)")
    replay_parser.add_argument(
        "--dry-run", action="store_true", help="Hiçbir şey yazmaz, sayıyı gösterir"
    )
    return parser


def _parse_date(value: str | None) -> datetime | None:
    """`YYYY-AA-GG` metnini UTC zamana çevirir."""
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)


def _run_normalize(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        summary = normalize_pending(
            session,
            store_id=uuid.UUID(args.store) if args.store else None,
            limit=args.limit,
        )
    print(json.dumps(summary.as_dict(), ensure_ascii=False))
    return 0


def _run_replay(args: argparse.Namespace) -> int:
    channel = ChannelCode(args.channel) if args.channel else None
    with SessionLocal() as session:
        summary = replay(
            session,
            channel=channel,
            store_id=uuid.UUID(args.store) if args.store else None,
            since=_parse_date(args.since),
            until=_parse_date(args.until),
            dry_run=args.dry_run,
        )
    print(json.dumps({"dry_run": args.dry_run, **summary.as_dict()}, ensure_ascii=False))
    return 0


def _run_seed() -> int:
    with SessionLocal() as session:
        result = seed_base(session)
        session.commit()
    print(
        json.dumps(
            {
                "tenant_id": result.tenant_id,
                "brands": result.brands,
                "stores": result.stores,
                "created": result.created,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _run_seed_demo() -> int:
    with SessionLocal() as session:
        summary = seed_demo(session)
    print(
        json.dumps(
            {"tenant_id": summary.tenant_id, "counts": summary.counts},
            ensure_ascii=False,
        )
    )
    return 0


def _run_wipe_demo() -> int:
    with SessionLocal() as session:
        deleted = wipe_demo(session)
    print(json.dumps({"deleted_rows": deleted}, ensure_ascii=False))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI giriş noktası; çıkış kodu döner (0 = başarılı)."""
    args = _build_parser().parse_args(argv)
    settings = get_settings()

    if args.command == "version":
        print(json.dumps({"app": settings.app_name, "version": API_VERSION}))
        return 0

    if args.command == "generate-key":
        print(generate_key())
        return 0

    if args.command == "seed":
        return _run_seed()

    if args.command == "seed-demo":
        return _run_seed_demo()

    if args.command == "wipe-demo":
        return _run_wipe_demo()

    if args.command == "normalize":
        return _run_normalize(args)

    if args.command == "replay":
        return _run_replay(args)

    database = check_database()
    print(json.dumps({"environment": settings.environment, "database": database}))
    return 0 if database["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
