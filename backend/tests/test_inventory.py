"""KVN-16: stok defteri, WAC durumu, açılış stoku ve replay (spec §12C.1-4).

Kabul kriterleri (§12C.11):
- Formül: 34@100 + 100@120 → 114,9254; 50 satış → ortalama değişmez, on_hand 84;
  20@130 alış → yeni ortalama doğru (motor testi `test_invoices.py`'de, burada DB üzerinden)
- Ledger replay: `sku_cost_state` silinip defterden yeniden üretildiğinde birebir aynı
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.context import RequestContext, system_scope, use_context
from app.main import create_app
from app.models.catalog import Product
from app.models.enums import InventoryMovement, OrderStatus, UserRole
from app.models.identity import Brand, Store
from app.models.inventory import InventoryLedger, SkuCostState
from app.models.results import Alert
from app.models.transactions import OrderLine, Return
from app.services import inventory
from tests.profit_factories import ORDER_DATE, make_order, make_product, make_store

D = Decimal
TODAY = ORDER_DATE.date()


@pytest.fixture
def store(db_session: Session) -> Iterator[Store]:
    """Mağaza + marka bağlamı."""
    with system_scope():
        store = make_store(db_session)
        brand = db_session.get(Brand, store.brand_id)
    assert brand is not None
    context = RequestContext(
        tenant_id=brand.tenant_id,
        user_id=None,
        brand_id=brand.id,
        brand_slug=brand.slug,
        role=UserRole.ADMIN,
    )
    with use_context(context):
        yield store


@pytest.fixture
def product(db_session: Session, store: Store) -> Product:
    """Stok hareketlerinin uygulanacağı ürün."""
    return make_product(db_session, store, "STOK-1", cost=D("100.0000"))


def _state(db_session: Session, product: Product) -> SkuCostState | None:
    return db_session.scalar(select(SkuCostState).where(SkuCostState.product_id == product.id))


# --- açılış stoku (spec §12C.4) ---------------------------------------------


def test_opening_stock_sets_state(db_session: Session, product: Product) -> None:
    """§12C.4: "eldeki 34 adet @100 TL" tek seferlik devirle girilir."""
    entry = inventory.opening_stock(
        db_session, product=product, qty=D("34"), unit_cost=D("100"), on_date=TODAY
    )

    assert entry.movement is InventoryMovement.OPENING
    state = _state(db_session, product)
    assert state is not None
    assert state.on_hand_qty == D("34")
    assert state.avg_cost == D("100.000000")


def test_opening_stock_cannot_be_entered_twice(db_session: Session, product: Product) -> None:
    """Devir tanım gereği tektir; ikinci giriş stoku sessizce şişirirdi."""
    inventory.opening_stock(
        db_session, product=product, qty=D("34"), unit_cost=D("100"), on_date=TODAY
    )

    with pytest.raises(inventory.InventoryError, match="zaten girilmiş"):
        inventory.opening_stock(
            db_session, product=product, qty=D("10"), unit_cost=D("120"), on_date=TODAY
        )


def test_opening_stock_blocked_when_another_writer_left_an_opening(
    db_session: Session, store: Store, product: Product
) -> None:
    """Açılışı seed/içe aktarım yazmışsa da ikinci giriş reddedilir (referanstan bağımsız)."""
    inventory.record_movement(
        db_session,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        product_id=product.id,
        movement=InventoryMovement.OPENING,
        qty=D("34"),
        unit_cost=D("100"),
        ref_type="seed",
        ref_id="opening",
    )

    with pytest.raises(inventory.InventoryError, match="zaten girilmiş"):
        inventory.opening_stock(
            db_session, product=product, qty=D("10"), unit_cost=D("120"), on_date=TODAY
        )


def test_opening_stock_rejects_non_positive_qty(db_session: Session, product: Product) -> None:
    """Sıfır/negatif açılış anlamsızdır."""
    with pytest.raises(inventory.InventoryError, match="pozitif"):
        inventory.opening_stock(
            db_session, product=product, qty=D("0"), unit_cost=D("100"), on_date=TODAY
        )


# --- WAC zinciri, DB üzerinden (kabul §12C.11) ------------------------------


def test_full_movement_chain_matches_the_spec_example(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12C.11: 34@100 → +100@120 → −50 satış → +20@130 zinciri."""
    inventory.opening_stock(
        db_session, product=product, qty=D("34"), unit_cost=D("100"), on_date=TODAY
    )
    inventory.record_movement(
        db_session,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        product_id=product.id,
        movement=InventoryMovement.PURCHASE_IN,
        qty=D("100"),
        unit_cost=D("120"),
    )
    state = _state(db_session, product)
    assert state is not None
    assert state.on_hand_qty == D("134")
    assert state.avg_cost.quantize(D("0.0001")) == D("114.9254")

    inventory.record_movement(
        db_session,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        product_id=product.id,
        movement=InventoryMovement.SALE_OUT,
        qty=D("50"),
    )
    state = _state(db_session, product)
    assert state is not None
    assert state.on_hand_qty == D("84")
    assert state.avg_cost.quantize(D("0.0001")) == D("114.9254")  # çıkışta değişmez

    inventory.record_movement(
        db_session,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        product_id=product.id,
        movement=InventoryMovement.PURCHASE_IN,
        qty=D("20"),
        unit_cost=D("130"),
    )
    state = _state(db_session, product)
    assert state is not None
    assert state.on_hand_qty == D("104")
    expected = (D("84") * D("114.925373") + D("20") * D("130")) / D("104")
    assert abs(state.avg_cost - expected) <= D("0.0001")


