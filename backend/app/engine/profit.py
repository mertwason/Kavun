"""Kâr motoru — sipariş satırı bazında net kâr (spec §6).

Saf fonksiyon: girdi → çıktı, DB erişimi yok (CLAUDE.md §1). DB'den okuma/yazma
`app/services/profit.py` katmanındadır.

## KDV modeli (bağlayıcı karar)

Spec §6.1'deki formül brüt (KDV dahil) tabanlıdır:

    kar = line_gross - cogs - komisyon - kargo - hizmet_bedeli - iade - reklam - net_kdv
    net_kdv = satış_kdv - indirilecek_kdv

Bunun tutarlı olması için **çıkarılan her maliyet KDV DAHİL tutar olmalıdır**.
Kavun'da maliyetler iki farklı biçimde durur, motor ikisini de doğru ele alır:

| Kalem | Nasıl saklanır | Motorda |
|---|---|---|
| Satış (`line_gross`) | KDV **dahil** | içindeki KDV satış KDV'sidir |
| Stok maliyeti (WAC, `sku_costs`) | KDV **hariç** (spec §12C: ithalat KDV'si maliyete girmez) | KDV eklenir, eklenen KDV indirilecek KDV olur |
| Komisyon / kargo / hizmet bedeli | KDV **dahil** (platform bu tutarı keser) | içindeki KDV indirilecek KDV olur |

Sonuç iki yoldan da aynıdır ve motor bunu kendi içinde doğrular:

    kar = brüt satış − brüt maliyetler − net KDV
        = net satış  − net maliyetler

`profit_net_check` alanı ikinci yolun sonucunu taşır; ikisi tutmuyorsa hesap hatalıdır.

## Kapsam

Faz 1: komisyon, kargo, hizmet bedeli, iade, değişim, kampanya satıcı payı, ceza,
KDV netleştirme. Reklam payı (Faz 4) girdide vardır ama sıfırdır.

## Değişim, kampanya ve ceza (spec §6.3.2, §6.3.3, §6.3.7)

- **Değişim iade değildir.** Müşteri parayı geri almaz, ürün elinde kalır: gelir,
  komisyon ve satış KDV'si yerinde durur; yalnızca iki ek kargo bacağı (geri geliş +
  yeni gönderi) gider yazılır. Geri gelen mal hurdaysa o adet için iki birim maliyet
  çıkar.
- **Kampanya:** `line_gross` müşterinin ödediği indirimli tutardır. İndirimin platform
  payı satıcıya geri ödendiği için gelire eklenir ve satış KDV'si doğurur. Varsayılan
  `campaign_seller_share_rate = 1` — yani aksi kanıtlanana kadar indirimin tamamını
  satıcı taşır (muhafazakâr varsayım, CLAUDE.md §5).
- **Ceza/tazmin:** siparişe eşleşen ceza satır gideridir (KDV'si indirilebilir sayılır,
  `TODO(verify)` — hakediş faturasından doğrulanacak). Eşleşmeyen ceza satırlara
  DAĞITILMAZ; `split_penalties()` onu mağaza seviyesinde ayrı tutar.

## İade modeli (spec §6.1'den bilinçli sapma)

Spec §6.1 iade için hem "satış geliri sıfırlanır" hem de "iade_maliyeti = refund + ..."
diyor. İkisi birlikte uygulanırsa aynı zarar İKİ KEZ sayılır: 1.000 TL'lik bir ürün iade
edildiğinde gelir 0 olur ve üstüne 1.000 TL gider yazılır; gerçek kayıp yalnızca kargo
iken satır −1.000 TL görünür. Bu, dashboard ve SKU marj listesini bozar.

Motor tek ve tutarlı bir model uygular: **iade edilen adedin geliri hesaba girmez**,
iade tutarı ayrıca gider yazılmaz. O adet için komisyon da doğmaz (komisyon gelir
üzerinden hesaplanır) ve satış KDV'si de oluşmaz — üçü birlikte geri çevrilir.

Gerçek kayıp kalemleri sayılır: gidiş kargosu (satırın `cargo_cost` kaleminde) ve dönüş
kargosu (`ReturnInput.return_cargo_cost`). Mal hurdaysa (`restocked=False`) o adedin
maliyeti de zarar olarak kalır (spec §12C.4).

`refund_amount` girdide taşınır ama gider olarak eklenmez; hakediş mutabakatında
(Faz 2) platformun iade ettiği tutarla karşılaştırmak için saklanır.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from app.engine.vat import (
    net_from_gross,
    quantize_money,
    vat_in_gross,
    vat_on_net,
)
from app.models.enums import CommissionSource, OrderStatus

ZERO = Decimal("0")
DEFAULT_SERVICE_VAT_PERCENT = Decimal("20.00")
"""Platform hizmetleri (komisyon, kargo, hizmet bedeli, ceza) genel KDV oranına tabidir."""

FULL_SELLER_SHARE = Decimal("1")
"""Kampanya indiriminin varsayılan taşıyıcısı satıcıdır — platform desteği kanıt ister."""

# Maliyet kalemi üretmeyen statüler (spec §6.3.5: iptal → maliyet kalemleri sıfır).
COSTLESS_STATUSES = frozenset({OrderStatus.CANCELLED})


@dataclass(frozen=True)
class ReturnInput:
    """İade girdisi (spec §6.1, §6.3.1, §12C.4).

    İade edilen adedin geliri hesaba girmez; `refund_amount` ayrıca gider yazılmaz —
    aksi halde aynı zarar iki kez sayılırdı (bkz. modül docstring'i, "İade modeli").
    Alan yine de taşınır: hakediş mutabakatında (Faz 2) platformun iade ettiği tutarla
    karşılaştırılacak.

    Gidiş kargosu satırın kendi `cargo_cost` kaleminde zaten vardır; burada yalnızca
    **dönüş** kargosu verilir.

    `restocked=False`: mal geri gelmedi/hurda → o adedin maliyeti zarar olarak kalır
    (spec §12C.4).
    """

    qty: int
    refund_amount: Decimal
    return_cargo_cost: Decimal = ZERO
    restocked: bool = True


@dataclass(frozen=True)
class ExchangeInput:
    """Değişim girdisi (spec §6.3.2: iade + yeni gönderi, çift kargo).

    Değişim iade DEĞİLDİR: müşteri parayı geri almaz, ürünü elinde tutar. Bu yüzden
    gelir, komisyon ve satış KDV'si **geri çevrilmez** — yalnızca iki ek kargo bacağı
    doğar: geri geliş (`return_cargo_cost`) ve yeni gönderi (`replacement_cargo_cost`).

    `restocked=False`: geri gelen mal satılamaz durumda → o adet için İKİ birim maliyet
    çıkmış olur (biri müşterideki, biri hurdadaki).
    """

    qty: int
    return_cargo_cost: Decimal = ZERO
    replacement_cargo_cost: Decimal = ZERO
    restocked: bool = True


@dataclass(frozen=True)
class LineInput:
    """Bir sipariş satırının kâr hesabı için gereken her şey.

    Tutarların KDV durumu: `line_gross`, `cargo_cost`, `service_fee` ve iade tutarları
    KDV **dahil**; `unit_cost_net` KDV **hariç**.
    """

    line_gross: Decimal
    qty: int
    vat_percent: Decimal
    status: OrderStatus = OrderStatus.DELIVERED

    unit_cost_net: Decimal | None = None
    commission_rate: Decimal | None = None
    commission_source: CommissionSource | None = None
    cargo_cost: Decimal = ZERO
    service_fee: Decimal = ZERO
    ad_alloc: Decimal = ZERO
    penalty: Decimal = ZERO
    returns: tuple[ReturnInput, ...] = ()
    exchanges: tuple[ExchangeInput, ...] = ()

    # Kampanya (spec §6.3.3): `line_gross` müşterinin ÖDEDİĞİ (indirimli) tutardır.
    # İndirimin platform payı satıcıya geri ödenir → gelire eklenir.
    campaign_discount: Decimal = ZERO
    campaign_seller_share_rate: Decimal = FULL_SELLER_SHARE

    service_vat_percent: Decimal = DEFAULT_SERVICE_VAT_PERCENT
    is_final: bool = False


@dataclass(frozen=True)
class ProfitBreakdown:
    """Kâr dökümü — `line_profit` tablosunun ve waterfall grafiğinin kaynağı."""

    revenue_gross: Decimal
    revenue_net_vat: Decimal
    revenue_campaign_support: Decimal
    cost_cogs: Decimal
    cost_commission: Decimal
    cost_cargo: Decimal
    cost_service_fee: Decimal
    cost_return: Decimal
    cost_ad_alloc: Decimal
    cost_penalty: Decimal
    vat_sales: Decimal
    vat_deductible: Decimal
    vat_net: Decimal
    profit: Decimal
    margin_pct: Decimal
    commission_source: CommissionSource | None = None
    is_final: bool = False
    warnings: tuple[str, ...] = field(default=())

    @property
    def waterfall(self) -> tuple[tuple[str, Decimal], ...]:
        """Sipariş detayındaki şelale grafiğinin adımları (tasarım brief'i, kalıp 4)."""
        return (
            ("satis", self.revenue_gross),
            ("kampanya_destegi", self.revenue_campaign_support),
            ("komisyon", -self.cost_commission),
            ("kargo", -self.cost_cargo),
            ("hizmet_bedeli", -self.cost_service_fee),
            ("iade", -self.cost_return),
            ("ceza", -self.cost_penalty),
            ("reklam", -self.cost_ad_alloc),
            ("kdv", -self.vat_net),
            ("maliyet", -self.cost_cogs),
            ("kar", self.profit),
        )


def _returned_qty(line: LineInput) -> int:
    return sum(item.qty for item in line.returns)


def compute_line_profit(line: LineInput) -> ProfitBreakdown:
    """Bir sipariş satırının net kârını hesaplar (spec §6.1)."""
    warnings: list[str] = []

    if line.status in COSTLESS_STATUSES:
        # İptal: ne gelir ne maliyet oluşur.
        return ProfitBreakdown(
            revenue_gross=ZERO,
            revenue_net_vat=ZERO,
            revenue_campaign_support=ZERO,
            cost_cogs=ZERO,
            cost_commission=ZERO,
            cost_cargo=ZERO,
            cost_service_fee=ZERO,
            cost_return=ZERO,
            cost_ad_alloc=ZERO,
            cost_penalty=ZERO,
            vat_sales=ZERO,
            vat_deductible=ZERO,
            vat_net=ZERO,
            profit=ZERO,
            margin_pct=ZERO,
            commission_source=line.commission_source,
            is_final=line.is_final,
            warnings=("iptal",),
        )

    returned_qty = min(_returned_qty(line), line.qty)
    scrapped_qty = min(sum(item.qty for item in line.returns if not item.restocked), line.qty)
    sold_qty = line.qty - returned_qty
    unit_gross = line.line_gross / line.qty if line.qty else ZERO

    # Değişim gelirle oynamaz; yalnızca geri gelen mal hurdaysa fazladan maliyet doğurur.
    exchange_scrapped_qty = min(
        sum(item.qty for item in line.exchanges if not item.restocked), line.qty
    )

    # İade edilen adetlerin geliri hesaba girmez; tamamı iade edildiyse gelir sıfırlanır.
    revenue_gross = quantize_money(unit_gross * sold_qty)
    revenue_net = net_from_gross(revenue_gross, line.vat_percent)
    vat_sales = quantize_money(revenue_gross - revenue_net)

    # Kampanya indiriminin platform payı satıcıya geri ödenir (spec §6.3.3). Yalnızca
    # satılan (iade edilmemiş) adetler için doğar.
    platform_share = FULL_SELLER_SHARE - line.campaign_seller_share_rate
    sold_ratio = Decimal(sold_qty) / Decimal(line.qty) if line.qty else ZERO
    campaign_support = quantize_money(line.campaign_discount * platform_share * sold_ratio)
    campaign_support_vat = vat_in_gross(campaign_support, line.vat_percent)

    # --- maliyetler (hepsi KDV dahil tutar) ---
    if line.unit_cost_net is None:
        warnings.append("maliyet_yok")
    unit_cost_net = line.unit_cost_net or ZERO
    # COGS satılan adetler için; geri gelmeyen (hurda) iade adetleri de maliyet doğurur
    # çünkü mal stoğa dönmedi (spec §12C.4).
    cogs_net = quantize_money(unit_cost_net * (sold_qty + scrapped_qty + exchange_scrapped_qty))
    cogs_vat = vat_on_net(cogs_net, line.vat_percent)
    cogs_gross = quantize_money(cogs_net + cogs_vat)

    if line.commission_rate is None:
        warnings.append("komisyon_orani_yok")
    commission_rate = line.commission_rate or ZERO
    # Komisyon KDV dahil satış tutarı üzerinden hesaplanır (spec §6.1).
    commission_gross = quantize_money(revenue_gross * commission_rate)
    # Değişimin yeni gönderisi ikinci bir gidiş kargosudur (spec §6.3.2).
    cargo_gross = quantize_money(
        line.cargo_cost + sum((item.replacement_cargo_cost for item in line.exchanges), ZERO)
    )
    service_gross = quantize_money(line.service_fee)
    ad_alloc = quantize_money(line.ad_alloc)
    penalty_gross = quantize_money(line.penalty)

    # --- iade maliyeti (spec §6.1, düzeltilmiş: çift sayma yok) ---
    # Gerçek nakit kaybı dönüş kargosudur; iade tutarı gelirden zaten düşülmüştür.
    # Değişimde de mal geri gelir → o bacak da burada sayılır.
    return_cost = quantize_money(
        sum((item.return_cargo_cost for item in line.returns), ZERO)
        + sum((item.return_cargo_cost for item in line.exchanges), ZERO)
    )

    # --- KDV netleştirme ---
    vat_sales_total = quantize_money(vat_sales + campaign_support_vat)
    vat_deductible = quantize_money(
        cogs_vat
        + vat_in_gross(commission_gross, line.service_vat_percent)
        + vat_in_gross(cargo_gross, line.service_vat_percent)
        + vat_in_gross(service_gross, line.service_vat_percent)
        + vat_in_gross(penalty_gross, line.service_vat_percent)
    )
    vat_net = quantize_money(vat_sales_total - vat_deductible)

    profit = quantize_money(
        revenue_gross
        + campaign_support
        - cogs_gross
        - commission_gross
        - cargo_gross
        - service_gross
        - return_cost
        - penalty_gross
        - ad_alloc
        - vat_net
    )
    margin_pct = quantize_money(profit / revenue_gross * Decimal(100)) if revenue_gross else ZERO

    return ProfitBreakdown(
        revenue_gross=revenue_gross,
        revenue_net_vat=revenue_net,
        revenue_campaign_support=campaign_support,
        cost_cogs=cogs_gross,
        cost_commission=commission_gross,
        cost_cargo=cargo_gross,
        cost_service_fee=service_gross,
        cost_return=return_cost,
        cost_ad_alloc=ad_alloc,
        cost_penalty=penalty_gross,
        vat_sales=vat_sales_total,
        vat_deductible=vat_deductible,
        vat_net=vat_net,
        profit=profit,
        margin_pct=margin_pct,
        commission_source=line.commission_source,
        is_final=line.is_final,
        warnings=tuple(warnings),
    )


def split_penalties(
    items: Iterable[tuple[uuid.UUID | None, Decimal]],
) -> tuple[dict[uuid.UUID, Decimal], Decimal]:
    """Ceza/tazmin kalemlerini satır bazlı ve mağaza bazlı olarak ayırır (spec §6.3.7).

    Sipariş satırına eşleşen ceza o satırın kârını düşürür; eşleşmeyen ceza satırlara
    dağıtılmaz (hangi satırın suçu olduğu bilinmez) — mağaza seviyesinde gider kalır ve
    dashboard'da ayrı gösterilir. Uydurma dağıtım yapılmaz.
    """
    per_line: dict[uuid.UUID, Decimal] = {}
    store_level = ZERO
    for line_id, amount in items:
        if line_id is None:
            store_level += amount
        else:
            per_line[line_id] = per_line.get(line_id, ZERO) + amount
    return {key: quantize_money(value) for key, value in per_line.items()}, quantize_money(
        store_level
    )


def profit_from_net_amounts(line: LineInput, breakdown: ProfitBreakdown) -> Decimal:
    """Aynı kârı KDV hariç tutarlarla hesaplar — motorun kendi kendini denetlemesi.

    `kar = net satış − net maliyetler` yolu, brüt yoldan çıkan sonuca eşit olmalıdır.
    """
    net_commission = net_from_gross(breakdown.cost_commission, line.service_vat_percent)
    net_cargo = net_from_gross(breakdown.cost_cargo, line.service_vat_percent)
    net_service = net_from_gross(breakdown.cost_service_fee, line.service_vat_percent)
    net_penalty = net_from_gross(breakdown.cost_penalty, line.service_vat_percent)
    net_campaign_support = net_from_gross(breakdown.revenue_campaign_support, line.vat_percent)
    net_cogs = quantize_money(
        breakdown.cost_cogs - vat_in_gross(breakdown.cost_cogs, line.vat_percent)
    )
    return quantize_money(
        breakdown.revenue_net_vat
        + net_campaign_support
        - net_cogs
        - net_commission
        - net_cargo
        - net_service
        - net_penalty
        - breakdown.cost_return
        - breakdown.cost_ad_alloc
    )
