"""KVN-15: PDF fatura ayrıştırma, öğrenen SKU eşleştirme, onay (spec §12C.3).

Kabul kriterleri:
- Fatura PDF'i fixture olarak repoda; parser + review + confirm zinciri uçtan uca (§12C.11)
- Onaylanmış faturayı değiştirme girişimi → 409 (§12C.11)
- WAC formülü: 34@100 + 100@120 → 114,9254 (§12C.1, §12C.11)
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.context import RequestContext, system_scope, use_context
from app.engine.inventory import StockState, apply_inbound, apply_outbound
from app.main import create_app
from app.models.catalog import Product, SkuCost, Supplier
from app.models.enums import (
    CostSource,
    InventoryMovement,
    InvoiceStatus,
    MatchStatus,
    UserRole,
)
from app.models.inventory import (
    InventoryLedger,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SkuCostState,
    SupplierProductMap,
)
from app.services import invoices
from tests.profit_factories import make_product, make_store

D = Decimal
INVOICE_DATE = date(2026, 8, 5)
FIXTURE = Path(__file__).parent / "fixtures" / "invoices" / "earsiv_fatura_ornek.pdf"


@pytest.fixture
def payload() -> bytes:
    """E-arşiv fatura biçimini taklit eden PDF."""
    return FIXTURE.read_bytes()


@pytest.fixture
def store(db_session: Session) -> Iterator[Any]:
    """Mağaza + marka bağlamı."""
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
    """Kahve tedarikçisi."""
    record = Supplier(
        tenant_id=store.tenant_id,
        name="Kahve Tedarik A.Ş.",
        vkn="1234567890",
        default_currency="TRY",
    )
    db_session.add(record)
    db_session.flush()
    return record


@pytest.fixture
def catalog(db_session: Session, store: Any) -> dict[str, Product]:
    """Faturadaki ürünlerin Kavun karşılıkları — gerçekçi adlarla."""
    products = {
        "brezilya": make_product(
            db_session, store, "KHV-BRZ-1K", cost=D("400.0000"), category="Kahve/Tek Origin"
        ),
        "kolombiya": make_product(
            db_session, store, "KHV-KOL-1K", cost=D("480.0000"), category="Kahve/Tek Origin"
        ),
        "filtre": make_product(
            db_session, store, "KHV-V60-FLT", cost=D("40.0000"), category="Ekipman/Sarf"
        ),
    }
    # `make_product` adı SKU olarak kurar; eşleştirme testi gerçekçi ad ister.
    products["brezilya"].name = "Brezilya Cerrado 1kg Çekirdek"
    products["kolombiya"].name = "Kolombiya Huila 1kg Çekirdek"
    products["filtre"].name = "V60 Filtre Kağıdı 100'lü"
    db_session.flush()
    return products


# --- WAC formülü (spec §12C.1, kabul §12C.11) -------------------------------


def test_wac_formula_matches_the_spec_example() -> None:
    """§12C.11: 34 adet @100 + 100 adet @120 → ortalama 114,9254."""
    state = apply_inbound(StockState.empty(), qty=D("34"), unit_cost=D("100"))
    state = apply_inbound(state, qty=D("100"), unit_cost=D("120"))

    assert state.on_hand == D("134")
    assert state.avg_cost.quantize(D("0.0001")) == D("114.9254")


def test_outbound_does_not_change_average() -> None:
    """§12C.1: satış stoku düşürür, ortalamayı DEĞİŞTİRMEZ."""
    state = apply_inbound(StockState.empty(), qty=D("34"), unit_cost=D("100"))
    state = apply_inbound(state, qty=D("100"), unit_cost=D("120"))
    before = state.avg_cost

    state = apply_outbound(state, qty=D("50"))

    assert state.on_hand == D("84")
    assert state.avg_cost == before


def test_further_inbound_updates_average_correctly() -> None:
    """§12C.11: 50 satıştan sonra 20 adet @130 alış → ortalama doğru güncellenir."""
    state = apply_inbound(StockState.empty(), qty=D("34"), unit_cost=D("100"))
    state = apply_inbound(state, qty=D("100"), unit_cost=D("120"))
    state = apply_outbound(state, qty=D("50"))

    state = apply_inbound(state, qty=D("20"), unit_cost=D("130"))

    # (84 × 114,925373… + 20 × 130) / 104
    expected = (D("84") * D("114.925373") + D("20") * D("130")) / D("104")
    assert state.on_hand == D("104")
    assert abs(state.avg_cost - expected) <= D("0.0001")


def test_negative_stock_normalises_on_first_inbound() -> None:
    """§12C.4: negatif stokta ortalama değişmez, ilk alışta normalleşir."""
    state = apply_outbound(StockState.empty(), qty=D("5"))
    assert state.on_hand == D("-5")
    assert state.avg_cost == D("0")

    state = apply_inbound(state, qty=D("10"), unit_cost=D("120"))

    assert state.on_hand == D("5")
    assert state.avg_cost == D("120.000000")


# --- PDF ayrıştırma (spec §12C.3.1-2) ---------------------------------------


def test_pdf_lines_are_extracted(payload: bytes) -> None:
    """§12C.11: fatura PDF'i fixture'dan okunur; alanlar doğru ayrışır."""
    text = invoices.extract_text(payload)
    lines = invoices.extract_lines(text)

    assert len(lines) == 3
    first = lines[0]
    assert "Brezilya" in first.name
    assert first.qty == D("20")
    assert first.unit_price == D("420.00")
    assert first.vat_rate == D("1")
    assert first.line_total == D("8400.00")


def test_summary_rows_are_not_treated_as_lines(payload: bytes) -> None:
    """Ara toplam/KDV satırları veri satırı sayılmaz."""
    lines = invoices.extract_lines(invoices.extract_text(payload))

    assert not any("Toplam" in line.name for line in lines)


def test_invoice_total_is_read(payload: bytes) -> None:
    """Genel toplam okunur (doğrulamanın girdisi)."""
    assert invoices.extract_total(invoices.extract_text(payload)) == D("15750.00")


def test_totals_validation_passes_within_tolerance(payload: bytes) -> None:
    """§12C.3.3: satır toplamı ± fatura toplamı 0,10 TL toleransında."""
    text = invoices.extract_text(payload)
    validation = invoices.validate_totals(
        invoices.extract_lines(text), invoices.extract_total(text)
    )

    assert validation.ok
    assert validation.lines_total == D("15750.0000")


def test_totals_mismatch_is_reported() -> None:
    """§12C.3.3: tutmayan toplam sessiz geçilmez."""
    lines = invoices.extract_lines("Kahve 10 100,00 1 1.000,00")
    validation = invoices.validate_totals(lines, D("900.00"))

    assert not validation.ok
    assert "tutmuyor" in validation.message


def test_non_pdf_payload_is_rejected() -> None:
    """PDF olmayan dosya anlaşılır hata verir."""
    with pytest.raises(invoices.InvoiceError, match="okunamadı"):
        invoices.extract_text(b"bu bir pdf degil")


# --- öğrenen eşleştirme (spec §12C.3.4) -------------------------------------


def test_barcode_match_wins(db_session: Session, store: Any, supplier: Supplier) -> None:
    """Eşleştirme sırası: önce barkod."""
    product = make_product(db_session, store, "BARKOD-1")
    product.barcode = "8690000000001"
    db_session.flush()

    match = invoices.match_line(
        db_session, supplier_id=supplier.id, raw_name="alakasiz isim", barcode="8690000000001"
    )

    assert match.product is not None and match.product.id == product.id
    assert match.status is MatchStatus.AUTO
    assert match.reason == "barkod"


def test_fuzzy_result_is_a_suggestion_not_an_automatic_match(
    db_session: Session, store: Any, supplier: Supplier, catalog: dict[str, Product]
) -> None:
    """§12C.3.4: fuzzy sonuç OTOMATİK kabul edilmez, kullanıcı onayı şarttır."""
    match = invoices.match_line(
        db_session, supplier_id=supplier.id, raw_name="V60 Filtre Kagidi 100lu"
    )

    assert match.product is None
    assert match.status is MatchStatus.UNMATCHED
    assert match.suggestions
    assert match.suggestions[0][0].sku == "KHV-V60-FLT"


def test_confirmed_match_is_learned_and_not_asked_again(
    db_session: Session, store: Any, supplier: Supplier, catalog: dict[str, Product], payload: bytes
) -> None:
    """§12C.3.4: "aynı tedarikçiden aynı ürün bir daha sorulmaz"."""
    result = invoices.upload_invoice(
        db_session,
        payload,
        supplier=supplier,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        invoice_no="KTA-1",
        invoice_date=INVOICE_DATE,
    )
    line = db_session.scalars(
        select(PurchaseInvoiceLine).where(PurchaseInvoiceLine.invoice_id == result.invoice.id)
    ).first()
    assert line is not None

    invoices.confirm_match(
        db_session, supplier_id=supplier.id, line=line, product=catalog["brezilya"]
    )

    assert line.match_status is MatchStatus.MANUAL
    assert db_session.scalar(select(SupplierProductMap)) is not None

    # Aynı isim ikinci faturada otomatik eşleşir.
    again = invoices.match_line(db_session, supplier_id=supplier.id, raw_name=line.raw_text)
    assert again.product is not None and again.product.id == catalog["brezilya"].id
    assert again.status is MatchStatus.AUTO
    assert again.reason == "öğrenilmiş eşleşme"


def test_learning_is_supplier_scoped(
    db_session: Session, store: Any, supplier: Supplier, catalog: dict[str, Product]
) -> None:
    """Öğrenilen eşleşme yalnızca o tedarikçi için geçerlidir."""
    other = Supplier(tenant_id=store.tenant_id, name="Başka Tedarik", default_currency="TRY")
    db_session.add(other)
    db_session.flush()
    db_session.add(
        SupplierProductMap(
            supplier_id=supplier.id,
            raw_name_normalized=invoices.normalize("Ozel Urun Adi"),
            product_id=catalog["brezilya"].id,
        )
    )
    db_session.flush()

    assert (
        invoices.match_line(db_session, supplier_id=supplier.id, raw_name="Ozel Urun Adi").product
        is not None
    )
    assert (
        invoices.match_line(db_session, supplier_id=other.id, raw_name="Ozel Urun Adi").product
        is None
    )


# --- yükleme (spec §12C.3.1-3) ----------------------------------------------


def test_upload_creates_invoice_without_touching_stock(
    db_session: Session, store: Any, supplier: Supplier, payload: bytes
) -> None:
    """§12C.3: ayrıştırma sonucu ASLA doğrudan stoka yazılmaz."""
    result = invoices.upload_invoice(
        db_session,
        payload,
        supplier=supplier,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        invoice_no="KTA-2",
        invoice_date=INVOICE_DATE,
    )

    assert result.invoice.status is InvoiceStatus.PARSED
    assert result.validation.ok
    assert db_session.scalar(select(InventoryLedger)) is None
    assert db_session.scalar(select(SkuCostState)) is None


def test_upload_with_mismatched_total_stays_in_review(
    db_session: Session, store: Any, supplier: Supplier, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§12C.3.3: toplam tutmuyorsa fatura `review` durumunda kalır."""
    monkeypatch.setattr(
        invoices, "extract_text", lambda _: "Kahve 10 100,00 1 1.000,00\nGenel Toplam: 900,00"
    )

    result = invoices.upload_invoice(
        db_session,
        b"%PDF-",
        supplier=supplier,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        invoice_no="KTA-3",
        invoice_date=INVOICE_DATE,
    )

    assert result.invoice.status is InvoiceStatus.REVIEW
    assert not result.validation.ok


