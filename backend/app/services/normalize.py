"""Normalize pipeline: `raw_events` → domain tabloları (spec §3.2, §5.3).

Bağlayıcı kural: ham veri değişmez, normalize tablolar ondan **yeniden üretilebilir**.
Bu modül tek yönlü çalışır (raw → domain) ve iki modu vardır:

- `normalize_pending`: işlenmemiş olayları işler, `processed_at` damgalar (sync sonrası zincir)
- `replay`: verilen aralıktaki normalize veriyi silip ham olaylardan yeniden kurar

Idempotency: sipariş `(tenant_id, store_id, external_order_id)`, satır
`(order_id, external_line_id)`, ürün eşlemesi `(store_id, external_product_id)` üzerinden
upsert edilir. Aynı olayın iki kez işlenmesi kopya üretmez.

Kâr hesabı burada YAPILMAZ: `line_profit` motorun çıktısıdır (KVN-07). Replay sonrası
etkilenen satırların kâr kaydı silinir, motor yeniden hesaplar.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.connectors import trendyol
from app.connectors.base import RawOrder, RawProduct
from app.core.context import system_scope
from app.core.logging import get_logger
from app.models.catalog import Product, ProductChannelMap
from app.models.enums import ChannelCode, CostState, OrderStatus
from app.models.identity import Channel, Store
from app.models.results import LineProfit
from app.models.transactions import Order, OrderLine, RawEvent, Shipment

log = get_logger("services.normalize")

DEFAULT_VAT_RATE = Decimal("20.00")
SHIPPED_STATUSES = frozenset({OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.RETURNED})

# Kargo tahmini: desi bazlı basit tarife. Gerçek tarife tablosu KVN-07'de motorun
# girdisi olacak; burada yalnızca `cargo_cost_estimated` alanı doldurulur.
CARGO_BASE = Decimal("42.00")
CARGO_PER_DESI = Decimal("18.50")


@dataclass
class NormalizeSummary:
    """Normalize sonucu — job sonunda özet metrik loglanır."""

    processed_events: int = 0
    orders_created: int = 0
    orders_updated: int = 0
    lines_written: int = 0
    products_matched: int = 0
    products_unmatched: int = 0
    skipped: dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        """Atlanan olayı sayar."""
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        """Log/JSON dostu özet."""
        return {
            "processed_events": self.processed_events,
            "orders_created": self.orders_created,
            "orders_updated": self.orders_updated,
            "lines_written": self.lines_written,
            "products_matched": self.products_matched,
            "products_unmatched": self.products_unmatched,
            "skipped": self.skipped,
        }


def estimate_cargo(desi: Decimal | None) -> Decimal:
    """Desi bazlı kargo tahmini (spec §6.1: `desi_bazli_tahmin`)."""
    return (CARGO_BASE + (desi or Decimal("0")) * CARGO_PER_DESI).quantize(Decimal("0.0001"))


def _channel_code(session: Session, store: Store) -> ChannelCode:
    code = session.scalar(select(Channel.code).where(Channel.id == store.channel_id))
    if code is None:  # pragma: no cover - kanal FK'si garanti eder
        raise LookupError(f"Mağazanın kanalı yok: {store.id}")
    return code


def _parse_event(channel: ChannelCode, event: RawEvent) -> RawOrder | list[RawProduct] | None:
    """Ham olayı kanalın ayrıştırıcısıyla çözer."""
    if channel is not ChannelCode.TRENDYOL:
        return None
    if event.event_type == "order":
        return trendyol.parse_order(event.payload)
    if event.event_type == "product":
        return trendyol.parse_product(event.payload)
    return None


def _find_product(
    session: Session, store: Store, *, barcode: str | None, seller_sku: str | None
) -> Product | None:
    """Satırı ürüne bağlar: önce kanal eşlemesi, sonra barkod, sonra SKU."""
    if barcode:
        mapped = session.scalar(
            select(Product)
            .join(ProductChannelMap, ProductChannelMap.product_id == Product.id)
            .where(
                ProductChannelMap.store_id == store.id,
                ProductChannelMap.external_barcode == barcode,
            )
        )
        if mapped is not None:
            return mapped
        by_barcode = session.scalar(
            select(Product).where(
                Product.tenant_id == store.tenant_id,
                Product.brand_id == store.brand_id,
                Product.barcode == barcode,
            )
        )
        if by_barcode is not None:
            return by_barcode
    if seller_sku:
        return session.scalar(
            select(Product).where(
                Product.tenant_id == store.tenant_id,
                Product.brand_id == store.brand_id,
                Product.sku == seller_sku,
            )
        )
    return None


def apply_order(
    session: Session, store: Store, raw_order: RawOrder, summary: NormalizeSummary
) -> Order:
    """Ham siparişi domain tablolarına yazar (upsert)."""
    order = session.scalar(
        select(Order).where(
            Order.tenant_id == store.tenant_id,
            Order.store_id == store.id,
            Order.external_order_id == raw_order.external_order_id,
        )
    )
    if order is None:
        order = Order(
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            store_id=store.id,
            external_order_id=raw_order.external_order_id,
            order_date=raw_order.order_date,
            status=raw_order.status,
            customer_city=raw_order.customer_city,
            gross_total=raw_order.gross_total,
            currency=raw_order.currency,
        )
        session.add(order)
        session.flush()
        summary.orders_created += 1
    else:
        order.status = raw_order.status
        order.gross_total = raw_order.gross_total
        order.customer_city = raw_order.customer_city
        order.order_date = raw_order.order_date
        summary.orders_updated += 1

    for raw_line in raw_order.lines:
        product = _find_product(
            session, store, barcode=raw_line.barcode, seller_sku=raw_line.seller_sku
        )
        if product is None:
            summary.products_unmatched += 1
        else:
            summary.products_matched += 1

        line = session.scalar(
            select(OrderLine).where(
                OrderLine.order_id == order.id,
                OrderLine.external_line_id == raw_line.external_line_id,
            )
        )
        vat_rate = (
            product.vat_rate
            if product is not None
            else (raw_line.vat_base_amount or DEFAULT_VAT_RATE)
        )
        if line is None:
            line = OrderLine(
                tenant_id=store.tenant_id,
                brand_id=store.brand_id,
                order_id=order.id,
                product_id=product.id if product else None,
                external_line_id=raw_line.external_line_id,
                qty=raw_line.quantity,
                unit_sale_price=raw_line.unit_price,
                line_gross=raw_line.line_amount,
                vat_rate=vat_rate,
                status=raw_line.status,
            )
            session.add(line)
        else:
            line.qty = raw_line.quantity
            line.unit_sale_price = raw_line.unit_price
            line.line_gross = raw_line.line_amount
            line.vat_rate = vat_rate
            line.status = raw_line.status
            line.product_id = product.id if product else line.product_id
        summary.lines_written += 1

    _apply_shipment(session, store, order, raw_order)
    session.flush()
    return order


def _apply_shipment(
    session: Session, store: Store, order: Order, raw_order: RawOrder
) -> Shipment | None:
    """Kargolanmış siparişler için gönderi kaydı (tahmini maliyetle)."""
    if raw_order.status not in SHIPPED_STATUSES:
        return None

    shipment = session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    estimated = estimate_cargo(raw_order.desi)
    if shipment is None:
        shipment = Shipment(
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            order_id=order.id,
            carrier=raw_order.cargo_provider,
            desi_declared=raw_order.desi,
            cargo_cost_estimated=estimated,
            cost_state=CostState.ESTIMATED,
        )
        session.add(shipment)
    elif shipment.cost_state is CostState.ESTIMATED:
        # Kesinleşmiş (actual) maliyet ASLA ezilmez — yalnızca tahmin güncellenir.
        shipment.carrier = raw_order.cargo_provider
        shipment.desi_declared = raw_order.desi
        shipment.cargo_cost_estimated = estimated
    return shipment


def apply_products(
    session: Session, store: Store, raw_products: list[RawProduct], summary: NormalizeSummary
) -> None:
    """Kanal ürünlerini mevcut ürünlerle eşler; eşleşme haritasını günceller.

    Ürün KAYDI OLUŞTURMAZ: katalog Kavun'un doğruluk kaynağıdır ve fiyat listesi
    Excel'inden yönetilir (KVN-10). Burada yalnızca kanal eşlemesi kurulur.
    """
    for raw_product in raw_products:
        product = _find_product(
            session, store, barcode=raw_product.barcode, seller_sku=raw_product.seller_sku
        )
        if product is None:
            summary.products_unmatched += 1
            continue

        summary.products_matched += 1
        mapping = session.scalar(
            select(ProductChannelMap).where(
                ProductChannelMap.store_id == store.id,
                ProductChannelMap.external_product_id == raw_product.external_product_id,
            )
        )
        if mapping is None:
            session.add(
                ProductChannelMap(
                    product_id=product.id,
                    store_id=store.id,
                    external_product_id=raw_product.external_product_id,
                    external_barcode=raw_product.barcode,
                )
            )
        else:
            mapping.product_id = product.id
            mapping.external_barcode = raw_product.barcode
    session.flush()


def normalize_events(
    session: Session, events: list[RawEvent], *, mark_processed: bool = True
) -> NormalizeSummary:
    """Verilen ham olayları domain tablolarına uygular."""
    summary = NormalizeSummary()
    store_cache: dict[uuid.UUID, tuple[Store, ChannelCode]] = {}

    for event in sorted(events, key=lambda item: (item.fetched_at, item.id)):
        cached = store_cache.get(event.store_id)
        if cached is None:
            store = session.get(Store, event.store_id)
            if store is None:
                summary.skip("store_not_found")
                continue
            cached = (store, _channel_code(session, store))
            store_cache[event.store_id] = cached
        store, channel = cached

        parsed = _parse_event(channel, event)
        if parsed is None:
            summary.skip(f"unsupported:{event.event_type}")
            continue

        if isinstance(parsed, RawOrder):
            apply_order(session, store, parsed, summary)
        else:
            apply_products(session, store, parsed, summary)

        summary.processed_events += 1
        if mark_processed:
            event.processed_at = datetime.now(UTC)

    session.flush()
    return summary


def normalize_pending(
    session: Session, *, store_id: uuid.UUID | None = None, limit: int = 5000
) -> NormalizeSummary:
    """İşlenmemiş ham olayları normalize eder (sync sonrası zincir)."""
    with system_scope():
        statement = (
            select(RawEvent)
            .where(RawEvent.processed_at.is_(None))
            .order_by(RawEvent.fetched_at, RawEvent.id)
            .limit(limit)
        )
        if store_id is not None:
            statement = statement.where(RawEvent.store_id == store_id)
        events = list(session.scalars(statement).all())
        summary = normalize_events(session, events)
        session.commit()

    log.info("normalize.completed", **summary.as_dict())
    return summary


def replay(
    session: Session,
    *,
    channel: ChannelCode | None = None,
    store_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    dry_run: bool = False,
) -> NormalizeSummary:
    """Normalize veriyi silip ham olaylardan yeniden kurar (spec §3.2).

    `dry_run=True` yalnızca kaç olayın işleneceğini söyler, hiçbir şey yazmaz.
    """
    with system_scope():
        event_query = select(RawEvent).order_by(RawEvent.fetched_at, RawEvent.id)
        if since is not None:
            event_query = event_query.where(RawEvent.fetched_at >= since)
        if until is not None:
            event_query = event_query.where(RawEvent.fetched_at < until)

        store_ids: list[uuid.UUID]
        if store_id is not None:
            store_ids = [store_id]
        elif channel is not None:
            channel_id = session.scalar(select(Channel.id).where(Channel.code == channel))
            store_ids = list(
                session.scalars(select(Store.id).where(Store.channel_id == channel_id)).all()
            )
        else:
            store_ids = list(session.scalars(select(Store.id)).all())

        event_query = event_query.where(RawEvent.store_id.in_(store_ids))
        events = list(session.scalars(event_query).all())

        if dry_run:
            summary = NormalizeSummary(processed_events=len(events))
            log.info("replay.dry_run", **summary.as_dict())
            return summary

        _purge_normalized(session, store_ids, since=since, until=until)
        summary = normalize_events(session, events, mark_processed=True)
        session.commit()

    log.info(
        "replay.completed",
        stores=len(store_ids),
        channel=channel.value if channel else None,
        **summary.as_dict(),
    )
    return summary


def _purge_normalized(
    session: Session,
    store_ids: list[uuid.UUID],
    *,
    since: datetime | None,
    until: datetime | None,
) -> None:
    """Yeniden kurulacak aralıktaki normalize kayıtları siler.

    Ham veriye DOKUNULMAZ. Kâr kayıtları da silinir; motor yeniden hesaplar (KVN-07).
    """
    order_query = select(Order.id).where(Order.store_id.in_(store_ids))
    if since is not None:
        order_query = order_query.where(Order.order_date >= since)
    if until is not None:
        order_query = order_query.where(Order.order_date < until)
    order_ids = list(session.scalars(order_query).all())

    if order_ids:
        line_ids = list(
            session.scalars(select(OrderLine.id).where(OrderLine.order_id.in_(order_ids))).all()
        )
        if line_ids:
            session.execute(delete(LineProfit).where(LineProfit.order_line_id.in_(line_ids)))
        session.execute(delete(Shipment).where(Shipment.order_id.in_(order_ids)))
        session.execute(delete(OrderLine).where(OrderLine.order_id.in_(order_ids)))
        session.execute(delete(Order).where(Order.id.in_(order_ids)))

    # İşlenmiş damgası sıfırlanır: olaylar yeniden işlenecek.
    reset = update(RawEvent).where(RawEvent.store_id.in_(store_ids)).values(processed_at=None)
    if since is not None:
        reset = reset.where(RawEvent.fetched_at >= since)
    if until is not None:
        reset = reset.where(RawEvent.fetched_at < until)
    session.execute(reset)
    session.flush()
