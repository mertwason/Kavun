"""Demo veri seti — `make seed-demo` (CLAUDE.md §6).

Amaç: gerçek API'ye bağlanmadan önce TÜM ekranların dolu ve gezilebilir olması.
Demo veri `demo` tenant'ında yaşar, gerçek tenant'a asla karışmaz; `make wipe-demo`
ile temizlenir.

Üretim deterministiktir (sabit tohumlu `random.Random`): aynı komut aynı veriyi üretir.
Kâr sonuçları (`line_profit`) burada ÜRETİLMEZ — o motorun işidir (KVN-07); demo yalnızca
motorun gireceği ham gerçekleri kurar.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.context import system_scope
from app.engine import cargo as cargo_engine
from app.models.catalog import (
    CargoTariff,
    CommissionChange,
    CommissionRate,
    Customer,
    Product,
    ProductChannelMap,
    SkuCost,
    SkuLogistics,
    SkuPrice,
    Supplier,
)
from app.models.enums import (
    AlertSeverity,
    ChannelCode,
    CommissionScope,
    CommissionSource,
    CostSource,
    CostState,
    DraftStatus,
    ImportCostItemType,
    InventoryMovement,
    InvoiceStatus,
    MatchStatus,
    OrderStatus,
    SettlementRecordType,
    UserRole,
)
from app.models.identity import (
    AuditLog,
    Brand,
    BrandFeature,
    Store,
    StoreCredential,
    Tenant,
    User,
    UserBrandRole,
)
from app.models.inventory import (
    ImportCostItem,
    ImportFile,
    InventoryLedger,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SkuCostState,
    SupplierPayment,
    SupplierProductMap,
)
from app.models.results import (
    Alert,
    LineProfit,
    ProfitRevision,
    ReconciliationDiff,
)
from app.models.transactions import (
    AdSpend,
    CargoInvoice,
    Order,
    OrderLine,
    Promotion,
    RawEvent,
    Return,
    SettlementRecord,
    Shipment,
)
from app.models.workspace import ImportBatch, PricingScenario, ProductDraft
from app.seeds.base import (
    ALESSI_FEATURES,
    KAHVEJI_FEATURES,
    SeedResult,
    ensure_brand,
    ensure_channels,
    ensure_store,
    ensure_user,
    get_or_create_tenant,
)
from app.seeds.catalog_data import ALESSI_PRODUCTS, KAHVEJI_PRODUCTS, DemoProduct
from app.services.alerts import STALE_SYNC_ALERT
from app.services.cargo import UNMATCHED_ALERT as UNMATCHED_CARGO_ALERT
from app.services.discipline import MARGIN_FLOOR_ALERT, MSRP_ALERT
from app.services.imports import add_cost_item, confirm_file, record_payment
from app.services.inventory import NEGATIVE_STOCK_ALERT, damage, record_returns, record_sales
from app.services.tariffs import ALERT_TYPE as COMMISSION_CHANGE_ALERT

IMPORT_FX_BEYANNAME = Decimal("37.500000")
"""Beyanname kuru — maliyet bu kurla sabitlenir (spec §12C.8)."""

IMPORT_FX_PAYMENT = Decimal("39.200000")
"""Ödeme günü kuru; aradaki fark kur farkı olarak raporlanır, maliyete girmez."""

DEMO_TENANT_SLUG = "demo"
DEMO_TENANT_NAME = "Demo (örnek veri)"

RANDOM_SEED = 1907
ORDER_COUNT = 200
D2B_ORDER_COUNT = 12
HISTORY_DAYS = 90

CITIES = (
    "İstanbul",
    "Ankara",
    "İzmir",
    "Bursa",
    "Antalya",
    "Konya",
    "Adana",
    "Gaziantep",
    "Eskişehir",
    "Trabzon",
)

# Kategori bazlı komisyon tarifesi — Trendyol mertebesinde gerçekçi oranlar.
CATEGORY_COMMISSION: dict[str, str] = {
    "Mutfak/Kahve": "0.1850",
    "Mutfak/Aksesuar": "0.2100",
    "Mutfak/Pişirme": "0.1950",
    "Sofra/Servis": "0.2050",
    "Sofra/Tabak": "0.2050",
    "Dekorasyon": "0.2250",
    "Outlet": "0.2250",
    "Kahve/Tek Origin": "0.1450",
    "Kahve/Harman": "0.1450",
    "Kahve/Hazır": "0.1650",
    "Kahve/Numune": "0.1650",
    "Ekipman/Demleme": "0.1850",
    "Ekipman/Öğütücü": "0.1850",
    "Ekipman/Aksesuar": "0.2000",
    "Ekipman/Sarf": "0.2200",
    "Abonelik": "0.1200",
    "Hediye": "0.1800",
}

# Demo kargo tarifesi (KVN-EK-04): gönderi maliyetleri Ayarlar ekranında GÖRÜNEN
# bantlardan üretilir — ekrandaki tarife ile veri birbirini tutsun.
DEMO_CARGO_BANDS: tuple[tuple[str | None, str, str | None, str], ...] = (
    # (firma, desi_min, desi_max, tutar)
    (None, "0", "1", "54.90"),
    (None, "1", "2", "66.50"),
    (None, "2", "3", "78.00"),
    (None, "3", "5", "94.50"),
    (None, "5", "10", "128.00"),
    (None, "10", None, "175.00"),
    # Firma özel bandı, "tüm firmalar" bandını yener (spec §6.1 çözümleme sırası).
    ("Trendyol Express", "0", "1", "49.90"),
)


@dataclass
class DemoSummary:
    """Demo seed sonrası sayımlar."""

    tenant_id: str = ""
    counts: dict[str, int] = field(default_factory=dict)

    def bump(self, key: str, amount: int = 1) -> None:
        """Sayaç artırır."""
        self.counts[key] = self.counts.get(key, 0) + amount


def _demo_barcode(sku: str) -> str:
    """SKU'dan kararlı sahte barkod üretir.

    Yerleşik `hash()` süreç başına tohumlanır (PYTHONHASHSEED); demo verinin
    koşudan koşuya aynı kalması için kararlı bir özet kullanılır.
    """
    # sha1 burada yalnızca kararlı bir sayı üretmek için; kriptografik amaç yok.
    digest = hashlib.sha1(sku.encode("utf-8")).hexdigest()
    return f"869{int(digest[:12], 16) % 10_000_000_000:010d}"


def _cargo_cost(
    desi: Decimal, bands: list[cargo_engine.Band], *, carrier: str | None = None
) -> Decimal:
    """Desi bazlı kargo tahmini — demo tarifesinden çözülür (spec §6.1)."""
    return cargo_engine.estimate(desi=desi, bands=bands, carrier=carrier).amount


def _seed_cargo_tariffs(
    session: Session, tenant: Tenant, brand: Brand, summary: DemoSummary, today: date
) -> list[cargo_engine.Band]:
    """Markanın kargo tarifesini kurar ve motorun kullanacağı bantları döner."""
    bands: list[cargo_engine.Band] = []
    for carrier, desi_min, desi_max, price in DEMO_CARGO_BANDS:
        row = CargoTariff(
            tenant_id=tenant.id,
            brand_id=brand.id,
            carrier=carrier,
            desi_min=Decimal(desi_min),
            desi_max=Decimal(desi_max) if desi_max is not None else None,
            price=Decimal(price),
            valid_from=today - timedelta(days=180),
        )
        session.add(row)
        bands.append(
            cargo_engine.Band(
                desi_min=row.desi_min,
                desi_max=row.desi_max,
                price=row.price,
                carrier=row.carrier,
                valid_from=row.valid_from,
            )
        )
        summary.bump("cargo_tariffs")
    session.flush()
    return bands


def _rounded(value: Decimal) -> Decimal:
    """Parasal alanlar için 4 hane."""
    return value.quantize(Decimal("0.0001"))


def _seed_products(
    session: Session,
    tenant: Tenant,
    brand: Brand,
    store: Store,
    definitions: tuple[DemoProduct, ...],
    summary: DemoSummary,
    today: date,
) -> list[tuple[Product, DemoProduct]]:
    """Ürün + maliyet + lojistik + açılış stoku (spec §12C.4) kaydeder."""
    created: list[tuple[Product, DemoProduct]] = []
    for definition in definitions:
        product = Product(
            tenant_id=tenant.id,
            brand_id=brand.id,
            sku=definition.sku,
            name=definition.name,
            barcode=_demo_barcode(definition.sku),
            category=definition.category,
            vat_rate=definition.vat_rate,
            msrp=definition.msrp,
        )
        session.add(product)
        session.flush()
        summary.bump("products")

        session.add(
            ProductChannelMap(
                product_id=product.id,
                store_id=store.id,
                external_product_id=f"EXT-{definition.sku}",
                external_barcode=product.barcode,
            )
        )
        session.add(
            SkuCost(
                product_id=product.id,
                unit_cost=_rounded(definition.unit_cost),
                currency="TRY",
                source=CostSource.INVOICE_WAC,
                effective_from=today - timedelta(days=120),
                created_by="seed-demo",
            )
        )
        session.add(
            SkuLogistics(
                product_id=product.id,
                desi=definition.desi,
                default_carrier="Trendyol Express",
                effective_from=today - timedelta(days=120),
            )
        )
        # Güncel satış fiyatı — fiyat listesi export'unun kaynağı (spec §12A.1).
        session.add(
            SkuPrice(
                product_id=product.id,
                store_id=store.id,
                price=_rounded(definition.sale_price),
                effective_from=today - timedelta(days=120),
                created_by="seed-demo",
            )
        )

        # Açılış stoku: ledger hareketi + güncel durum (spec §12C.4). Adet 0 ise hareket
        # YAZILMAZ — sıfır adetli bir "devir" ortalama maliyet üretemez, defterden yeniden
        # kurulduğunda duruma uymazdı (stok tutulmayan abonelik SKU'ları böyledir).
        opening_qty = Decimal(definition.opening_qty)
        if opening_qty > 0:
            avg_cost = _rounded(definition.unit_cost).quantize(Decimal("0.000001"))
            moved_at = datetime.combine(
                today - timedelta(days=120), datetime.min.time(), tzinfo=UTC
            )
            session.add(
                InventoryLedger(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    product_id=product.id,
                    movement=InventoryMovement.OPENING,
                    qty_delta=opening_qty,
                    unit_cost_at_movement=avg_cost,
                    avg_cost_after=avg_cost,
                    on_hand_after=opening_qty,
                    ref_type="opening",
                    ref_id=str(product.id),
                    moved_at=moved_at,
                )
            )
            session.add(
                SkuCostState(
                    product_id=product.id,
                    on_hand_qty=opening_qty,
                    avg_cost=avg_cost,
                    last_movement_at=moved_at,
                )
            )
            summary.bump("inventory_ledger")
        created.append((product, definition))
    session.flush()
    return created


def _seed_commission_rates(
    session: Session,
    store: Store,
    products: list[tuple[Product, DemoProduct]],
    summary: DemoSummary,
    today: date,
) -> None:
    """Kategori tarifesi + birkaç ürün bazlı oran (spec §12B.1 hiyerarşisi için)."""
    categories = {definition.category for _, definition in products}
    for category in sorted(categories):
        session.add(
            CommissionRate(
                store_id=store.id,
                scope=CommissionScope.CATEGORY,
                category_code=category,
                rate=Decimal(CATEGORY_COMMISSION.get(category, "0.2000")),
                source=CommissionSource.API_CATEGORY,
                valid_from=today - timedelta(days=180),
                snapshot_date=today,
            )
        )
        summary.bump("commission_rates")

    # İlk üç ürün için ürün bazlı oran — hiyerarşide kategoriyi ezer.
    for product, definition in products[:3]:
        session.add(
            CommissionRate(
                store_id=store.id,
                scope=CommissionScope.PRODUCT,
                product_id=product.id,
                rate=Decimal(CATEGORY_COMMISSION.get(definition.category, "0.2000"))
                - Decimal("0.0100"),
                source=CommissionSource.API_PRODUCT,
                valid_from=today - timedelta(days=90),
                snapshot_date=today,
            )
        )
        summary.bump("commission_rates")

    # Değişiklik geçmişi: günlük snapshot diff'i gerçek kurulumda yazar, demo'da iki örnek
    # konur — biri kârı düşüren artış, biri kârı artıran indirim. Ekranın "geçmiş" sekmesi
    # boş kalmasın (CLAUDE.md §6: her ekran dolu durumda gezilebilir olmalı).
    ordered = sorted(categories)
    for offset, (category, old_rate, new_rate, impact) in enumerate(
        (
            (ordered[0], "0.2100", "0.2300", "-4820.00"),
            (ordered[-1], "0.1900", "0.1750", "960.00"),
        )
    ):
        session.add(
            CommissionChange(
                store_id=store.id,
                category_code=category,
                old_rate=Decimal(old_rate),
                new_rate=Decimal(new_rate),
                detected_at=datetime.combine(
                    today - timedelta(days=7 + offset * 12), datetime.min.time(), tzinfo=UTC
                ),
                monthly_profit_impact=Decimal(impact),
            )
        )
        summary.bump("commission_changes")


def _seed_orders(
    session: Session,
    tenant: Tenant,
    brand: Brand,
    store: Store,
    products: list[tuple[Product, DemoProduct]],
    rng: random.Random,
    count: int,
    summary: DemoSummary,
    now: datetime,
    *,
    prefix: str,
    bands: list[cargo_engine.Band],
    with_returns: bool = True,
    customers: list[Customer] | None = None,
) -> None:
    """Sipariş + satır + gönderi + iade üretir (farklı statüler dahil)."""
    carrier = "Trendyol Express" if prefix != "D2B" else "Aras Kargo"
    statuses = (
        [OrderStatus.DELIVERED] * 14
        + [OrderStatus.SHIPPED] * 3
        + [OrderStatus.CREATED] * 2
        + [OrderStatus.CANCELLED]
    )
    for index in range(count):
        order_date = now - timedelta(
            days=rng.randint(0, HISTORY_DAYS),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
        status = rng.choice(statuses)
        line_count = rng.choices([1, 2, 3], weights=[70, 25, 5])[0]
        chosen = rng.sample(products, k=min(line_count, len(products)))

        order = Order(
            tenant_id=tenant.id,
            brand_id=brand.id,
            store_id=store.id,
            # D2B satışı kurumsal müşteriye bağlıdır; kademe analizi bunun üstünden yapılır.
            customer_id=(customers[index % len(customers)].id if customers else None),
            external_order_id=f"{prefix}-{index + 1:05d}",
            order_date=order_date,
            status=status,
            customer_city=rng.choice(CITIES),
            gross_total=Decimal("0"),
            currency="TRY",
        )
        session.add(order)
        session.flush()

        gross_total = Decimal("0")
        total_desi = Decimal("0")
        for line_index, (product, definition) in enumerate(chosen):
            qty = rng.choices([1, 2, 3], weights=[80, 15, 5])[0]
            # Kampanyalı satışlar: satırların ~%20'sinde indirim uygulanır.
            discount = Decimal("0.90") if rng.randint(1, 100) <= 20 else Decimal("1.00")
            unit_price = _rounded(definition.sale_price * discount)
            line_gross = _rounded(unit_price * qty)
            gross_total += line_gross
            total_desi += definition.desi * qty

            line = OrderLine(
                tenant_id=tenant.id,
                brand_id=brand.id,
                order_id=order.id,
                product_id=product.id,
                external_line_id=f"{prefix}-{index + 1:05d}-{line_index + 1}",
                qty=qty,
                unit_sale_price=unit_price,
                line_gross=line_gross,
                vat_rate=definition.vat_rate,
                # D2B/kurumsal satışta komisyon YOKTUR (spec §12C.9).
                commission_rate_used=(
                    Decimal("0")
                    if prefix == "D2B"
                    else Decimal(CATEGORY_COMMISSION.get(definition.category, "0.2000"))
                ),
                commission_source=(
                    CommissionSource.MANUAL if prefix == "D2B" else CommissionSource.API_CATEGORY
                ),
                status=status,
            )
            session.add(line)
            session.flush()
            summary.bump("order_lines")

            # İade: teslim edilmiş satırların ~%8'i (kısmi iade dahil).
            if with_returns and status == OrderStatus.DELIVERED and rng.randint(1, 100) <= 8:
                returned_qty = 1 if qty == 1 else rng.randint(1, qty)
                session.add(
                    Return(
                        tenant_id=tenant.id,
                        brand_id=brand.id,
                        order_line_id=line.id,
                        return_date=order_date + timedelta(days=rng.randint(2, 14)),
                        qty=returned_qty,
                        reason=rng.choice(
                            ("Beğenmedi", "Hasarlı geldi", "Yanlış ürün", "Geç teslimat")
                        ),
                        refund_amount=_rounded(unit_price * returned_qty),
                        return_cargo_cost_estimated=_cargo_cost(definition.desi, bands),
                        cost_state=CostState.ESTIMATED,
                        restocked=rng.randint(1, 100) <= 70,
                    )
                )
                summary.bump("returns")

        order.gross_total = _rounded(gross_total)
        summary.bump("orders")

        if status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED):
            session.add(
                Shipment(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    order_id=order.id,
                    carrier=carrier,
                    tracking_no=f"TK{order.external_order_id[-10:]}",
                    desi_declared=total_desi,
                    cargo_cost_estimated=_cargo_cost(total_desi, bands, carrier=carrier),
                    cost_state=CostState.ESTIMATED,
                )
            )
            summary.bump("shipments")
    session.flush()


def _seed_purchasing(
    session: Session,
    tenant: Tenant,
    kahveji: Brand,
    alessi: Brand,
    kahveji_products: list[tuple[Product, DemoProduct]],
    alessi_products: list[tuple[Product, DemoProduct]],
    summary: DemoSummary,
    today: date,
    now: datetime,
) -> None:
    """Tedarikçi, alış faturaları ve bir ithalat dosyası (spec §12C)."""
    yurtici = Supplier(
        tenant_id=tenant.id, name="Ege Kahve Ticaret A.Ş.", vkn="1234567890", default_currency="TRY"
    )
    ithalat = Supplier(
        tenant_id=tenant.id, name="Alessi S.p.A.", vkn="IT00123456789", default_currency="EUR"
    )
    session.add_all([yurtici, ithalat])
    session.flush()
    summary.bump("suppliers", 2)

    # Yurtiçi alış faturaları — biri onaylı, biri incelemede.
    for offset, status in ((45, InvoiceStatus.CONFIRMED), (12, InvoiceStatus.REVIEW)):
        invoice = PurchaseInvoice(
            tenant_id=tenant.id,
            brand_id=kahveji.id,
            supplier_id=yurtici.id,
            invoice_no=f"EGE2026{offset:04d}",
            invoice_date=today - timedelta(days=offset),
            currency="TRY",
            landed_cost_extra=Decimal("1250.00"),
            status=status,
            confirmed_at=(
                datetime.combine(today - timedelta(days=offset), datetime.min.time(), tzinfo=UTC)
                if status == InvoiceStatus.CONFIRMED
                else None
            ),
        )
        session.add(invoice)
        session.flush()
        summary.bump("purchase_invoices")

        total = Decimal("0")
        for product, definition in kahveji_products[:6]:
            qty = Decimal("50")
            unit = _rounded(definition.unit_cost * Decimal("0.98"))
            total += unit * qty
            session.add(
                PurchaseInvoiceLine(
                    invoice_id=invoice.id,
                    raw_text=definition.name.upper(),
                    product_id=product.id,
                    qty=qty,
                    unit_price_original=unit,
                    unit_price_try=unit,
                    vat_rate=definition.vat_rate,
                    match_status=MatchStatus.AUTO,
                )
            )
            if status == InvoiceStatus.CONFIRMED:
                session.add(
                    SupplierProductMap(
                        supplier_id=yurtici.id,
                        raw_name_normalized=definition.name.lower(),
                        barcode=product.barcode,
                        product_id=product.id,
                        confirmed_at=now,
                    )
                )
            summary.bump("purchase_invoice_lines")

        # İncelemedeki faturada eşleştirme ekranının İKİ zor durumu da bulunsun:
        # fuzzy öneri gelen satır ve hiçbir ürüne benzemeyen ambalaj satırı. Onay
        # ekranı demo veriyle yalnızca "hepsi eşleşti" hâlinde gezilemez olmasın.
        if status == InvoiceStatus.REVIEW:
            for raw_text, qty, unit in (
                ("GUATEMALA ANTIGUA 250G CEK.", Decimal("40"), Decimal("174.44")),
                ("KRAFT KUTU AMBALAJ 24LU", Decimal("10"), Decimal("62.00")),
            ):
                total += unit * qty
                session.add(
                    PurchaseInvoiceLine(
                        invoice_id=invoice.id,
                        raw_text=raw_text,
                        product_id=None,
                        qty=qty,
                        unit_price_original=unit,
                        unit_price_try=unit,
                        vat_rate=Decimal("20"),
                        match_status=MatchStatus.UNMATCHED,
                    )
                )
                summary.bump("purchase_invoice_lines")

        invoice.total = _rounded(total)

    # Ayrıştırılmış ama toplamı tutmayan fatura: PDF'te bir satır okunamamış
    # (gerçek hayatta sık) — doğrulama barının kırmızı hâli demo veriyle görünür.
    torn = PurchaseInvoice(
        tenant_id=tenant.id,
        brand_id=kahveji.id,
        supplier_id=yurtici.id,
        invoice_no="EGE20260078",
        invoice_date=today - timedelta(days=3),
        currency="TRY",
        status=InvoiceStatus.PARSED,
    )
    session.add(torn)
    session.flush()
    summary.bump("purchase_invoices")

    torn_total = Decimal("0")
    for product, definition in kahveji_products[:3]:
        qty = Decimal("20")
        unit = _rounded(definition.unit_cost * Decimal("0.98"))
        torn_total += unit * qty
        session.add(
            PurchaseInvoiceLine(
                invoice_id=torn.id,
                raw_text=definition.name.upper(),
                product_id=product.id,
                qty=qty,
                unit_price_original=unit,
                unit_price_try=unit,
                vat_rate=definition.vat_rate,
                match_status=MatchStatus.AUTO,
            )
        )
        summary.bump("purchase_invoice_lines")
    # Beyan edilen toplam okunamayan satırı da içeriyor: 620 TL fark.
    torn.total = _rounded(torn_total + Decimal("620.00"))

    # İthalat dosyası (Alessi): EUR mal bedeli + TL navlun + müşavirlik (spec §12C.7).
    import_file = ImportFile(
        tenant_id=tenant.id,
        brand_id=alessi.id,
        supplier_id=ithalat.id,
        file_no="ITH-2026-014",
        beyanname_no="26341300IM123456",
        beyanname_date=today - timedelta(days=38),
        currency="EUR",
        fx_rate_beyanname=Decimal("37.500000"),
        # İthalat KDV'si maliyete GİRMEZ; yalnızca nakit akışı için kayıt altında.
        import_vat_paid=Decimal("114500.00"),
    )
    session.add(import_file)
    session.flush()
    summary.bump("import_files")

    # Mal faturası dosyaya bağlanır; landed cost artık dosyanın masraf kalemlerinden gelir.
    goods_invoice = PurchaseInvoice(
        tenant_id=tenant.id,
        brand_id=alessi.id,
        supplier_id=ithalat.id,
        import_file_id=import_file.id,
        invoice_no="IT-2026-4471",
        invoice_date=today - timedelta(days=40),
        currency="EUR",
        fx_rate=IMPORT_FX_BEYANNAME,
        status=InvoiceStatus.PARSED,
    )
    session.add(goods_invoice)
    session.flush()
    summary.bump("purchase_invoices")

    goods_total_eur = Decimal("0")
    for product, definition in alessi_products[:4]:
        qty = Decimal(40)
        unit_eur = (definition.unit_cost / IMPORT_FX_BEYANNAME).quantize(Decimal("0.01"))
        goods_total_eur += unit_eur * qty
        session.add(
            PurchaseInvoiceLine(
                invoice_id=goods_invoice.id,
                raw_text=definition.name,
                product_id=product.id,
                qty=qty,
                unit_price_original=unit_eur,
                unit_price_try=_rounded(unit_eur * IMPORT_FX_BEYANNAME),
                vat_rate=definition.vat_rate,
                match_status=MatchStatus.AUTO,
            )
        )
        summary.bump("purchase_invoice_lines")
    goods_invoice.total = _rounded(goods_total_eur)
    session.flush()

    # Masraf kalemleri servis üzerinden girilir: TL karşılıkları orada sabitlenir.
    # Mal bedeli kalem olarak GİRİLMEZ — fatura satırlarında zaten var, iki kez sayılmaz.
    for item_type, amount, currency in (
        (ImportCostItemType.NAVLUN, Decimal("38500.00"), "TRY"),
        (ImportCostItemType.SIGORTA, Decimal("320.00"), "EUR"),
        (ImportCostItemType.GUMRUK_MUSAVIRLIGI, Decimal("14500.00"), "TRY"),
        (ImportCostItemType.ARDIYE_LIMAN, Decimal("8750.00"), "TRY"),
    ):
        add_cost_item(
            session,
            import_file=import_file,
            item_type=item_type,
            amount_original=amount,
            currency=currency,
            vendor="Med Lojistik" if item_type is ImportCostItemType.NAVLUN else None,
        )
        summary.bump("import_cost_items")

    # Onay motorun kendisiyle yapılır: ledger + WAC + maliyet versiyonu birlikte yazılır,
    # böylece demo durumu da defterden birebir yeniden kurulabilir kalır (§12C.11).
    confirm_file(session, import_file=import_file, user="seed-demo")

    # Ödeme + kur farkı: beyanname kuru 37,50 · ödeme kuru 39,20 (spec §12C.8).
    record_payment(
        session,
        import_file=import_file,
        pay_date=today - timedelta(days=10),
        amount_original=Decimal("8000.00"),
        fx_rate_payment=IMPORT_FX_PAYMENT,
    )
    summary.bump("supplier_payments")

    # Alessi ürünleri için tedarikçi eşleştirme belleği.
    for product, definition in alessi_products[:5]:
        session.add(
            SupplierProductMap(
                supplier_id=ithalat.id,
                raw_name_normalized=definition.name.lower(),
                barcode=product.barcode,
                product_id=product.id,
                confirmed_at=now,
            )
        )
    session.flush()


def _seed_customers(
    session: Session, tenant: Tenant, brand: Brand, summary: DemoSummary
) -> list[Customer]:
    """Kurumsal müşteriler — D2B siparişleri bunlara bağlanır (spec §12C.9)."""
    created: list[Customer] = []
    for name, tier, discount in (
        ("Divan Otelcilik A.Ş.", "gold", Decimal("18.00")),
        ("Mimarlar Kolektifi Ltd.", "silver", Decimal("12.00")),
        ("Concept Store İstanbul", "bayi", Decimal("25.00")),
    ):
        customer = Customer(
            tenant_id=tenant.id,
            brand_id=brand.id,
            name=name,
            tier=tier,
            default_discount_pct=discount,
        )
        session.add(customer)
        created.append(customer)
        summary.bump("customers")
    session.flush()
    return created


def _seed_settlements(
    session: Session,
    tenant: Tenant,
    brand: Brand,
    store: Store,
    summary: DemoSummary,
    rng: random.Random,
    today: date,
) -> None:
    """Hakediş kalemleri (spec §7): satış, komisyon, kargo, hizmet bedeli, ceza.

    Gerçek hayatta kalemlerin çoğu bizim hesabımızla tutar; küçük bir kısmı tutmaz —
    mutabakat ekranının varlık sebebi o kısımdır. Demo veride bilinçli olarak üç tür
    sapma var: komisyonu farklı kesilmiş satırlar, siparişi bulunamayan bir kalem ve
    siparişe bağlanamayan bir ceza.
    """
    period_start = today.replace(day=1)
    lines = list(
        session.scalars(
            select(OrderLine)
            .join(Order, Order.id == OrderLine.order_id)
            .where(Order.store_id == store.id, Order.status != OrderStatus.CANCELLED)
            .order_by(OrderLine.external_line_id)
            .limit(40)
        ).all()
    )
    if not lines:
        return

    for index, line in enumerate(lines):
        order = session.scalar(select(Order).where(Order.id == line.order_id))
        assert order is not None
        # Komisyon motorla aynı tabandan hesaplanır: iade edilen adedin geliri —
        # dolayısıyla komisyonu — geri çevrilir. Aksi halde her iadeli satır sahte fark
        # üretir ve mutabakat ekranı okunamaz hale gelir.
        returned = sum(
            (
                item.qty
                for item in session.scalars(
                    select(Return).where(Return.order_line_id == line.id)
                ).all()
            ),
            0,
        )
        sold_ratio = (
            Decimal(max(line.qty - returned, 0)) / Decimal(line.qty) if line.qty else Decimal("0")
        )
        commission = _rounded(
            line.line_gross * sold_ratio * (line.commission_rate_used or Decimal("0"))
        )
        # Her 7. satırda platform farklı kesmiş: mutabakat bunu yakalamalı.
        if index % 7 == 6:
            commission = _rounded(commission * Decimal("1.08"))

        session.add(
            SettlementRecord(
                tenant_id=tenant.id,
                brand_id=brand.id,
                store_id=store.id,
                external_ref=line.external_line_id,
                record_type=SettlementRecordType.COMMISSION,
                amount=-commission,
                vat_amount=None,
                transaction_date=period_start + timedelta(days=rng.randint(0, 20)),
            )
        )
        summary.bump("settlement_records")

    # Siparişi bulunamayan kalem: ayrı kuyrukta görünmeli (spec §7.5).
    session.add(
        SettlementRecord(
            tenant_id=tenant.id,
            brand_id=brand.id,
            store_id=store.id,
            external_ref="TY-BILINMEYEN-9999",
            record_type=SettlementRecordType.COMMISSION,
            amount=Decimal("-142.50"),
            transaction_date=period_start + timedelta(days=5),
        )
    )
    # Ceza: siparişe bağlanmaz, mağaza gideridir (spec §6.3.7).
    session.add(
        SettlementRecord(
            tenant_id=tenant.id,
            brand_id=brand.id,
            store_id=store.id,
            external_ref="CEZA-2026-08-01",
            record_type=SettlementRecordType.PENALTY,
            amount=Decimal("-350.00"),
            transaction_date=period_start + timedelta(days=9),
        )
    )
    summary.bump("settlement_records", 2)
    session.flush()


def _seed_cargo_invoice(
    session: Session,
    tenant: Tenant,
    brand: Brand,
    summary: DemoSummary,
    rng: random.Random,
    today: date,
) -> None:
    """Kargo faturası: gönderilerin ~%60'ının maliyeti kesinleşir (spec §5.3, §6.2).

    Gerçek tutar tahminden sapar (kargo firması desiyi kendi ölçer); demo veride bu sapma
    bilinçli olarak hem yukarı hem aşağı yönlüdür ki "revize edilen kâr" görünsün.
    """
    shipments = list(
        session.scalars(
            select(Shipment).where(Shipment.brand_id == brand.id).order_by(Shipment.id)
        ).all()
    )
    if not shipments:
        return

    chosen = shipments[: max(1, len(shipments) * 6 // 10)]
    lines: list[dict[str, Any]] = []
    total = Decimal("0")
    for index, shipment in enumerate(chosen, start=1):
        # Fatura tutarı tahminin %85-%125'i arasında: kargo firması kendi desisini ölçer.
        factor = Decimal(rng.randint(85, 125)) / Decimal("100")
        actual = _rounded(shipment.cargo_cost_estimated * factor)
        shipment.cargo_cost_actual = actual
        shipment.desi_invoiced = shipment.desi_declared
        shipment.cost_state = CostState.ACTUAL
        total += actual
        lines.append(
            {
                "row_no": index,
                "reference": shipment.tracking_no or "",
                "action": "kesinlesti",
                "amount": str(actual),
                "previous": str(shipment.cargo_cost_estimated),
                "message": "",
            }
        )

    session.add(
        CargoInvoice(
            tenant_id=tenant.id,
            brand_id=brand.id,
            store_id=chosen[0].order_id and _store_of(session, chosen[0]),
            invoice_no=f"KRG-{today:%Y%m}-001",
            period=f"{today:%Y-%m}",
            total=_rounded(total),
            lines=lines,
        )
    )
    summary.bump("cargo_invoices")
    session.flush()


def _store_of(session: Session, shipment: Shipment) -> uuid.UUID:
    """Gönderinin siparişinin mağazası."""
    order = session.scalar(select(Order).where(Order.id == shipment.order_id))
    assert order is not None
    return order.store_id


def _seed_alerts_and_workspace(
    session: Session,
    tenant: Tenant,
    kahveji: Brand,
    alessi: Brand,
    kahveji_products: list[tuple[Product, DemoProduct]],
    alessi_products: list[tuple[Product, DemoProduct]],
    summary: DemoSummary,
) -> None:
    """Uyarılar, taslak ürünler, senaryolar ve B2B müşterileri."""
    # Tür adları literal DEĞİL, servislerin gerçekten yazdığı sabitlerden gelir: sabit
    # yeniden adlandırılırsa demo veri de kendiliğinden takip eder (KVN-EK-06).
    alerts = (
        (kahveji, AlertSeverity.CRITICAL, MARGIN_FLOOR_ALERT, "KHV-SMPL-50 negatif marjda: −%8,4"),
        (
            kahveji,
            AlertSeverity.WARNING,
            COMMISSION_CHANGE_ALERT,
            "Ekipman/Sarf komisyonu %21,0 → %22,0",
        ),
        (
            kahveji,
            AlertSeverity.WARNING,
            UNMATCHED_CARGO_ALERT,
            "KRG-2026-08-001 faturasında 2 satır gönderiyle eşleşmedi",
        ),
        (kahveji, AlertSeverity.INFO, NEGATIVE_STOCK_ALERT, "KHV-BLD-ESP stoğu −3 adede düştü"),
        (
            alessi,
            AlertSeverity.CRITICAL,
            MSRP_ALERT,
            "ALS-OUTL-1 liste fiyatı MSRP disiplinini bozuyor",
        ),
        (
            alessi,
            AlertSeverity.WARNING,
            STALE_SYNC_ALERT,
            "Alessi D2B mağazası 14 saattir senkronlanmadı",
        ),
        (alessi, AlertSeverity.INFO, NEGATIVE_STOCK_ALERT, "ALS-KTL-01 stok 6 adete düştü"),
    )
    for index, (brand, severity, alert_type, message) in enumerate(alerts):
        session.add(
            Alert(
                tenant_id=tenant.id,
                brand_id=brand.id,
                type=alert_type,
                severity=severity,
                message=message,
                # Ekran hem açık hem kapatılmış durumu göstersin: sonuncusu kapatılmış.
                acknowledged_at=(
                    datetime.now(UTC) - timedelta(hours=3) if index == len(alerts) - 1 else None
                ),
            )
        )
        summary.bump("alerts")

    drafts = (
        (
            kahveji,
            "Ruanda Nyungwe 250g",
            "KHV-RWA-250",
            Decimal("205.00"),
            Decimal("419.00"),
            Decimal("1.00"),
        ),
        (
            alessi,
            "Alessi Plissé Su Isıtıcısı",
            "ALS-PLIS-K",
            Decimal("5400.00"),
            Decimal("9890.00"),
            Decimal("20.00"),
        ),
    )
    for brand, name, sku, cost, price, vat in drafts:
        session.add(
            ProductDraft(
                tenant_id=tenant.id,
                brand_id=brand.id,
                name=name,
                sku_onerisi=sku,
                alis_maliyeti=cost,
                hedef_satis_fiyati=price,
                kanal="trendyol",
                vat_rate=vat,
                desi=Decimal("2.00"),
                status=DraftStatus.DRAFT,
            )
        )
        summary.bump("product_drafts")

    scenarios = (
        (kahveji, kahveji_products[0][0], "Mevcut fiyat", Decimal("389.00")),
        (kahveji, kahveji_products[0][0], "Kampanya -%10", Decimal("350.10")),
        (alessi, alessi_products[0][0], "Zam senaryosu +%5", Decimal("7234.50")),
    )
    for brand, product, name, price in scenarios:
        session.add(
            PricingScenario(
                tenant_id=tenant.id,
                brand_id=brand.id,
                product_id=product.id,
                name=name,
                satis_fiyati=price,
                adet_varsayimi=100,
                created_by="seed-demo",
            )
        )
        summary.bump("pricing_scenarios")

    session.flush()


def seed_demo(session: Session) -> DemoSummary:
    """Demo tenant'ını sıfırdan kurar. Var olan demo verisi önce temizlenir (idempotent)."""
    with system_scope():
        return _seed_demo(session)


