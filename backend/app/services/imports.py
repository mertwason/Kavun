"""İthalat dosyası modu ve kur farkı takibi (spec §12C.7-8).

## İthalat dosyası nedir

Tek fatura + tek "ekstra masraf" alanı ithalat için yetersizdir. İthal alım bir **dosyadır**:

    mal faturası (EUR)  +  beyanname  +  masraf kalemleri (navlun, sigorta, müşavirlik…)

Masraf kalemleri kendi para biriminde ve kendi faturasıyla girilir; her biri TL karşılığıyla
saklanır. Dosya onaylandığında masraf toplamı mal satırlarına **mal bedeli ağırlıklı**
dağıtılır ve 12C.3'teki atomik zincir çalışır: ledger + WAC + `sku_costs` tek transaction.

## İki kural

1. **İthalat KDV'si masraf kalemi DEĞİLDİR.** Gümrükte ödenir ama indirilecek KDV'dir;
   maliyete girerse ürün maliyeti şişer. `import_files.import_vat_paid` alanında nakit
   akışı/KDV raporu için tutulur, landed cost hesabına asla katılmaz (§12C.7).
2. **Kur farkı ürün maliyetine girmez.** Maliyet beyanname (ya da fatura) tarihi kuruyla
   sabitlenir ve WAC'a öyle girer — muhasebeyle tutarlı, geriye dönük oynamaz. Ödeme günü
   kur değiştiyse fark `supplier_payments.fx_diff_try`de ayrı raporlanır (§12C.8), böylece
   marj erimesinin ürün mü kur mu kaynaklı olduğu ayrışır.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engine.vat import quantize_money
from app.models.enums import ImportCostItemType, ImportFileStatus, InvoiceStatus
from app.models.inventory import (
    ImportCostItem,
    ImportFile,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SupplierPayment,
)

log = get_logger("services.imports")

ZERO = Decimal("0")


class ImportFileError(RuntimeError):
    """İthalat akışının reddettiği durum."""


@dataclass(frozen=True)
class LandedLine:
    """Bir mal satırının dağıtım sonrası maliyeti (önizleme; henüz yazılmaz)."""

    line_id: uuid.UUID
    product_id: uuid.UUID | None
    raw_text: str
    qty: Decimal
    goods_total_try: Decimal
    extra_share_try: Decimal
    landed_unit_cost_try: Decimal


@dataclass(frozen=True)
class FxExposure:
    """Açık (ödenmemiş) döviz pozisyonu ve kur farkı özeti (spec §12C.8)."""

    currency: str
    open_amount: Decimal
    """Faturalanan tutardan ödenen tutar düşülmüş bakiye (orijinal para biriminde)."""

    cost_fx_rate: Decimal | None
    """Maliyete giren ağırlıklı ortalama kur — WAC'ın sabitlendiği kur."""

    paid_amount: Decimal
    realized_fx_diff_try: Decimal
    """Gerçekleşmiş kur farkı (P&L yönlü): negatif = gider, pozitif = gelir."""


def import_cost_total(session: Session, *, import_file_id: uuid.UUID | None) -> Decimal:
    """Dosyanın **mal bedeli hariç** masraf toplamı (TL).

    Mal bedeli zaten fatura satırlarında; ikinci kez sayılmaz. İthalat KDV'si burada
    zaten yoktur — `import_cost_items`'a girmez (§12C.7).
    """
    if import_file_id is None:
        return ZERO
    items = session.scalars(
        select(ImportCostItem).where(ImportCostItem.import_file_id == import_file_id)
    ).all()
    return quantize_money(
        sum(
            (
                item.amount_try
                for item in items
                if item.item_type is not ImportCostItemType.MAL_BEDELI
            ),
            ZERO,
        )
    )


def cost_items(session: Session, *, import_file_id: uuid.UUID) -> list[ImportCostItem]:
    """Dosyanın masraf kalemleri."""
    return list(
        session.scalars(
            select(ImportCostItem)
            .where(ImportCostItem.import_file_id == import_file_id)
            .order_by(ImportCostItem.item_type)
        ).all()
    )


def add_cost_item(
    session: Session,
    *,
    import_file: ImportFile,
    item_type: ImportCostItemType,
    amount_original: Decimal,
    currency: str,
    fx_rate: Decimal | None = None,
    vendor: str | None = None,
    doc_ref: str | None = None,
) -> ImportCostItem:
    """Masraf kalemi ekler; TL karşılığı burada sabitlenir.

    TL kalem için kur istenmez. Dövizli kalemde kur verilmezse dosyanın beyanname kuru
    kullanılır; o da yoksa akış durur — uydurma kurla maliyet yazılmaz.
    """
    if import_file.status is ImportFileStatus.CONFIRMED:
        raise ImportFileError("Onaylanmış dosyaya masraf eklenemez; düzeltme ters kayıtla yapılır")
    if amount_original <= ZERO:
        raise ImportFileError("Masraf tutarı pozitif olmalı")

    if currency.upper() == "TRY":
        amount_try = quantize_money(amount_original)
    else:
        rate = fx_rate or import_file.fx_rate_beyanname
        if rate is None:
            raise ImportFileError(f"{currency} kalem için kur gerekli (beyanname kuru da yok)")
        amount_try = quantize_money(amount_original * rate)

    item = ImportCostItem(
        import_file_id=import_file.id,
        item_type=item_type,
        amount_original=quantize_money(amount_original),
        currency=currency.upper(),
        amount_try=amount_try,
        vendor=vendor,
        doc_ref=doc_ref,
    )
    session.add(item)
    session.flush()
    return item


