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
from app.connectors.base import (
    RawCargoInvoice,
    RawCargoInvoiceLine,
    RawOrder,
    RawProduct,
    RawReturn,
    RawReturnLine,
    RawSettlementRow,
)
from app.core.context import system_scope
from app.core.logging import get_logger
from app.engine import cargo as cargo_engine
from app.models.catalog import Product, ProductChannelMap
from app.models.enums import ChannelCode, CostState, OrderStatus, SettlementRecordType
from app.models.identity import Channel, Store
from app.models.results import LineProfit
from app.models.transactions import (
    CargoInvoice,
    Order,
    OrderLine,
    RawEvent,
    Return,
    SettlementRecord,
    Shipment,
)
from app.services import cargo_tariffs

log = get_logger("services.normalize")

DEFAULT_VAT_RATE = Decimal("20.00")
SHIPPED_STATUSES = frozenset({OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.RETURNED})

# Kargo tahmini artık tarife tablosundan çözülür (KVN-EK-04); tarife tanımlı değilse
# motor varsayılan formüle düşer. Sabitler `app/engine/cargo.py`'de tek yerde durur.


@dataclass
class NormalizeSummary:
    """Normalize sonucu — job sonunda özet metrik loglanır."""

    processed_events: int = 0
    orders_created: int = 0
    orders_updated: int = 0
    lines_written: int = 0
    products_matched: int = 0
    products_unmatched: int = 0
    returns_written: int = 0
    settlements_written: int = 0
    cargo_lines_matched: int = 0
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
            "returns_written": self.returns_written,
            "settlements_written": self.settlements_written,
            "cargo_lines_matched": self.cargo_lines_matched,
            "skipped": self.skipped,
        }


def estimate_cargo(
    desi: Decimal | None,
    *,
    bands: list[cargo_engine.Band] | None = None,
    carrier: str | None = None,
) -> Decimal:
    """Desi bazlı kargo tahmini (spec §6.1: `desi_bazli_tahmin(desi, carrier_tarife)`).

    Bant listesi verilmezse — ya da hiçbiri eşleşmezse — varsayılan formüle düşülür.
    """
    return cargo_engine.estimate(desi=desi, bands=bands or (), carrier=carrier).amount


def _channel_code(session: Session, store: Store) -> ChannelCode:
    code = session.scalar(select(Channel.code).where(Channel.id == store.channel_id))
    if code is None:  # pragma: no cover - kanal FK'si garanti eder
        raise LookupError(f"Mağazanın kanalı yok: {store.id}")
    return code


ParsedEvent = RawOrder | list[RawProduct] | RawReturn | RawSettlementRow | RawCargoInvoice


def _parse_event(channel: ChannelCode, event: RawEvent) -> ParsedEvent | None:
    """Ham olayı kanalın ayrıştırıcısıyla çözer."""
    if channel is not ChannelCode.TRENDYOL:
        return None
    if event.event_type == "order":
        return trendyol.parse_order(event.payload)
    if event.event_type == "product":
        return trendyol.parse_product(event.payload)
    if event.event_type == "return":
        return trendyol.parse_claim(event.payload)
    if event.event_type == "settlement":
        return trendyol.parse_settlement_row(event.payload)
    if event.event_type == "cargo_invoice":
        return _parse_cargo_invoice_event(event.payload)
    return None


def _parse_cargo_invoice_event(payload: dict[str, Any]) -> RawCargoInvoice:
    """Kargo faturası olayını ham sözlükten yeniden kurar.

    `raw_events` ham yanıtı saklar (`{"invoice": ..., "items": [...]}`); normalize onu
    her replay'de yeniden ayrıştırır — ham veriden yeniden üretilebilirlik ilkesi.
    """
    invoice_row = payload.get("invoice") or {}
    items = payload.get("items") or []
    parsed = trendyol.parse_settlement_row(invoice_row)
    lines = [trendyol.parse_cargo_invoice_line(item) for item in items]
    return RawCargoInvoice(
        invoice_no=str(invoice_row.get("id") or ""),
        period=parsed.transaction_date.strftime("%Y-%m"),
        total=sum((line.amount for line in lines), Decimal("0")),
        lines=tuple(lines),
        payload=payload,
    )


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
    session: Session,
    store: Store,
    raw_order: RawOrder,
    summary: NormalizeSummary,
    *,
    bands: list[cargo_engine.Band] | None = None,
) -> Order:
    """Ham siparişi domain tablolarına yazar (upsert).

    `bands` kargo tarifesidir; koşu başında bir kez yüklenir (sipariş başına sorgu atmamak
    için) ve gönderi tahmininde kullanılır.
    """
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

    _apply_shipment(session, store, order, raw_order, bands=bands)
    session.flush()
    return order