def _seed_demo(session: Session) -> DemoSummary:
    wipe_demo(session)

    summary = DemoSummary()
    rng = random.Random(RANDOM_SEED)
    now = datetime.now(UTC)
    today = now.date()

    tenant = get_or_create_tenant(session, DEMO_TENANT_SLUG, DEMO_TENANT_NAME)
    summary.tenant_id = str(tenant.id)

    base_result = SeedResult()
    channels = ensure_channels(session, base_result)
    kahveji = ensure_brand(
        session,
        tenant,
        "kahveji",
        "Kahveji",
        base_result,
        min_margin_floor_pct=Decimal("12.00"),
        default_vat_rate=Decimal("1.00"),
        features=KAHVEJI_FEATURES,
    )
    alessi = ensure_brand(
        session,
        tenant,
        "alessi",
        "Alessi",
        base_result,
        min_margin_floor_pct=Decimal("18.00"),
        default_vat_rate=Decimal("20.00"),
        features=ALESSI_FEATURES,
    )
    summary.bump("brands", 2)

    kahveji_store = ensure_store(
        session,
        tenant,
        kahveji,
        channels[ChannelCode.TRENDYOL],
        "Kahveji — Trendyol",
        base_result,
        external_seller_id="DEMO-KHV",
        service_fee_per_order=Decimal("8.99"),
    )
    alessi_store = ensure_store(
        session,
        tenant,
        alessi,
        channels[ChannelCode.TRENDYOL],
        "Alessi — Trendyol",
        base_result,
        external_seller_id="DEMO-ALS",
        service_fee_per_order=Decimal("8.99"),
    )
    alessi_d2b = ensure_store(
        session,
        tenant,
        alessi,
        channels[ChannelCode.MANUAL],
        "Alessi D2B",
        base_result,
        external_seller_id="DEMO-ALS-D2B",
    )
    summary.bump("stores", 3)

    ensure_user(
        session,
        tenant,
        "demo@mokkalabs.com",
        "Demo Kullanıcı",
        [kahveji, alessi],
        base_result,
        role=UserRole.ADMIN,
        is_holding_viewer=True,
    )

    kahveji_products = _seed_products(
        session, tenant, kahveji, kahveji_store, KAHVEJI_PRODUCTS, summary, today
    )
    alessi_products = _seed_products(
        session, tenant, alessi, alessi_store, ALESSI_PRODUCTS, summary, today
    )

    _seed_commission_rates(session, kahveji_store, kahveji_products, summary, today)
    _seed_commission_rates(session, alessi_store, alessi_products, summary, today)

    # Kargo tarifesi siparişlerden ÖNCE kurulur: gönderi tahminleri bu bantlardan çıkar.
    kahveji_bands = _seed_cargo_tariffs(session, tenant, kahveji, summary, today)
    alessi_bands = _seed_cargo_tariffs(session, tenant, alessi, summary, today)

    # Sipariş hacmi markalar arasında bölünür: Kahveji daha çok adet, Alessi daha yüksek sepet.
    kahveji_orders = ORDER_COUNT * 6 // 10
    _seed_orders(
        session,
        tenant,
        kahveji,
        kahveji_store,
        kahveji_products,
        rng,
        kahveji_orders,
        summary,
        now,
        prefix="KHV",
        bands=kahveji_bands,
    )
    _seed_orders(
        session,
        tenant,
        alessi,
        alessi_store,
        alessi_products,
        rng,
        ORDER_COUNT - kahveji_orders,
        summary,
        now,
        prefix="ALS",
        bands=alessi_bands,
    )
    # D2B: komisyonsuz kurumsal satış (spec §12C.9).
    d2b_customers = _seed_customers(session, tenant, alessi, summary)
    _seed_orders(
        session,
        tenant,
        alessi,
        alessi_d2b,
        alessi_products,
        rng,
        D2B_ORDER_COUNT,
        summary,
        now,
        prefix="D2B",
        bands=alessi_bands,
        with_returns=False,
        customers=d2b_customers,
    )

    _seed_purchasing(
        session, tenant, kahveji, alessi, kahveji_products, alessi_products, summary, today, now
    )
    # Fire/hasar (spec §12C.10): kırılgan ürünlerde gerçekçi birkaç kayıt.
    for product, _definition in alessi_products[:2]:
        damage(
            session,
            product=product,
            qty=Decimal(2),
            reason="Nakliyede kırıldı — sevk 2026/14",
            moved_at=now - timedelta(days=20),
        )
        summary.bump("inventory_ledger")

    # Satış/iade stok hareketleri (spec §12C.1) — stok defteri ekranı boş kalmasın.
    sales = record_sales(session)
    returns = record_returns(session)
    summary.bump("inventory_ledger", sales.sale_out + returns.return_in + returns.return_out)

    _seed_cargo_invoice(session, tenant, kahveji, summary, rng, today)
    _seed_settlements(session, tenant, kahveji, kahveji_store, summary, rng, today)
    _seed_alerts_and_workspace(
        session, tenant, kahveji, alessi, kahveji_products, alessi_products, summary
    )

    session.commit()
    return summary


