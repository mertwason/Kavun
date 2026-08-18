"""Kavun komut satırı arayüzü.

Komutlar: `version`, `check`, `seed`, `seed-demo`, `wipe-demo`.
Sonraki görevlerde eklenecek: `replay --channel trendyol --from 2026-08-01` (KVN-06, spec §3.2).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from app.core.config import get_settings
from app.core.crypto import generate_key
from app.core.db import SessionLocal, check_database
from app.main import API_VERSION
from app.seeds.base import seed_base
from app.seeds.demo import seed_demo, wipe_demo


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Kavun CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Sürüm bilgisini yazdırır")
    sub.add_parser("check", help="Ayarları ve DB bağlantısını doğrular")
    sub.add_parser("seed", help="Çekirdek veriyi kurar (tenant, marka, kanal, mağaza)")
    sub.add_parser("seed-demo", help="Demo tenant'ını gerçekçi örnek veriyle doldurur")
    sub.add_parser("wipe-demo", help="Demo tenant'ını ve tüm verisini siler")
    sub.add_parser("generate-key", help="Yeni bir KAVUN_ENCRYPTION_KEY üretir")
    return parser


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

    database = check_database()
    print(json.dumps({"environment": settings.environment, "database": database}))
    return 0 if database["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
