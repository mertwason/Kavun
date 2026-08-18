"""Trendyol adapter (spec §4, Faz 1).

Tüm uç noktalar ve alan adları developers.trendyol.com'dan **doğrulandı** (2026-08-18);
tahmin edilen alan yoktur. Doğrulanamayan noktalar `TODO(verify)` ile işaretlidir.

| Ne | Uç | Not |
|---|---|---|
| Siparişler | `GET /order/sellers/{sellerId}/orders` | page 0-tabanlı, `size` max 200, tarih aralığı max 2 hafta, 3 ay geriye |
| Ürünler (onaylı) | `GET /product/sellers/{sellerId}/products/approved` | V2; `size` max 100, 10.000 üstü için `nextPageToken` |
| Hakediş | `GET /finance/che/sellers/{sellerId}/settlements` | Faz 2; `commissionRate`/`commissionAmount` burada |

Kimlik doğrulama: HTTP Basic (API Key : API Secret) + `User-Agent: {SellerID} - SelfIntegration`
(User-Agent olmadan 403). Hız sınırı: dakikada 1.000 istek (sipariş servisi).

**Komisyon oranları:** Trendyol'un pazaryeri API'sinde ürün/kategori komisyon oranı
döndüren bir servis YOKTUR (doküman indeksinde böyle bir uç bulunmuyor; oranlar Satıcı
Yardım Merkezi'nde dönemsel tablo olarak yayımlanır). Bu yüzden `fetch_commission_rates`
boş liste döner ve komisyon iki gerçek kaynaktan çözülür:
`settlement_actual` (hakediş, Faz 2) ve tarife Excel yüklemesi (KVN-14, spec §12B.2).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.connectors.base import (
    MarketplaceConnector,
    RawCargoInvoice,
    RawCommission,
    RawOrder,
    RawOrderLine,
    RawProduct,
    RawReturn,
    RawSettlementRow,
)
from app.connectors.http import ApiClient
from app.core.logging import get_logger
from app.models.enums import OrderStatus

log = get_logger("connectors.trendyol")

PRODUCTION_BASE_URL = "https://apigw.trendyol.com/integration"
STAGE_BASE_URL = "https://stageapigw.trendyol.com/integration"

# Doğrulanmış limitler.
ORDER_PAGE_SIZE = 200  # servis üst sınırı
ORDER_WINDOW_DAYS = 14  # startDate–endDate arası en fazla iki hafta
PRODUCT_PAGE_SIZE = 100  # onaylı ürün servisinin üst sınırı
REQUESTS_PER_MINUTE = 600  # dokümandaki 1.000/dk sınırının altında güvenli pas

DEFAULT_STOREFRONT_CODE = "TR"

# Trendyol paket/satır statüleri → içeri normalize enum (spec §4).
STATUS_MAP: dict[str, OrderStatus] = {
    "Awaiting": OrderStatus.CREATED,
    "Created": OrderStatus.CREATED,
    "Picking": OrderStatus.PICKING,
    "Invoiced": OrderStatus.PICKING,
    "Shipped": OrderStatus.SHIPPED,
    "AtCollectionPoint": OrderStatus.SHIPPED,
    "Delivered": OrderStatus.DELIVERED,
    "UnDelivered": OrderStatus.SHIPPED,
    "Cancelled": OrderStatus.CANCELLED,
    "UnSupplied": OrderStatus.CANCELLED,
    "Returned": OrderStatus.RETURNED,
}


def normalize_status(raw_status: str | None) -> OrderStatus:
    """Kanal statüsünü içeri enum'a çevirir; bilinmeyen statü `created` sayılır."""
    if raw_status and raw_status in STATUS_MAP:
        return STATUS_MAP[raw_status]
    if raw_status:
        log.warning("trendyol.unknown_status", status=raw_status)
    return OrderStatus.CREATED


def to_millis(moment: datetime) -> int:
    """Zamanı Unix milisaniyeye çevirir (servis `int64` bekler)."""
    return int(moment.timestamp() * 1000)


