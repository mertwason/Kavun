"""Golden dataset referans hesabı — motordan BAĞIMSIZ ikinci uygulama (spec §11 kabul).

Faz 1 kabul kriteri: "rastgele 20 sipariş için elle hesaplanan kârla motor çıktısı kuruş
kuruş eşit". Bu dosya o "elle hesabı" temsil eder: spec §6.1'in **brüt tabanlı** formülü
adım adım, motorun kodunu görmeden yazılabilecek en düz biçimde uygulanır.

    kâr = brüt gelir − brüt maliyetler − net KDV
    net KDV = satış KDV'si − indirilecek KDV

`app.engine.profit` içindeki hiçbir şey buraya import EDİLMEZ (yalnızca yuvarlama
yardımcıları ve enum'lar paylaşılır); iki uygulamanın aynı sayıyı vermesi tesadüf olamaz.
Fark çıkarsa hangisinin yanlış olduğunu insan karar verir — test ikisinin de sessizce
kaymasını engeller.

Kapsam bilinçli olarak dardır: golden dataset'teki senaryolar (iade, hurda iade, değişim,
kampanya, ceza, iptal, KDV %1/%20). Motorun tüm yüzeyi değil, kabul kriterinin istediği
yüzey doğrulanır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

KURUS = Decimal("0.01")
MONEY = Decimal("0.0001")
"""Alan hassasiyeti: parasal değerler NUMERIC(14,4) (CLAUDE.md §1) — yuvarlama gösterimde."""

ZERO = Decimal("0")
HUNDRED = Decimal("100")
SERVICE_VAT = Decimal("20")
"""Komisyon/kargo/hizmet bedeli/ceza genel KDV oranına tabidir."""


def _round(value: Decimal) -> Decimal:
    """Alan hassasiyetine (4 hane) yuvarlar — motorun sakladığı hassasiyet.

    Kuruşa yuvarlama yalnızca karşılaştırma anında yapılır (`to_kurus`): kabul kriteri
    "kuruş kuruş eşit" der, ara adımlarda kuruşa inmek yapay fark üretirdi.
    """
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def to_kurus(value: Decimal) -> Decimal:
    """Gösterim/karşılaştırma hassasiyeti: kuruş."""
    return value.quantize(KURUS, rounding=ROUND_HALF_UP)


def _vat_inside(gross: Decimal, rate: Decimal) -> Decimal:
    """KDV dahil tutarın içindeki KDV: brüt − brüt / (1 + oran)."""
    return _round(gross - gross / (Decimal("1") + rate / HUNDRED))


@dataclass(frozen=True)
class GoldenReturn:
    """İade: adet, dönüş kargosu ve malın stoğa dönüp dönmediği."""

    qty: int
    return_cargo_cost: Decimal = ZERO
    restocked: bool = True


@dataclass(frozen=True)
class GoldenExchange:
    """Değişim: mal geri gelir + yenisi gider; müşteri parayı geri ALMAZ."""

    qty: int
    return_cargo_cost: Decimal = ZERO
    replacement_cargo_cost: Decimal = ZERO
    restocked: bool = True


@dataclass(frozen=True)
class GoldenCase:
    """Bir sipariş satırı — golden dataset'in girdisi."""

    case_id: str
    note: str
    line_gross: Decimal
    qty: int
    vat_percent: Decimal
    unit_cost_net: Decimal | None = None
    commission_rate: Decimal | None = None
    cargo_cost: Decimal = ZERO
    service_fee: Decimal = ZERO
    penalty: Decimal = ZERO
    campaign_discount: Decimal = ZERO
    campaign_seller_share_rate: Decimal = Decimal("1")
    cancelled: bool = False
    returns: tuple[GoldenReturn, ...] = field(default_factory=tuple)
    exchanges: tuple[GoldenExchange, ...] = field(default_factory=tuple)


def reference_profit(case: GoldenCase) -> Decimal:
    """Satırın net kârı — spec §6.1 formülünün düz uygulaması.

    Adımlar (her biri spec metnindeki cümleye karşılık gelir):

    1. İptal satırda ne gelir ne maliyet vardır → 0.
    2. İade edilen adedin geliri hesaba girmez; kalan adetlerin brüt geliri alınır.
    3. Kampanya indiriminin platform payı satıcıya geri ödenir → gelire eklenir.
    4. COGS satılan adetler için; stoğa dönmeyen (hurda) iade/değişim adetleri de maliyet
       doğurur çünkü mal geri gelmedi. Stok maliyeti KDV hariç saklanır → KDV eklenir.
    5. Komisyon KDV dahil satış tutarı üzerinden doğar.
    6. Kargo (gidiş + değişimin yeni gönderisi), hizmet bedeli ve ceza KDV dahildir.
    7. İade/değişimin dönüş kargosu gerçek nakit kaybıdır.
    8. Net KDV = satış KDV'si − (maliyet + hizmet kalemlerinin içindeki KDV).
    9. Kâr = brüt gelir + kampanya desteği − brüt maliyetler − dönüş kargoları − net KDV.
    """
    if case.cancelled:
        return ZERO

    returned_qty = min(sum(item.qty for item in case.returns), case.qty)
    scrapped_qty = min(sum(item.qty for item in case.returns if not item.restocked), case.qty)
    exchange_scrapped = min(
        sum(item.qty for item in case.exchanges if not item.restocked), case.qty
    )
    sold_qty = case.qty - returned_qty

    unit_gross = case.line_gross / case.qty if case.qty else ZERO
    revenue_gross = _round(unit_gross * sold_qty)

    platform_share = Decimal("1") - case.campaign_seller_share_rate
    sold_ratio = Decimal(sold_qty) / Decimal(case.qty) if case.qty else ZERO
    campaign_support = _round(case.campaign_discount * platform_share * sold_ratio)

    unit_cost_net = case.unit_cost_net or ZERO
    cogs_net = _round(unit_cost_net * (sold_qty + scrapped_qty + exchange_scrapped))
    cogs_vat = _round(cogs_net * case.vat_percent / HUNDRED)
    cogs_gross = _round(cogs_net + cogs_vat)

    commission = _round(revenue_gross * (case.commission_rate or ZERO))
    cargo = _round(
        case.cargo_cost + sum((item.replacement_cargo_cost for item in case.exchanges), ZERO)
    )
    service = _round(case.service_fee)
    penalty = _round(case.penalty)
    return_cargo = _round(
        sum((item.return_cargo_cost for item in case.returns), ZERO)
        + sum((item.return_cargo_cost for item in case.exchanges), ZERO)
    )

    vat_sales = _vat_inside(revenue_gross, case.vat_percent) + _vat_inside(
        campaign_support, case.vat_percent
    )
    vat_deductible = (
        cogs_vat
        + _vat_inside(commission, SERVICE_VAT)
        + _vat_inside(cargo, SERVICE_VAT)
        + _vat_inside(service, SERVICE_VAT)
        + _vat_inside(penalty, SERVICE_VAT)
    )
    vat_net = _round(vat_sales - vat_deductible)

    return _round(
        revenue_gross
        + campaign_support
        - cogs_gross
        - commission
        - cargo
        - service
        - return_cargo
        - penalty
        - vat_net
    )
