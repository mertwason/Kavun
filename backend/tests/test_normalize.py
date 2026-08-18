"""KVN-06: normalize pipeline ve replay (spec §3.2, §5.3).

Bağlayıcı kabul kriteri: normalize tablolar silinip `raw_events`'ten yeniden
üretildiğinde birebir aynı sonuç çıkmalı.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import system_scope
from app.models.catalog import Product, ProductChannelMap
from app.models.enums import ChannelCode, CostState, OrderStatus
from app.models.identity import Channel, Store
from app.models.transactions import Order, OrderLine, RawEvent, Shipment
from app.seeds.base import seed_base
from app.services import normalize as normalize_service
from app.services.sync import record_raw_events

FIXTURES = Path(__file__).parent / "fixtures" / "trendyol"


def fixture_orders(name: str = "orders_page0") -> list[dict[str, Any]]:
    """Fixture'daki sipariş paketleri."""
    body: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    content: list[dict[str, Any]] = body["content"]
    return content


@pytest.fixture(autouse=True)
def system_context() -> Iterator[None]:
    """Normalize bir sistem işidir (KVN-03 guard'ı)."""
    with system_scope():
        yield


@pytest.fixture
def store(db_session: Session) -> Store:
    """Kahveji Trendyol mağazası."""
    seed_base(db_session)
    channel = db_session.scalar(select(Channel).where(Channel.code == ChannelCode.TRENDYOL))
    assert channel is not None
    store = db_session.scalar(
        select(Store).where(Store.channel_id == channel.id).order_by(Store.name)
    )
    assert store is not None
    return store


@pytest.fixture
def catalog(db_session: Session, store: Store) -> dict[str, Product]:
    """Sipariş satırlarının bağlanacağı ürünler (katalog Kavun'da yönetilir)."""
    products = {
        "KHV-BLD-ESP": ("8690584683940", Decimal("1.00")),
        "KHV-V60-FLT": ("8690584111222", Decimal("20.00")),
    }
    created: dict[str, Product] = {}
    for sku, (barcode, vat) in products.items():
        product = Product(
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            sku=sku,
            name=sku,
            barcode=barcode,
            vat_rate=vat,
        )
        db_session.add(product)
        db_session.flush()
        created[sku] = product
    return created


def _record(
    db_session: Session,
    store: Store,
    payloads: list[dict[str, Any]],
    *,
    event_type: str = "order",
    fetched_at: datetime | None = None,
) -> None:
    """Ham olayları yazar (sync'in yaptığı işin aynısı)."""
    record_raw_events(
        db_session,
        store,
        event_type,
        [
            (str(payload.get("orderNumber") or payload.get("contentId") or index), payload)
            for index, payload in enumerate(payloads)
        ],
        fetched_at=fetched_at or datetime.now(UTC),
    )


# --- normalize --------------------------------------------------------------


