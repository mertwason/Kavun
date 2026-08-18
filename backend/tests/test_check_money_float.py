"""CLAUDE.md §1: float ile para hesabı yasağı lint kuralıyla zorlanır."""

from __future__ import annotations

from pathlib import Path

from tools.check_money_float import check_paths, check_source, main


def test_float_annotation_is_rejected() -> None:
    violations = check_source("def kar(fiyat: float) -> float:\n    return fiyat\n")
    assert len(violations) == 2


def test_float_literal_is_rejected() -> None:
    violations = check_source("KOMISYON = 0.215\n")
    assert len(violations) == 1
    assert "float literal" in violations[0].detail


def test_decimal_usage_is_clean() -> None:
    source = (
        "from decimal import Decimal\n"
        "\n"
        "KOMISYON = Decimal('0.215')\n"
        "\n"
        "def kar(fiyat: Decimal) -> Decimal:\n"
        "    return fiyat * KOMISYON\n"
    )
    assert check_source(source) == []


def test_allow_marker_suppresses_violation() -> None:
    source = "ORAN = 1.5  # allow-float: desi eşiği, para değil\n"
    assert check_source(source) == []


def test_app_package_has_no_float_usage() -> None:
    """Asıl kural: uygulama kodu her zaman temiz kalmalı."""
    violations = check_paths([Path(__file__).resolve().parents[1] / "app"])
    assert violations == [], "\n".join(v.render() for v in violations)


def test_main_returns_error_code_on_violation(tmp_path: Path) -> None:
    offender = tmp_path / "kotu.py"
    offender.write_text("maliyet = 12.5\n", encoding="utf-8")
    assert main([str(offender)]) == 1


def test_main_returns_zero_when_clean(tmp_path: Path) -> None:
    clean = tmp_path / "iyi.py"
    clean.write_text("from decimal import Decimal\n\nmaliyet = Decimal('12.5')\n", encoding="utf-8")
    assert main([str(clean)]) == 0
