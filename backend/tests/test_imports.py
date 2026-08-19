"""KVN-17: ithalat dosyası modu ve kur farkı takibi (spec §12C.7-8).

Kabul kriterleri (§12C.11):
- EUR mal faturası + TL navlun + EUR sigorta + müşavirlik → satır bazlı landed cost
  elle hesaplananla birebir; ithalat KDV'sinin maliyete GİRMEDİĞİ asserte edilir
- Beyanname kuru 37,50 · ödeme kuru 39,20 → `fx_diff` doğru; **WAC değişmez**
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.context import RequestContext, system_scope, use_context
from app.main import create_app
from app.models.catalog import Product, SkuCost, Supplier
from app.models.enums import (
    ImportCostItemType,
    ImportFileStatus,
    InventoryMovement,
    InvoiceStatus,
    MatchStatus,
    UserRole,
)
from app.models.inventory import (
    ImportFile,
    InventoryLedger,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SkuCostState,
)
from app.services import imports
from tests.profit_factories import make_product, make_store

D = Decimal

BEYANNAME_DATE = date(2026, 7, 10)
BEYANNAME_RATE = D("37.500000")
PAYMENT_RATE = D("39.200000")

# Elle hesap (spec §12C.7 dağıtımı):
#   A: 10 adet × 100 EUR × 37,50 =  37.500 TL   ağırlık 0,40
#   B:  5 adet × 300 EUR × 37,50 =  56.250 TL   ağırlık 0,60
#   mal toplamı                  =  93.750 TL
#   masraf: navlun 12.000 TL + sigorta 200 EUR×37,50=7.500 TL + müşavirlik 3.000 TL
#         =  22.500 TL   (ithalat KDV'si 18.750 TL DAHİL DEĞİL)
#   A payı = 22.500 × 0,40 =  9.000 → birim landed = 3.750 + 900   =  4.650,00
#   B payı = 22.500 × 0,60 = 13.500 → birim landed = 11.250 + 2.700 = 13.950,00
GOODS_TOTAL_TRY = D("93750.00")
EXTRA_TOTAL_TRY = D("22500.00")
IMPORT_VAT = D("18750.00")
LANDED_A = D("4650.000000")
LANDED_B = D("13950.000000")


@pytest.fixture
def store(db_session: Session) -> Iterator[Any]:
    """Alessi mağazası + marka bağlamı (`import_files` bayrağı açık markadır)."""
    from app.models.identity import Brand

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
def supplier(db_session: Session, store: Any) -> Supplier:
    """İtalyan tedarikçi — EUR fatura keser."""
    record = Supplier(
        tenant_id=store.tenant_id,
        name="Alessi S.p.A.",
        vkn="IT00123456789",
        default_currency="EUR",
    )
    db_session.add(record)
    db_session.flush()
    return record


@pytest.fixture
def products(db_session: Session, store: Any) -> tuple[Product, Product]:
    """Dosyadaki iki mal kalemi."""
    first = make_product(db_session, store, "ALS-9090-3", cost=D("3000.0000"))
    second = make_product(db_session, store, "ALS-KTL-01", cost=D("9000.0000"))
    return first, second


@pytest.fixture
def import_file(db_session: Session, store: Any, supplier: Supplier) -> ImportFile:
    """Beyanname kuru sabitlenmiş açık dosya."""
    record = ImportFile(
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        supplier_id=supplier.id,
        file_no="ITH-2026-014",
        beyanname_no="26341300IM123456",
        beyanname_date=BEYANNAME_DATE,
        currency="EUR",
        fx_rate_beyanname=BEYANNAME_RATE,
        import_vat_paid=IMPORT_VAT,
    )
    db_session.add(record)
    db_session.flush()
    return record


@pytest.fixture
def goods_invoice(
    db_session: Session,
    store: Any,
    supplier: Supplier,
    import_file: ImportFile,
    products: tuple[Product, Product],
) -> PurchaseInvoice:
    """EUR mal faturası — dosyaya bağlı, satırları eşleşmiş."""
    first, second = products
    invoice = PurchaseInvoice(
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        supplier_id=supplier.id,
        invoice_no="IT-2026-77",
        invoice_date=BEYANNAME_DATE,
        currency="EUR",
        fx_rate=BEYANNAME_RATE,
        # Basit yurtiçi modun alanı; dosyaya bağlanınca kullanılmamalı.
        landed_cost_extra=D("99999.00"),
        total=D("2500.00"),
        status=InvoiceStatus.PARSED,
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add_all(
        [
            PurchaseInvoiceLine(
                invoice_id=invoice.id,
                raw_text="A — 9090 Espresso 3 Cup",
                product_id=first.id,
                qty=D("10"),
                unit_price_original=D("100.00"),
                unit_price_try=D("3750.00"),
                vat_rate=D("20.00"),
                match_status=MatchStatus.MANUAL,
            ),
            PurchaseInvoiceLine(
                invoice_id=invoice.id,
                raw_text="B — Il Conico Su Isıtıcısı",
                product_id=second.id,
                qty=D("5"),
                unit_price_original=D("300.00"),
                unit_price_try=D("11250.00"),
                vat_rate=D("20.00"),
                match_status=MatchStatus.MANUAL,
            ),
        ]
    )
    db_session.flush()
    imports.attach_invoice(db_session, import_file=import_file, invoice=invoice)
    return invoice


@pytest.fixture
def costed_file(db_session: Session, import_file: ImportFile, goods_invoice: Any) -> ImportFile:
    """Masraf kalemleri girilmiş dosya: TL navlun + EUR sigorta + TL müşavirlik."""
    imports.add_cost_item(
        db_session,
        import_file=import_file,
        item_type=ImportCostItemType.NAVLUN,
        amount_original=D("12000.00"),
        currency="TRY",
        vendor="Med Lojistik",
    )
    imports.add_cost_item(
        db_session,
        import_file=import_file,
        item_type=ImportCostItemType.SIGORTA,
        amount_original=D("200.00"),
        currency="EUR",
    )
    imports.add_cost_item(
        db_session,
        import_file=import_file,
        item_type=ImportCostItemType.GUMRUK_MUSAVIRLIGI,
        amount_original=D("3000.00"),
        currency="TRY",
    )
    return import_file


# --- Landed cost dağıtımı (kabul §12C.11) -----------------------------------


def test_landed_cost_matches_the_hand_calculation(
    db_session: Session, costed_file: ImportFile
) -> None:
    """§12C.11: EUR mal + TL navlun + EUR sigorta + müşavirlik → satır bazlı maliyet."""
    lines = imports.landed_costs(db_session, import_file=costed_file)

    assert len(lines) == 2
    first, second = lines
    assert first.goods_total_try == D("37500.00")
    assert second.goods_total_try == D("56250.00")
    assert first.extra_share_try == D("9000.00")
    assert second.extra_share_try == D("13500.00")
    assert first.landed_unit_cost_try == LANDED_A
    assert second.landed_unit_cost_try == LANDED_B


def test_import_vat_is_not_part_of_the_cost(db_session: Session, costed_file: ImportFile) -> None:
    """§12C.7: gümrükte ödenen KDV indirilecek KDV'dir, maliyete ASLA girmez."""
    total = imports.import_cost_total(db_session, import_file_id=costed_file.id)

    assert costed_file.import_vat_paid == IMPORT_VAT
    assert total == EXTRA_TOTAL_TRY
    assert total < EXTRA_TOTAL_TRY + IMPORT_VAT