def _apply_shipment(
    session: Session,
    store: Store,
    order: Order,
    raw_order: RawOrder,
    *,
    bands: list[cargo_engine.Band] | None = None,
) -> Shipment | None:
    """Kargolanmış siparişler için gönderi kaydı (tahmini maliyetle)."""
    if raw_order.status not in SHIPPED_STATUSES:
        return None

    shipment = session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    estimated = estimate_cargo(raw_order.desi, bands=bands, carrier=raw_order.cargo_provider)
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
    # Kargo tarifesi marka başına bir kez yüklenir: sipariş başına sorgu atmamak için.
    band_cache: dict[uuid.UUID, list[cargo_engine.Band]] = {}
    # Kargo faturası kesinleşen siparişlerin kârı koşu sonunda yeniden hesaplanır (§6.2).
    touched_orders: list[uuid.UUID] = []

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
            bands = band_cache.get(store.brand_id)
            if bands is None:
                bands = cargo_tariffs.bands_for_brand(session, store.brand_id)
                band_cache[store.brand_id] = bands
            apply_order(session, store, parsed, summary, bands=bands)
        elif isinstance(parsed, RawReturn):
            apply_return(session, store, parsed, summary)
        elif isinstance(parsed, RawSettlementRow):
            apply_settlement(session, store, parsed, summary)
        elif isinstance(parsed, RawCargoInvoice):
            touched_orders.extend(apply_cargo_invoice(session, store, parsed, summary))
        else:
            apply_products(session, store, parsed, summary)

        summary.processed_events += 1
        if mark_processed:
            event.processed_at = datetime.now(UTC)

    session.flush()
    if touched_orders:
        from app.services.profit import recompute_orders

        recompute_orders(session, order_ids=touched_orders, reason="kargo_faturasi")
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


# --- Faz 2 uygulayıcıları (KVN-EK-05) ----------------------------------------


def apply_return(
    session: Session, store: Store, raw_return: RawReturn, summary: NormalizeSummary
) -> None:
    """İade talebini `returns` tablosuna yazar.

    İki kural bağlayıcı:

    1. **Yalnızca kabul edilen kalem iade sayılır.** Reddedilen talep ciroyu düşürmez;
       `accepted=False` satırlar atlanır ve `iade_reddedildi` olarak sayılır.
    2. **Satır bulunamazsa iade YAZILMAZ.** İade, sipariş satırına bağlıdır; uydurma
       eşleştirme yanlış satırın kârını sıfırlar. Eşleşmeyen kalem `iade_satir_yok`
       sayacına düşer ve görünür kalır.

    `restocked` alanı iade servisinden gelmez (talep yanıtında böyle bir alan yok) ve
    **False** varsayılır: malın yeniden satılabilir olduğunu kanıtsız varsaymak kârı
    olduğundan yüksek gösterirdi. Stok geri alındığında düzeltme kaydıyla girilir.
    """
    for line in raw_return.lines:
        if not line.accepted:
            summary.skip("iade_reddedildi")
            continue

        order_line = _find_order_line(session, store, raw_return, line)
        if order_line is None:
            summary.skip("iade_satir_yok")
            continue

        existing = session.scalar(
            select(Return).where(
                Return.order_line_id == order_line.id,
                Return.return_date == raw_return.return_date,
            )
        )
        if existing is not None:
            # Aynı iade ikinci kez işlenirse kopya yazılmaz (idempotency).
            existing.qty = line.quantity
            existing.refund_amount = line.refund_amount
            existing.reason = line.reason
            continue

        session.add(
            Return(
                tenant_id=store.tenant_id,
                brand_id=store.brand_id,
                order_line_id=order_line.id,
                return_date=raw_return.return_date,
                qty=line.quantity,
                reason=line.reason,
                refund_amount=line.refund_amount,
                # Dönüş kargosu gerçek tutarı kargo faturasından gelir; şimdilik gidiş
                # tahminiyle aynı bant kullanılır.
                return_cargo_cost_estimated=_return_cargo_estimate(session, store, order_line),
                cost_state=CostState.ESTIMATED,
                restocked=False,
            )
        )
        summary.returns_written += 1


def _find_order_line(
    session: Session, store: Store, raw_return: RawReturn, line: RawReturnLine
) -> OrderLine | None:
    """İade kalemini sipariş satırına bağlar: önce satır id'si, sonra sipariş + barkod."""
    statement = (
        select(OrderLine)
        .join(Order, Order.id == OrderLine.order_id)
        .where(Order.tenant_id == store.tenant_id, Order.store_id == store.id)
    )
    if line.external_line_id:
        found = session.scalar(statement.where(OrderLine.external_line_id == line.external_line_id))
        if found is not None:
            return found

    if raw_return.external_order_id and (line.barcode or line.seller_sku):
        # `order_lines` barkod taşımaz; ürün üzerinden eşleştirilir.
        by_product = statement.join(Product, Product.id == OrderLine.product_id).where(
            Order.external_order_id == raw_return.external_order_id
        )
        if line.barcode:
            found = session.scalar(by_product.where(Product.barcode == line.barcode))
            if found is not None:
                return found
        if line.seller_sku:
            return session.scalar(by_product.where(Product.sku == line.seller_sku))
    return None


