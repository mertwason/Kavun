"""Fiyatlandırma çözücüsü — hedef marj için gereken satış fiyatı (spec §12A.4).

Saf fonksiyon: girdi → çıktı, DB yok (CLAUDE.md §1). **Deterministik**: talep tahmini,
elastikiyet ya da olasılık yok.

## Cebirsel türetme (spec §12A.4: "iteratif değil kapalı formülle")

Kısaltmalar (hepsi kâr motorundaki tanımlarla birebir aynı):

    β = v / (1 + v)          satış KDV'sinin brüt içindeki payı (v = KDV oranı)
    α = s / (1 + s)          platform hizmet KDV'sinin brüt içindeki payı (s = %20)
    A = 1 − β − k(1 − α)     birim brüt satışın kâra kalan payı (k = komisyon oranı)
    B = c + (G + S)(1 − α)   fiyattan bağımsız maliyet tabanı
                             (c = KDV hariç birim maliyet, G = kargo, S = hizmet bedeli)

Motorun kâr denklemi (liste fiyatı P, kampanya indirimi oranı d, satıcı payı σ):

    müşterinin ödediği   = P(1 − d)
    platform desteği     = P·d·(1 − σ)          → gelire eklenir, KDV'si doğar
    kar = P(1 − d)·A + P·d(1 − σ)(1 − β) − B

Marj tanımı motordakiyle aynı: `marj = kar / brüt satış`, yani payda P(1 − d).
Hedef marj m için:

    P(1 − d)A + P·d(1 − σ)(1 − β) − B = m · P(1 − d)
    P[(1 − d)(A − m) + d(1 − σ)(1 − β)] = B
    P = B / [(1 − d)(A − m) + d(1 − σ)(1 − β)]

Payda ≤ 0 ise hedef marj bu maliyet yapısıyla **ulaşılamaz** (fiyat ne olursa olsun);
fonksiyon `None` döner — sonsuza giden bir fiyat uydurulmaz.

Başabaş fiyat = hedef marjın sıfır olduğu hâl.

Doğruluk kanıtı testte: çözücünün verdiği fiyat motora geri verildiğinde hedef marj
±0,01 puan tutmalıdır (spec §12A.6 kabul kriteri).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.engine.profit import DEFAULT_SERVICE_VAT_PERCENT, FULL_SELLER_SHARE
from app.engine.vat import quantize_money

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class PriceInputs:
    """Fiyattan BAĞIMSIZ girdiler — çözücü bunları sabit tutup fiyatı arar."""

    unit_cost_net: Decimal
    """KDV hariç birim maliyet."""

    vat_percent: Decimal
    commission_rate: Decimal
    cargo_cost: Decimal = ZERO
    """KDV dahil; kargoyu satıcı ödemiyorsa çağıran sıfır verir."""

    service_fee: Decimal = ZERO
    service_vat_percent: Decimal = DEFAULT_SERVICE_VAT_PERCENT
    campaign_discount_rate: Decimal = ZERO
    """Liste fiyatı üzerinden indirim oranı (0–1)."""

    campaign_seller_share_rate: Decimal = FULL_SELLER_SHARE
    """İndirimin satıcıya kalan payı; 1 = tamamı satıcıda (varsayılan)."""


def _beta(vat_percent: Decimal) -> Decimal:
    rate = vat_percent / HUNDRED
    return rate / (ONE + rate)


def margin_coefficients(inputs: PriceInputs) -> tuple[Decimal, Decimal]:
    """`(A, B)` katsayıları — kâr = P·(kampanyalı A) − B ilişkisinin taşıyıcıları."""
    beta = _beta(inputs.vat_percent)
    alpha = _beta(inputs.service_vat_percent)
    coefficient = ONE - beta - inputs.commission_rate * (ONE - alpha)
    base = inputs.unit_cost_net + (inputs.cargo_cost + inputs.service_fee) * (ONE - alpha)
    return coefficient, base


def price_for_margin(target_margin_pct: Decimal, inputs: PriceInputs) -> Decimal | None:
    """Hedef marjı (%) tutturan liste fiyatı; ulaşılamıyorsa `None` (spec §12A.4).

    Kapalı formül — iterasyon yok. Türetme modül docstring'inde.
    """
    coefficient, base = margin_coefficients(inputs)
    beta = _beta(inputs.vat_percent)
    discount = inputs.campaign_discount_rate
    seller_share = inputs.campaign_seller_share_rate
    target = target_margin_pct / HUNDRED

    denominator = (ONE - discount) * (coefficient - target) + discount * (ONE - seller_share) * (
        ONE - beta
    )
    if denominator <= ZERO:
        return None
    if base <= ZERO:
        # Maliyetsiz ürün: hedef marj her fiyatta sağlanır; anlamlı bir fiyat yok.
        return None
    return quantize_money(base / denominator)


def break_even_price(inputs: PriceInputs) -> Decimal | None:
    """Kârın sıfırlandığı liste fiyatı (marj %0)."""
    return price_for_margin(ZERO, inputs)
