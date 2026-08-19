"""Alış faturası: PDF ayrıştırma, öğrenen SKU eşleştirme, onay (spec §12C.3).

## Akış

1. **Yükle** → PDF metni çıkarılır (pdfplumber), satırlar ayrıştırılır, fatura `parsed`
   ya da `review` durumunda kaydedilir.
2. **Doğrula** → satır toplamları fatura genel toplamıyla ±0,10 TL tutmalı; tutmuyorsa
   fatura `review`de kalır (spec §12C.3.3).
3. **Eşleştir** → barkod → `supplier_product_map` → fuzzy öneri. Fuzzy öneri **asla**
   kendiliğinden yazılmaz, kullanıcı onayı şarttır (spec §12C.3.4).
4. **Onayla** → her satır için `inventory_ledger` girişi + WAC güncellemesi + `sku_costs`
   versiyonu **tek transaction'da** yazılır (spec §12C.3.5).
5. Onaylanmış fatura **değiştirilemez**; düzeltme ancak ters kayıtla yapılır (§12C.3.6).

## Ayrıştırıcı hakkında (spec §12C.3.2'den sapma — bilinçli)

Spec satır çıkarımı için "LLM destekli ayrıştırma (Claude API)" diyor. Kavun'da yapılandırılmış
bir LLM anahtarı yok ve harici servise bağımlı, tekrarlanamayan bir ayrıştırma testte
doğrulanamaz. Bu yüzden varsayılan ayrıştırıcı **deterministik** bir tablo okuyucudur:
e-arşiv/e-fatura PDF'lerinin satır düzenini (adet · birim fiyat · KDV · tutar) okur.

`LineExtractor` protokolü LLM ayrıştırıcısının sonradan takılabilmesi için duruyor —
sözleşme aynı: metin → satır listesi. Spec'in asıl kuralı zaten korunuyor: **ayrıştırıcı
çıktısı asla doğrudan yazılmaz, her zaman review ekranından geçer.**

OCR fallback (tesseract) bu ortamda kurulu değil; metin çıkmayan PDF sessizce boş
dönmez, açık hata verir.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engine.inventory import StockState, apply_inbound, quantize_avg_cost
from app.engine.vat import quantize_money
from app.models.catalog import Product, SkuCost, Supplier
from app.models.enums import (
    CostSource,
    InventoryMovement,
    InvoiceStatus,
    MatchStatus,
)
from app.models.inventory import (
    InventoryLedger,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SkuCostState,
    SupplierProductMap,
)

log = get_logger("services.invoices")

ZERO = Decimal("0")
ONE = Decimal("1")
TOTAL_TOLERANCE = Decimal("0.10")
"""Spec §12C.3.3: satır toplamları ± fatura toplamı bu toleransta tutmalı."""

FUZZY_THRESHOLD = Decimal("0.62")
"""Bu eşiğin altındaki benzerlik öneri bile sayılmaz — kullanıcıyı gürültüye boğmamak için.