def _return_cargo_estimate(session: Session, store: Store, order_line: OrderLine) -> Decimal:
    """Dönüş kargosu tahmini — gidiş gönderisinin tahminiyle aynı tarifeden."""
    shipment = session.scalar(select(Shipment).where(Shipment.order_id == order_line.order_id))
    if shipment is not None:
        return shipment.cargo_cost_estimated
    return estimate_cargo(None, bands=cargo_tariffs.bands_for_brand(session, store.brand_id))


def apply_settlement(
    session: Session, store: Store, row: RawSettlementRow, summary: NormalizeSummary
) -> None:
    """Hakediş kalemini `settlement_records`'a yazar (upsert).

    Tekillik `(tenant_id, store_id, external_ref)`; aynı kalem iki kez çekilirse güncellenir,
    kopyalanmaz. Sipariş eşleşmesi burada YAPILMAZ — mutabakat motorunun işidir (spec §7).
    """
    if not row.external_ref:
        summary.skip("hakedis_ref_yok")
        return

    record = session.scalar(
        select(SettlementRecord).where(
            SettlementRecord.tenant_id == store.tenant_id,
            SettlementRecord.store_id == store.id,
            SettlementRecord.external_ref == row.external_ref,
        )
    )
    record_type = SettlementRecordType(row.record_type)
    if record is None:
        record = SettlementRecord(
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            store_id=store.id,
            external_ref=row.external_ref,
            record_type=record_type,
            amount=row.amount,
            transaction_date=row.transaction_date.date(),
        )
        session.add(record)
        summary.settlements_written += 1
    else:
        record.record_type = record_type
        record.amount = row.amount
        record.transaction_date = row.transaction_date.date()


def apply_cargo_invoice(
    session: Session, store: Store, invoice: RawCargoInvoice, summary: NormalizeSummary
) -> list[uuid.UUID]:
    """Kargo faturasını yazar ve gönderi maliyetlerini kesinleştirir (spec §6.2).

    KVN-EK-02'deki Excel akışıyla **aynı kurallar**: eşleştirme önce takip numarası, sonra
    sipariş numarası üzerinden; kesinleşmiş (`actual`) maliyet ikinci faturayla ezilmez;
    eşleşmeyen satır uydurulmaz, sayılır. Kâr yeniden hesabı çağıran katmanda tetiklenir.
    """
    existing = session.scalar(
        select(CargoInvoice).where(
            CargoInvoice.store_id == store.id, CargoInvoice.invoice_no == invoice.invoice_no
        )
    )
    if existing is not None:
        summary.skip("kargo_faturasi_zaten_islenmis")
        return []

    touched: list[uuid.UUID] = []
    results: list[dict[str, Any]] = []

    for line in invoice.lines:
        shipment = _find_shipment_for_invoice(session, store, line)
        if shipment is None:
            results.append({"parcel": line.parcel_id, "sonuc": "eslesmedi"})
            summary.skip("kargo_gonderi_yok")
            continue
        if shipment.cost_state is CostState.ACTUAL:
            results.append({"parcel": line.parcel_id, "sonuc": "zaten_kesin"})
            continue

        shipment.cargo_cost_actual = line.amount
        shipment.desi_invoiced = line.desi
        shipment.cost_state = CostState.ACTUAL
        if line.parcel_id and not shipment.tracking_no:
            shipment.tracking_no = line.parcel_id
        touched.append(shipment.order_id)
        summary.cargo_lines_matched += 1
        results.append({"parcel": line.parcel_id, "sonuc": "kesinlesti"})

    session.add(
        CargoInvoice(
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            store_id=store.id,
            invoice_no=invoice.invoice_no,
            period=invoice.period,
            total=invoice.total,
            lines=results,
        )
    )
    session.flush()
    return touched


def _find_shipment_for_invoice(
    session: Session, store: Store, line: RawCargoInvoiceLine
) -> Shipment | None:
    """Fatura kalemini gönderiye bağlar: önce takip no, sonra sipariş numarası."""
    if line.parcel_id:
        found = session.scalar(
            select(Shipment)
            .join(Order, Order.id == Shipment.order_id)
            .where(Order.store_id == store.id, Shipment.tracking_no == line.parcel_id)
        )
        if found is not None:
            return found

    if line.external_order_id:
        return session.scalar(
            select(Shipment)
            .join(Order, Order.id == Shipment.order_id)
            .where(
                Order.store_id == store.id,
                Order.external_order_id == line.external_order_id,
            )
        )
    return None
