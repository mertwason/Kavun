"""Ağırlıklı ortalama maliyet (WAC) — bağlayıcı formül (spec §12C.1).

Saf fonksiyon: girdi → çıktı, DB yok (CLAUDE.md §1).

    yeni_ortalama = (eldeki_adet × mevcut_ortalama + gelen_adet × gelen_birim_maliyet)
                    ───────────────────────────────────────────────────────────────────
                                  (eldeki_adet + gelen_adet)

Kurallar (spec §12C.1):
- **Yalnızca girişler** ortalamayı günceller (alış faturası, iade-kabul kendi maliyetiyle,
  sayım fazlası).
- Çıkışlar (satış, fire, iade-red) stoku düşürür, **ortalamayı DEĞİŞTİRMEZ** — mevcut
  ortalamadan çıkarlar.
- Negatif stokta ortalama değişmez; ilk alış girişinde normalleşir (§12C.4).
- Ortalama `NUMERIC(14,6)` hassasiyetle saklanır; yuvarlama birikimini önlemek için ara
  hesaplar tam `Decimal` yapılır, yalnızca sonuç kuantize edilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")
AVG_COST_PRECISION = Decimal("0.000001")
"""`sku_cost_state.avg_cost` ve `inventory_ledger.avg_cost_after` ile aynı hassasiyet."""


def quantize_avg_cost(value: Decimal) -> Decimal:
    """Ortalama maliyeti 6 haneye yuvarlar (DB kolonuyla aynı hassasiyet)."""
    return value.quantize(AVG_COST_PRECISION)


@dataclass(frozen=True)
class StockState:
    """Bir ürünün stok durumu."""

    on_hand: Decimal
    avg_cost: Decimal

    @classmethod
    def empty(cls) -> StockState:
        """Hiç hareket görmemiş ürün."""
        return cls(on_hand=ZERO, avg_cost=ZERO)


def apply_inbound(state: StockState, *, qty: Decimal, unit_cost: Decimal) -> StockState:
    """Giriş hareketi: stok artar, ortalama maliyet yeniden hesaplanır (spec §12C.1)."""
    if qty <= ZERO:
        return state

    new_on_hand = state.on_hand + qty
    if new_on_hand <= ZERO:
        # Negatif stok bir girişle bile kapanmadıysa ortalama anlamsızlaşır; girişin
        # kendi maliyeti taşınır (ilk pozitif bakiyede normalleşir — spec §12C.4).
        return StockState(on_hand=new_on_hand, avg_cost=quantize_avg_cost(unit_cost))

    if state.on_hand <= ZERO:
        # Negatif ya da sıfır stoktan gelen girişte eski ortalama taşınmaz.
        return StockState(on_hand=new_on_hand, avg_cost=quantize_avg_cost(unit_cost))

    total_value = state.on_hand * state.avg_cost + qty * unit_cost
    return StockState(on_hand=new_on_hand, avg_cost=quantize_avg_cost(total_value / new_on_hand))


def apply_outbound(state: StockState, *, qty: Decimal) -> StockState:
    """Çıkış hareketi: stok düşer, **ortalama maliyet değişmez** (spec §12C.1)."""
    if qty <= ZERO:
        return state
    return StockState(on_hand=state.on_hand - qty, avg_cost=state.avg_cost)


def allocate_landed_cost(line_amounts: list[Decimal], extra: Decimal) -> list[Decimal]:
    """Navlun/gümrük/sigorta toplamını satırlara **tutar ağırlıklı** dağıtır (§12C.2).

    Paylaştırma `engine/allocation.py` ile aynı disipline uyar: artık kuruş son parçaya
    eklenir, parçaların toplamı her zaman dağıtılan tutara eşittir.
    """
    from app.engine.allocation import allocate

    return allocate(extra, line_amounts)