def test_allocated_shares_sum_to_the_cost_total(
    db_session: Session, costed_file: ImportFile
) -> None:
    """Dağıtım kuruş kaybetmez: payların toplamı masraf toplamına eşittir."""
    lines = imports.landed_costs(db_session, import_file=costed_file)

    assert sum(line.extra_share_try for line in lines) == EXTRA_TOTAL_TRY
    assert sum(line.goods_total_try for line in lines) == GOODS_TOTAL_TRY


def test_file_mode_ignores_the_simple_landed_cost_extra(
    db_session: Session, costed_file: ImportFile, goods_invoice: PurchaseInvoice
) -> None:
    """§12C.7: `landed_cost_extra` yalnızca basit yurtiçi moda aittir; iki kaynak sayılmaz."""
    assert goods_invoice.landed_cost_extra == D("0")

    lines = imports.landed_costs(db_session, import_file=costed_file)
    assert sum(line.extra_share_try for line in lines) == EXTRA_TOTAL_TRY


def test_foreign_currency_item_without_a_rate_is_rejected(
    db_session: Session, store: Any, supplier: Supplier
) -> None:
    """Kur yoksa akış durur — uydurma kurla maliyet yazılmaz."""
    record = ImportFile(
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        supplier_id=supplier.id,
        file_no="ITH-KURSUZ",
        currency="EUR",
    )
    db_session.add(record)
    db_session.flush()

    with pytest.raises(imports.ImportFileError, match="kur gerekli"):
        imports.add_cost_item(
            db_session,
            import_file=record,
            item_type=ImportCostItemType.NAVLUN,
            amount_original=D("100.00"),
            currency="EUR",
        )