def attach_invoice(
    session: Session, *, import_file: ImportFile, invoice: PurchaseInvoice
) -> PurchaseInvoice:
    """Mal faturasını dosyaya bağlar — landed cost artık dosyadan gelir (§12C.7)."""
    if invoice.status is InvoiceStatus.CONFIRMED:
        raise ImportFileError("Onaylanmış fatura başka bir dosyaya bağlanamaz")
    if invoice.brand_id != import_file.brand_id:
        raise ImportFileError("Fatura ve ithalat dosyası aynı markaya ait olmalı")
    invoice.import_file_id = import_file.id
    # Basit yurtiçi moda ait alan artık anlamsız; iki kaynak birden sayılmasın.
    invoice.landed_cost_extra = ZERO
    session.flush()
    return invoice


def file_invoices(session: Session, *, import_file_id: uuid.UUID) -> list[PurchaseInvoice]:
    """Dosyaya bağlı mal faturaları."""
    return list(
        session.scalars(
            select(PurchaseInvoice)
            .where(PurchaseInvoice.import_file_id == import_file_id)
            .order_by(PurchaseInvoice.invoice_no)
        ).all()
    )


def goods_lines(session: Session, *, import_file_id: uuid.UUID) -> list[PurchaseInvoiceLine]:
    """Dosyaya bağlı faturaların mal satırları.

    Faturalar önce ayrı bir sorguyla çözülür: `purchase_invoices` marka kapsamlı bir
    tablodur ve guard alt sorguda kendi filtresini taşımayan kullanımı reddeder
    (CLAUDE.md §2). Böylece marka filtresi kesin olarak uygulanmış olur.
    """
    invoice_ids = [invoice.id for invoice in file_invoices(session, import_file_id=import_file_id)]
    if not invoice_ids:
        return []
    return list(
        session.scalars(
            select(PurchaseInvoiceLine)
            .where(PurchaseInvoiceLine.invoice_id.in_(invoice_ids))
            .order_by(PurchaseInvoiceLine.raw_text)
        ).all()
    )


def landed_costs(session: Session, *, import_file: ImportFile) -> list[LandedLine]:
    """Satır bazlı landed cost **önizlemesi** — hiçbir şey yazılmaz.

    Dağıtım mal bedeli ağırlıklıdır; artık kuruş son satıra eklenir, böylece payların
    toplamı her zaman dağıtılan masrafa eşittir.
    """
    from app.engine.inventory import allocate_landed_cost, quantize_avg_cost

    lines = goods_lines(session, import_file_id=import_file.id)
    if not lines:
        return []

    amounts = [line.unit_price_try * line.qty for line in lines]
    extras = allocate_landed_cost(
        amounts, import_cost_total(session, import_file_id=import_file.id)
    )

    result: list[LandedLine] = []
    for line, goods_total, extra in zip(lines, amounts, extras, strict=True):
        unit = quantize_avg_cost(line.unit_price_try + (extra / line.qty if line.qty else ZERO))
        result.append(
            LandedLine(
                line_id=line.id,
                product_id=line.product_id,
                raw_text=line.raw_text,
                qty=line.qty,
                goods_total_try=quantize_money(goods_total),
                extra_share_try=quantize_money(extra),
                landed_unit_cost_try=unit,
            )
        )
    return result


def confirm_file(
    session: Session, *, import_file: ImportFile, user: str | None = None
) -> dict[str, int]:
    """Dosyayı onaylar: bağlı her faturayı 12C.3 zinciriyle stoka işler (§12C.7).

    Zincirin tek kopyası vardır — `invoices.confirm_invoice`. Burada yalnızca hangi
    faturaların işleneceği ve dosyanın kapanması yönetilir.
    """
    from app.services.invoices import confirm_invoice

    if import_file.status is ImportFileStatus.CONFIRMED:
        raise ImportFileError("Dosya zaten onaylanmış; düzeltme ancak ters kayıtla yapılır")

    invoices = file_invoices(session, import_file_id=import_file.id)
    if not invoices:
        raise ImportFileError("Dosyaya bağlı mal faturası yok")

    totals = {"invoices": 0, "lines": 0, "ledger_entries": 0}
    for invoice in invoices:
        if invoice.status is InvoiceStatus.CONFIRMED:
            continue
        summary = confirm_invoice(session, invoice, user=user)
        totals["invoices"] += 1
        totals["lines"] += summary.lines
        totals["ledger_entries"] += summary.ledger_entries

    import_file.status = ImportFileStatus.CONFIRMED
    session.flush()
    log.info("import_file.confirmed", import_file_id=str(import_file.id), **totals)
    return totals