def from_millis(value: Any) -> datetime:
    """Unix milisaniyeyi UTC zamana çevirir."""
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """JSON alanını `Decimal`e çevirir (para asla float'a düşmez)."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def date_windows(
    since: datetime, until: datetime, *, days: int = ORDER_WINDOW_DAYS
) -> Iterator[tuple[datetime, datetime]]:
    """Aralığı servis sınırına uyan pencerelere böler (en fazla iki hafta)."""
    if until <= since:
        return
    cursor = since
    step = timedelta(days=days)
    while cursor < until:
        window_end = min(cursor + step, until)
        yield cursor, window_end
        cursor = window_end


class TrendyolConnector(MarketplaceConnector):
    """Trendyol pazaryeri adapter'i."""

    channel_code = "trendyol"

    def __init__(
        self,
        seller_id: str,
        api_key: str,
        api_secret: str,
        *,
        base_url: str = PRODUCTION_BASE_URL,
        storefront_code: str = DEFAULT_STOREFRONT_CODE,
        integration_name: str = "SelfIntegration",
        client: ApiClient | None = None,
    ) -> None:
        self.seller_id = seller_id
        self._client = client or ApiClient(
            base_url,
            headers={
                # User-Agent zorunlu; eksikse servis 403 döner.
                "User-Agent": f"{seller_id} - {integration_name}",
                "storeFrontCode": storefront_code,
                "Accept": "application/json",
            },
            auth=(api_key, api_secret),
            requests_per_minute=REQUESTS_PER_MINUTE,
        )

    async def aclose(self) -> None:
        """Bağlantıları kapatır."""
        await self._client.aclose()

    # --- siparişler ---------------------------------------------------------

    async def fetch_orders(self, since: datetime, until: datetime) -> list[RawOrder]:
        """Sipariş paketlerini çeker; tüm sayfalar ve tarih pencereleri tüketilir."""
        orders: list[RawOrder] = []
        for window_start, window_end in date_windows(since, until):
            page = 0
            while True:
                body = await self._client.get_json(
                    f"/order/sellers/{self.seller_id}/orders",
                    params={
                        "startDate": to_millis(window_start),
                        "endDate": to_millis(window_end),
                        "page": page,
                        "size": ORDER_PAGE_SIZE,
                        "orderByField": "PackageLastModifiedDate",
                        "orderByDirection": "ASC",
                    },
                )
                content = body.get("content") or []
                orders.extend(parse_order(item) for item in content)

                total_pages = int(body.get("totalPages") or 0)
                page += 1
                if page >= total_pages or not content:
                    break

        log.info(
            "trendyol.orders.fetched",
            seller_id=self.seller_id,
            count=len(orders),
            since=since.isoformat(),
            until=until.isoformat(),
        )
        return orders

    # --- ürünler ------------------------------------------------------------

    async def fetch_products(self) -> list[RawProduct]:
        """Onaylı ürünleri çeker (V2). 10.000 üstünde `nextPageToken` ile devam eder."""
        products: list[RawProduct] = []
        page = 0
        next_page_token: str | None = None

        while True:
            params: dict[str, Any] = {"size": PRODUCT_PAGE_SIZE}
            if next_page_token:
                params["nextPageToken"] = next_page_token
            else:
                params["page"] = page

            body = await self._client.get_json(
                f"/product/sellers/{self.seller_id}/products/approved", params=params
            )
            content = body.get("content") or []
            for item in content:
                products.extend(parse_product(item))

            next_page_token = body.get("nextPageToken") or None
            total_pages = int(body.get("totalPages") or 0)
            page += 1
            if not content or (not next_page_token and page >= total_pages):
                break

        log.info("trendyol.products.fetched", seller_id=self.seller_id, count=len(products))
        return products

    # --- komisyon -----------------------------------------------------------

    async def fetch_commission_rates(self) -> list[RawCommission]:
        """Trendyol'da komisyon oranı servisi yoktur — boş liste döner.

        Oranlar tarife Excel yüklemesiyle (KVN-14) girilir ve hakedişten
        (`settlement_actual`, Faz 2) kesinleşir. Bkz. modül docstring'i.
        """
        log.info("trendyol.commissions.unavailable", seller_id=self.seller_id)
        return []

    # --- Faz 2 uçları -------------------------------------------------------

    async def fetch_returns(self, since: datetime) -> list[RawReturn]:
        """İade/talep servisi — Faz 2 (`/order/sellers/{sellerId}/claims`)."""
        raise NotImplementedError("İade senkronu Faz 2 kapsamında (spec §11)")

    async def fetch_settlements(self, since: datetime) -> list[RawSettlementRow]:
        """Hakediş — Faz 2: `GET /finance/che/sellers/{sellerId}/settlements`.

        Doğrulanmış kısıtlar: `transactionType` (Sale|Return) zorunlu, tarih aralığı
        en fazla 15 gün, `size` yalnızca 500 veya 1000.
        """
        raise NotImplementedError("Hakediş senkronu Faz 2 kapsamında (spec §7)")

    async def fetch_cargo_invoices(self, since: datetime) -> list[RawCargoInvoice]:
        """Kargo faturaları — Faz 2."""
        raise NotImplementedError("Kargo faturası senkronu Faz 2 kapsamında (spec §11)")


# --- ayrıştırıcılar (saf fonksiyonlar, HTTP'den bağımsız test edilir) --------


