"""Alış faturası, stok ledger'ı ve WAC durumu (spec §12C)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import (
    AvgCost,
    FxRate,
    Money,
    Qty,
    TimestampMixin,
    VatRate,
    brand_fk,
    pg_enum,
    tenant_fk,
    uuid_fk,
    uuid_fk_opt,
    uuid_pk,
)
from app.models.enums import (
    ImportCostItemType,
    ImportFileStatus,
    InventoryMovement,
    InvoiceStatus,
    MatchStatus,
)


class PurchaseInvoice(Base, TimestampMixin):
    """Alış faturası — maliyetin doğruluk kaynağı (spec §12C.2)."""

    __tablename__ = "purchase_invoices"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "supplier_id", "invoice_no", name="uq_purchase_invoices_supplier_no"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    supplier_id: Mapped[uuid.UUID] = uuid_fk("suppliers.id")
    invoice_no: Mapped[str] = mapped_column(String(120), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    # Fatura para birimi TL değilse fatura tarihindeki kur (TCMB döviz satış varsayılan).
    fx_rate: Mapped[Decimal | None] = mapped_column(FxRate, nullable=True)
    # Nakliye + gümrük + sigorta toplamı; yalnızca basit yurtiçi akışta kullanılır (spec §12C.7).
    landed_cost_extra: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    total: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        pg_enum(InvoiceStatus, "invoice_status"), nullable=False, default=InvoiceStatus.PARSED
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PurchaseInvoiceLine(Base, TimestampMixin):
    """Fatura satırı + SKU eşleştirme durumu (spec §12C.2)."""

    __tablename__ = "purchase_invoice_lines"

    id: Mapped[uuid.UUID] = uuid_pk()
    invoice_id: Mapped[uuid.UUID] = uuid_fk("purchase_invoices.id")
    raw_text: Mapped[str] = mapped_column(String(500), nullable=False)
    product_id: Mapped[uuid.UUID | None] = uuid_fk_opt("products.id")
    qty: Mapped[Decimal] = mapped_column(Qty, nullable=False)
    unit_price_original: Mapped[Decimal] = mapped_column(Money, nullable=False)
    unit_price_try: Mapped[Decimal] = mapped_column(Money, nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(VatRate, nullable=False)
    landed_unit_cost_try: Mapped[Decimal | None] = mapped_column(AvgCost, nullable=True)
    match_status: Mapped[MatchStatus] = mapped_column(
        pg_enum(MatchStatus, "match_status"), nullable=False, default=MatchStatus.UNMATCHED
    )


class SupplierProductMap(Base, TimestampMixin):
    """Öğrenen eşleştirme belleği — aynı tedarikçiden aynı ürün bir daha sorulmaz (spec §12C.3)."""

    __tablename__ = "supplier_product_map"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "raw_name_normalized", name="uq_supplier_product_map_supplier_name"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    supplier_id: Mapped[uuid.UUID] = uuid_fk("suppliers.id")
    raw_name_normalized: Mapped[str] = mapped_column(String(400), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_id: Mapped[uuid.UUID] = uuid_fk("products.id")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InventoryLedger(Base):
    """Stok hareket defteri — append-only (spec §12C.2).

    `sku_cost_state` bu tablodan yeniden üretilebilir olmalıdır (replay testi, §12C.11).
    """

    __tablename__ = "inventory_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    product_id: Mapped[uuid.UUID] = uuid_fk("products.id")
    movement: Mapped[InventoryMovement] = mapped_column(
        pg_enum(InventoryMovement, "inventory_movement"), nullable=False
    )
    qty_delta: Mapped[Decimal] = mapped_column(Qty, nullable=False)
    unit_cost_at_movement: Mapped[Decimal | None] = mapped_column(AvgCost, nullable=True)
    avg_cost_after: Mapped[Decimal] = mapped_column(AvgCost, nullable=False)
    on_hand_after: Mapped[Decimal] = mapped_column(Qty, nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    moved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class SkuCostState(Base):
    """Güncel stok/maliyet durumu — ledger'dan türetilir (spec §12C.2)."""

    __tablename__ = "sku_cost_state"

    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    on_hand_qty: Mapped[Decimal] = mapped_column(Qty, nullable=False, default=0)
    avg_cost: Mapped[Decimal] = mapped_column(AvgCost, nullable=False, default=0)
    last_movement_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ImportFile(Base, TimestampMixin):
    """İthalat dosyası: mal faturası + beyanname + masraf kalemleri (spec §12C.7)."""

    __tablename__ = "import_files"
    __table_args__ = (UniqueConstraint("tenant_id", "file_no", name="uq_import_files_tenant_no"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    supplier_id: Mapped[uuid.UUID] = uuid_fk("suppliers.id")
    file_no: Mapped[str] = mapped_column(String(120), nullable=False)
    beyanname_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    beyanname_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    fx_rate_beyanname: Mapped[Decimal | None] = mapped_column(FxRate, nullable=True)
    # İthalat KDV'si maliyet DEĞİLDİR; yalnızca nakit akışı/KDV raporu için tutulur (§12C.7).
    import_vat_paid: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    status: Mapped[ImportFileStatus] = mapped_column(
        pg_enum(ImportFileStatus, "import_file_status"),
        nullable=False,
        default=ImportFileStatus.OPEN,
    )


class ImportCostItem(Base, TimestampMixin):
    """İthalat masraf kalemi — mal bedeli ağırlıklı dağıtılır (spec §12C.7)."""

    __tablename__ = "import_cost_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    import_file_id: Mapped[uuid.UUID] = uuid_fk("import_files.id")
    item_type: Mapped[ImportCostItemType] = mapped_column(
        pg_enum(ImportCostItemType, "import_cost_item_type"), nullable=False
    )
    amount_original: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")
    amount_try: Mapped[Decimal] = mapped_column(Money, nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    doc_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)


class SupplierPayment(Base, TimestampMixin):
    """Ödeme ve kur farkı (spec §12C.8). Kur farkı ürün maliyetine GİRMEZ."""

    __tablename__ = "supplier_payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    brand_id: Mapped[uuid.UUID] = brand_fk()
    supplier_id: Mapped[uuid.UUID] = uuid_fk("suppliers.id")
    import_file_id: Mapped[uuid.UUID | None] = uuid_fk_opt("import_files.id")
    invoice_id: Mapped[uuid.UUID | None] = uuid_fk_opt("purchase_invoices.id")
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_original: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    fx_rate_payment: Mapped[Decimal] = mapped_column(FxRate, nullable=False)
    fx_diff_try: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
