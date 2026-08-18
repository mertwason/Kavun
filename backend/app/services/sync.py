"""Sync servisi: kanaldan çek → `raw_events`'e yaz (spec §3.2, §12.7).

Ham veri değişmezdir: her yanıt önce `raw_events`'e düşer, normalize işlem oradan okur
(KVN-06). Bu yüzden sync şu an **dry-run mantığıyla** çalışır — normalize tablolara
yazmaz. İlk gerçek veriyle şema doğrulaması bu şekilde yapılır (spec §12.7).

Idempotency: `(tenant_id, store_id, event_type, external_id, fetched_at)` tekildir; aynı
kayıt aynı çekimde iki kez yazılamaz, tekrar çekimlerde yeni bir `fetched_at` ile yeni
sürüm olarak durur (ham veri append-only).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError, MarketplaceConnector
from app.connectors.trendyol import TrendyolConnector
from app.core.context import system_scope
from app.core.logging import get_logger
from app.models.enums import ChannelCode
from app.models.identity import Store
from app.models.partitions import ensure_monthly_partition
from app.models.transactions import RawEvent
from app.services.stores import get_channel_code, load_credentials

log = get_logger("services.sync")

DEFAULT_LOOKBACK_DAYS = 7


class UnsupportedChannelError(RuntimeError):
    """Kanal için henüz adapter yazılmadı."""


@dataclass
class SyncSummary:
    """Sync sonucu — her job sonunda özet metrik loglanır (CLAUDE.md §4)."""

    store_id: uuid.UUID
    channel: str
    fetched: dict[str, int] = field(default_factory=dict)
    written: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Hatasız tamamlandı mı."""
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        """Log/JSON dostu özet."""
        return {
            "store_id": str(self.store_id),
            "channel": self.channel,
            "fetched": self.fetched,
            "written": self.written,
            "errors": self.errors,
        }


def build_connector(session: Session, store: Store) -> MarketplaceConnector:
    """Mağazanın kanalına uygun adapter'i credential'larıyla kurar."""
    channel = get_channel_code(session, store)
    if channel is not ChannelCode.TRENDYOL:
        raise UnsupportedChannelError(f"Adapter yok: {channel.value}")

    credentials = load_credentials(session, store)
    return TrendyolConnector(
        seller_id=str(credentials.get("seller_id") or store.external_seller_id or ""),
        api_key=str(credentials["api_key"]),
        api_secret=str(credentials["api_secret"]),
    )


def record_raw_events(
    session: Session,
    store: Store,
    event_type: str,
    items: list[tuple[str, dict[str, Any]]],
    *,
    fetched_at: datetime,
) -> int:
    """Ham kayıtları `raw_events`'e yazar; aynı çekimdeki tekrarları yok sayar."""
    if not items:
        return 0

    connection = session.connection()
    ensure_monthly_partition(connection, fetched_at.date())

    statement = (
        pg_insert(RawEvent)
        .values(
            [
                {
                    "tenant_id": store.tenant_id,
                    "store_id": store.id,
                    "event_type": event_type,
                    "external_id": external_id,
                    "payload": payload,
                    "fetched_at": fetched_at,
                }
                for external_id, payload in items
            ]
        )
        .on_conflict_do_nothing(constraint="uq_raw_events_identity")
        # `rowcount` sürücüye göre -1 dönebiliyor; yazılan satırları RETURNING ile
        # kesin sayarız (çakışan satırlar zaten dönmez).
        .returning(RawEvent.id)
    )
    return len(session.execute(statement).all())


async def sync_store(
    session: Session,
    store: Store,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    connector: MarketplaceConnector | None = None,
) -> SyncSummary:
    """Bir mağazayı senkronlar: siparişler, ürünler ve (varsa) komisyon oranları."""
    fetched_at = datetime.now(UTC)
    until = until or fetched_at
    since = since or (until - timedelta(days=DEFAULT_LOOKBACK_DAYS))

    with system_scope(store.tenant_id):
        channel = get_channel_code(session, store)
        summary = SyncSummary(store_id=store.id, channel=channel.value)
        adapter = connector or build_connector(session, store)

        try:
            orders = await adapter.fetch_orders(since, until)
            summary.fetched["orders"] = len(orders)
            summary.written["orders"] = record_raw_events(
                session,
                store,
                "order",
                [(order.external_order_id, order.payload) for order in orders],
                fetched_at=fetched_at,
            )

            products = await adapter.fetch_products()
            summary.fetched["products"] = len(products)
            summary.written["products"] = record_raw_events(
                session,
                store,
                "product",
                [(product.external_product_id, product.payload) for product in products],
                fetched_at=fetched_at,
            )

            commissions = await adapter.fetch_commission_rates()
            summary.fetched["commissions"] = len(commissions)
            summary.written["commissions"] = record_raw_events(
                session,
                store,
                "commission",
                [
                    (
                        commission.category_code or commission.external_product_id or "unknown",
                        commission.payload,
                    )
                    for commission in commissions
                ],
                fetched_at=fetched_at,
            )

            store.last_synced_at = fetched_at
            session.commit()
        except ConnectorError as exc:
            session.rollback()
            summary.errors.append(f"{type(exc).__name__}: {exc}")
            log.error("sync.failed", **summary.as_dict())
            return summary

    log.info("sync.completed", **summary.as_dict())
    return summary


def load_store_for_sync(session: Session, store_id: uuid.UUID) -> Store | None:
    """Sync için mağazayı yükler (arka plan işleri marka bağlamı olmadan çalışır)."""
    with system_scope():
        return session.scalar(select(Store).where(Store.id == store_id))
