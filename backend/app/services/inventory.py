"""Stok defteri: satış/iade hareketleri, açılış stoku, replay (spec §12C.1-4).

Ledger **append-only**'dir: geçmiş hareket güncellenmez, düzeltme ayrı kayıtla yapılır
(CLAUDE.md §1). `sku_cost_state` bu defterden türetilir ve her an yeniden kurulabilir —
`rebuild_state()` bunu yapar, kabul kriteri (§12C.11) bunu doğrular.

Hareket yönleri (spec §12C.1):
- `purchase_in` · `opening` · `return_in` (kabul edilen iade) → stok artar, **ortalama
  güncellenir**
- `sale_out` · `return_out` (hurda) · `damage` · negatif `adjustment` → stok düşer,
  **ortalama değişmez**

Satış hareketleri kâr hesabından SONRA yazılır ve idempotenttir: aynı sipariş satırı
için ikinci kez `sale_out` üretilmez (`ref_type='order_line'`, `ref_id=<satır id>`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engine.inventory import StockState, apply_inbound, apply_outbound
from app.models.catalog import Product
from app.models.enums import AlertSeverity, InventoryMovement, OrderStatus
from app.models.inventory import InventoryLedger, SkuCostState
from app.models.results import Alert
from app.models.transactions import Order, OrderLine, Return

log = get_logger("services.inventory")

ZERO = Decimal("0")

INBOUND_MOVEMENTS = (
    InventoryMovement.PURCHASE_IN,
    InventoryMovement.OPENING,
    InventoryMovement.RETURN_IN,
)
"""Ortalama maliyeti güncelleyen hareketler (spec §12C.1)."""

NEGATIVE_STOCK_ALERT = "negatif_stok"


class InventoryError(RuntimeError):
    """Stok akışının reddettiği durum."""


@dataclass
class MovementSummary:
    """Hareket yazma turunun özeti."""

    sale_out: int = 0
    return_in: int = 0
    return_out: int = 0
    skipped: int = 0
    negative: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Log dostu özet."""
        return {
            "sale_out": self.sale_out,
            "return_in": self.return_in,
            "return_out": self.return_out,
            "skipped": self.skipped,
            "negative": len(self.negative),
        }


def _state(session: Session, product_id: uuid.UUID) -> tuple[SkuCostState | None, StockState]:
    record = session.scalar(select(SkuCostState).where(SkuCostState.product_id == product_id))
    if record is None:
        return None, StockState.empty()
    return record, StockState(on_hand=record.on_hand_qty, avg_cost=record.avg_cost)


def _persist_state(
    session: Session,
    record: SkuCostState | None,
    product_id: uuid.UUID,
    state: StockState,
    moved_at: datetime,
) -> None:
    if record is None:
        session.add(
            SkuCostState(
                product_id=product_id,
                on_hand_qty=state.on_hand,
                avg_cost=state.avg_cost,
                last_movement_at=moved_at,
            )
        )
    else:
        record.on_hand_qty = state.on_hand
        record.avg_cost = state.avg_cost
        record.last_movement_at = moved_at


def _already_recorded(
    session: Session, *, movement: InventoryMovement, ref_type: str, ref_id: str
) -> bool:
    """Aynı referans için hareket zaten yazıldı mı (idempotency)."""
    return (
        session.scalar(
            select(func.count(InventoryLedger.id)).where(
                InventoryLedger.movement == movement,
                InventoryLedger.ref_type == ref_type,
                InventoryLedger.ref_id == ref_id,
            )
        )
        or 0
    ) > 0


def _has_opening(session: Session, *, product_id: uuid.UUID) -> bool:
    """Bu ürüne daha önce açılış (devir) girilmiş mi — referanstan bağımsız (spec §12C.4)."""
    return (
        session.scalar(
            select(func.count(InventoryLedger.id)).where(
                InventoryLedger.product_id == product_id,
                InventoryLedger.movement == InventoryMovement.OPENING,
            )
        )
        or 0
    ) > 0