def test_upload_converts_foreign_currency_with_fx_rate(
    db_session: Session, store: Any, supplier: Supplier, payload: bytes
) -> None:
    """§12C.2: EUR faturada orijinal tutar saklanır, TL kurla hesaplanır."""
    result = invoices.upload_invoice(
        db_session,
        payload,
        supplier=supplier,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        invoice_no="KTA-EUR",
        invoice_date=INVOICE_DATE,
        currency="EUR",
        fx_rate=D("37.5000"),
    )

    line = db_session.scalars(
        select(PurchaseInvoiceLine).where(PurchaseInvoiceLine.invoice_id == result.invoice.id)
    ).first()
    assert line is not None
    assert line.unit_price_original == D("420.00")
    assert line.unit_price_try == D("15750.0000")  # 420 × 37,50


# --- onay (spec §12C.3.5-6) --------------------------------------------------


def _matched_invoice(
    db_session: Session, store: Any, supplier: Supplier, catalog: dict[str, Product], payload: bytes
) -> PurchaseInvoice:
    """Yüklenmiş ve tüm satırları eşleştirilmiş fatura."""
    result = invoices.upload_invoice(
        db_session,
        payload,
        supplier=supplier,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        invoice_no=f"KTA-{len(catalog)}-{store.id.hex[:4]}",
        invoice_date=INVOICE_DATE,
    )
    lines = db_session.scalars(
        select(PurchaseInvoiceLine).where(PurchaseInvoiceLine.invoice_id == result.invoice.id)
    ).all()
    for line, key in zip(lines, ("brezilya", "kolombiya", "filtre"), strict=True):
        invoices.confirm_match(db_session, supplier_id=supplier.id, line=line, product=catalog[key])
    return result.invoice


