"""Connector arayüzü — yeni kanal = yeni adapter, motor koduna dokunulmaz (spec §4).

Adapter'ler kanalın ham yanıtını **olduğu gibi** taşır: `Raw*` nesneleri hem normalize
edilmiş alanları hem de `payload` içinde orijinal JSON'ı tutar. `raw_events`'e yazılan
şey bu payload'dır; normalize tablolar ondan üretilir ve `replay` ile yeniden kurulabilir
(spec §3.2, KVN-06).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.models.enums import OrderStatus


class ConnectorError(RuntimeError):
    """Kanal entegrasyonunda kurtarılamayan hata."""


class AuthenticationError(ConnectorError):
    """Credential geçersiz (401/403). Credential içeriği ASLA mesaja konmaz."""


class RateLimitError(ConnectorError):
    """Kanal hız sınırı aşıldı ve tüm denemeler tükendi."""


@dataclass(frozen=True)
class RawOrderLine:
    """Ham sipariş satırı."""

    external_line_id: str
    barcode: str | None
    seller_sku: str | None
    product_name: str
    quantity: int
    unit_price: Decimal
    line_amount: Decimal
    discount: Decimal
    vat_base_amount: Decimal | None
    status: OrderStatus
    currency: str = "TRY"


@dataclass(frozen=True)
class RawOrder:
    """Ham sipariş paketi."""

    external_order_id: str
    order_date: datetime
    status: OrderStatus
    gross_total: Decimal
    currency: str
    customer_city: str | None
    cargo_provider: str | None
    desi: Decimal | None
    lines: tuple[RawOrderLine, ...]
    cargo_tracking_no: str | None = None
    """Gönderi takip numarası — kargo faturası eşleştirmesinin birincil anahtarı."""

    payload: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass(frozen=True)
class RawProduct:
    """Ham ürün/varyant."""

    external_product_id: str
    barcode: str | None
    seller_sku: str | None
    name: str
    category: str | None
    brand: str | None
    sale_price: Decimal | None
    list_price: Decimal | None
    stock: int | None
    vat_rate: Decimal | None
    desi: Decimal | None
    payload: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass(frozen=True)
class RawCommission:
    """Ham komisyon oranı (kategori ya da ürün bazlı)."""

    category_code: str | None
    external_product_id: str | None
    rate: Decimal
    source: str
    payload: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass(frozen=True)
class RawReturnLine:
    """İade edilen tek satır — hangi sipariş satırı, kaç adet, ne kadar geri ödendi."""

    external_line_id: str
    """Sipariş satırının kanal id'si (`orderLineItemId`) — iadeyi satıra bağlar."""

    barcode: str | None
    seller_sku: str | None
    quantity: int
    refund_amount: Decimal
    reason: str | None
    accepted: bool
    """Kabul edilmemiş talep iade sayılmaz; kâr etkisi ancak kabulle doğar."""


@dataclass(frozen=True)
class RawReturn:
    """Ham iade kaydı (Faz 2)."""

    external_return_id: str
    external_order_id: str
    return_date: datetime
    lines: tuple[RawReturnLine, ...] = ()
    cargo_tracking_no: str | None = None
    payload: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass(frozen=True)
class RawSettlementRow:
    """Ham hakediş satırı (Faz 2) — komisyonun ground truth'u."""

    external_ref: str
    transaction_date: datetime
    record_type: str
    amount: Decimal
    commission_rate: Decimal | None
    external_order_id: str | None
    payload: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass(frozen=True)
class RawCargoInvoiceLine:
    """Kargo faturasının tek kalemi: hangi gönderi, ne kadar, kaç desi."""

    parcel_id: str | None
    external_order_id: str | None
    amount: Decimal
    desi: Decimal | None


@dataclass(frozen=True)
class RawCargoInvoice:
    """Ham kargo faturası (Faz 2)."""

    invoice_no: str
    period: str
    total: Decimal
    lines: tuple[RawCargoInvoiceLine, ...] = ()
    payload: dict[str, Any] = field(repr=False, default_factory=dict)


class MarketplaceConnector(ABC):
    """Tüm kanal adapter'lerinin ortak arayüzü (spec §4)."""

    channel_code: str

    @abstractmethod
    async def fetch_orders(self, since: datetime, until: datetime) -> list[RawOrder]:
        """Verilen aralıktaki siparişleri döndürür."""

    @abstractmethod
    async def fetch_products(self) -> list[RawProduct]:
        """Satıcının ürün listesini döndürür."""

    @abstractmethod
    async def fetch_commission_rates(self) -> list[RawCommission]:
        """Komisyon oranlarını döndürür (kanalda servis yoksa boş liste)."""

    @abstractmethod
    async def fetch_returns(self, since: datetime) -> list[RawReturn]:
        """İade/talep kayıtları (Faz 2)."""

    @abstractmethod
    async def fetch_settlements(self, since: datetime) -> list[RawSettlementRow]:
        """Hakediş kalemleri (Faz 2)."""

    @abstractmethod
    async def fetch_cargo_invoices(self, since: datetime) -> list[RawCargoInvoice]:
        """Kargo fatura kalemleri (Faz 2)."""
