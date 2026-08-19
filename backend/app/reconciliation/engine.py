"""Hakediş mutabakatı motoru — saf fonksiyonlar (spec §7).

Soru basit ama kritik: **platformun kestiği tutar ile bizim hesapladığımız tutar aynı mı?**
Değilse fark nerede? Bu modül o karşılaştırmayı yapar; DB'ye dokunmaz (CLAUDE.md §1).

## Kalem türü → beklenen değer

| `record_type`  | Beklenen kaynak                                   |
|----------------|---------------------------------------------------|
| `commission`   | motorun hesapladığı komisyon (`line_profit`)      |
| `cargo`        | gönderinin kesinleşmiş/tahmini kargo maliyeti     |
| `service_fee`  | mağazanın sipariş başına hizmet bedeli            |
| `sale`         | satır brüt cirosu                                  |
| `refund`       | iade tutarı                                        |
| `penalty`      | beklenen yok — ceza tanımı gereği sürprizdir       |

Platform kesintileri hakedişte **negatif** gelir (bizden alınan tutar). Karşılaştırma
mutlak değer üzerinden yapılır; işaret farkı fark sayılmaz, tutar farkı sayılır.

## Eşik

Varsayılan **0,05 TL** (spec §7.3). Altındaki sapmalar yuvarlama gürültüsüdür ve kayıt
üretmez; üstündekiler `reconciliation_diffs`'e düşer. Eşik mağaza bazında değil, tek
yerden gelir — "eşiği büyüterek farkı gizleme" kolaylığı bilinçli olarak verilmiyor.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import SettlementRecordType

ZERO = Decimal("0")
DEFAULT_TOLERANCE = Decimal("0.05")
"""Spec §7.3: |beklenen − gerçek| bu eşiği aşarsa fark kaydı üretilir."""


@dataclass(frozen=True)
class Expectation:
    """Bir hakediş kalemi için bizim beklediğimiz tutar."""

    record_type: SettlementRecordType
    expected: Decimal
    """Beklenen tutar — her zaman POZİTİF (mutlak) büyüklük."""

    source: str
    """Beklentinin nereden geldiği: `line_profit`, `shipment`, `store`…"""


@dataclass(frozen=True)
class Comparison:
    """Karşılaştırma sonucu."""

    expected: Decimal
    actual: Decimal
    diff: Decimal
    """`gerçek − beklenen`. Pozitif = platform bizden fazla kesmiş / fazla ödemiş."""

    within_tolerance: bool


def normalise(amount: Decimal) -> Decimal:
    """Hakediş tutarını karşılaştırılabilir hale getirir.

    Platform kesintileri negatif gelir (komisyon −48,00 gibi); bizim kalemlerimiz pozitif
    büyüklüktür. İşaret bilgisi kalem TÜRÜNDE zaten var, tutarda tekrar edilmesi
    karşılaştırmayı yanıltır — bu yüzden mutlak değer alınır.
    """
    return abs(amount)


def compare(
    *, expected: Decimal, actual: Decimal, tolerance: Decimal = DEFAULT_TOLERANCE
) -> Comparison:
    """Beklenen ile gerçeği karşılaştırır (spec §7.3)."""
    normalised = normalise(actual)
    diff = (normalised - expected).quantize(Decimal("0.0001"))
    return Comparison(
        expected=expected,
        actual=normalised,
        diff=diff,
        within_tolerance=abs(diff) <= tolerance,
    )


def is_explainable_without_order(record_type: SettlementRecordType) -> bool:
    """Siparişe bağlanamayan kalem türü beklenen değer üretebilir mi?

    Ceza/tazmin ve reklam harcaması tanımı gereği siparişten türetilemez: onlar için
    "beklenen" yoktur, kalem doğrudan mağaza gideri sayılır (spec §6.3.7). Diğer türlerde
    sipariş eşleşmesi yoksa fark kaydı açılır — sessiz geçilmez.
    """
    return record_type in (SettlementRecordType.PENALTY, SettlementRecordType.AD_SPEND)