def test_confirm_writes_ledger_state_and_cost_version(
    db_session: Session, store: Any, supplier: Supplier, catalog: dict[str, Product], payload: bytes
) -> None:
    """§12C.3.5: onayda ledger + WAC + `sku_costs` birlikte yazılır."""
    invoice = _matched_invoice(db_session, store, supplier, catalog, payload)

    summary = invoices.confirm_invoice(db_session, invoice)

    assert invoice.status is InvoiceStatus.CONFIRMED
    assert summary.ledger_entries == 3
    entries = db_session.scalars(select(InventoryLedger)).all()
    assert all(entry.movement is InventoryMovement.PURCHASE_IN for entry in entries)

    state = db_session.scalar(
        select(SkuCostState).where(SkuCostState.product_id == catalog["brezilya"].id)
    )
    assert state is not None
    assert state.on_hand_qty == D("20")
    assert state.avg_cost == D("420.000000")

    cost = db_session.scalar(
        select(SkuCost).where(
            SkuCost.product_id == catalog["brezilya"].id,
            SkuCost.source == CostSource.INVOICE_WAC,
            SkuCost.invoice_ref == invoice.invoice_no,
        )
    )
    assert cost is not None
    assert cost.effective_from == INVOICE_DATE
    assert cost.unit_cost == D("420.0000")