def wipe_demo(session: Session) -> int:
    """Demo tenant'ını ve tüm verisini siler. Gerçek tenant'a dokunmaz.

    Silme sırası FK bağımlılıklarına göre elle verilir: `brand_id` FK'leri RESTRICT
    olduğundan tenant cascade'ine güvenilemez.
    """
    with system_scope():
        return _wipe_demo(session)


def _wipe_demo(session: Session) -> int:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG))
    if tenant is None:
        return 0

    tenant_id = tenant.id
    product_ids = select(Product.id).where(Product.tenant_id == tenant_id)
    order_ids = select(Order.id).where(Order.tenant_id == tenant_id)
    line_ids = select(OrderLine.id).where(OrderLine.tenant_id == tenant_id)
    store_ids = select(Store.id).where(Store.tenant_id == tenant_id)
    supplier_ids = select(Supplier.id).where(Supplier.tenant_id == tenant_id)
    invoice_ids = select(PurchaseInvoice.id).where(PurchaseInvoice.tenant_id == tenant_id)
    import_file_ids = select(ImportFile.id).where(ImportFile.tenant_id == tenant_id)
    user_ids = select(User.id).where(User.tenant_id == tenant_id)
    brand_ids = select(Brand.id).where(Brand.tenant_id == tenant_id)

    statements = (
        delete(ProfitRevision).where(ProfitRevision.tenant_id == tenant_id),
        delete(LineProfit).where(LineProfit.tenant_id == tenant_id),
        delete(ReconciliationDiff).where(ReconciliationDiff.tenant_id == tenant_id),
        delete(SettlementRecord).where(SettlementRecord.tenant_id == tenant_id),
        delete(Return).where(Return.tenant_id == tenant_id),
        delete(Shipment).where(Shipment.tenant_id == tenant_id),
        delete(OrderLine).where(OrderLine.id.in_(line_ids)),
        delete(Order).where(Order.id.in_(order_ids)),
        delete(RawEvent).where(RawEvent.tenant_id == tenant_id),
        delete(CargoInvoice).where(CargoInvoice.tenant_id == tenant_id),
        delete(AdSpend).where(AdSpend.tenant_id == tenant_id),
        delete(Promotion).where(Promotion.tenant_id == tenant_id),
        delete(PurchaseInvoiceLine).where(PurchaseInvoiceLine.invoice_id.in_(invoice_ids)),
        delete(PurchaseInvoice).where(PurchaseInvoice.tenant_id == tenant_id),
        delete(ImportCostItem).where(ImportCostItem.import_file_id.in_(import_file_ids)),
        delete(SupplierPayment).where(SupplierPayment.tenant_id == tenant_id),
        delete(ImportFile).where(ImportFile.tenant_id == tenant_id),
        delete(SupplierProductMap).where(SupplierProductMap.supplier_id.in_(supplier_ids)),
        delete(InventoryLedger).where(InventoryLedger.tenant_id == tenant_id),
        delete(SkuCostState).where(SkuCostState.product_id.in_(product_ids)),
        delete(CommissionChange).where(CommissionChange.store_id.in_(store_ids)),
        delete(CommissionRate).where(CommissionRate.store_id.in_(store_ids)),
        delete(CargoTariff).where(CargoTariff.tenant_id == tenant_id),
        delete(SkuCost).where(SkuCost.product_id.in_(product_ids)),
        delete(SkuLogistics).where(SkuLogistics.product_id.in_(product_ids)),
        delete(SkuPrice).where(SkuPrice.product_id.in_(product_ids)),
        delete(ProductChannelMap).where(ProductChannelMap.product_id.in_(product_ids)),
        delete(PricingScenario).where(PricingScenario.tenant_id == tenant_id),
        delete(ProductDraft).where(ProductDraft.tenant_id == tenant_id),
        delete(ImportBatch).where(ImportBatch.tenant_id == tenant_id),
        delete(Alert).where(Alert.tenant_id == tenant_id),
        delete(AuditLog).where(AuditLog.tenant_id == tenant_id),
        delete(Customer).where(Customer.tenant_id == tenant_id),
        delete(Product).where(Product.tenant_id == tenant_id),
        delete(Supplier).where(Supplier.tenant_id == tenant_id),
        delete(StoreCredential).where(StoreCredential.store_id.in_(store_ids)),
        delete(Store).where(Store.tenant_id == tenant_id),
        delete(UserBrandRole).where(UserBrandRole.user_id.in_(user_ids)),
        delete(BrandFeature).where(BrandFeature.brand_id.in_(brand_ids)),
        delete(User).where(User.tenant_id == tenant_id),
        delete(Brand).where(Brand.tenant_id == tenant_id),
        delete(Tenant).where(Tenant.id == tenant_id),
    )
    deleted = 0
    for statement in statements:
        result = cast("CursorResult[Any]", session.execute(statement))
        deleted += result.rowcount or 0
    session.commit()
    return deleted
