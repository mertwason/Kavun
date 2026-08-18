"""KDV yardımcıları — saf fonksiyonlar (spec §6.1).

Tüm hesaplar `Decimal`; yuvarlama yalnızca 4 haneye (NUMERIC(14,4)) ve
`ROUND_HALF_UP` ile yapılır. Gösterim yuvarlaması UI'ın işidir (CLAUDE.md §1).

Terminoloji:
- **brüt (inclusive)**: KDV dahil tutar — pazaryeri kesintileri ve satış fiyatı böyledir
- **net (exclusive)**: KDV hariç tutar — stok maliyeti (WAC) böyle saklanır (spec §12C)
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

MONEY = Decimal("0.0001")
PERCENT = Decimal("100")


def quantize_money(amount: Decimal) -> Decimal:
    """Parasal tutarı 4 haneye yuvarlar (DB hassasiyeti)."""
    return amount.quantize(MONEY, rounding=ROUND_HALF_UP)


def rate_from_percent(percent: Decimal) -> Decimal:
    """Yüzdeyi orana çevirir: 20.00 → 0.20."""
    return percent / PERCENT


def net_from_gross(gross: Decimal, vat_percent: Decimal) -> Decimal:
    """KDV dahil tutardan KDV hariç tutar: `gross / (1 + oran)` (spec §6.1)."""
    return quantize_money(gross / (Decimal(1) + rate_from_percent(vat_percent)))


def vat_in_gross(gross: Decimal, vat_percent: Decimal) -> Decimal:
    """KDV dahil tutarın içindeki KDV."""
    return quantize_money(gross - net_from_gross(gross, vat_percent))


def gross_from_net(net: Decimal, vat_percent: Decimal) -> Decimal:
    """KDV hariç tutardan KDV dahil tutar."""
    return quantize_money(net * (Decimal(1) + rate_from_percent(vat_percent)))


def vat_on_net(net: Decimal, vat_percent: Decimal) -> Decimal:
    """KDV hariç tutar üzerindeki KDV."""
    return quantize_money(gross_from_net(net, vat_percent) - net)