def test_confirm_applies_wac_over_existing_stock(
    db_session: Session, store: Any, supplier: Supplier, catalog: dict[str, Product], payload: bytes
) -> None:
    """§12C.1: mevcut stok varsa ortalama formülle güncellenir."""
    db_session.add(
        SkuCostState(
            product_id=catalog["brezilya"].id,
            on_hand_qty=D("34"),
            avg_cost=D("100.000000"),
        )
    )
    db_session.flush()
    invoice = _matched_invoice(db_session, store, supplier, catalog, payload)

    invoices.confirm_invoice(db_session, invoice)

    state = db_session.scalar(
        select(SkuCostState).where(SkuCostState.product_id == catalog["brezilya"].id)
    )
    assert state is not None
    # (34×100 + 20×420) / 54
    expected = (D("34") * D("100") + D("20") * D("420")) / D("54")
    assert state.on_hand_qty == D("54")
    assert abs(state.avg_cost - expected) <= D("0.000001")


def test_landed_cost_is_allocated_by_amount(
    db_session: Session, store: Any, supplier: Supplier, catalog: dict[str, Product], payload: bytes
) -> None:
    """§12C.2: navlun/gümrük satırlara tutar ağırlıklı dağıtılır."""
    result = invoices.upload_invoice(
        db_session,
        payload,
        supplier=supplier,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        invoice_no="KTA-LANDED",
        invoice_date=INVOICE_DATE,
        landed_cost_extra=D("1575.00"),  # toplamın %10'u
    )
    lines = db_session.scalars(
        select(PurchaseInvoiceLine).where(PurchaseInvoiceLine.invoice_id == result.invoice.id)
    ).all()
    for line, key in zip(lines, ("brezilya", "kolombiya", "filtre"), strict=True):
        invoices.confirm_match(db_session, supplier_id=supplier.id, line=line, product=catalog[key])

    invoices.confirm_invoice(db_session, result.invoice)

    refreshed = db_session.scalars(
        select(PurchaseInvoiceLine).where(PurchaseInvoiceLine.invoice_id == result.invoice.id)
    ).all()
    # Her satır kendi tutarının %10'u kadar ek maliyet almalı → birim maliyet %10 artar.
    for line in refreshed:
        assert line.landed_unit_cost_try is not None
        assert abs(line.landed_unit_cost_try - line.unit_price_try * D("1.1")) <= D("0.01")