def record_movement(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    product_id: uuid.UUID,
    movement: InventoryMovement,
    qty: Decimal,
    unit_cost: Decimal | None = None,
    ref_type: str | None = None,
    ref_id: str | None = None,
    reason: str | None = None,
    moved_at: datetime | None = None,
) -> InventoryLedger:
    """Tek bir stok hareketi yazar ve `sku_cost_state`'i günceller.

    Giriş hareketleri ortalamayı günceller, çıkışlar yalnızca stoku düşürür (§12C.1).
    """
    when = moved_at or datetime.now(UTC)
    record, state = _state(session, product_id)

    if movement in INBOUND_MOVEMENTS:
        if unit_cost is None:
            raise InventoryError(f"{movement.value} hareketi birim maliyet olmadan yazılamaz")
        updated = apply_inbound(state, qty=qty, unit_cost=unit_cost)
        delta = qty
    else:
        updated = apply_outbound(state, qty=qty)
        delta = -qty

    entry = InventoryLedger(
        tenant_id=tenant_id,
        brand_id=brand_id,
        product_id=product_id,
        movement=movement,
        qty_delta=delta,
        unit_cost_at_movement=unit_cost if unit_cost is not None else state.avg_cost,
        avg_cost_after=updated.avg_cost,
        on_hand_after=updated.on_hand,
        ref_type=ref_type,
        ref_id=ref_id,
        reason=reason,
        moved_at=when,
    )
    session.add(entry)
    _persist_state(session, record, product_id, updated, when)
    session.flush()
    return entry


# --- açılış stoku (spec §12C.4) ---------------------------------------------


def opening_stock(
    session: Session,
    *,
    product: Product,
    qty: Decimal,
    unit_cost: Decimal,
    on_date: date,
    user: str | None = None,
) -> InventoryLedger:
    """Tek seferlik devir girişi: "eldeki 34 adet @100 TL" (spec §12C.4).

    Bir ürüne ikinci kez açılış girilemez — devir tanım gereği tektir; ikinci giriş
    stoku sessizce şişirirdi. Düzeltme `adjustment` ile yapılır.
    """
    if qty <= ZERO:
        raise InventoryError("Açılış adedi pozitif olmalı")
    # Kontrol referansa değil ÜRÜNE bakar: açılışı kim yazmış olursa olsun (seed, içe
    # aktarım, API) ikincisi stoku sessizce şişirirdi.
    if _has_opening(session, product_id=product.id):
        raise InventoryError(f"{product.sku} için açılış stoku zaten girilmiş")

    return record_movement(
        session,
        tenant_id=product.tenant_id,
        brand_id=product.brand_id,
        product_id=product.id,
        movement=InventoryMovement.OPENING,
        qty=qty,
        unit_cost=unit_cost,
        ref_type="opening",
        ref_id=str(product.id),
        reason=f"açılış devri ({user})" if user else "açılış devri",
        moved_at=datetime.combine(on_date, datetime.min.time(), tzinfo=UTC),
    )


def adjust(
    session: Session,
    *,
    product: Product,
    qty_delta: Decimal,
    reason: str,
    unit_cost: Decimal | None = None,
    moved_at: datetime | None = None,
) -> InventoryLedger:
    """Düzeltme kaydı — geçmiş silinmez, ters/ek kayıt atılır (CLAUDE.md §1)."""
    if not reason.strip():
        raise InventoryError("Düzeltme kaydı gerekçesiz yazılamaz")
    if qty_delta == ZERO:
        raise InventoryError("Düzeltme miktarı sıfır olamaz")

    if qty_delta > ZERO:
        _, state = _state(session, product.id)
        cost = unit_cost if unit_cost is not None else state.avg_cost
        return record_movement(
            session,
            tenant_id=product.tenant_id,
            brand_id=product.brand_id,
            product_id=product.id,
            movement=InventoryMovement.ADJUSTMENT,
            qty=qty_delta,
            unit_cost=cost,
            ref_type="adjustment",
            reason=reason,
            moved_at=moved_at,
        )

    # Negatif düzeltme bir çıkıştır: ortalama değişmez.
    entry = record_movement(
        session,
        tenant_id=product.tenant_id,
        brand_id=product.brand_id,
        product_id=product.id,
        movement=InventoryMovement.ADJUSTMENT,
        qty=-qty_delta,
        ref_type="adjustment",
        reason=reason,
        moved_at=moved_at,
    )
    return entry


# --- satış ve iade hareketleri (spec §12C.1, §12C.4) ------------------------


def _negative_stock_alert(
    session: Session, product: Product, on_hand: Decimal, moved_at: datetime
) -> None:
    """Stok negatife düştüyse uyarı üretir (spec §12C.4)."""
    session.add(
        Alert(
            tenant_id=product.tenant_id,
            brand_id=product.brand_id,
            type=NEGATIVE_STOCK_ALERT,
            severity=AlertSeverity.WARNING,
            entity_ref=f"product:{product.sku}",
            message=(
                f"Stok kaydı eksik: {product.sku} ({product.name}) "
                f"stoğu {on_hand} adede düştü. Açılış devri ya da alış faturası eksik olabilir."
            ),
            created_at=moved_at,
        )
    )


