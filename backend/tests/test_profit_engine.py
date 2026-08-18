"""KVN-07: kâr motoru çekirdek hesabı (spec §6.1).

Saf fonksiyon testleri — DB yok. Edge-case paketi KVN-08'de genişletilecek.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.allocation import allocate
from app.engine.profit import (
    LineInput,
    ReturnInput,
    compute_line_profit,
    profit_from_net_amounts,
)
from app.engine.vat import (
    gross_from_net,
    net_from_gross,
    quantize_money,
    vat_in_gross,
    vat_on_net,
)
from app.models.enums import OrderStatus

D = Decimal


def line(**overrides: object) -> LineInput:
    """Varsayılan bir satır girdisi (KDV %20, maliyet net 50, komisyon %20)."""
    defaults: dict[str, object] = {
        "line_gross": D("120.00"),
        "qty": 1,
        "vat_percent": D("20.00"),
        "unit_cost_net": D("50.00"),
        "commission_rate": D("0.2000"),
        "cargo_cost": D("24.00"),
        "service_fee": D("12.00"),
    }
    return LineInput(**{**defaults, **overrides})  # type: ignore[arg-type]


# --- KDV yardımcıları -------------------------------------------------------


def test_net_from_gross_matches_spec_formula() -> None:
    """`satis_kdv_haric = line_gross / (1 + vat_rate)` (spec §6.1)."""
    assert net_from_gross(D("120.00"), D("20.00")) == D("100.0000")
    assert net_from_gross(D("101.00"), D("1.00")) == D("100.0000")


def test_vat_helpers_are_consistent() -> None:
    """Brüt → net → brüt turu kuruş kaybetmez."""
    for gross, vat in ((D("389.00"), D("1.00")), (D("6890.00"), D("20.00"))):
        net = net_from_gross(gross, vat)
        assert quantize_money(net + vat_in_gross(gross, vat)) == quantize_money(gross)
        assert gross_from_net(net, vat) == quantize_money(gross)
        assert vat_on_net(net, vat) == vat_in_gross(gross, vat)


# --- paylaştırma ------------------------------------------------------------


def test_allocation_preserves_total() -> None:
    """Paylaştırılan parçaların toplamı dağıtılan tutara eşittir (kuruş kaybolmaz)."""
    parts = allocate(D("100.00"), [D("1"), D("1"), D("1")])
    assert sum(parts, D(0)) == D("100.0000")
    assert parts == [D("33.3333"), D("33.3333"), D("33.3334")]


def test_allocation_is_weighted() -> None:
    """Desi ağırlıklı kargo dağıtımı (spec §6.3.6)."""
    assert allocate(D("100.00"), [D("3"), D("1")]) == [D("75.0000"), D("25.0000")]


def test_allocation_without_weights_is_equal() -> None:
    """Ağırlık yoksa eşit bölünür ve toplam korunur."""
    parts = allocate(D("10.00"), [D("0"), D("0"), D("0")])
    assert sum(parts, D(0)) == D("10.0000")


def test_allocation_edge_cases() -> None:
    """Boş liste ve tek satır."""
    assert allocate(D("50.00"), []) == []
    assert allocate(D("50.00"), [D("7")]) == [D("50.0000")]


# --- çekirdek hesap ---------------------------------------------------------


def test_profit_matches_hand_calculation() -> None:
    """Elle hesap: 120 brüt satış, 50 net maliyet, %20 komisyon, 24 kargo, 12 hizmet.

    KDV: satış 20,00 · indirilecek 10 (mal) + 4 (komisyon) + 4 (kargo) + 2 (hizmet) = 20,00
    Net KDV 0,00 → kâr = 120 − 60 − 24 − 24 − 12 − 0 = 0,00
    """
    result = compute_line_profit(line())

    assert result.revenue_gross == D("120.0000")
    assert result.revenue_net_vat == D("100.0000")
    assert result.cost_cogs == D("60.0000")  # 50 net + 10 KDV
    assert result.cost_commission == D("24.0000")
    assert result.vat_sales == D("20.0000")
    assert result.vat_deductible == D("20.0000")
    assert result.vat_net == D("0.0000")
    assert result.profit == D("0.0000")


def test_profitable_line() -> None:
    """Kârlı satır: 389 TL kahve, %1 KDV, 185 maliyet, %14,5 komisyon."""
    result = compute_line_profit(
        line(
            line_gross=D("389.00"),
            vat_percent=D("1.00"),
            unit_cost_net=D("185.00"),
            commission_rate=D("0.1450"),
            cargo_cost=D("51.25"),
            service_fee=D("8.99"),
        )
    )

    assert result.profit > 0
    assert result.margin_pct > 0
    # Brüt ve net yol aynı kârı vermeli.
    assert result.profit == profit_from_net_amounts(
        line(
            line_gross=D("389.00"),
            vat_percent=D("1.00"),
            unit_cost_net=D("185.00"),
            commission_rate=D("0.1450"),
            cargo_cost=D("51.25"),
            service_fee=D("8.99"),
        ),
        result,
    )


def test_negative_margin_is_reported_not_clamped() -> None:
    """Maliyetin altında satış negatif kâr verir — sıfıra kırpılmaz."""
    result = compute_line_profit(
        line(line_gross=D("69.00"), vat_percent=D("1.00"), unit_cost_net=D("48.00"))
    )

    assert result.profit < 0
    assert result.margin_pct < 0


def test_gross_and_net_paths_agree() -> None:
    """Motorun kendi denetimi: brüt yol = net yol (her senaryoda)."""
    scenarios = [
        line(),
        line(vat_percent=D("1.00")),
        line(qty=3, line_gross=D("360.00")),
        line(commission_rate=D("0.2250"), cargo_cost=D("0")),
        line(unit_cost_net=None),
    ]
    for scenario in scenarios:
        result = compute_line_profit(scenario)
        assert profit_from_net_amounts(scenario, result) == result.profit


def test_cancelled_line_has_no_costs() -> None:
    """İptal → tüm maliyet kalemleri sıfır (spec §6.3.5)."""
    result = compute_line_profit(line(status=OrderStatus.CANCELLED))

    assert result.profit == D("0")
    assert result.revenue_gross == D("0")
    assert result.cost_commission == D("0")
    assert result.cost_cargo == D("0")
    assert result.warnings == ("iptal",)


def test_missing_cost_is_flagged_not_guessed() -> None:
    """Maliyet yoksa uydurulmaz; satır uyarı ile işaretlenir."""
    result = compute_line_profit(line(unit_cost_net=None))

    assert "maliyet_yok" in result.warnings
    assert result.cost_cogs == D("0")


def test_missing_commission_rate_is_flagged() -> None:
    """Komisyon oranı yoksa uydurma oran kullanılmaz (KVN-05 bulgusu)."""
    result = compute_line_profit(line(commission_rate=None))

    assert "komisyon_orani_yok" in result.warnings
    assert result.cost_commission == D("0")


# --- iadeler ----------------------------------------------------------------


def test_full_return_leaves_only_real_costs() -> None:
    """Tam iade: gelir, komisyon ve satış KDV'si geri çevrilir; kayıp kargo kadardır.

    120 TL'lik ürün iade edildiğinde satır −120 TL görünmez: gerçek kayıp gidiş
    kargosu (24) + dönüş kargosu (24) + hizmet bedeli (12) − indirilecek KDV (6) = 54.
    """
    result = compute_line_profit(
        line(returns=(ReturnInput(qty=1, refund_amount=D("120.00"), return_cargo_cost=D("24.00")),))
    )

    assert result.revenue_gross == D("0.0000")
    assert result.cost_commission == D("0.0000")  # gelir yoksa komisyon da yok
    assert result.cost_cogs == D("0.0000")  # mal stoğa döndü
    assert result.cost_return == D("24.0000")  # dönüş kargosu
    assert result.vat_net == D("-6.0000")  # indirilecek KDV alacağı
    assert result.profit == D("-54.0000")


def test_refund_is_not_double_counted() -> None:
    """İade tutarı gelirden düşülür VE ayrıca gider yazılmaz (spec §6.1 çelişkisi).

    Spec her ikisini de söylüyor; ikisi birlikte uygulanırsa aynı zarar iki kez sayılır.
    """
    result = compute_line_profit(
        line(returns=(ReturnInput(qty=1, refund_amount=D("120.00"), return_cargo_cost=D("24.00")),))
    )

    # Çift sayım olsaydı kâr −174 olurdu (−54 − 120).
    assert result.profit == D("-54.0000")
    assert result.cost_return == D("24.0000")


def test_partial_return_keeps_sold_units(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kısmi iade: 3 adetin 1'i iade → 2 adedin geliri ve maliyeti kalır (spec §6.3.1)."""
    result = compute_line_profit(
        line(
            qty=3,
            line_gross=D("360.00"),
            returns=(ReturnInput(qty=1, refund_amount=D("120.00"), return_cargo_cost=D("24.00")),),
        )
    )

    assert result.revenue_gross == D("240.0000")
    assert result.cost_cogs == D("120.0000")  # 2 × (50 + 10 KDV)
    assert result.cost_return == D("24.0000")


def test_scrapped_return_keeps_cost_of_goods() -> None:
    """İade edilen mal hurdaysa maliyeti zarar olarak kalır (spec §12C.4)."""
    restocked = compute_line_profit(
        line(
            qty=2, line_gross=D("240.00"), returns=(ReturnInput(qty=1, refund_amount=D("120.00")),)
        )
    )
    scrapped = compute_line_profit(
        line(
            qty=2,
            line_gross=D("240.00"),
            returns=(ReturnInput(qty=1, refund_amount=D("120.00"), restocked=False),),
        )
    )

    assert scrapped.cost_cogs > restocked.cost_cogs
    assert scrapped.profit < restocked.profit


def test_waterfall_steps_sum_to_profit() -> None:
    """Şelale adımları kâra iner (tasarım brief'i, kalıp 4)."""
    result = compute_line_profit(line(line_gross=D("389.00"), vat_percent=D("1.00")))

    steps = dict(result.waterfall)
    total = sum((value for key, value in result.waterfall if key != "kar"), D("0"))
    assert quantize_money(total) == steps["kar"]
