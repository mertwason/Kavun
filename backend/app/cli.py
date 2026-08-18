"""Kavun komut satırı arayüzü.

Şu an: `version`, `check`. Sonraki görevlerde eklenecekler:
- `seed` / `seed-demo` (KVN-02)
- `replay --channel trendyol --from 2026-08-01` (KVN-06, spec §3.2)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from app.core.config import get_settings
from app.core.db import check_database
from app.main import API_VERSION


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Kavun CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Sürüm bilgisini yazdırır")
    sub.add_parser("check", help="Ayarları ve DB bağlantısını doğrular")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI giriş noktası; çıkış kodu döner (0 = başarılı)."""
    args = _build_parser().parse_args(argv)
    settings = get_settings()

    if args.command == "version":
        print(json.dumps({"app": settings.app_name, "version": API_VERSION}))
        return 0

    database = check_database()
    print(json.dumps({"environment": settings.environment, "database": database}))
    return 0 if database["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