def record_sales(
    session: Session, *, limit: int = 5000, order_ids: list[uuid.UUID] | None = None
) -> MovementSummary:
    """Satılan adetleri stoktan düşer (spec §12C.1).

    İdempotent: aynı sipariş satırı için ikinci `sale_out` yazılmaz. İptal siparişler
    stoktan düşmez. Ortalama maliyet çıkışlarda değişmez.
    """
    summary = MovementSummary()
    rows = session.execute(
        select(OrderLine, Order)
        .join(Order, Order.id == OrderLine.order_id)
        .where(
            OrderLine.product_id.is_not(None),
            Order.status.notin_((OrderStatus.CANCELLED,)),
        )
        .order_by(Order.order_date)
        .limit(limit)
    ).all()

    for line, order in rows:
        if order_ids is not None and order.id not in order_ids:
            continue
        if _already_recorded(
            session,
            movement=InventoryMovement.SALE_OUT,
            ref_type="order_line",
            ref_id=str(line.id),
        ):
            summary.skipped += 1
            continue

        product = session.scalar(select(Product).where(Product.id == line.product_id))
        if product is None:
            summary.skipped += 1
            continue

        entry = record_movement(
            session,
            tenant_id=order.tenant_id,
            brand_id=order.brand_id,
            product_id=product.id,
            movement=InventoryMovement.SALE_OUT,
            qty=Decimal(line.qty),
            ref_type="order_line",
            ref_id=str(line.id),
            moved_at=order.order_date,
        )
        summary.sale_out += 1
        if entry.on_hand_after < ZERO:
            summary.negative.append(product.sku)
            _negative_stock_alert(session, product, entry.on_hand_after, order.order_date)

    session.flush()
    log.info("inventory.sales_recorded", **summary.as_dict())
    return summary


def record_returns(session: Session, *, limit: int = 5000) -> MovementSummary:
    """İade hareketleri (spec §12C.4).

    - Satılabilir durumda geri gelen mal (`restocked`) → `return_in`, **satış anındaki
      ortalama maliyetle** girer ve ortalamayı günceller.
    - Hurda mal (`restocked=False`) → stok girmez; `return_out` kaydı iz bırakır, kâr
      motorunda zarar zaten duruyor.
    """
    summary = MovementSummary()
    rows = session.execute(
        select(Return, OrderLine, Order)
        .join(OrderLine, OrderLine.id == Return.order_line_id)
        .join(Order, Order.id == OrderLine.order_id)
        .where(OrderLine.product_id.is_not(None))
        .order_by(Return.return_date)
        .limit(limit)
    ).all()

    for return_row, line, order in rows:
        movement = (
            InventoryMovement.RETURN_IN if return_row.restocked else InventoryMovement.RETURN_OUT
        )
        if _already_recorded(
            session, movement=movement, ref_type="return", ref_id=str(return_row.id)
        ):
            summary.skipped += 1
            continue

        product = session.scalar(select(Product).where(Product.id == line.product_id))
        if product is None:
            summary.skipped += 1
            continue

        if not return_row.restocked:
            # Hurda: stok girmez. İz için sıfır adetlik çıkış yazılmaz; kayıt yalnızca
            # `return_out` olarak, satılan adet zaten düşülmüş olduğu için 0 adetle
            # tutulur — defterde "geri gelmedi" bilgisi kalsın diye.
            summary.return_out += 1
            record_movement(
                session,
                tenant_id=order.tenant_id,
                brand_id=order.brand_id,
                product_id=product.id,
                movement=InventoryMovement.RETURN_OUT,
                qty=ZERO,
                ref_type="return",
                ref_id=str(return_row.id),
                reason="iade edilen mal hurda — stoğa girmedi",
                moved_at=return_row.return_date,
            )
            continue

        _, state = _state(session, product.id)
        record_movement(
            session,
            tenant_id=order.tenant_id,
            brand_id=order.brand_id,
            product_id=product.id,
            movement=InventoryMovement.RETURN_IN,
            qty=Decimal(return_row.qty),
            unit_cost=state.avg_cost,
            ref_type="return",
            ref_id=str(return_row.id),
            reason="iade kabul — satış maliyetiyle stoğa döndü",
            moved_at=return_row.return_date,
        )
        summary.return_in += 1

    session.flush()
    log.info("inventory.returns_recorded", **summary.as_dict())
    return summary