def test_inbound_without_cost_is_rejected(
    db_session: Session, store: Store, product: Product
) -> None:
    """Giriş hareketi maliyet olmadan yazılamaz — ortalama bozulurdu."""
    with pytest.raises(inventory.InventoryError, match="birim maliyet"):
        inventory.record_movement(
            db_session,
            tenant_id=store.tenant_id,
            brand_id=store.brand_id,
            product_id=product.id,
            movement=InventoryMovement.PURCHASE_IN,
            qty=D("10"),
        )


# --- satış hareketleri (spec §12C.1) ----------------------------------------


def test_sales_are_recorded_once(db_session: Session, store: Store, product: Product) -> None:
    """Satış stoktan düşer ve idempotenttir — ikinci turda tekrar yazılmaz."""
    inventory.opening_stock(
        db_session, product=product, qty=D("100"), unit_cost=D("100"), on_date=TODAY
    )
    make_order(db_session, store, [(product, 3, D("360.0000"))])

    first = inventory.record_sales(db_session)
    second = inventory.record_sales(db_session)

    assert first.sale_out == 1
    assert second.sale_out == 0
    assert second.skipped == 1
    state = _state(db_session, product)
    assert state is not None
    assert state.on_hand_qty == D("97")
    assert state.avg_cost == D("100.000000")


def test_cancelled_orders_do_not_touch_stock(
    db_session: Session, store: Store, product: Product
) -> None:
    """§6.3.5: iptal sipariş stoktan düşmez."""
    inventory.opening_stock(
        db_session, product=product, qty=D("50"), unit_cost=D("100"), on_date=TODAY
    )
    make_order(db_session, store, [(product, 5, D("600"))], status=OrderStatus.CANCELLED)

    summary = inventory.record_sales(db_session)

    assert summary.sale_out == 0
    state = _state(db_session, product)
    assert state is not None and state.on_hand_qty == D("50")


def test_negative_stock_writes_alert(db_session: Session, store: Store, product: Product) -> None:
    """§12C.4: stok negatife düşerse hareket yine yazılır ama uyarı üretilir."""
    make_order(db_session, store, [(product, 5, D("600"))])

    summary = inventory.record_sales(db_session)

    assert summary.sale_out == 1
    assert product.sku in summary.negative
    state = _state(db_session, product)
    assert state is not None and state.on_hand_qty == D("-5")
    alert = db_session.scalar(select(Alert).where(Alert.type == inventory.NEGATIVE_STOCK_ALERT))
    assert alert is not None
    assert product.sku in alert.message


# --- iade hareketleri (spec §12C.4) -----------------------------------------


def _return_for(
    db_session: Session, store: Store, order_line: OrderLine, *, restocked: bool
) -> Return:
    record = Return(
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        order_line_id=order_line.id,
        return_date=ORDER_DATE + timedelta(days=2),
        qty=1,
        refund_amount=D("120.0000"),
        return_cargo_cost_estimated=D("24.0000"),
        restocked=restocked,
    )
    db_session.add(record)
    db_session.flush()
    return record


