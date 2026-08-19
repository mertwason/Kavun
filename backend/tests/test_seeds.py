"""KVN-02: çekirdek seed ve demo veri seti."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import system_scope
from app.models.catalog import CommissionRate, Product
from app.models.enums import AlertSeverity, CommissionScope, InventoryMovement, OrderStatus
from app.models.identity import Brand, BrandFeature, Store, Tenant, User
from app.models.inventory import ImportCostItem, ImportFile, InventoryLedger, SkuCostState
from app.models.results import Alert
from app.models.transactions import Order, OrderLine, Return
from app.seeds.base import ALESSI_FEATURES, TENANT_SLUG, seed_base
from app.seeds.catalog_data import demo_opening_stock_count, demo_product_count
from app.seeds.demo import DEMO_TENANT_SLUG, _demo_barcode, seed_demo, wipe_demo
from app.services.inventory import rebuild_state


@pytest.fixture(autouse=True)
def system_context() -> Iterator[None]:
    """Seed testleri sistem bağlamında koşar.

    Seed ve doğrulama sorguları markalar üstü işlerdir; brand-scope guard'ı
    (KVN-03) bu bağlamı açıkça istemeyen sorguları reddeder.
    """
    with system_scope():
        yield


def test_seed_base_creates_expected_structure(db_session: Session) -> None:
    """Tenant, 2 marka, 5 kanal, 3 mağaza ve admin kullanıcı kurulur (spec §12.5)."""
    result = seed_base(db_session)

    assert result.created["brands"] == 2
    assert result.created["channels"] == 5
    assert result.created["stores"] == 3
    assert set(result.brands) == {"kahveji", "alessi"}

    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    assert tenant is not None
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_seed_base_is_idempotent(db_session: Session) -> None:
    """İkinci koşu hiçbir şey yaratmaz — seed tekrar çalıştırılabilir."""
    seed_base(db_session)
    second = seed_base(db_session)

    assert second.created == {}
    assert db_session.scalar(select(func.count()).select_from(Brand)) == 2
    assert db_session.scalar(select(func.count()).select_from(Store)) == 3


def test_brand_feature_flags_follow_spec(db_session: Session) -> None:
    """Alessi'de dört modül açık, Kahveji'de dördü de kapalı (spec §3A.4)."""
    seed_base(db_session)

    def flags(slug: str) -> dict[str, bool]:
        brand = db_session.scalar(select(Brand).where(Brand.slug == slug))
        assert brand is not None
        rows = db_session.scalars(
            select(BrandFeature).where(BrandFeature.brand_id == brand.id)
        ).all()
        return {row.feature_code: row.enabled for row in rows}

    alessi_flags = flags("alessi")
    kahveji_flags = flags("kahveji")

    assert all(alessi_flags[feature] for feature in ALESSI_FEATURES)
    assert not any(kahveji_flags.values())
    # "Kayıt yok" ile "kapalı" karışmasın: her marka için tam liste yazılır.
    assert set(alessi_flags) == set(kahveji_flags) == set(ALESSI_FEATURES)


def test_seed_demo_fills_every_screen(db_session: Session) -> None:
    """Demo veri tüm ekranları dolduracak hacimde ve çeşitlilikte olmalı (CLAUDE.md §6)."""
    summary = seed_demo(db_session)

    assert summary.counts["products"] == demo_product_count()
    assert summary.counts["orders"] >= 200
    assert summary.counts["order_lines"] > summary.counts["orders"]
    assert summary.counts["returns"] > 0
    assert summary.counts["alerts"] >= 6

    # Statü çeşitliliği: iptal, kargolandı ve teslim edildi birlikte bulunmalı.
    statuses = set(db_session.scalars(select(Order.status).distinct()).all())
    assert {OrderStatus.DELIVERED, OrderStatus.CANCELLED} <= statuses

    # Uyarılar üç severity'yi de kapsar (tasarım brief'i, kalıp 7).
    severities = set(db_session.scalars(select(Alert.severity).distinct()).all())
    assert severities == {AlertSeverity.INFO, AlertSeverity.WARNING, AlertSeverity.CRITICAL}


def test_demo_has_both_vat_rates_and_negative_margin_examples(db_session: Session) -> None:
    """Gıda %1 ve genel %20 birlikte; maliyetin altında satılan SKU'lar var (spec §6.3.4)."""
    seed_demo(db_session)

    vat_rates = set(db_session.scalars(select(Product.vat_rate).distinct()).all())
    assert {Decimal("1.00"), Decimal("20.00")} <= vat_rates

    # Negatif marj adayı: satış fiyatı, maliyet + komisyon + kargonun altında kalan satırlar.
    cheap_lines = db_session.scalar(
        select(func.count())
        .select_from(OrderLine)
        .where(OrderLine.unit_sale_price < Decimal("100"))
    )
    assert cheap_lines and cheap_lines > 0


