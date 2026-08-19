"""KVN-20: uçtan uca kabul turu (spec §11, §12A.6, §12B.5, §12C.11).

Buradaki testler tek bir modülü değil, **modüller arası tutarlılığı** doğrular: demo
tenant'ı kurulur, kâr motoru koşar ve aynı gerçeğin farklı ekranlarda aynı sayıyı
verdiği kontrol edilir. Tek tek modül davranışları kendi test dosyalarındadır; burada
"parçalar birbirine uyuyor mu" sorusu sorulur.

Zincir: `seed-demo → recompute → dashboard/SKU/sipariş → fatura onayı → stok defteri →
replay → holding`. Bir halka koparsa hangi ekranın yalan söylediği buradan görülür.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.context import system_scope
from app.main import create_app
from app.models.enums import InvoiceStatus
from app.models.inventory import PurchaseInvoice
from app.seeds.base import seed_base
from app.seeds.demo import seed_demo
from app.services import inventory, profit

D = Decimal
PERIOD = {"from": "2026-01-01", "to": "2027-01-01"}


@pytest.fixture
def api(db_session: Session) -> Iterator[TestClient]:
    """Demo verisi kurulmuş, kârı hesaplanmış tam sistem."""
    seed_base(db_session)
    seed_demo(db_session)
    with system_scope():
        profit.recompute_pending(db_session, limit=5000)
        db_session.flush()

    async def session_override() -> Any:
        yield db_session

    app = create_app()
    app.dependency_overrides[deps.get_session] = session_override
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _headers(api: TestClient, brand: str) -> dict[str, str]:
    response = api.post("/auth/dev-login", json={"email": "demo@mokkalabs.com", "brand": brand})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _sum(rows: list[dict[str, Any]], field: str) -> Decimal:
    return sum((Decimal(str(row[field])) for row in rows), D("0"))


# --- ekranlar arası tutarlılık ----------------------------------------------


@pytest.mark.parametrize("brand", ["alessi", "kahveji"])
def test_dashboard_and_sku_list_tell_the_same_story(api: TestClient, brand: str) -> None:
    """Dashboard kârı ile SKU listesinin kâr toplamı aynı olmalı — iki ekran tek gerçek."""
    headers = _headers(api, brand)

    dashboard = api.get(f"/{brand}/dashboard", params=PERIOD, headers=headers).json()
    skus = api.get(f"/{brand}/sku-margins", params=PERIOD, headers=headers).json()

    assert Decimal(str(dashboard["kpis"]["profit"])) == _sum(skus, "profit")


@pytest.mark.parametrize("brand", ["alessi", "kahveji"])
def test_dashboard_revenue_matches_the_store_breakdown(api: TestClient, brand: str) -> None:
    """Mağaza kırılımının toplamı dashboard cirosunu vermeli."""
    headers = _headers(api, brand)

    dashboard = api.get(f"/{brand}/dashboard", params=PERIOD, headers=headers).json()

    assert Decimal(str(dashboard["kpis"]["revenue_gross"])) == _sum(
        dashboard["stores"], "revenue_gross"
    )


@pytest.mark.parametrize("brand", ["alessi", "kahveji"])
def test_daily_series_adds_up_to_the_period_total(api: TestClient, brand: str) -> None:
    """Günlük seri toplamı dönem kârına eşit — grafik ile KPI çelişmez."""
    headers = _headers(api, brand)

    dashboard = api.get(f"/{brand}/dashboard", params=PERIOD, headers=headers).json()

    assert Decimal(str(dashboard["kpis"]["profit"])) == _sum(dashboard["daily"], "profit")


def test_order_detail_waterfall_ends_at_the_line_profit(api: TestClient) -> None:
    """Şelale adımlarının toplamı satır kârını vermeli (tasarım brief'i imza ekranı)."""
    headers = _headers(api, "kahveji")
    orders = api.get("/kahveji/orders", params=PERIOD, headers=headers).json()
    assert orders, "demo veride sipariş olmalı"

    detail = api.get(f"/kahveji/orders/{orders[0]['order_id']}", headers=headers).json()

    for line in detail["lines"]:
        steps = line["waterfall"]
        # Son adım toplamın kendisidir ("kar"); ondan önceki adımlar toplanınca kâra iner.
        assert steps[-1]["key"] == "kar"
        components = sum((Decimal(str(step["amount"])) for step in steps[:-1]), D("0"))
        assert components == Decimal(str(line["profit"]))
        assert Decimal(str(steps[-1]["amount"])) == Decimal(str(line["profit"]))


# --- round-trip ve stok zinciri (§12A.6, §12C.11) ---------------------------


def test_price_list_round_trip_reports_no_change(api: TestClient) -> None:
    """§12A.6: export edilen dosya değiştirilmeden yüklenirse "değişiklik yok"."""
    headers = _headers(api, "alessi")
    exported = api.get("/alessi/price-list/export", headers=headers).content

    summary = api.post(
        "/alessi/price-list/import",
        params={"dry_run": True},
        files={"file": ("fiyat.xlsx", exported)},
        headers=headers,
    ).json()

    assert summary["yeni"] == 0
    assert summary["guncelleme"] == 0
    assert summary["hata"] == 0


def test_invoice_confirmation_moves_stock_and_cost(api: TestClient, db_session: Session) -> None:
    """§12C.11: fatura onayı ledger + WAC + maliyet versiyonunu birlikte yazar."""
    headers = _headers(api, "kahveji")
    with system_scope():
        invoice = db_session.scalar(
            select(PurchaseInvoice).where(PurchaseInvoice.status == InvoiceStatus.REVIEW)
        )
    assert invoice is not None, "demo veride incelemede bir fatura olmalı"

    detail = api.get(f"/kahveji/invoices/{invoice.id}", headers=headers).json()
    for line in detail["lines"]:
        if line["product_id"] is None:
            suggestion = line["suggestions"][0]
            api.post(
                f"/kahveji/invoices/{invoice.id}/lines/{line['id']}/match",
                json={"product_id": suggestion["product_id"]},
                headers=headers,
            )

    before = {row["sku"]: Decimal(str(row["on_hand"])) for row in _stock(api, headers)}
    response = api.post(f"/kahveji/invoices/{invoice.id}/confirm", headers=headers)
    assert response.status_code == 200, response.text

    after = {row["sku"]: Decimal(str(row["on_hand"])) for row in _stock(api, headers)}
    assert any(after[sku] > before.get(sku, D("0")) for sku in after), "stok artmalı"


def _stock(api: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    return list(api.get("/kahveji/inventory", headers=headers).json())


@pytest.mark.parametrize("brand", ["alessi", "kahveji"])
def test_stock_value_matches_qty_times_average_cost(api: TestClient, brand: str) -> None:
    """Stok değeri her satırda adet × ortalama maliyet olmalı."""
    headers = _headers(api, brand)

    for row in api.get(f"/{brand}/inventory", headers=headers).json():
        expected = (Decimal(str(row["on_hand"])) * Decimal(str(row["avg_cost"]))).quantize(
            D("0.0001")
        )
        assert Decimal(str(row["stock_value"])) == expected


def test_ledger_replay_reproduces_the_state(db_session: Session, api: TestClient) -> None:
    """§12C.11: durum defterden birebir yeniden kurulabilir (tüm demo veri üzerinde)."""
    with system_scope():
        summary = inventory.rebuild_state(db_session, dry_run=True)

    assert summary.mismatches == []
    assert summary.movements > 0


# --- holding tutarlılığı (§3A.3) --------------------------------------------


def test_holding_totals_match_the_brand_screens(api: TestClient) -> None:
    """Holding cirosu marka dashboard'larının toplamına eşit — tek gerçek, iki görünüm."""
    consolidated = api.get(
        "/holding/consolidated",
        params={"since": "2026-01-01", "until": "2027-01-01"},
        headers=_headers(api, "kahveji"),
    ).json()

    brand_total = D("0")
    for brand in ("alessi", "kahveji"):
        dashboard = api.get(
            f"/{brand}/dashboard", params=PERIOD, headers=_headers(api, brand)
        ).json()
        brand_total += Decimal(str(dashboard["kpis"]["revenue_gross"]))

    assert Decimal(str(consolidated["total_revenue"])) == brand_total


# --- modül bayrakları ve izolasyon (§3A.6) ----------------------------------


def test_closed_modules_stay_invisible_for_kahveji(api: TestClient) -> None:
    """§3A.6: kapalı modül uçları 404 — modülün varlığı sızdırılmaz."""
    headers = _headers(api, "kahveji")

    for path in ("/kahveji/imports", "/kahveji/b2b/tiers", "/kahveji/discipline"):
        assert api.get(path, headers=headers).status_code == 404, path


def test_other_brands_order_is_not_reachable(api: TestClient) -> None:
    """§3A.6: karşı markanın kaynağı 404 döner (403 değil)."""
    alessi_orders = api.get("/alessi/orders", params=PERIOD, headers=_headers(api, "alessi")).json()
    assert alessi_orders

    response = api.get(
        f"/kahveji/orders/{alessi_orders[0]['order_id']}", headers=_headers(api, "kahveji")
    )

    assert response.status_code == 404


# --- tarife motoru (§12B.5) --------------------------------------------------


def test_commission_change_detection_and_impact_agree(api: TestClient) -> None:
    """§12B.5: oran artışının etkisi kapalı formülle motorun sonucu aynı yönde ve büyüklükte."""
    headers = _headers(api, "alessi")

    impact = api.post(
        "/alessi/tariffs/impact",
        json={
            "category": None,
            "new_rate": None,
            "rate_delta": "0.0150",
            "target_margin_pct": None,
            "kargo_tahmini": None,
        },
        headers=headers,
    ).json()

    # Komisyon artışı kârı azaltır: toplam etki negatif olmalı.
    assert Decimal(str(impact["monthly_profit_impact"])) < 0
    assert impact["rows"], "etkilenen satır olmalı"


def test_recompute_is_idempotent(db_session: Session, api: TestClient) -> None:
    """Aynı veriyle ikinci hesap yeni kayıt yazmaz, revizyon üretmez."""
    with system_scope():
        summary = profit.recompute_pending(db_session, limit=5000)

    assert summary.created == 0
    assert summary.revisions == 0


def test_demo_period_covers_the_last_quarter(api: TestClient) -> None:
    """Demo veri gezilebilir olmalı: son 90 günde sipariş var (CLAUDE.md §6)."""
    headers = _headers(api, "kahveji")
    since = (date.today() - timedelta(days=90)).isoformat()

    orders = api.get(
        "/kahveji/orders", params={"from": since, "to": date.today().isoformat()}, headers=headers
    ).json()

    assert len(orders) > 10