def record_payment(
    session: Session,
    *,
    import_file: ImportFile,
    pay_date: date,
    amount_original: Decimal,
    fx_rate_payment: Decimal,
    currency: str | None = None,
) -> SupplierPayment:
    """Ödemeyi kaydeder ve kur farkını hesaplar (spec §12C.8).

    `fx_diff_try = tutar × (maliyet kuru − ödeme kuru)`. İşaret **P&L yönündedir**:
    negatif = kur farkı gideri (maliyeti sabitlediğimiz kurdan pahalıya ödedik),
    pozitif = kur farkı geliri. Uygulamanın her yerinde negatif rakam kârı azaltan
    kalemdir; kur farkı da aynı okumayı taşır (spec §12C.8 "kur farkı gideri/geliri").

    Bu fark ürün maliyetine dokunmaz — WAC beyanname kuruyla sabitlenmiştir.
    """
    if amount_original <= ZERO:
        raise ImportFileError("Ödeme tutarı pozitif olmalı")
    if fx_rate_payment <= ZERO:
        raise ImportFileError("Ödeme kuru pozitif olmalı")

    cost_rate = import_file.fx_rate_beyanname
    fx_diff = (
        quantize_money(amount_original * (cost_rate - fx_rate_payment))
        if cost_rate is not None
        else None
    )

    payment = SupplierPayment(
        tenant_id=import_file.tenant_id,
        brand_id=import_file.brand_id,
        supplier_id=import_file.supplier_id,
        import_file_id=import_file.id,
        pay_date=pay_date,
        amount_original=quantize_money(amount_original),
        currency=(currency or import_file.currency).upper(),
        fx_rate_payment=fx_rate_payment,
        fx_diff_try=fx_diff,
    )
    session.add(payment)
    session.flush()
    log.info(
        "import_file.payment_recorded",
        import_file_id=str(import_file.id),
        fx_diff_try=str(fx_diff),
    )
    return payment


def payments(session: Session, *, import_file_id: uuid.UUID) -> list[SupplierPayment]:
    """Dosyanın ödemeleri (en yeni üstte)."""
    return list(
        session.scalars(
            select(SupplierPayment)
            .where(SupplierPayment.import_file_id == import_file_id)
            .order_by(SupplierPayment.pay_date.desc())
        ).all()
    )


def fx_exposure(session: Session) -> list[FxExposure]:
    """Marka kapsamlı açık döviz pozisyonu (spec §12C.8 raporu).

    Açık pozisyon = dosyalara giren dövizli tutar − ödenen tutar. Maliyet kuru, dosya
    tutarlarıyla ağırlıklandırılmış beyanname kurudur: "hangi kurdan maliyetlendik".
    """
    files = list(session.scalars(select(ImportFile)).all())
    by_currency: dict[str, list[ImportFile]] = {}
    for item in files:
        if item.currency.upper() == "TRY":
            continue
        by_currency.setdefault(item.currency.upper(), []).append(item)

    result: list[FxExposure] = []
    for currency, group in sorted(by_currency.items()):
        invoiced = ZERO
        weighted = ZERO
        weight = ZERO
        for item in group:
            amount = file_goods_amount(session, import_file=item)
            invoiced += amount
            if item.fx_rate_beyanname is not None:
                weighted += amount * item.fx_rate_beyanname
                weight += amount

        rows = [
            payment
            for item in group
            for payment in payments(session, import_file_id=item.id)
            if payment.currency.upper() == currency
        ]
        paid = sum((row.amount_original for row in rows), ZERO)
        realized = sum((row.fx_diff_try or ZERO for row in rows), ZERO)

        result.append(
            FxExposure(
                currency=currency,
                open_amount=quantize_money(invoiced - paid),
                cost_fx_rate=(weighted / weight).quantize(Decimal("0.000001")) if weight else None,
                paid_amount=quantize_money(paid),
                realized_fx_diff_try=quantize_money(realized),
            )
        )
    return result


def file_goods_amount(session: Session, *, import_file: ImportFile) -> Decimal:
    """Dosyanın dövizli mal bedeli — faturalardan, yoksa `mal_bedeli` kaleminden."""
    lines = goods_lines(session, import_file_id=import_file.id)
    if lines:
        return sum((line.unit_price_original * line.qty for line in lines), ZERO)
    items = [
        item
        for item in cost_items(session, import_file_id=import_file.id)
        if item.item_type is ImportCostItemType.MAL_BEDELI
    ]
    return sum((item.amount_original for item in items), ZERO)


def files(session: Session) -> list[ImportFile]:
    """Marka kapsamlı ithalat dosyaları (en yeni üstte)."""
    return list(session.scalars(select(ImportFile).order_by(ImportFile.created_at.desc())).all())