def test_demo_seed_is_repeatable(db_session: Session) -> None:
    """İkinci koşu önce temizler: sayımlar aynı kalır, veri ikiye katlanmaz."""
    first = seed_demo(db_session)
    second = seed_demo(db_session)

    assert first.counts == second.counts
    assert db_session.scalar(select(func.count()).select_from(Product)) == demo_product_count()


def test_demo_data_stays_in_demo_tenant(db_session: Session) -> None:
    """Demo veri gerçek tenant'a karışmaz (CLAUDE.md §6)."""
    seed_base(db_session)
    seed_demo(db_session)

    real_tenant = db_session.scalar(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    demo_tenant = db_session.scalar(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG))
    assert real_tenant is not None and demo_tenant is not None

    real_products = db_session.scalar(
        select(func.count()).select_from(Product).where(Product.tenant_id == real_tenant.id)
    )
    demo_products = db_session.scalar(
        select(func.count()).select_from(Product).where(Product.tenant_id == demo_tenant.id)
    )
    assert real_products == 0
    assert demo_products == demo_product_count()


def test_wipe_demo_removes_demo_only(db_session: Session) -> None:
    """`wipe-demo` demo tenant'ını siler, gerçek tenant'a dokunmaz."""
    seed_base(db_session)
    seed_demo(db_session)

    deleted = wipe_demo(db_session)
    assert deleted > 0

    assert db_session.scalar(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG)) is None
    assert db_session.scalar(select(Tenant).where(Tenant.slug == TENANT_SLUG)) is not None
    for model in (Product, Order, OrderLine, Return, Alert, SkuCostState):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0
    # Gerçek tenant'ın yapısı yerinde kalır.
    assert db_session.scalar(select(func.count()).select_from(Store)) == 3


def test_demo_opening_stock_matches_ledger(db_session: Session) -> None:
    """Açılış stoku hem ledger'a hem güncel duruma yazılır (spec §12C.4)."""
    seed_demo(db_session)

    # Adedi 0 olan SKU'ya (abonelik) devir yazılmaz — sıfır adet ortalama maliyet üretmez.
    openings = db_session.scalar(
        select(func.count())
        .select_from(InventoryLedger)
        .where(InventoryLedger.movement == InventoryMovement.OPENING)
    )
    assert openings == demo_opening_stock_count()

    states = db_session.scalars(select(SkuCostState)).all()
    assert any(state.on_hand_qty > 0 for state in states)
    assert all(state.avg_cost > 0 for state in states if state.on_hand_qty > 0)


def test_demo_state_can_be_rebuilt_from_the_ledger(db_session: Session) -> None:
    """§12C.11: demo verinin durumu defterden birebir yeniden üretilebilir olmalı.

    Elle kurulan seed satırları motorun üreteceğinden sapamaz; sapma burada yakalanır.
    """
    seed_demo(db_session)

    with system_scope():
        summary = rebuild_state(db_session, dry_run=True)

    assert summary.mismatches == []
    assert summary.movements > 0


def test_demo_import_file_excludes_import_vat_from_cost(db_session: Session) -> None:
    """İthalat KDV'si masraf kalemi DEĞİLDİR, ayrı alanda tutulur (spec §12C.7)."""
    seed_demo(db_session)

    import_file = db_session.scalar(select(ImportFile))
    assert import_file is not None
    assert import_file.import_vat_paid is not None and import_file.import_vat_paid > 0

    item_types = db_session.scalars(
        select(ImportCostItem.item_type).where(ImportCostItem.import_file_id == import_file.id)
    ).all()
    assert all("kdv" not in item_type.value for item_type in item_types)


def test_demo_commission_rates_cover_hierarchy(db_session: Session) -> None:
    """Hem kategori hem ürün bazlı oran var — çözümleme hiyerarşisi test edilebilir (§12B.1)."""
    seed_demo(db_session)

    scopes = set(db_session.scalars(select(CommissionRate.scope).distinct()).all())
    assert scopes == {CommissionScope.CATEGORY, CommissionScope.PRODUCT}


def test_demo_barcodes_are_stable_across_processes(db_session: Session) -> None:
    """Barkodlar süreçten sürece değişmemeli (yerleşik `hash()` kullanılmaz)."""
    seed_demo(db_session)

    barcode = db_session.scalar(select(Product.barcode).where(Product.sku == "KHV-ETH-250"))
    assert barcode == _demo_barcode("KHV-ETH-250")
    assert barcode is not None and barcode.startswith("869") and len(barcode) == 13