def test_restocked_return_goes_back_to_stock(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12C.4: satılabilir iade `return_in` olarak satış maliyetiyle stoğa döner."""
    inventory.opening_stock(
        db_session, product=product, qty=D("10"), unit_cost=D("100"), on_date=TODAY
    )
    order = make_order(db_session, store, [(product, 2, D("240"))])
    inventory.record_sales(db_session)
    line = db_session.scalar(select(OrderLine).where(OrderLine.order_id == order.id))
    assert line is not None
    _return_for(db_session, store, line, restocked=True)

    summary = inventory.record_returns(db_session)

    assert summary.return_in == 1
    state = _state(db_session, product)
    assert state is not None
    assert state.on_hand_qty == D("9")  # 10 − 2 satış + 1 iade
    assert state.avg_cost == D("100.000000")


def test_scrapped_return_does_not_restock(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12C.4: hurda iade stoğa girmez; defterde izi kalır."""
    inventory.opening_stock(
        db_session, product=product, qty=D("10"), unit_cost=D("100"), on_date=TODAY
    )
    order = make_order(db_session, store, [(product, 2, D("240"))])
    inventory.record_sales(db_session)
    line = db_session.scalar(select(OrderLine).where(OrderLine.order_id == order.id))
    assert line is not None
    _return_for(db_session, store, line, restocked=False)

    summary = inventory.record_returns(db_session)

    assert summary.return_out == 1
    state = _state(db_session, product)
    assert state is not None and state.on_hand_qty == D("8")
    entry = db_session.scalar(
        select(InventoryLedger).where(InventoryLedger.movement == InventoryMovement.RETURN_OUT)
    )
    assert entry is not None and entry.reason is not None and "hurda" in entry.reason


# --- düzeltme (CLAUDE.md §1) -------------------------------------------------


def test_adjustment_requires_a_reason(db_session: Session, product: Product) -> None:
    """Gerekçesiz düzeltme yazılamaz — defterde neden bilinmeyen hareket olmaz."""
    with pytest.raises(inventory.InventoryError, match="gerekçesiz"):
        inventory.adjust(db_session, product=product, qty_delta=D("5"), reason="  ")


def test_negative_adjustment_keeps_average(db_session: Session, product: Product) -> None:
    """Negatif düzeltme bir çıkıştır: ortalama değişmez."""
    inventory.opening_stock(
        db_session, product=product, qty=D("10"), unit_cost=D("100"), on_date=TODAY
    )

    inventory.adjust(db_session, product=product, qty_delta=D("-3"), reason="sayım eksiği")

    state = _state(db_session, product)
    assert state is not None
    assert state.on_hand_qty == D("7")
    assert state.avg_cost == D("100.000000")


# --- replay (kabul kriteri §12C.11) -----------------------------------------


def test_state_can_be_rebuilt_from_the_ledger(
    db_session: Session, store: Store, product: Product
) -> None:
    """§12C.11 kabul: `sku_cost_state` silinip defterden yeniden üretilince BİREBİR aynı."""
    inventory.opening_stock(
        db_session, product=product, qty=D("34"), unit_cost=D("100"), on_date=TODAY
    )
    inventory.record_movement(
        db_session,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        product_id=product.id,
        movement=InventoryMovement.PURCHASE_IN,
        qty=D("100"),
        unit_cost=D("120"),
        moved_at=datetime.combine(TODAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=1),
    )
    make_order(db_session, store, [(product, 50, D("6000"))])
    inventory.record_sales(db_session)

    before = _state(db_session, product)
    assert before is not None
    expected_on_hand, expected_avg = before.on_hand_qty, before.avg_cost

    db_session.delete(before)
    db_session.flush()
    assert _state(db_session, product) is None

    summary = inventory.rebuild_state(db_session)

    rebuilt = _state(db_session, product)
    assert rebuilt is not None
    assert rebuilt.on_hand_qty == expected_on_hand
    assert rebuilt.avg_cost == expected_avg
    assert summary.movements == 3


def test_rebuild_replays_in_posting_order_not_by_date(
    db_session: Session, store: Store, product: Product
) -> None:
    """Geriye dönük tarihli hareket replay'i bozmaz — defter yevmiye sırasıyla oynatılır.

    Bugün onaylanan 40 gün önceki ithalat faturası gibi kayıtlar gerçek hayatta olur;
    ortalama maliyet yol bağımlı olduğu için tarih sırasıyla oynatmak farklı sonuç verirdi.
    """
    inventory.opening_stock(
        db_session, product=product, qty=D("10"), unit_cost=D("100"), on_date=TODAY
    )
    # Sonradan yazılan ama TARİHİ geçmişte olan alış.
    inventory.record_movement(
        db_session,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        product_id=product.id,
        movement=InventoryMovement.PURCHASE_IN,
        qty=D("10"),
        unit_cost=D("200"),
        moved_at=datetime.combine(TODAY, datetime.min.time(), tzinfo=UTC) - timedelta(days=40),
    )

    before = _state(db_session, product)
    assert before is not None
    expected_on_hand, expected_avg = before.on_hand_qty, before.avg_cost

    summary = inventory.rebuild_state(db_session, dry_run=True)

    assert summary.mismatches == []
    rebuilt = _state(db_session, product)
    assert rebuilt is not None
    assert (rebuilt.on_hand_qty, rebuilt.avg_cost) == (expected_on_hand, expected_avg)


def test_rebuild_dry_run_reports_without_writing(db_session: Session, product: Product) -> None:
    """`dry_run` yazmaz; sessiz sapmayı raporlar."""
    inventory.opening_stock(
        db_session, product=product, qty=D("10"), unit_cost=D("100"), on_date=TODAY
    )
    state = _state(db_session, product)
    assert state is not None
    state.on_hand_qty = D("999")  # elle bozulmuş durum
    db_session.flush()

    summary = inventory.rebuild_state(db_session, dry_run=True)

    assert str(product.id) in summary.mismatches
    assert _state(db_session, product) is not None
    assert _state(db_session, product).on_hand_qty == D("999")  # type: ignore[union-attr]


# --- API katmanı -------------------------------------------------------------


@pytest.fixture
def api(db_session: Session, store: Store, product: Product) -> Iterator[TestClient]:
    """Test oturumuna bağlı API istemcisi."""

    async def session_override() -> Any:
        yield db_session

    app = create_app()
    app.dependency_overrides[deps.get_session] = session_override
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _headers(api: TestClient, brand: str = "alessi") -> dict[str, str]:
    response = api.post("/auth/dev-login", json={"email": "mert@mokkalabs.com", "brand": brand})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_opening_endpoint_creates_entry(api: TestClient, product: Product) -> None:
    """Açılış girişi ucu (spec §12C.4)."""
    response = api.post(
        "/alessi/inventory/opening",
        json={
            "product_id": str(product.id),
            "qty": "34",
            "unit_cost": "100",
            "on_date": str(TODAY),
        },
        headers=_headers(api),
    )

    assert response.status_code == 201, response.text
    assert response.json()["on_hand_after"] == "34.000"


def test_second_opening_returns_422(api: TestClient, product: Product) -> None:
    """İkinci açılış girişi reddedilir."""
    body = {"product_id": str(product.id), "qty": "34", "unit_cost": "100"}
    api.post("/alessi/inventory/opening", json=body, headers=_headers(api))

    response = api.post("/alessi/inventory/opening", json=body, headers=_headers(api))

    assert response.status_code == 422


def test_stock_endpoint_lists_rows(api: TestClient, product: Product) -> None:
    """Stok & maliyet ekranının kaynağı."""
    api.post(
        "/alessi/inventory/opening",
        json={"product_id": str(product.id), "qty": "10", "unit_cost": "100"},
        headers=_headers(api),
    )

    response = api.get("/alessi/inventory", headers=_headers(api))

    assert response.status_code == 200, response.text
    row = next(item for item in response.json() if item["sku"] == "STOK-1")
    assert row["on_hand"] == "10.000"
    assert row["stock_value"] == "1000.0000"


def test_adjustment_endpoint_requires_reason(api: TestClient, product: Product) -> None:
    """Gerekçesiz düzeltme şema seviyesinde reddedilir."""
    response = api.post(
        "/alessi/inventory/adjust",
        json={"product_id": str(product.id), "qty_delta": "-1", "reason": ""},
        headers=_headers(api),
    )

    assert response.status_code == 422


def test_ledger_endpoint_returns_history(api: TestClient, product: Product) -> None:
    """Hareket defteri okunabilir."""
    api.post(
        "/alessi/inventory/opening",
        json={"product_id": str(product.id), "qty": "10", "unit_cost": "100"},
        headers=_headers(api),
    )

    response = api.get(
        "/alessi/inventory/ledger", params={"product_id": str(product.id)}, headers=_headers(api)
    )

    assert response.status_code == 200, response.text
    assert response.json()[0]["movement"] == "opening"


def test_rebuild_endpoint_reports_no_mismatch(api: TestClient, product: Product) -> None:
    """§12C.11: replay farkı olmamalı."""
    api.post(
        "/alessi/inventory/opening",
        json={"product_id": str(product.id), "qty": "10", "unit_cost": "100"},
        headers=_headers(api),
    )

    response = api.post("/alessi/inventory/rebuild", headers=_headers(api))

    assert response.status_code == 200, response.text
    assert response.json()["mismatches"] == []