def parse_order_line(raw: dict[str, Any], *, package_status: OrderStatus) -> RawOrderLine:
    """Sipariş satırını normalize eder.

    Alan adları doğrulandı: `id`, `barcode`, `merchantSku`, `productName`, `quantity`,
    `price`, `amount`, `discount`, `vatBaseAmount`, `orderLineItemStatusName`.
    """
    quantity = int(raw.get("quantity") or 0)
    unit_price = _decimal(raw.get("price"))
    amount = _decimal(raw.get("amount"), unit_price * quantity)
    status_name = raw.get("orderLineItemStatusName")
    return RawOrderLine(
        external_line_id=str(raw.get("id")),
        barcode=raw.get("barcode"),
        seller_sku=raw.get("merchantSku") or raw.get("sku"),
        product_name=str(raw.get("productName") or ""),
        quantity=quantity,
        unit_price=unit_price,
        line_amount=amount,
        discount=_decimal(raw.get("discount")),
        # `vatBaseAmount` KDV oranıdır (ör. 20), tutar değil — TODO(verify): dokümanda
        # birim açıkça yazılmıyor; hakediş mutabakatında (Faz 2) doğrulanacak.
        vat_base_amount=_decimal(raw.get("vatBaseAmount"), Decimal("0")) or None,
        status=normalize_status(status_name) if status_name else package_status,
        currency=str(raw.get("currencyCode") or "TRY"),
    )


def parse_order(raw: dict[str, Any]) -> RawOrder:
    """Sipariş paketini normalize eder.

    Alan adları doğrulandı: `orderNumber`, `orderDate`, `status`, `grossAmount`,
    `totalPrice`, `shipmentAddress.city`, `cargoProviderName`, `deci`, `lines`.
    """
    status = normalize_status(raw.get("status") or raw.get("shipmentPackageStatus"))
    shipment_address = raw.get("shipmentAddress") or {}
    order_date_raw = raw.get("orderDate") or raw.get("packageCreationDate")

    return RawOrder(
        external_order_id=str(raw.get("orderNumber") or raw.get("id")),
        order_date=from_millis(order_date_raw) if order_date_raw else datetime.now(UTC),
        status=status,
        gross_total=_decimal(raw.get("totalPrice"), _decimal(raw.get("grossAmount"))),
        currency=str(raw.get("currencyCode") or "TRY"),
        customer_city=shipment_address.get("city"),
        cargo_provider=raw.get("cargoProviderName"),
        desi=_decimal(raw.get("deci")) or None,
        lines=tuple(
            parse_order_line(line, package_status=status) for line in raw.get("lines") or []
        ),
        payload=raw,
    )


def parse_product(raw: dict[str, Any]) -> list[RawProduct]:
    """Onaylı ürün kaydını varyant bazında normalize eder (V2 yanıtı).

    V2 `approved` yanıtında ürün başlığı ve kategori üst seviyede, barkod/stok/fiyat
    `variants` dizisindedir. KDV oranı ve desi bu yanıtta YOKTUR — TODO(verify): bu iki
    alan onaysız ürün filtresinde (`vatRate`, `dimensionalWeight`) mevcut; Faz 1'de
    fiyat listesi Excel'inden (KVN-10) beslenecek.
    """
    category = (raw.get("category") or {}).get("name")
    brand = (raw.get("brand") or {}).get("name")
    title = str(raw.get("title") or "")
    product_main_id = str(raw.get("productMainId") or raw.get("contentId") or "")

    variants = raw.get("variants") or []
    if not variants:
        return [
            RawProduct(
                external_product_id=product_main_id,
                barcode=raw.get("barcode"),
                seller_sku=raw.get("stockCode"),
                name=title,
                category=category,
                brand=brand,
                sale_price=_decimal(raw.get("salePrice")) or None,
                list_price=_decimal(raw.get("listPrice")) or None,
                stock=int(raw["quantity"]) if raw.get("quantity") is not None else None,
                vat_rate=_decimal(raw.get("vatRate")) or None,
                desi=_decimal(raw.get("dimensionalWeight")) or None,
                payload=raw,
            )
        ]

    return [
        RawProduct(
            external_product_id=str(variant.get("variantId") or product_main_id),
            barcode=variant.get("barcode"),
            seller_sku=variant.get("stockCode"),
            name=title,
            category=category,
            brand=brand,
            sale_price=_decimal(variant.get("price")) or None,
            list_price=_decimal(variant.get("listPrice")) or None,
            stock=int(variant["stock"]) if variant.get("stock") is not None else None,
            vat_rate=_decimal(variant.get("vatRate")) or None,
            desi=_decimal(variant.get("dimensionalWeight")) or None,
            payload={**raw, "variant": variant},
        )
        for variant in variants
    ]
