"""Maliyet paylaştırma — saf fonksiyonlar (spec §6.1, §6.3.6).

İki kural bağlayıcıdır:

1. **Kuruş kaybolmaz:** paylaştırılan parçaların toplamı her zaman dağıtılan tutara
   birebir eşittir. Yuvarlama artığı son parçaya yazılır.
2. **Ağırlık yoksa eşit dağıtım:** tüm ağırlıklar sıfırsa tutar eşit bölünür
   (ör. desi bilgisi olmayan paket).
"""

from __future__ import annotations

from decimal import Decimal

from app.engine.vat import quantize_money


def allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Tutarı ağırlıklara göre paylaştırır; toplam korunur.

    Örnek: aynı pakette iki satır, desi ağırlıkları 3 ve 1 → kargo %75/%25 dağılır.
    """
    if not weights:
        return []
    if len(weights) == 1:
        return [quantize_money(total)]

    weight_sum = sum(weights, Decimal(0))
    if weight_sum <= 0:
        share = quantize_money(total / Decimal(len(weights)))
        parts = [share] * (len(weights) - 1)
        parts.append(quantize_money(total - share * (len(weights) - 1)))
        return parts

    parts = [quantize_money(total * weight / weight_sum) for weight in weights[:-1]]
    parts.append(quantize_money(total - sum(parts, Decimal(0))))
    return parts