Benzerlik skoru para değil ama `Decimal` tutulur: kod tabanında float hiç dolaşmasın
(CLAUDE.md §1) ve API yanıtındaki `confidence` alanıyla aynı tipte olsun."""


class InvoiceError(RuntimeError):
    """Fatura akışının reddettiği durum."""


class ImmutableInvoiceError(InvoiceError):
    """Onaylanmış fatura değiştirilemez (spec §12C.3.6) — API 409 döner."""


# --- metin çıkarımı ----------------------------------------------------------


def extract_text(payload: bytes) -> str:
    """PDF'ten metin çıkarır (pdfplumber).

    Metin çıkmazsa (taranmış görüntü PDF) sessizce boş dönmez: OCR fallback bu ortamda
    kurulu olmadığı için açık hata verilir — yarım veri yazmaktansa akış durur.
    """
    import pdfplumber

    try:
        with pdfplumber.open(BytesIO(payload)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:  # pdfminer çeşitli hata tipleri fırlatır
        raise InvoiceError("PDF okunamadı; geçerli bir PDF dosyası bekleniyor.") from exc

    text = "\n".join(pages).strip()
    if not text:
        raise InvoiceError(
            "PDF'ten metin çıkarılamadı (taranmış görüntü olabilir). "
            "OCR bu kurulumda etkin değil; metin tabanlı e-arşiv PDF'i yükleyin."
        )
    return text


# --- satır ayrıştırma --------------------------------------------------------


@dataclass(frozen=True)
class ParsedLine:
    """Ayrıştırıcının bulduğu bir fatura satırı (henüz yazılmadı)."""

    raw_text: str
    name: str
    qty: Decimal
    unit_price: Decimal
    vat_rate: Decimal
    line_total: Decimal


class LineExtractor(Protocol):
    """Satır çıkarıcı sözleşmesi — LLM ayrıştırıcısı buraya takılabilir."""

    def __call__(self, text: str) -> list[ParsedLine]:
        """Fatura metninden satırları çıkarır."""
        ...


def _decimal(raw: str) -> Decimal | None:
    """`1.234,56` · `1234.56` · `12,5` → Decimal."""
    text = raw.strip().replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "")
    text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


# Satır kalıbı: "<ad> <adet> <birim fiyat> %<kdv> <tutar>" — e-arşiv tablolarının
# yaygın düzeni. Sayı biçimleri hem TR (1.234,56) hem EN (1234.56) kabul edilir.
LINE_PATTERN = re.compile(
    r"^(?P<name>.+?)\s+"
    r"(?P<qty>\d+(?:[.,]\d+)?)\s+(?:ADET|AD|ADT|KG|LT|PK)?\s*"
    r"(?P<price>\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:\.\d+)?)\s+"
    r"%?\s*(?P<vat>\d{1,2}(?:[.,]\d+)?)\s*%?\s+"
    r"(?P<total>\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:\.\d+)?)\s*(?:TL|TRY|₺|EUR|€|USD|\$)?$",
    re.IGNORECASE,
)

# Toplam/ara toplam satırları veri satırı değildir.
SUMMARY_MARKERS = (
    "toplam",
    "ara toplam",
    "genel toplam",
    "kdv",
    "iskonto",
    "matrah",
    "yalniz",
    "yalnız",
)


def _looks_like_summary(line: str) -> bool:
    lowered = fold(line).strip()
    return any(lowered.startswith(fold(marker)) for marker in SUMMARY_MARKERS)


def extract_lines(text: str) -> list[ParsedLine]:
    """Deterministik satır çıkarıcı (varsayılan `LineExtractor`)."""
    lines: list[ParsedLine] = []
    for raw in text.splitlines():
        candidate = raw.strip()
        if not candidate or _looks_like_summary(candidate):
            continue
        match = LINE_PATTERN.match(candidate)
        if not match:
            continue

        qty = _decimal(match.group("qty"))
        price = _decimal(match.group("price"))
        vat = _decimal(match.group("vat"))
        total = _decimal(match.group("total"))
        name = match.group("name").strip(" .-•\t")
        if qty is None or price is None or vat is None or total is None or not name:
            continue
        if qty <= ZERO or price < ZERO:
            continue

        lines.append(
            ParsedLine(
                raw_text=candidate,
                name=name,
                qty=qty,
                unit_price=price,
                vat_rate=vat,
                line_total=total,
            )
        )
    return lines


TOTAL_PATTERN = re.compile(
    r"(?:genel\s+toplam|odenecek\s+tutar|ödenecek\s+tutar)\s*:?\s*"
    r"(?P<total>\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def fold(text: str) -> str:
    """Küçük harf + aksansız, ama NOKTALAMA KORUNUR.

    `normalize()` eşleştirme içindir ve rakam ayraçlarını da siler; tutar okurken
    "15.750,00" değerinin bozulmaması için ayrı bir sadeleştirme gerekir.
    """
    raw = str(text or "").lower().replace("ı", "i").replace("İ", "i")
    decomposed = unicodedata.normalize("NFKD", raw)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def extract_total(text: str) -> Decimal | None:
    """Fatura genel toplamı (doğrulama için)."""
    for raw in text.splitlines():
        match = TOTAL_PATTERN.search(fold(raw))
        if match:
            return _decimal(match.group("total"))
    return None


# --- doğrulama (spec §12C.3.3) ----------------------------------------------


@dataclass
class Validation:
    """Satır toplamı ile fatura toplamının karşılaştırması."""

    lines_total: Decimal
    invoice_total: Decimal | None
    difference: Decimal | None
    ok: bool
    message: str = ""


def validate_totals(lines: list[ParsedLine], invoice_total: Decimal | None) -> Validation:
    """Satır toplamları fatura genel toplamıyla ±0,10 TL tutmalı (spec §12C.3.3)."""
    lines_total = quantize_money(sum((line.line_total for line in lines), ZERO))
    if invoice_total is None:
        return Validation(
            lines_total=lines_total,
            invoice_total=None,
            difference=None,
            ok=False,
            message="Fatura genel toplamı okunamadı; satır toplamları doğrulanamıyor.",
        )

    difference = quantize_money(lines_total - invoice_total)
    if abs(difference) <= TOTAL_TOLERANCE:
        return Validation(
            lines_total=lines_total, invoice_total=invoice_total, difference=difference, ok=True
        )
    return Validation(
        lines_total=lines_total,
        invoice_total=invoice_total,
        difference=difference,
        ok=False,
        message=(
            f"Satır toplamı {lines_total} ile fatura toplamı {invoice_total} tutmuyor "
            f"(fark {difference})."
        ),
    )


# --- öğrenen SKU eşleştirme (spec §12C.3.4) ---------------------------------


def normalize(text: str) -> str:
    """Eşleştirme için sadeleştirme: küçük harf, aksansız, tek boşluk."""
    raw = str(text or "").strip().lower().replace("ı", "i").replace("İ", "i")
    decomposed = unicodedata.normalize("NFKD", raw)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9 ]+", " ", re.sub(r"\s+", " ", stripped)).strip()


MIN_OVERLAP_TOKENS = 2
"""Tek ortak kelime ("kahve") öneri üretmeye yetmez — yanlış öneri gürültüsünü keser."""


def _similarity(left: str, right: str) -> Decimal:
    """Token örtüşmesi — kapsama ağırlıklı.

    Fatura satır adı ("Brezilya Cerrado Cekirdek Kahve 1kg") genelde katalog adından
    (`KHV-BRZ-1K Brezilya Cerrado 1kg Çekirdek`) daha uzundur; saf Jaccard bu asimetride
    doğru eşleşmeyi de cezalandırır. Bu yüzden **kapsama** (overlap / kısa tarafın
    uzunluğu) kullanılır, ama en az iki ortak kelime şartı aranır.
    """
    left_tokens = set(normalize(left).split())
    right_tokens = set(normalize(right).split())
    if not left_tokens or not right_tokens:
        return ZERO
    overlap = len(left_tokens & right_tokens)
    if overlap < MIN_OVERLAP_TOKENS:
        return ZERO
    return (Decimal(overlap) / Decimal(min(len(left_tokens), len(right_tokens)))).quantize(
        Decimal("0.0001")
    )


@dataclass
class MatchResult:
    """Bir satırın eşleştirme sonucu."""

    product: Product | None
    status: MatchStatus
    confidence: Decimal = ZERO
    reason: str = ""
    suggestions: list[tuple[Product, Decimal]] = field(default_factory=list)


def match_line(
    session: Session,
    *,
    supplier_id: uuid.UUID,
    raw_name: str,
    barcode: str | None = None,
) -> MatchResult:
    """Eşleştirme sırası: barkod → öğrenilmiş eşleşme → fuzzy öneri (spec §12C.3.4).

    Fuzzy sonuç **otomatik kabul edilmez**: `MatchStatus.UNMATCHED` döner ve öneri
    listesi taşınır; kullanıcı onaylayınca `confirm_match()` çağrılır.
    """
    if barcode:
        product = session.scalar(select(Product).where(Product.barcode == barcode))
        if product is not None:
            return MatchResult(
                product=product, status=MatchStatus.AUTO, confidence=ONE, reason="barkod"
            )

    normalized = normalize(raw_name)
    learned = session.scalar(
        select(SupplierProductMap).where(
            SupplierProductMap.supplier_id == supplier_id,
            SupplierProductMap.raw_name_normalized == normalized,
        )
    )
    if learned is not None:
        product = session.scalar(select(Product).where(Product.id == learned.product_id))
        if product is not None:
            return MatchResult(
                product=product,
                status=MatchStatus.AUTO,
                confidence=ONE,
                reason="öğrenilmiş eşleşme",
            )

    scored = [
        (product, _similarity(raw_name, f"{product.sku} {product.name}"))
        for product in session.scalars(select(Product)).all()
    ]
    suggestions = sorted(
        (item for item in scored if item[1] >= FUZZY_THRESHOLD),
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    return MatchResult(
        product=None,
        status=MatchStatus.UNMATCHED,
        confidence=suggestions[0][1] if suggestions else ZERO,
        reason="öneri (onay gerekli)" if suggestions else "eşleşme bulunamadı",
        suggestions=suggestions,
    )


def confirm_match(
    session: Session,
    *,
    supplier_id: uuid.UUID,
    line: PurchaseInvoiceLine,
    product: Product,
    barcode: str | None = None,
) -> SupplierProductMap:
    """Kullanıcının onayladığı eşleştirmeyi ÖĞRENİR (spec §12C.3.4).

    "Aynı tedarikçiden aynı ürün bir daha sorulmaz."
    """
    normalized = normalize(line.raw_text)
    existing = session.scalar(
        select(SupplierProductMap).where(
            SupplierProductMap.supplier_id == supplier_id,
            SupplierProductMap.raw_name_normalized == normalized,
        )
    )
    if existing is None:
        existing = SupplierProductMap(
            supplier_id=supplier_id,
            raw_name_normalized=normalized,
            barcode=barcode,
            product_id=product.id,
            confirmed_at=datetime.now(UTC),
        )
        session.add(existing)
    else:
        existing.product_id = product.id
        existing.confirmed_at = datetime.now(UTC)

    line.product_id = product.id
    line.match_status = MatchStatus.MANUAL
    session.flush()
    return existing


# --- yükleme ------------------------------------------------------------------


@dataclass
class UploadResult:
    """Yükleme sonucu — review ekranının kaynağı."""

    invoice: PurchaseInvoice
    validation: Validation
    unmatched: int
    suggestions: dict[uuid.UUID, list[tuple[Product, Decimal]]] = field(default_factory=dict)


def upload_invoice(
    session: Session,
    payload: bytes,
    *,
    supplier: Supplier,
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    invoice_no: str,
    invoice_date: date,
    currency: str = "TRY",
    fx_rate: Decimal | None = None,
    landed_cost_extra: Decimal = ZERO,
    pdf_path: str | None = None,
    extractor: LineExtractor | None = None,
) -> UploadResult:
    """PDF'i ayrıştırır ve faturayı `parsed`/`review` durumunda kaydeder (spec §12C.3).

    Ayrıştırıcı çıktısı ASLA doğrudan stoka yazılmaz — bu fonksiyon yalnızca fatura ve
    satır kayıtlarını oluşturur; stok/maliyet ancak `confirm_invoice()` ile işlenir.
    """
    text = extract_text(payload)
    parse = extractor or extract_lines
    lines = parse(text)
    if not lines:
        raise InvoiceError("Faturada satır bulunamadı; PDF düzeni tanınmadı.")

    validation = validate_totals(lines, extract_total(text))
    rate = fx_rate or Decimal("1")

    invoice = PurchaseInvoice(
        tenant_id=tenant_id,
        brand_id=brand_id,
        supplier_id=supplier.id,
        invoice_no=invoice_no,
        invoice_date=invoice_date,
        currency=currency,
        fx_rate=fx_rate,
        landed_cost_extra=landed_cost_extra,
        total=validation.invoice_total,
        pdf_path=pdf_path,
        status=InvoiceStatus.PARSED if validation.ok else InvoiceStatus.REVIEW,
    )
    session.add(invoice)
    session.flush()

    suggestions: dict[uuid.UUID, list[tuple[Product, Decimal]]] = {}
    unmatched = 0
    for parsed in lines:
        match = match_line(session, supplier_id=supplier.id, raw_name=parsed.name)
        record = PurchaseInvoiceLine(
            invoice_id=invoice.id,
            raw_text=parsed.name,
            product_id=match.product.id if match.product else None,
            qty=parsed.qty,
            unit_price_original=parsed.unit_price,
            unit_price_try=quantize_money(parsed.unit_price * rate),
            vat_rate=parsed.vat_rate,
            match_status=match.status,
        )
        session.add(record)
        session.flush()
        if match.product is None:
            unmatched += 1
            if match.suggestions:
                suggestions[record.id] = match.suggestions

    log.info(
        "invoice.uploaded",
        invoice_id=str(invoice.id),
        lines=len(lines),
        unmatched=unmatched,
        totals_ok=validation.ok,
    )
    return UploadResult(
        invoice=invoice, validation=validation, unmatched=unmatched, suggestions=suggestions
    )


# --- onay (spec §12C.3.5) ----------------------------------------------------


@dataclass
class ConfirmSummary:
    """Onay sonucu."""

    invoice_id: uuid.UUID
    lines: int = 0
    ledger_entries: int = 0
    cost_versions: int = 0


def _state_for(session: Session, product_id: uuid.UUID) -> tuple[SkuCostState | None, StockState]:
    record = session.scalar(select(SkuCostState).where(SkuCostState.product_id == product_id))
    if record is None:
        return None, StockState.empty()
    return record, StockState(on_hand=record.on_hand_qty, avg_cost=record.avg_cost)


def confirm_invoice(
    session: Session, invoice: PurchaseInvoice, *, user: str | None = None
) -> ConfirmSummary:
    """Faturayı onaylar: ledger + WAC + `sku_costs` **tek transaction'da** (spec §12C.3.5).

    Eşleşmemiş satır kaldıysa onay reddedilir — yanlış ürüne maliyet yazmaktansa akış durur.
    """
    if invoice.status is InvoiceStatus.CONFIRMED:
        raise ImmutableInvoiceError("Fatura zaten onaylanmış; düzeltme ancak ters kayıtla yapılır")

    lines = list(
        session.scalars(
            select(PurchaseInvoiceLine).where(PurchaseInvoiceLine.invoice_id == invoice.id)
        ).all()
    )
    if not lines:
        raise InvoiceError("Faturanın satırı yok")

    missing = [line for line in lines if line.product_id is None]
    if missing:
        raise InvoiceError(f"{len(missing)} satır hâlâ eşleşmemiş; onaydan önce SKU seçilmeli")

    # Landed cost (navlun/gümrük/sigorta) satırlara tutar ağırlıklı dağıtılır (§12C.2).
    from app.engine.inventory import allocate_landed_cost

    amounts = [line.unit_price_try * line.qty for line in lines]
    extras = allocate_landed_cost(amounts, invoice.landed_cost_extra or ZERO)

    summary = ConfirmSummary(invoice_id=invoice.id)
    moved_at = datetime.combine(invoice.invoice_date, datetime.min.time(), tzinfo=UTC)

    for line, extra in zip(lines, extras, strict=True):
        assert line.product_id is not None
        unit_cost = quantize_avg_cost(
            line.unit_price_try + (extra / line.qty if line.qty else ZERO)
        )
        line.landed_unit_cost_try = unit_cost

        record, state = _state_for(session, line.product_id)
        updated = apply_inbound(state, qty=line.qty, unit_cost=unit_cost)

        session.add(
            InventoryLedger(
                tenant_id=invoice.tenant_id,
                brand_id=invoice.brand_id,
                product_id=line.product_id,
                movement=InventoryMovement.PURCHASE_IN,
                qty_delta=line.qty,
                unit_cost_at_movement=unit_cost,
                avg_cost_after=updated.avg_cost,
                on_hand_after=updated.on_hand,
                ref_type="purchase_invoice",
                ref_id=str(invoice.id),
                moved_at=moved_at,
            )
        )
        summary.ledger_entries += 1

        if record is None:
            session.add(
                SkuCostState(
                    product_id=line.product_id,
                    on_hand_qty=updated.on_hand,
                    avg_cost=updated.avg_cost,
                    last_movement_at=moved_at,
                )
            )
        else:
            record.on_hand_qty = updated.on_hand
            record.avg_cost = updated.avg_cost
            record.last_movement_at = moved_at

        # Kâr motoru maliyeti tarih bazlı çözer; her WAC değişimi yeni versiyon (§12C.2).
        session.add(
            SkuCost(
                product_id=line.product_id,
                unit_cost=quantize_money(updated.avg_cost),
                currency="TRY",
                source=CostSource.INVOICE_WAC,
                invoice_ref=invoice.invoice_no,
                effective_from=invoice.invoice_date,
                created_by=user,
            )
        )
        summary.cost_versions += 1
        summary.lines += 1

    invoice.status = InvoiceStatus.CONFIRMED
    invoice.confirmed_at = datetime.now(UTC)
    session.flush()

    log.info(
        "invoice.confirmed",
        invoice_id=str(invoice.id),
        **{
            "lines": summary.lines,
            "ledger_entries": summary.ledger_entries,
        },
    )
    return summary