# --- replay (kabul kriteri §12C.11) -----------------------------------------


@dataclass
class RebuildSummary:
    """Replay sonucu."""

    products: int = 0
    movements: int = 0
    mismatches: list[str] = field(default_factory=list)


def rebuild_state(session: Session, *, dry_run: bool = False) -> RebuildSummary:
    """`sku_cost_state`'i defterden yeniden kurar (spec §12C.11 kabul kriteri).

    Ledger append-only olduğu için durum her zaman ondan türetilebilir. `dry_run=True`
    yazmaz, yalnızca mevcut durumla farkları raporlar — sessiz sapma yakalanır.

    **Sıra: kayıt sırası (`id`), hareket tarihi değil.** Ortalama maliyet yol bağımlıdır ve
    canlı durum hareketler yazıldıkça bu sırayla oluşur. Geriye dönük tarihli bir hareket
    (ör. bugün onaylanan 40 gün önceki ithalat faturası) tarih sırasına göre oynatılırsa
    farklı bir ortalama çıkar; defter bir yevmiye kaydıdır, kayıtlar yazıldıkları sırayla
    uygulanır. §12C.11'in "birebir aynı" kriteri ancak böyle sağlanır.
    """
    summary = RebuildSummary()
    entries = session.scalars(select(InventoryLedger).order_by(InventoryLedger.id)).all()

    states: dict[uuid.UUID, StockState] = {}
    last_moved: dict[uuid.UUID, datetime] = {}
    for entry in entries:
        state = states.get(entry.product_id, StockState.empty())
        if entry.movement in INBOUND_MOVEMENTS:
            state = apply_inbound(
                state,
                qty=abs(entry.qty_delta),
                unit_cost=entry.unit_cost_at_movement or state.avg_cost,
            )
        else:
            state = apply_outbound(state, qty=abs(entry.qty_delta))
        states[entry.product_id] = state
        # "Son hareket" en yeni TARİHtir; kayıt sırası geriye dönük olabilir.
        previous = last_moved.get(entry.product_id)
        last_moved[entry.product_id] = (
            entry.moved_at if previous is None else max(previous, entry.moved_at)
        )
        summary.movements += 1

    for product_id, state in states.items():
        summary.products += 1
        record, current = _state(session, product_id)
        if current.on_hand != state.on_hand or current.avg_cost != state.avg_cost:
            summary.mismatches.append(str(product_id))
        if not dry_run:
            _persist_state(session, record, product_id, state, last_moved[product_id])

    if not dry_run:
        session.flush()
    log.info(
        "inventory.state_rebuilt",
        products=summary.products,
        movements=summary.movements,
        mismatches=len(summary.mismatches),
        dry_run=dry_run,
    )
    return summary


@dataclass
class StockRow:
    """Stok & maliyet ekranının bir satırı (tasarım brief'i ekran 8)."""

    product_id: uuid.UUID
    sku: str
    name: str
    category: str | None
    on_hand: Decimal
    avg_cost: Decimal
    stock_value: Decimal
    last_movement_at: datetime | None


def stock_rows(session: Session) -> list[StockRow]:
    """Eldeki adet, ortalama maliyet ve stok değeri."""
    rows = session.execute(
        select(Product, SkuCostState)
        .outerjoin(SkuCostState, SkuCostState.product_id == Product.id)
        .order_by(Product.sku)
    ).all()
    result: list[StockRow] = []
    for product, state in rows:
        on_hand = state.on_hand_qty if state else ZERO
        avg_cost = state.avg_cost if state else ZERO
        result.append(
            StockRow(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                category=product.category,
                on_hand=on_hand,
                avg_cost=avg_cost,
                stock_value=(on_hand * avg_cost).quantize(Decimal("0.0001")),
                last_movement_at=state.last_movement_at if state else None,
            )
        )
    return result


def ledger_rows(
    session: Session, *, product_id: uuid.UUID | None = None, limit: int = 200
) -> list[InventoryLedger]:
    """Hareket zaman çizelgesi (en yeni üstte)."""
    statement = select(InventoryLedger).order_by(
        InventoryLedger.moved_at.desc(), InventoryLedger.id.desc()
    )
    if product_id is not None:
        statement = statement.where(InventoryLedger.product_id == product_id)
    return list(session.scalars(statement.limit(limit)).all())
