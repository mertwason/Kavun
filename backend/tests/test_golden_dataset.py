"""KVN-20: golden dataset — 20 sipariş, elle hesapla motor kuruş kuruş eşit (spec §11).

Faz 1 kabul kriteri birebir budur. Beklenen değerler `tests/golden/orders.json` içinde
**donmuş literal** olarak durur; hem motor hem bağımsız referans hesabı (`golden_reference`)
bu literallerle karşılaştırılır. Üç kaynak birden aynı sayıyı vermelidir:

    motor  ==  referans uygulama  ==  dosyadaki donmuş beklenen değer

Böylece iki tür sessiz kayma yakalanır: motorda yapılan bir hata (referans yakalar) ve
ikisinin birden aynı yönde kayması (donmuş literal yakalar — literal ancak insan
onayıyla değişir).

Dosya `python -m tests.golden_generate` ile üretilir; üretim yalnızca girdileri yazar,
beklenen değerler referans hesaptan gelir ve gözden geçirilerek commit edilir.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.engine.profit import ExchangeInput as EngineExchange
from app.engine.profit import LineInput, ReturnInput, compute_line_profit
from app.models.enums import OrderStatus
from tests.golden_reference import (
    GoldenCase,
    GoldenExchange,
    GoldenReturn,
    reference_profit,
    to_kurus,
)

GOLDEN_PATH = Path(__file__).parent / "golden" / "orders.json"

D = Decimal


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _case(raw: dict[str, Any]) -> GoldenCase:
    """JSON satırını referans hesabın girdisine çevirir."""
    return GoldenCase(
        case_id=raw["id"],
        note=raw["note"],
        line_gross=_decimal(raw["line_gross"]),
        qty=int(raw["qty"]),
        vat_percent=_decimal(raw["vat_percent"]),
        unit_cost_net=None if raw["unit_cost_net"] is None else _decimal(raw["unit_cost_net"]),
        commission_rate=(
            None if raw["commission_rate"] is None else _decimal(raw["commission_rate"])
        ),
        cargo_cost=_decimal(raw.get("cargo_cost", 0)),
        service_fee=_decimal(raw.get("service_fee", 0)),
        penalty=_decimal(raw.get("penalty", 0)),
        campaign_discount=_decimal(raw.get("campaign_discount", 0)),
        campaign_seller_share_rate=_decimal(raw.get("campaign_seller_share_rate", 1)),
        cancelled=bool(raw.get("cancelled", False)),
        returns=tuple(
            GoldenReturn(
                qty=int(item["qty"]),
                return_cargo_cost=_decimal(item.get("return_cargo_cost", 0)),
                restocked=bool(item.get("restocked", True)),
            )
            for item in raw.get("returns", [])
        ),
        exchanges=tuple(
            GoldenExchange(
                qty=int(item["qty"]),
                return_cargo_cost=_decimal(item.get("return_cargo_cost", 0)),
                replacement_cargo_cost=_decimal(item.get("replacement_cargo_cost", 0)),
                restocked=bool(item.get("restocked", True)),
            )
            for item in raw.get("exchanges", [])
        ),
    )


def _engine_input(case: GoldenCase) -> LineInput:
    """Aynı girdiyi motorun beklediği biçimde kurar."""
    return LineInput(
        line_gross=case.line_gross,
        qty=case.qty,
        vat_percent=case.vat_percent,
        status=OrderStatus.CANCELLED if case.cancelled else OrderStatus.DELIVERED,
        unit_cost_net=case.unit_cost_net,
        commission_rate=case.commission_rate,
        cargo_cost=case.cargo_cost,
        service_fee=case.service_fee,
        penalty=case.penalty,
        campaign_discount=case.campaign_discount,
        campaign_seller_share_rate=case.campaign_seller_share_rate,
        returns=tuple(
            ReturnInput(
                qty=item.qty,
                refund_amount=case.line_gross / case.qty * item.qty,
                return_cargo_cost=item.return_cargo_cost,
                restocked=item.restocked,
            )
            for item in case.returns
        ),
        exchanges=tuple(
            EngineExchange(
                qty=item.qty,
                return_cargo_cost=item.return_cargo_cost,
                replacement_cargo_cost=item.replacement_cargo_cost,
                restocked=item.restocked,
            )
            for item in case.exchanges
        ),
    )


def _dataset() -> list[dict[str, Any]]:
    return list(json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["cases"])


DATASET = _dataset()


def test_dataset_has_twenty_orders() -> None:
    """§11 Faz 1 kabul: "rastgele 20 sipariş" — sayı azalırsa kriter zayıflar."""
    assert len(DATASET) == 20
    assert len({row["id"] for row in DATASET}) == 20


@pytest.mark.parametrize("raw", DATASET, ids=[row["id"] for row in DATASET])
def test_engine_matches_the_hand_calculation(raw: dict[str, Any]) -> None:
    """§11 Faz 1 kabul: motor çıktısı elle hesapla **kuruş kuruş** eşit."""
    case = _case(raw)
    expected = _decimal(raw["expected_profit"])

    engine = compute_line_profit(_engine_input(case))
    reference = reference_profit(case)

    assert to_kurus(engine.profit) == expected, f"{case.case_id}: motor ≠ donmuş beklenen değer"
    assert to_kurus(reference) == expected, f"{case.case_id}: referans ≠ donmuş beklenen değer"
    # Yuvarlamanın gizleyebileceği yapısal farkı da yakala: yarım kuruştan fazla sapma
    # iki uygulamanın aynı şeyi hesaplamadığı anlamına gelir.
    assert abs(engine.profit - reference) <= D("0.005"), f"{case.case_id}: yapısal fark"


@pytest.mark.parametrize("raw", DATASET, ids=[row["id"] for row in DATASET])
def test_engine_margin_matches_the_frozen_value(raw: dict[str, Any]) -> None:
    """Marj yüzdesi de donmuş değerle eşleşir — kâr doğru ama marj yanlış olamaz."""
    engine = compute_line_profit(_engine_input(_case(raw)))

    assert to_kurus(engine.margin_pct) == _decimal(raw["expected_margin_pct"])


def test_totals_match_the_frozen_summary() -> None:
    """Toplam kâr da donmuştur: tek satır değişse toplam yakalar."""
    payload = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    total = sum(
        (to_kurus(compute_line_profit(_engine_input(_case(raw))).profit) for raw in DATASET),
        Decimal("0"),
    )

    assert total == _decimal(payload["expected_total_profit"])


def test_worked_example_is_reproducible_by_hand() -> None:
    """Dosyadaki elle çözümlü örnek (`GOLD-01`) adım adım doğrulanır.

    Satır: 2 adet × 1.000 TL = 2.000 TL brüt, KDV %20, birim maliyet 600 TL (KDV hariç),
    komisyon %20, kargo 60 TL, hizmet bedeli 12 TL. Ara adımlar **4 haneyle** taşınır
    (CLAUDE.md §1: yuvarlama yalnızca gösterimde), sonuç kuruşa yuvarlanır:

        COGS brüt       = 2 × 600 × 1,20                        = 1.440,0000
        komisyon        = 2.000 × 0,20                          =   400,0000
        satış KDV       = 2.000 − 2.000/1,20                    =   333,3333
        indirilecek KDV = 240,0000 + 66,6667 + 10,0000 + 2,0000 =   318,6667
        net KDV         = 333,3333 − 318,6667                   =    14,6666
        kâr             = 2.000 − 1.440 − 400 − 60 − 12 − 14,6666 = 73,3334
        kuruşa yuvarlanmış                                        = 73,33

    Not: ara adımlar kuruşa yuvarlansaydı 73,34 çıkardı. Fark, "hangi aşamada
    yuvarlanır" sorusunun cevabıdır ve CLAUDE.md §1 bunu net söyler: gösterimde.
    """
    case = _case(next(row for row in DATASET if row["id"] == "GOLD-01"))

    engine = compute_line_profit(_engine_input(case))

    assert engine.profit == D("73.3334")
    assert to_kurus(engine.profit) == D("73.33")
    assert to_kurus(reference_profit(case)) == D("73.33")