# --- Onay zinciri (§12C.7 → §12C.3.5) ---------------------------------------


def test_confirm_writes_ledger_wac_and_cost_version(
    db_session: Session, costed_file: ImportFile, products: tuple[Product, Product]
) -> None:
    """Dosya onayı 12C.3 zincirini çalıştırır: ledger + WAC + `sku_costs`."""
    first, second = products

    totals = imports.confirm_file(db_session, import_file=costed_file, user="mert@mokkalabs.com")

    assert totals == {"invoices": 1, "lines": 2, "ledger_entries": 2}
    assert costed_file.status is ImportFileStatus.CONFIRMED

    entries = db_session.scalars(
        select(InventoryLedger).where(InventoryLedger.movement == InventoryMovement.PURCHASE_IN)
    ).all()
    assert {entry.product_id for entry in entries} == {first.id, second.id}

    state = db_session.scalar(select(SkuCostState).where(SkuCostState.product_id == first.id))
    assert state is not None
    assert state.on_hand_qty == D("10")
    assert state.avg_cost == LANDED_A

    versions = db_session.scalars(select(SkuCost).where(SkuCost.product_id == first.id)).all()
    assert any(version.invoice_ref == "IT-2026-77" for version in versions)


def test_confirmed_file_cannot_be_confirmed_twice(
    db_session: Session, costed_file: ImportFile
) -> None:
    """Onaylanmış dosya değiştirilemez; düzeltme ancak ters kayıtla yapılır."""
    imports.confirm_file(db_session, import_file=costed_file)

    with pytest.raises(imports.ImportFileError, match="zaten onaylanmış"):
        imports.confirm_file(db_session, import_file=costed_file)


def test_confirmed_file_rejects_new_cost_items(
    db_session: Session, costed_file: ImportFile
) -> None:
    """Onaydan sonra masraf eklenirse dağıtım geriye dönük değişirdi — reddedilir."""
    imports.confirm_file(db_session, import_file=costed_file)

    with pytest.raises(imports.ImportFileError, match="Onaylanmış dosyaya"):
        imports.add_cost_item(
            db_session,
            import_file=costed_file,
            item_type=ImportCostItemType.ARDIYE_LIMAN,
            amount_original=D("500.00"),
            currency="TRY",
        )


def test_file_without_invoice_cannot_be_confirmed(
    db_session: Session, import_file: ImportFile
) -> None:
    """Mal faturası olmayan dosya onaylanamaz — neyin stoka gireceği belirsiz."""
    with pytest.raises(imports.ImportFileError, match="mal faturası yok"):
        imports.confirm_file(db_session, import_file=import_file)


# --- Kur farkı (spec §12C.8, kabul §12C.11) ---------------------------------


def test_payment_records_the_fx_difference(db_session: Session, costed_file: ImportFile) -> None:
    """§12C.11: beyanname 37,50 · ödeme 39,20 → fark = tutar × 1,70, işareti gider yönünde."""
    payment = imports.record_payment(
        db_session,
        import_file=costed_file,
        pay_date=date(2026, 8, 1),
        amount_original=D("2500.00"),
        fx_rate_payment=PAYMENT_RATE,
    )

    assert payment.currency == "EUR"
    assert payment.fx_diff_try == D("-4250.00")  # 2500 × (37,50 − 39,20), negatif = gider


def test_fx_difference_does_not_touch_the_average_cost(
    db_session: Session, costed_file: ImportFile, products: tuple[Product, Product]
) -> None:
    """§12C.8: kur farkı ürün maliyetine GİRMEZ — WAC beyanname kuruyla sabittir."""
    first, _ = products
    imports.confirm_file(db_session, import_file=costed_file)
    before = db_session.scalar(select(SkuCostState).where(SkuCostState.product_id == first.id))
    assert before is not None
    avg_before = before.avg_cost

    imports.record_payment(
        db_session,
        import_file=costed_file,
        pay_date=date(2026, 8, 1),
        amount_original=D("2500.00"),
        fx_rate_payment=PAYMENT_RATE,
    )

    after = db_session.scalar(select(SkuCostState).where(SkuCostState.product_id == first.id))
    assert after is not None
    assert after.avg_cost == avg_before == LANDED_A


