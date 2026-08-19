"""KVN-05: sync servisi — ham veri `raw_events`'e yazılır (spec §3.2, §12.7)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.connectors.base import (
    ConnectorError,
    MarketplaceConnector,
    RawCargoInvoice,
    RawCommission,
    RawOrder,
    RawProduct,
    RawReturn,
    RawSettlementRow,
)
from app.core.context import system_scope
from app.models.enums import ChannelCode, OrderStatus
from app.models.identity import Channel, Store, Tenant
from app.models.transactions import RawEvent
from app.seeds.base import seed_base
from app.services import sync as sync_service


class FakeConnector(MarketplaceConnector):
    """Testler için kanal taklidi — ağ yok."""

    channel_code = "trendyol"

    def __init__(
        self,
        orders: list[RawOrder],
        products: list[RawProduct],
        *,
        returns: list[RawReturn] | None = None,
        settlements: list[RawSettlementRow] | None = None,
        cargo_invoices: list[RawCargoInvoice] | None = None,
    ) -> None:
        self.orders = orders
        self.products = products
        self.returns = returns or []
        self.settlements = settlements or []
        self.cargo_invoices = cargo_invoices or []
        self.calls: list[str] = []

    async def fetch_orders(self, since: datetime, until: datetime) -> list[RawOrder]:
        self.calls.append("orders")
        return self.orders

    async def fetch_products(self) -> list[RawProduct]:
        self.calls.append("products")
        return self.products

    async def fetch_commission_rates(self) -> list[RawCommission]:
        self.calls.append("commissions")
        return []

    async def fetch_returns(self, since: datetime) -> list[RawReturn]:
        self.calls.append("returns")
        return self.returns

    async def fetch_settlements(self, since: datetime) -> list[RawSettlementRow]:
        self.calls.append("settlements")
        return self.settlements

    async def fetch_cargo_invoices(self, since: datetime) -> list[RawCargoInvoice]:
        self.calls.append("cargo_invoices")
        return self.cargo_invoices


class FailingConnector(FakeConnector):
    """Sipariş çekiminde hata veren kanal."""

    async def fetch_orders(self, since: datetime, until: datetime) -> list[RawOrder]:
        raise ConnectorError("kanal ulaşılamıyor")


def _order(external_id: str) -> RawOrder:
    return RawOrder(
        external_order_id=external_id,
        order_date=datetime.now(UTC),
        status=OrderStatus.DELIVERED,
        gross_total=Decimal("100.0000"),
        currency="TRY",
        customer_city="İstanbul",
        cargo_provider="Trendyol Express",
        desi=Decimal("1.5"),
        lines=(),
        payload={"orderNumber": external_id, "totalPrice": "100.00"},
    )


def _product(external_id: str) -> RawProduct:
    return RawProduct(
        external_product_id=external_id,
        barcode="8690000000001",
        seller_sku="SKU-1",
        name="Test",
        category="Kahve",
        brand="Kahveji",
        sale_price=Decimal("100.0000"),
        list_price=None,
        stock=5,
        vat_rate=None,
        desi=None,
        payload={"variantId": external_id},
    )


@pytest.fixture(autouse=True)
def system_context() -> Iterator[None]:
    """Sync bir sistem işidir (KVN-03 guard'ı)."""
    with system_scope():
        yield


@pytest.fixture
def store(db_session: Session) -> Store:
    """Trendyol mağazası (çekirdek seed'den)."""
    seed_base(db_session)
    channel = db_session.scalar(select(Channel).where(Channel.code == ChannelCode.TRENDYOL))
    assert channel is not None
    store = db_session.scalar(select(Store).where(Store.channel_id == channel.id))
    assert store is not None
    return store


@pytest.mark.asyncio
async def test_sync_writes_raw_events(db_session: Session, store: Store) -> None:
    """Çekilen her kayıt `raw_events`'e düşer; normalize tablolara dokunulmaz."""
    connector = FakeConnector([_order("TY-1"), _order("TY-2")], [_product("V-1")])

    summary = await sync_service.sync_store(db_session, store, connector=connector)

    assert summary.ok
    assert summary.fetched == {
        "orders": 2,
        "products": 1,
        "returns": 0,
        "settlements": 0,
        "cargo_invoices": 0,
        "commissions": 0,
    }
    assert summary.written == {
        "orders": 2,
        "products": 1,
        "returns": 0,
        "settlements": 0,
        "cargo_invoices": 0,
        "commissions": 0,
    }

    events = db_session.scalars(select(RawEvent).where(RawEvent.store_id == store.id)).all()
    assert {event.event_type for event in events} == {"order", "product"}
    assert {event.external_id for event in events} == {"TY-1", "TY-2", "V-1"}
    # Ham payload olduğu gibi durur (spec §3.2).
    order_event = next(event for event in events if event.external_id == "TY-1")
    assert order_event.payload == {"orderNumber": "TY-1", "totalPrice": "100.00"}
    assert order_event.processed_at is None


@pytest.mark.asyncio
async def test_sync_updates_last_synced_at(db_session: Session, store: Store) -> None:
    """Mağazanın sync damgası güncellenir (mağaza listesi bunu gösterir)."""
    before = store.last_synced_at
    await sync_service.sync_store(db_session, store, connector=FakeConnector([_order("A")], []))
    assert store.last_synced_at is not None and store.last_synced_at != before


@pytest.mark.asyncio
async def test_duplicate_records_in_same_fetch_are_ignored(
    db_session: Session, store: Store
) -> None:
    """Aynı çekimde tekrarlanan kayıt iki kez yazılmaz (spec §3.7 idempotency)."""
    connector = FakeConnector([_order("TY-1"), _order("TY-1")], [])

    summary = await sync_service.sync_store(db_session, store, connector=connector)

    assert summary.fetched["orders"] == 2
    assert summary.written["orders"] == 1
    total = db_session.scalar(
        select(func.count()).select_from(RawEvent).where(RawEvent.store_id == store.id)
    )
    assert total == 1


@pytest.mark.asyncio
async def test_repeated_sync_keeps_history(db_session: Session, store: Store) -> None:
    """Tekrar çekimde ham veri silinmez; yeni sürüm olarak eklenir (append-only)."""
    await sync_service.sync_store(db_session, store, connector=FakeConnector([_order("TY-1")], []))
    await sync_service.sync_store(db_session, store, connector=FakeConnector([_order("TY-1")], []))

    versions = db_session.scalars(
        select(RawEvent.fetched_at).where(RawEvent.external_id == "TY-1")
    ).all()
    assert len(versions) == 2
    assert len(set(versions)) == 2


@pytest.mark.asyncio
async def test_connector_failure_is_reported_not_swallowed(
    db_session: Session, store: Store
) -> None:
    """Kanal hatası özet metriğe yazılır ve yazma geri alınır."""
    store_id = store.id
    summary = await sync_service.sync_store(db_session, store, connector=FailingConnector([], []))

    assert not summary.ok
    assert "ConnectorError" in summary.errors[0]
    # Hata sonrası yazma geri alınır (sync içindeki rollback bu testte seed'i de geri alır;
    # önemli olan ham kaydın kalmamış olması).
    remaining = db_session.scalar(
        select(func.count()).select_from(RawEvent).where(RawEvent.store_id == store_id)
    )
    assert remaining == 0


@pytest.mark.asyncio
async def test_default_window_is_last_week(db_session: Session, store: Store) -> None:
    """Aralık verilmezse son bir hafta çekilir."""
    captured: dict[str, Any] = {}

    class WindowCapturingConnector(FakeConnector):
        async def fetch_orders(self, since: datetime, until: datetime) -> list[RawOrder]:
            captured["since"] = since
            captured["until"] = until
            return []

    await sync_service.sync_store(db_session, store, connector=WindowCapturingConnector([], []))

    span = captured["until"] - captured["since"]
    assert span == timedelta(days=sync_service.DEFAULT_LOOKBACK_DAYS)


def test_unsupported_channel_is_explicit(db_session: Session) -> None:
    """Adapter'i olmayan kanal sessizce atlanmaz."""
    seed_base(db_session)
    manual_channel = db_session.scalar(select(Channel).where(Channel.code == ChannelCode.MANUAL))
    assert manual_channel is not None
    store = db_session.scalar(select(Store).where(Store.channel_id == manual_channel.id))
    assert store is not None

    with pytest.raises(sync_service.UnsupportedChannelError):
        sync_service.build_connector(db_session, store)


def test_load_store_for_sync_returns_none_for_unknown(db_session: Session) -> None:
    """Silinmiş mağaza için job sessizce çöker değil, None döner."""
    assert sync_service.load_store_for_sync(db_session, uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_raw_events_partition_is_created_on_demand(db_session: Session, store: Store) -> None:
    """Yazmadan önce ayın partition'ı garanti edilir (KVN-02 riskinin kapatılması)."""
    from sqlalchemy import text

    future = datetime.now(UTC) + timedelta(days=1500)
    partition = f"raw_events_{future:%Y_%m}"
    db_session.execute(text(f"DROP TABLE IF EXISTS {partition}"))

    sync_service.record_raw_events(
        db_session,
        store,
        "order",
        [("FUTURE-1", {"orderNumber": "FUTURE-1"})],
        fetched_at=future,
    )

    exists = db_session.execute(
        text("SELECT 1 FROM pg_class WHERE relname = :name"), {"name": partition}
    ).scalar()
    assert exists == 1


@pytest.mark.asyncio
async def test_tenant_isolation_of_raw_events(db_session: Session, store: Store) -> None:
    """Ham kayıt mağazanın tenant'ına yazılır — başka tenant'a karışmaz."""
    await sync_service.sync_store(db_session, store, connector=FakeConnector([_order("TY-9")], []))

    event = db_session.scalar(select(RawEvent).where(RawEvent.external_id == "TY-9"))
    assert event is not None
    tenant = db_session.get(Tenant, event.tenant_id)
    assert tenant is not None and tenant.id == store.tenant_id


def test_worker_tasks_are_registered() -> None:
    """Worker görevleri tanıyor olmalı — `include` unutulursa job sessizce düşer.

    Worker açılışta `import_default_modules()` çağırır; test aynı yolu izler.
    """
    from app.workers.celery_app import celery_app

    celery_app.loader.import_default_modules()
    registered = set(celery_app.tasks)
    assert {
        "kavun.sync_store",
        "kavun.normalize_pending",
        "kavun.ensure_raw_event_partitions",
        "kavun.recompute_pending_profits",
        "kavun.detect_commission_changes",
        "kavun.record_stock_movements",
        "kavun.check_price_discipline",
    } <= registered