def test_orders_are_normalized_from_raw_events(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """Ham olaydan sipariş, satır ve gönderi üretilir."""
    _record(db_session, store, fixture_orders())

    summary = normalize_service.normalize_pending(db_session)

    assert summary.processed_events == 2
    assert summary.orders_created == 2

    order = db_session.scalar(select(Order).where(Order.external_order_id == "TY-2026-0001"))
    assert order is not None
    assert order.status is OrderStatus.DELIVERED
    assert order.gross_total == Decimal("1078.0000")
    assert order.customer_city == "İstanbul"
    assert order.brand_id == store.brand_id

    lines = db_session.scalars(select(OrderLine).where(OrderLine.order_id == order.id)).all()
    assert len(lines) == 2
    espresso = next(line for line in lines if line.external_line_id == "55501")
    assert espresso.qty == 2
    assert espresso.unit_sale_price == Decimal("449.0000")
    assert espresso.line_gross == Decimal("898.0000")
    assert espresso.product_id == catalog["KHV-BLD-ESP"].id
    # KDV oranı katalogdan gelir (kanal değil, Kavun doğruluk kaynağı).
    assert espresso.vat_rate == Decimal("1.00")


def test_shipment_is_created_for_shipped_orders(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """Kargolanan siparişe tahmini maliyetli gönderi kaydı açılır."""
    _record(db_session, store, fixture_orders())
    normalize_service.normalize_pending(db_session)

    order = db_session.scalar(select(Order).where(Order.external_order_id == "TY-2026-0001"))
    assert order is not None
    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    assert shipment is not None
    assert shipment.carrier == "Trendyol Express"
    assert shipment.desi_declared == Decimal("3.50")
    assert shipment.cost_state is CostState.ESTIMATED
    assert shipment.cargo_cost_estimated == normalize_service.estimate_cargo(Decimal("3.5"))

    # İptal edilen siparişe gönderi açılmaz (maliyet kalemleri sıfır, spec §6.3.5).
    cancelled = db_session.scalar(select(Order).where(Order.external_order_id == "TY-2026-0002"))
    assert cancelled is not None
    assert db_session.scalar(select(Shipment).where(Shipment.order_id == cancelled.id)) is None


def test_actual_cargo_cost_is_never_overwritten(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """Kesinleşmiş maliyet yeniden normalize'de ezilmez (spec §3.4)."""
    _record(db_session, store, fixture_orders())
    normalize_service.normalize_pending(db_session)

    order = db_session.scalar(select(Order).where(Order.external_order_id == "TY-2026-0001"))
    assert order is not None
    shipment = db_session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    assert shipment is not None
    shipment.cargo_cost_actual = Decimal("77.5000")
    shipment.cost_state = CostState.ACTUAL
    db_session.flush()

    _record(db_session, store, fixture_orders(), fetched_at=datetime.now(UTC) + timedelta(hours=1))
    normalize_service.normalize_pending(db_session)

    db_session.refresh(shipment)
    assert shipment.cost_state is CostState.ACTUAL
    assert shipment.cargo_cost_actual == Decimal("77.5000")


def test_unmatched_lines_are_kept_without_product(db_session: Session, store: Store) -> None:
    """Katalogda olmayan ürün satırı düşürülmez; `product_id` boş kalır."""
    _record(db_session, store, fixture_orders())
    summary = normalize_service.normalize_pending(db_session)

    assert summary.products_unmatched > 0
    lines = db_session.scalars(select(OrderLine)).all()
    assert lines and all(line.product_id is None for line in lines)
    # Eşleşmeyen satır yine de tutar taşır — kâr motoru maliyetsiz satırı raporlayabilsin.
    assert all(line.line_gross > 0 for line in lines)


def test_normalize_is_idempotent(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """Aynı olay iki kez işlenirse kopya sipariş/satır oluşmaz."""
    _record(db_session, store, fixture_orders())
    normalize_service.normalize_pending(db_session)

    # Aynı sipariş yeni bir çekimde tekrar geldi (append-only ham veri).
    _record(db_session, store, fixture_orders(), fetched_at=datetime.now(UTC) + timedelta(hours=1))
    second = normalize_service.normalize_pending(db_session)

    assert second.orders_created == 0
    assert second.orders_updated == 2
    assert db_session.scalar(select(func.count()).select_from(Order)) == 2
    assert db_session.scalar(select(func.count()).select_from(OrderLine)) == 3


def test_status_change_updates_existing_order(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """Statü değişimi mevcut kayda uygulanır (Picking → Delivered)."""
    picking = fixture_orders("orders_page1")
    _record(db_session, store, picking)
    normalize_service.normalize_pending(db_session)

    order = db_session.scalar(select(Order).where(Order.external_order_id == "TY-2026-0003"))
    assert order is not None and order.status is OrderStatus.PICKING

    delivered = json.loads(json.dumps(picking))
    delivered[0]["status"] = "Delivered"
    delivered[0]["lines"][0]["orderLineItemStatusName"] = "Delivered"
    _record(db_session, store, delivered, fetched_at=datetime.now(UTC) + timedelta(hours=2))
    normalize_service.normalize_pending(db_session)

    db_session.expire_all()
    updated = db_session.scalar(select(Order).where(Order.external_order_id == "TY-2026-0003"))
    assert updated is not None
    assert updated.status is OrderStatus.DELIVERED


def test_processed_events_are_stamped(db_session: Session, store: Store) -> None:
    """İşlenen olay damgalanır; ikinci koşuda tekrar işlenmez."""
    _record(db_session, store, fixture_orders())
    normalize_service.normalize_pending(db_session)

    unprocessed = db_session.scalar(
        select(func.count()).select_from(RawEvent).where(RawEvent.processed_at.is_(None))
    )
    assert unprocessed == 0
    assert normalize_service.normalize_pending(db_session).processed_events == 0


def test_product_events_update_channel_mapping(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """Ürün olayı kanal eşlemesini kurar; yeni ürün YARATMAZ (katalog Kavun'da)."""
    body = json.loads((FIXTURES / "products_approved.json").read_text(encoding="utf-8"))
    _record(db_session, store, body["content"], event_type="product")

    before = db_session.scalar(select(func.count()).select_from(Product))
    normalize_service.normalize_pending(db_session)

    assert db_session.scalar(select(func.count()).select_from(Product)) == before
    mapping = db_session.scalar(
        select(ProductChannelMap).where(
            ProductChannelMap.external_barcode == "8690584683940",
            ProductChannelMap.store_id == store.id,
        )
    )
    assert mapping is not None
    assert mapping.product_id == catalog["KHV-BLD-ESP"].id


# --- replay (spec §3.2 kabul kriteri) ---------------------------------------


def _snapshot(db_session: Session) -> dict[str, Any]:
    """Normalize durumun karşılaştırılabilir özeti."""
    orders = db_session.scalars(select(Order).order_by(Order.external_order_id)).all()
    lines = db_session.scalars(select(OrderLine).order_by(OrderLine.external_line_id)).all()
    shipments = db_session.scalars(select(Shipment)).all()
    return {
        "orders": [
            (order.external_order_id, order.status, order.gross_total, order.customer_city)
            for order in orders
        ],
        "lines": [
            (line.external_line_id, line.qty, line.unit_sale_price, line.line_gross, line.vat_rate)
            for line in lines
        ],
        "shipments": sorted(
            (shipment.carrier or "", shipment.cargo_cost_estimated) for shipment in shipments
        ),
    }


def test_replay_rebuilds_identical_state(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """Normalize tablolar silinip ham olaylardan yeniden üretildiğinde sonuç birebir aynı."""
    _record(db_session, store, fixture_orders())
    _record(db_session, store, fixture_orders("orders_page1"))
    normalize_service.normalize_pending(db_session)
    expected = _snapshot(db_session)

    summary = normalize_service.replay(db_session, channel=ChannelCode.TRENDYOL)

    assert summary.processed_events == 3
    assert _snapshot(db_session) == expected


def test_replay_does_not_touch_raw_events(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """Ham veri değişmez (spec §3.2)."""
    _record(db_session, store, fixture_orders())
    normalize_service.normalize_pending(db_session)
    before = db_session.scalar(select(func.count()).select_from(RawEvent))

    normalize_service.replay(db_session, channel=ChannelCode.TRENDYOL)

    assert db_session.scalar(select(func.count()).select_from(RawEvent)) == before


def test_replay_recovers_from_deleted_normalized_tables(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """Normalize tablolar tamamen silinse bile ham veriden geri kurulur."""
    _record(db_session, store, fixture_orders())
    normalize_service.normalize_pending(db_session)
    expected = _snapshot(db_session)

    from sqlalchemy import delete

    db_session.execute(delete(Shipment))
    db_session.execute(delete(OrderLine))
    db_session.execute(delete(Order))
    db_session.flush()
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0

    normalize_service.replay(db_session, store_id=store.id)

    assert _snapshot(db_session) == expected


def test_replay_respects_date_window(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """`--from/--to` aralığı dışındaki olaylar yeniden işlenmez."""
    old = datetime.now(UTC) - timedelta(days=30)
    _record(db_session, store, fixture_orders(), fetched_at=old)
    _record(db_session, store, fixture_orders("orders_page1"))
    normalize_service.normalize_pending(db_session)

    summary = normalize_service.replay(
        db_session, store_id=store.id, since=datetime.now(UTC) - timedelta(days=1)
    )

    assert summary.processed_events == 1


def test_replay_dry_run_writes_nothing(
    db_session: Session, store: Store, catalog: dict[str, Product]
) -> None:
    """`--dry-run` yalnızca sayar."""
    _record(db_session, store, fixture_orders())
    normalize_service.normalize_pending(db_session)
    expected = _snapshot(db_session)

    summary = normalize_service.replay(db_session, store_id=store.id, dry_run=True)

    assert summary.processed_events == 2
    assert summary.orders_created == 0
    assert _snapshot(db_session) == expected


def test_replay_of_unknown_store_is_noop(db_session: Session, store: Store) -> None:
    """Bilinmeyen mağaza için replay veri bozmaz."""
    summary = normalize_service.replay(db_session, store_id=uuid.uuid4())
    assert summary.processed_events == 0