def test_fx_exposure_reports_open_position(db_session: Session, costed_file: ImportFile) -> None:
    """§12C.8 raporu: açık pozisyon, maliyet kuru, gerçekleşmiş fark."""
    imports.record_payment(
        db_session,
        import_file=costed_file,
        pay_date=date(2026, 8, 1),
        amount_original=D("1000.00"),
        fx_rate_payment=PAYMENT_RATE,
    )

    rows = imports.fx_exposure(db_session)

    assert len(rows) == 1
    row = rows[0]
    assert row.currency == "EUR"
    # Faturalanan 2.500 EUR (10×100 + 5×300), ödenen 1.000 EUR.
    assert row.paid_amount == D("1000.00")
    assert row.open_amount == D("1500.00")
    assert row.cost_fx_rate == BEYANNAME_RATE
    assert row.realized_fx_diff_try == D("-1700.00")


def test_payment_amount_must_be_positive(db_session: Session, costed_file: ImportFile) -> None:
    """Sıfır/negatif ödeme anlamsızdır."""
    with pytest.raises(imports.ImportFileError, match="pozitif"):
        imports.record_payment(
            db_session,
            import_file=costed_file,
            pay_date=date(2026, 8, 1),
            amount_original=D("0"),
            fx_rate_payment=PAYMENT_RATE,
        )


# --- API ---------------------------------------------------------------------


@pytest.fixture
def api(db_session: Session, store: Any, supplier: Supplier) -> Iterator[TestClient]:
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


def test_list_endpoint_returns_files(api: TestClient, costed_file: ImportFile) -> None:
    """Dosya listesi marka kapsamlıdır."""
    response = api.get("/alessi/imports", headers=_headers(api))

    assert response.status_code == 200, response.text
    assert [row["file_no"] for row in response.json()] == ["ITH-2026-014"]


def test_detail_endpoint_returns_allocation_preview(
    api: TestClient, costed_file: ImportFile
) -> None:
    """Detay ucu dağıtım önizlemesini döner; hiçbir şey yazılmaz."""
    response = api.get(f"/alessi/imports/{costed_file.id}", headers=_headers(api))

    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["cost_total_try"]) == EXTRA_TOTAL_TRY
    assert Decimal(body["goods_total_try"]) == GOODS_TOTAL_TRY
    assert [Decimal(line["landed_unit_cost_try"]) for line in body["lines"]] == [
        LANDED_A,
        LANDED_B,
    ]
    assert costed_file.status is ImportFileStatus.OPEN


def test_confirm_endpoint_writes_stock(api: TestClient, costed_file: ImportFile) -> None:
    """Onay ucu zinciri çalıştırır."""
    response = api.post(f"/alessi/imports/{costed_file.id}/confirm", headers=_headers(api))

    assert response.status_code == 200, response.text
    assert response.json() == {"invoices": 1, "lines": 2, "ledger_entries": 2}


def test_payment_endpoint_returns_fx_difference(api: TestClient, costed_file: ImportFile) -> None:
    """Ödeme ucu kur farkını hesaplayıp döner."""
    response = api.post(
        f"/alessi/imports/{costed_file.id}/payments",
        json={
            "pay_date": "2026-08-01",
            "amount_original": "2500.00",
            "fx_rate_payment": "39.20",
        },
        headers=_headers(api),
    )

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["fx_diff_try"]) == D("-4250.00")


def test_fx_exposure_endpoint(api: TestClient, costed_file: ImportFile) -> None:
    """Rapor ucu açık pozisyonu döner."""
    response = api.get("/alessi/imports/fx-exposure", headers=_headers(api))

    assert response.status_code == 200, response.text
    assert response.json()[0]["currency"] == "EUR"


def test_module_returns_404_when_the_feature_flag_is_off(
    api: TestClient, costed_file: ImportFile
) -> None:
    """CLAUDE.md §2: kapalı modül 404 döner (403 değil — varlığı sızdırılmaz)."""
    headers = _headers(api, brand="kahveji")

    assert api.get("/kahveji/imports", headers=headers).status_code == 404
    assert api.get("/kahveji/imports/fx-exposure", headers=headers).status_code == 404
    assert (
        api.post(
            "/kahveji/imports",
            json={"supplier_id": str(costed_file.supplier_id), "file_no": "X"},
            headers=headers,
        ).status_code
        == 404
    )


def test_cost_item_endpoint_rejects_confirmed_file(
    api: TestClient, db_session: Session, costed_file: ImportFile
) -> None:
    """Onaylanmış dosyaya masraf eklenemez → 422."""
    imports.confirm_file(db_session, import_file=costed_file)

    response = api.post(
        f"/alessi/imports/{costed_file.id}/cost-items",
        json={"item_type": "ardiye_liman", "amount_original": "500.00", "currency": "TRY"},
        headers=_headers(api),
    )

    assert response.status_code == 422, response.text
