"""KVN-08: kâr motoru edge-case paketi — spec §6.3'teki 8 senaryo, birebir.

Her senaryo spec'teki numarasıyla adlandırılmıştır; test adı kabul kriterini referanslar
(CLAUDE.md §3). Saf senaryolar motoru doğrudan çağırır, DB gerektirenler (paylaştırma,
tarihli komisyon) gerçek kayıtlar üzerinden gider.

Property-based testler (Hypothesis) dosyanın sonundadır: para matematiğinin
senaryodan bağımsız değişmezleri.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import system_scope
from app.engine.allocation import allocate
from app.engine.profit import (
    ExchangeInput,
    LineInput,
    ReturnInput,
    compute_line_profit,
    profit_from_net_amounts,
    split_penalties,
)
from app.engine.vat import quantize_money
from app.models.enums import OrderStatus
from app.models.identity import Store
from app.models.results import LineProfit
from app.models.transactions import OrderLine
from app.services import profit as profit_service
from tests.profit_factories import (
    ORDER_DATE,
    make_commission,
    make_order,
    make_product,
    make_store,
)

D = Decimal

# Kahveji: %1 KDV'li gıda · Alessi: %20 KDV'li genel ürün (spec §6.3.4).
KAHVE_VAT = D("1.00")
GENEL_VAT = D("20.00")


def line(**overrides: object) -> LineInput:
    """Referans satır: 120 TL brüt, %20 KDV, 50 TL net maliyet, %20 komisyon."""
    defaults: dict[str, object] = {
        "line_gross": D("120.00"),
        "qty": 1,
        "vat_percent": GENEL_VAT,
        "unit_cost_net": D("50.00"),
        "commission_rate": D("0.2000"),
        "cargo_cost": D("24.00"),
        "service_fee": D("12.00"),
    }
    return LineInput(**{**defaults, **overrides})  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def system_context() -> Iterator[None]:
    """Kâr hesabı bir sistem işidir (KVN-03 guard'ı)."""
    with system_scope():
        yield


@pytest.fixture
def store(db_session: Session) -> Store:
    """Hizmet bedeli tanımlı Trendyol mağazası."""
    return make_store(db_session)


def _profit_of(db_session: Session, order_line_id: uuid.UUID) -> LineProfit:
    record = db_session.scalar(select(LineProfit).where(LineProfit.order_line_id == order_line_id))
    assert record is not None
    return record


# --- §6.3.1 kısmi iade -------------------------------------------------------


def test_6_3_1_partial_return_keeps_revenue_of_unreturned_units() -> None:
    """§6.3.1: 3 adetlik satırın 1 adedi iade → 2 adedin geliri ve maliyeti durur.

    Elle hesap (360 brüt = 3 × 120, %20 KDV, 50 net maliyet, %20 komisyon):
    kalan gelir 240 · komisyon 48 · COGS 2 × 60 = 120 · kargo 24 · hizmet 12 ·
    dönüş kargosu 24
    net KDV = satış 40 − indirilecek (20 mal + 8 komisyon + 4 kargo + 2 hizmet) = 6
    kâr = 240 − 120 − 48 − 24 − 12 − 24 − 6 = 6,00
    """
    result = compute_line_profit(
        line(
            qty=3,
            line_gross=D("360.00"),
            returns=(ReturnInput(qty=1, refund_amount=D("120.00"), return_cargo_cost=D("24.00")),),
        )
    )

    assert result.revenue_gross == D("240.0000")
    assert result.cost_cogs == D("120.0000")
    assert result.cost_commission == D("48.0000")
    assert result.cost_return == D("24.0000")
    assert result.vat_net == D("6.0000")
    assert result.profit == D("6.0000")


def test_6_3_1_partial_return_beats_full_return() -> None:
    """§6.3.1: kısmi iade, aynı satırın tam iadesinden her zaman daha iyidir."""
    partial = compute_line_profit(
        line(qty=3, line_gross=D("360.00"), returns=(ReturnInput(qty=1, refund_amount=D("120")),))
    )
    full = compute_line_profit(
        line(qty=3, line_gross=D("360.00"), returns=(ReturnInput(qty=3, refund_amount=D("360")),))
    )

    assert partial.profit > full.profit


# --- §6.3.2 değişim ----------------------------------------------------------


def test_6_3_2_exchange_keeps_revenue_and_charges_two_extra_cargo_legs() -> None:
    """§6.3.2: değişim iade değildir — gelir durur, iki ek kargo bacağı gider yazılır.

    Müşteri parayı geri almadığı için komisyon ve satış KDV'si de yerinde kalır;
    kayıp yalnızca geri geliş + yeni gönderi kargosudur.
    """
    plain = compute_line_profit(line())
    exchange = compute_line_profit(
        line(
            exchanges=(
                ExchangeInput(
                    qty=1,
                    return_cargo_cost=D("24.00"),
                    replacement_cargo_cost=D("24.00"),
                ),
            )
        )
    )

    assert exchange.revenue_gross == plain.revenue_gross
    assert exchange.cost_commission == plain.cost_commission
    assert exchange.cost_cargo == D("48.0000")  # ilk gönderi + yeni gönderi
    assert exchange.cost_return == D("24.0000")  # geri geliş
    assert exchange.profit < plain.profit


def test_6_3_2_exchange_is_not_a_return() -> None:
    """§6.3.2: aynı adet iade edilseydi gelir sıfırlanırdı; değişimde sıfırlanmaz."""
    exchange = compute_line_profit(
        line(exchanges=(ExchangeInput(qty=1, return_cargo_cost=D("24.00")),))
    )
    returned = compute_line_profit(
        line(returns=(ReturnInput(qty=1, refund_amount=D("120.00"), return_cargo_cost=D("24.00")),))
    )

    assert exchange.revenue_gross == D("120.0000")
    assert returned.revenue_gross == D("0.0000")


def test_6_3_2_scrapped_exchange_costs_two_units() -> None:
    """§6.3.2 + §12C.4: geri gelen mal satılamazsa tek satış için iki birim maliyet çıkar."""
    restocked = compute_line_profit(line(exchanges=(ExchangeInput(qty=1),)))
    scrapped = compute_line_profit(line(exchanges=(ExchangeInput(qty=1, restocked=False),)))

    assert restocked.cost_cogs == D("60.0000")
    assert scrapped.cost_cogs == D("120.0000")


# --- §6.3.3 kampanya: satıcı payı vs platform payı ---------------------------


def test_6_3_3_campaign_discount_defaults_to_full_seller_share() -> None:
    """§6.3.3: platform desteği KANITLANANA kadar indirimin tamamını satıcı taşır.

    Muhafazakâr varsayım (CLAUDE.md §5): `seller_share_rate` verilmezse kâr, indirimsiz
    satırla aynıdır — uydurma platform desteği gelire eklenmez.
    """
    without_promo = compute_line_profit(line())
    with_promo = compute_line_profit(line(campaign_discount=D("30.00")))

    assert with_promo.revenue_campaign_support == D("0.0000")
    assert with_promo.profit == without_promo.profit


def test_6_3_3_platform_share_of_discount_is_credited_to_seller() -> None:
    """§6.3.3: indirimin platform payı satıcıya geri ödenir → gelire eklenir, KDV'si doğar.

    30 TL indirimin %60'ını platform karşılıyorsa destek 18 TL; bunun 3 TL'si satış KDV'si,
    yani satıra net katkı 15 TL'dir.
    """
    seller_only = compute_line_profit(line(campaign_discount=D("30.00")))
    shared = compute_line_profit(
        line(campaign_discount=D("30.00"), campaign_seller_share_rate=D("0.4000"))
    )

    assert shared.revenue_campaign_support == D("18.0000")
    assert shared.profit - seller_only.profit == D("15.0000")


def test_6_3_3_campaign_support_follows_returned_units() -> None:
    """§6.3.3: iade edilen adedin kampanya desteği de geri çevrilir."""
    result = compute_line_profit(
        line(
            qty=2,
            line_gross=D("240.00"),
            campaign_discount=D("40.00"),
            campaign_seller_share_rate=D("0.5000"),
            returns=(ReturnInput(qty=1, refund_amount=D("120.00")),),
        )
    )

    assert result.revenue_campaign_support == D("10.0000")  # 40 × %50 × (1/2 adet)


# --- §6.3.4 farklı KDV oranları ---------------------------------------------


@pytest.mark.parametrize("vat_percent", [KAHVE_VAT, GENEL_VAT])
def test_6_3_4_both_vat_rates_net_out_correctly(vat_percent: Decimal) -> None:
    """§6.3.4: %1 (gıda/Kahveji) ve %20 (genel/Alessi) — iki oran da doğru netleşir."""
    result = compute_line_profit(line(vat_percent=vat_percent))

    assert result.vat_net == quantize_money(result.vat_sales - result.vat_deductible)
    assert result.profit == profit_from_net_amounts(line(vat_percent=vat_percent), result)


def test_6_3_4_low_vat_line_is_more_profitable_at_equal_prices() -> None:
    """§6.3.4: aynı fiyat ve maliyette %1 KDV'li satır, %20 KDV'liden daha kârlıdır.

    Sebep: satış KDV'si düşerken platform kesintilerinin indirilecek KDV'si %20'de kalır.
    Kahveji ile Alessi'nin marjları bu yüzden doğrudan karşılaştırılamaz.
    """
    food = compute_line_profit(line(vat_percent=KAHVE_VAT))
    general = compute_line_profit(line(vat_percent=GENEL_VAT))

    assert food.profit > general.profit


# --- §6.3.5 iptal ------------------------------------------------------------


def test_6_3_5_cancelled_line_has_zero_cost_items() -> None:
    """§6.3.5: kargolanmadan iptal → tüm maliyet kalemleri sıfır, satır uyarıyla işaretli."""
    result = compute_line_profit(
        line(status=OrderStatus.CANCELLED, cargo_cost=D("24.00"), service_fee=D("12.00"))
    )

    assert result.profit == D("0")
    assert result.warnings == ("iptal",)
    assert all(
        value == D("0")
        for value in (
            result.revenue_gross,
            result.cost_cogs,
            result.cost_commission,
            result.cost_cargo,
            result.cost_service_fee,
            result.cost_return,
            result.cost_penalty,
            result.vat_net,
        )
    )


def test_6_3_5_cancelled_order_writes_zero_profit_rows(db_session: Session, store: Store) -> None:
    """§6.3.5: iptal sipariş DB'de de sıfır kârla yazılır — satır kaybolmaz."""
    product = make_product(db_session, store, "IPTAL-1")
    make_commission(db_session, store)
    order = make_order(db_session, store, [(product, 1, D("120.00"))], status=OrderStatus.CANCELLED)

    profit_service.recompute_orders(db_session, order_ids=[order.id])

    order_line = db_session.scalar(select(OrderLine).where(OrderLine.order_id == order.id))
    assert order_line is not None
    record = _profit_of(db_session, order_line.id)
    assert record.profit == D("0.0000")
    assert record.cost_cargo == D("0.0000")


# --- §6.3.6 aynı pakette çoklu satır ----------------------------------------


def test_6_3_6_cargo_is_allocated_by_desi_across_lines(db_session: Session, store: Store) -> None:
    """§6.3.6: tek paketteki iki satıra kargo desi ağırlıklı dağıtılır, kuruş kaybolmaz.

    Desi 3 ve desi 1 → 100 TL kargo 75/25 bölünür.
    """
    heavy = make_product(db_session, store, "AGIR-1", desi=D("3.00"))
    light = make_product(db_session, store, "HAFIF-1", desi=D("1.00"))
    make_commission(db_session, store)
    order = make_order(
        db_session,
        store,
        [(heavy, 1, D("240.00")), (light, 1, D("240.00"))],
        cargo=D("100.0000"),
    )

    profit_service.recompute_orders(db_session, order_ids=[order.id])

    lines = list(
        db_session.scalars(
            select(OrderLine)
            .where(OrderLine.order_id == order.id)
            .order_by(OrderLine.external_line_id)
        ).all()
    )
    parts = [_profit_of(db_session, item.id).cost_cargo for item in lines]
    assert parts == [D("75.0000"), D("25.0000")]
    assert sum(parts, D("0")) == D("100.0000")


def test_6_3_6_unknown_desi_falls_back_to_equal_split(db_session: Session, store: Store) -> None:
    """§6.3.6: desi bilinmeyen satırlarda kargo eşit bölünür — kimse cezalandırılmaz."""
    first = make_product(db_session, store, "DESISIZ-1", desi=D("0.00"))
    second = make_product(db_session, store, "DESISIZ-2", desi=D("0.00"))
    make_commission(db_session, store)
    order = make_order(
        db_session,
        store,
        [(first, 1, D("120.00")), (second, 1, D("120.00"))],
        cargo=D("50.0000"),
    )

    profit_service.recompute_orders(db_session, order_ids=[order.id])

    lines = list(db_session.scalars(select(OrderLine).where(OrderLine.order_id == order.id)).all())
    parts = [_profit_of(db_session, item.id).cost_cargo for item in lines]
    assert sum(parts, D("0")) == D("50.0000")
    assert max(parts) - min(parts) <= D("0.0001")


# --- §6.3.7 ceza / tazmin ----------------------------------------------------


def test_6_3_7_matched_penalty_reduces_line_profit() -> None:
    """§6.3.7: siparişe eşleşen ceza o satırın gideridir (KDV'si indirilebilir)."""
    clean = compute_line_profit(line())
    penalised = compute_line_profit(line(penalty=D("60.00")))

    assert penalised.cost_penalty == D("60.0000")
    # 60 TL cezanın 10 TL'si indirilecek KDV → satıra net etkisi 50 TL.
    assert clean.profit - penalised.profit == D("50.0000")


def test_6_3_7_unmatched_penalty_stays_at_store_level() -> None:
    """§6.3.7: sipariş eşleşmeyen ceza satırlara DAĞITILMAZ, mağaza gideri kalır."""
    first, second = uuid.uuid4(), uuid.uuid4()
    per_line, store_level = split_penalties(
        [
            (first, D("60.00")),
            (None, D("250.00")),
            (second, D("40.00")),
            (first, D("15.00")),
            (None, D("100.00")),
        ]
    )

    assert per_line == {first: D("75.0000"), second: D("40.0000")}
    assert store_level == D("350.0000")


def test_6_3_7_penalties_are_never_invented() -> None:
    """§6.3.7: eşleşme yoksa satır bazlı ceza da üretilmez."""
    per_line, store_level = split_penalties([(None, D("500.00"))])

    assert per_line == {}
    assert store_level == D("500.0000")


# --- §6.3.8 komisyon oranı değişimi -----------------------------------------


def test_6_3_8_commission_rate_change_is_resolved_by_order_date(
    db_session: Session, store: Store
) -> None:
    """§6.3.8: tarihli tarifeler — her sipariş kendi tarihinde geçerli oranla hesaplanır.

    Aynı ürün, aynı fiyat; tarife 1 Ağustos'ta %20'den %25'e çıkmışsa temmuz siparişi
    %20, ağustos siparişi %25 komisyon görür. Geçmiş sipariş geriye dönük ezilmez.
    """
    product = make_product(db_session, store, "TARIFE-1")
    make_commission(db_session, store, rate=D("0.2000"), valid_from=ORDER_DATE - timedelta(days=90))
    make_commission(db_session, store, rate=D("0.2500"), valid_from=ORDER_DATE - timedelta(days=5))

    old_order = make_order(
        db_session,
        store,
        [(product, 1, D("120.00"))],
        order_date=ORDER_DATE - timedelta(days=30),
    )
    new_order = make_order(db_session, store, [(product, 1, D("120.00"))])

    profit_service.recompute_orders(db_session, order_ids=[old_order.id, new_order.id])

    def commission_of(order_id: uuid.UUID) -> Decimal:
        order_line = db_session.scalar(select(OrderLine).where(OrderLine.order_id == order_id))
        assert order_line is not None
        return _profit_of(db_session, order_line.id).cost_commission

    assert commission_of(old_order.id) == D("24.0000")  # 120 × %20
    assert commission_of(new_order.id) == D("30.0000")  # 120 × %25


# --- property-based testler (CLAUDE.md §3) ----------------------------------

money = st.decimals(
    min_value=D("0"), max_value=D("100000"), places=2, allow_nan=False, allow_infinity=False
)
positive_money = st.decimals(
    min_value=D("1"), max_value=D("100000"), places=2, allow_nan=False, allow_infinity=False
)
rate = st.decimals(min_value=D("0"), max_value=D("0.5"), places=4)
vat = st.sampled_from([D("0.00"), D("1.00"), D("10.00"), D("20.00")])

PROPERTY_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@given(
    gross=positive_money,
    vat_percent=vat,
    cost=money,
    commission=rate,
    cargo=money,
    service=money,
    qty=st.integers(min_value=1, max_value=10),
)
@PROPERTY_SETTINGS
def test_property_gross_and_net_paths_always_agree(
    gross: Decimal,
    vat_percent: Decimal,
    cost: Decimal,
    commission: Decimal,
    cargo: Decimal,
    service: Decimal,
    qty: int,
) -> None:
    """Değişmez: brüt yol ile net yol her girdide aynı kârı verir (motorun öz denetimi)."""
    scenario = LineInput(
        line_gross=gross,
        qty=qty,
        vat_percent=vat_percent,
        unit_cost_net=cost,
        commission_rate=commission,
        cargo_cost=cargo,
        service_fee=service,
    )
    result = compute_line_profit(scenario)

    assert abs(profit_from_net_amounts(scenario, result) - result.profit) <= D("0.0100")


@given(
    gross=positive_money,
    vat_percent=vat,
    qty=st.integers(min_value=1, max_value=10),
    returned=st.integers(min_value=0, max_value=10),
)
@PROPERTY_SETTINGS
def test_property_returned_revenue_never_exceeds_sales(
    gross: Decimal, vat_percent: Decimal, qty: int, returned: int
) -> None:
    """Değişmez: iade toplamı satış gelirini aşamaz (CLAUDE.md §3)."""
    result = compute_line_profit(
        LineInput(
            line_gross=gross,
            qty=qty,
            vat_percent=vat_percent,
            returns=(ReturnInput(qty=returned, refund_amount=gross),),
        )
    )

    assert D("0") <= result.revenue_gross <= quantize_money(gross)


@given(
    gross=positive_money,
    vat_percent=vat,
    cheap=money,
    extra=positive_money,
)
@PROPERTY_SETTINGS
def test_property_higher_cost_never_increases_profit(
    gross: Decimal, vat_percent: Decimal, cheap: Decimal, extra: Decimal
) -> None:
    """Değişmez: maliyet arttıkça kâr azalır (monotonluk) — yuvarlama bunu bozamaz."""
    base = compute_line_profit(
        LineInput(line_gross=gross, qty=1, vat_percent=vat_percent, unit_cost_net=cheap)
    )
    pricier = compute_line_profit(
        LineInput(line_gross=gross, qty=1, vat_percent=vat_percent, unit_cost_net=cheap + extra)
    )

    assert pricier.profit <= base.profit


@given(
    total=money,
    weights=st.lists(
        st.decimals(min_value=D("0"), max_value=D("1000"), places=2), min_size=1, max_size=12
    ),
)
@PROPERTY_SETTINGS
def test_property_allocation_never_loses_or_creates_money(
    total: Decimal, weights: list[Decimal]
) -> None:
    """Değişmez: paylaştırılan parçaların toplamı her zaman dağıtılan tutara eşittir."""
    parts = allocate(total, weights)

    assert len(parts) == len(weights)
    assert sum(parts, D("0")) == quantize_money(total)


@given(gross=positive_money, vat_percent=vat, commission=rate)
@PROPERTY_SETTINGS
def test_property_penalty_only_ever_reduces_profit(
    gross: Decimal, vat_percent: Decimal, commission: Decimal
) -> None:
    """Değişmez: ceza kalemi kârı asla artıramaz (§6.3.7)."""
    kwargs = {
        "line_gross": gross,
        "qty": 1,
        "vat_percent": vat_percent,
        "commission_rate": commission,
    }
    clean = compute_line_profit(LineInput(**kwargs))  # type: ignore[arg-type]
    penalised = compute_line_profit(LineInput(penalty=D("100.00"), **kwargs))  # type: ignore[arg-type]

    assert penalised.profit <= clean.profit


@given(
    gross=positive_money,
    vat_percent=vat,
    cost=money,
    commission=rate,
    penalty=money,
    discount=money,
    share=st.decimals(min_value=D("0"), max_value=D("1"), places=4),
)
@PROPERTY_SETTINGS
def test_property_waterfall_always_sums_to_profit(
    gross: Decimal,
    vat_percent: Decimal,
    cost: Decimal,
    commission: Decimal,
    penalty: Decimal,
    discount: Decimal,
    share: Decimal,
) -> None:
    """Değişmez: şelale adımları her senaryoda kâra iner (sipariş detayı ekranı buna güvenir)."""
    assume(discount <= gross)
    result = compute_line_profit(
        LineInput(
            line_gross=gross,
            qty=1,
            vat_percent=vat_percent,
            unit_cost_net=cost,
            commission_rate=commission,
            penalty=penalty,
            campaign_discount=discount,
            campaign_seller_share_rate=share,
        )
    )

    steps = dict(result.waterfall)
    total = sum((value for key, value in result.waterfall if key != "kar"), D("0"))
    assert abs(quantize_money(total) - steps["kar"]) <= D("0.0100")