def test_confirm_is_rejected_while_lines_are_unmatched(
    db_session: Session, store: Any, supplier: Supplier, payload: bytes
) -> None:
    """Eşleşmemiş satır varken onay reddedilir — yanlış ürüne maliyet yazılmaz."""
    result = invoices.upload_invoice(
        db_session,
        payload,
        supplier=supplier,
        tenant_id=store.tenant_id,
        brand_id=store.brand_id,
        invoice_no="KTA-UNMATCHED",
        invoice_date=INVOICE_DATE,
    )

    with pytest.raises(invoices.InvoiceError, match="eşleşmemiş"):
        invoices.confirm_invoice(db_session, result.invoice)


def test_confirmed_invoice_cannot_be_confirmed_again(
    db_session: Session, store: Any, supplier: Supplier, catalog: dict[str, Product], payload: bytes
) -> None:
    """§12C.3.6: onaylanmış fatura değiştirilemez."""
    invoice = _matched_invoice(db_session, store, supplier, catalog, payload)
    invoices.confirm_invoice(db_session, invoice)

    with pytest.raises(invoices.ImmutableInvoiceError):
        invoices.confirm_invoice(db_session, invoice)


# --- API katmanı -------------------------------------------------------------


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


def test_upload_endpoint_returns_review_payload(
    api: TestClient, supplier: Supplier, payload: bytes
) -> None:
    """Yükleme ucu ayrıştırma özetini döner; stoka dokunmaz."""
    response = api.post(
        "/alessi/invoices/upload",
        data={
            "supplier_id": str(supplier.id),
            "invoice_no": "API-1",
            "invoice_date": str(INVOICE_DATE),
        },
        files={"file": ("fatura.pdf", payload, "application/pdf")},
        headers=_headers(api),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["lines"] == 3
    assert body["unmatched"] == 3
    assert body["totals_ok"] is True


def test_detail_endpoint_carries_suggestions(
    api: TestClient, supplier: Supplier, catalog: dict[str, Product], payload: bytes
) -> None:
    """Review ekranı eşleşmemiş satırlar için öneri alır."""
    upload = api.post(
        "/alessi/invoices/upload",
        data={
            "supplier_id": str(supplier.id),
            "invoice_no": "API-2",
            "invoice_date": str(INVOICE_DATE),
        },
        files={"file": ("fatura.pdf", payload, "application/pdf")},
        headers=_headers(api),
    ).json()

    detail = api.get(f"/alessi/invoices/{upload['invoice_id']}", headers=_headers(api))

    assert detail.status_code == 200, detail.text
    lines = detail.json()["lines"]
    assert len(lines) == 3
    assert any(line["suggestions"] for line in lines)


def test_full_chain_upload_match_confirm(
    api: TestClient,
    db_session: Session,
    supplier: Supplier,
    catalog: dict[str, Product],
    payload: bytes,
) -> None:
    """§12C.11 kabul: parser → review → confirm zinciri uçtan uca."""
    upload = api.post(
        "/alessi/invoices/upload",
        data={
            "supplier_id": str(supplier.id),
            "invoice_no": "API-3",
            "invoice_date": str(INVOICE_DATE),
        },
        files={"file": ("fatura.pdf", payload, "application/pdf")},
        headers=_headers(api),
    ).json()
    invoice_id = upload["invoice_id"]

    detail = api.get(f"/alessi/invoices/{invoice_id}", headers=_headers(api)).json()
    for line, key in zip(detail["lines"], ("brezilya", "kolombiya", "filtre"), strict=True):
        matched = api.post(
            f"/alessi/invoices/{invoice_id}/lines/{line['id']}/match",
            json={"product_id": str(catalog[key].id)},
            headers=_headers(api),
        )
        assert matched.status_code == 200, matched.text

    confirmed = api.post(f"/alessi/invoices/{invoice_id}/confirm", headers=_headers(api))

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert len(db_session.scalars(select(InventoryLedger)).all()) == 3


def test_editing_a_confirmed_invoice_returns_409(
    api: TestClient, supplier: Supplier, catalog: dict[str, Product], payload: bytes
) -> None:
    """§12C.11 kabul: onaylanmış faturayı değiştirme girişimi 409."""
    upload = api.post(
        "/alessi/invoices/upload",
        data={
            "supplier_id": str(supplier.id),
            "invoice_no": "API-4",
            "invoice_date": str(INVOICE_DATE),
        },
        files={"file": ("fatura.pdf", payload, "application/pdf")},
        headers=_headers(api),
    ).json()
    invoice_id = upload["invoice_id"]
    detail = api.get(f"/alessi/invoices/{invoice_id}", headers=_headers(api)).json()
    for line, key in zip(detail["lines"], ("brezilya", "kolombiya", "filtre"), strict=True):
        api.post(
            f"/alessi/invoices/{invoice_id}/lines/{line['id']}/match",
            json={"product_id": str(catalog[key].id)},
            headers=_headers(api),
        )
    api.post(f"/alessi/invoices/{invoice_id}/confirm", headers=_headers(api))

    retry = api.post(
        f"/alessi/invoices/{invoice_id}/lines/{detail['lines'][0]['id']}/match",
        json={"product_id": str(catalog["filtre"].id)},
        headers=_headers(api),
    )
    reconfirm = api.post(f"/alessi/invoices/{invoice_id}/confirm", headers=_headers(api))

    assert retry.status_code == 409
    assert reconfirm.status_code == 409


def test_invoice_of_other_brand_returns_404(
    api: TestClient, supplier: Supplier, payload: bytes
) -> None:
    """§3A.6: başka markanın faturası 404."""
    upload = api.post(
        "/alessi/invoices/upload",
        data={
            "supplier_id": str(supplier.id),
            "invoice_no": "API-5",
            "invoice_date": str(INVOICE_DATE),
        },
        files={"file": ("fatura.pdf", payload, "application/pdf")},
        headers=_headers(api),
    ).json()

    response = api.get(
        f"/kahveji/invoices/{upload['invoice_id']}", headers=_headers(api, "kahveji")
    )

    assert response.status_code == 404
