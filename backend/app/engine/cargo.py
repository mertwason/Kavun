"""Kargo tahmin motoru — desi bandı bazlı tarife çözümlemesi (spec §6.1, §10.7).

Spec §6.1 kargoyu `desi_bazli_tahmin(desi, carrier_tarife)` olarak tanımlıyor: tahmin
**tarife tablosundan** gelmeli. KVN-07'de tarife tablosu henüz yoktu ve tahmin iki sabite
gömülmüştü (taban + desi başı tutar); bu modül o sabitleri tek yerde tutarken gerçek
tarifeyi de çözer. DB'ye dokunmaz (CLAUDE.md §1) — bantları çağıran katman yükler.

## Çözümleme sırası

Bir gönderi için birden çok bant eşleşebilir. Sıra **daralttıkça öncelikli**:

1. **Firma eşleşmesi** — gönderinin kargo firmasına özel bant, "tüm firmalar" bandını yener.
2. **Yürürlük tarihi** — geçerli bantlar arasında en YENİ `valid_from` kazanır.
3. **Dar bant** — eşit koşulda üst sınırı olan bant, sınırsız banttan öncelikli.

Hiçbir bant eşleşmezse `None` döner; çağıran katman varsayılan formüle düşer. Sessizce
sıfır KARGO yazılmaz — kargosu sıfır sanılan sipariş, kârı olduğundan yüksek gösterir.

## Bant sınırları

`desi_min` **dahil**, `desi_max` **hariç** (yarı açık aralık). Bitişik bantlar
(0–1, 1–2, 2–5) böylece boşluk ve çakışma üretmez; 1,00 desi ikinci banda düşer.
`desi_max = None` üst sınırsız banttır ("10 desi ve üzeri").
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")

DEFAULT_BASE = Decimal("42.00")
"""Tarife tanımlı değilken taban ücret (KVN-06'dan devralınan varsayılan)."""

DEFAULT_PER_DESI = Decimal("18.50")
"""Tarife tanımlı değilken desi başına ücret."""


@dataclass(frozen=True)
class Band:
    """Tek bir tarife satırı: `[desi_min, desi_max)` aralığı için sabit ücret."""

    desi_min: Decimal
    desi_max: Decimal | None
    price: Decimal
    carrier: str | None = None
    """`None` = tüm kargo firmaları için geçerli."""

    valid_from: date | None = None
    """`None` = her zaman geçerli (tarih filtresi uygulanmaz)."""

    def covers(self, desi: Decimal) -> bool:
        """Desi bu banda düşüyor mu? Alt sınır dahil, üst sınır hariç."""
        if desi < self.desi_min:
            return False
        return self.desi_max is None or desi < self.desi_max


@dataclass(frozen=True)
class Estimate:
    """Tahmin sonucu — tutar ve nereden geldiği."""

    amount: Decimal
    source: str
    """`tarife` (bant eşleşti) veya `varsayilan` (formüle düşüldü)."""

    band: Band | None = None


def default_estimate(desi: Decimal | None) -> Decimal:
    """Tarife yokken kullanılan taban + desi formülü."""
    return (DEFAULT_BASE + (desi or ZERO) * DEFAULT_PER_DESI).quantize(Decimal("0.0001"))


def resolve_band(
    bands: Iterable[Band],
    *,
    desi: Decimal,
    carrier: str | None = None,
    on: date | None = None,
) -> Band | None:
    """Desi/firma/tarih için en spesifik bandı seçer; eşleşme yoksa `None`.

    Firma karşılaştırması büyük/küçük harf duyarsızdır: kanal "Yurtiçi Kargo" derken
    tarifeye "yurtiçi kargo" girilmiş olması eşleşmeyi bozmamalı.
    """
    normalised = carrier.strip().lower() if carrier else None
    candidates = [
        band
        for band in bands
        if band.covers(desi)
        and (band.valid_from is None or on is None or band.valid_from <= on)
        and (
            band.carrier is None
            or (normalised is not None and band.carrier.strip().lower() == normalised)
        )
    ]
    if not candidates:
        return None
    return max(candidates, key=_specificity)


def _specificity(band: Band) -> tuple[int, date, int]:
    """Sıralama anahtarı: firma eşleşmesi > yürürlük tarihi > dar bant."""
    return (
        1 if band.carrier is not None else 0,
        band.valid_from or date.min,
        1 if band.desi_max is not None else 0,
    )


def estimate(
    *,
    desi: Decimal | None,
    bands: Iterable[Band] = (),
    carrier: str | None = None,
    on: date | None = None,
) -> Estimate:
    """Gönderinin tahmini kargo maliyeti (spec §6.1).

    Desi bilinmiyorsa tarife uygulanamaz — bant aralıkları desiye dayanır — ve varsayılan
    formüle düşülür; formül desisiz gönderiye taban ücreti yazar.
    """
    if desi is not None:
        band = resolve_band(bands, desi=desi, carrier=carrier, on=on)
        if band is not None:
            return Estimate(
                amount=band.price.quantize(Decimal("0.0001")), source="tarife", band=band
            )
    return Estimate(amount=default_estimate(desi), source="varsayilan")
