"""Domain enum'ları. Spec'teki ENUM tanımlarının birebir karşılığı."""

from __future__ import annotations

from enum import StrEnum


class ChannelCode(StrEnum):
    """Satış kanalları (spec §5.1, §12C.9)."""

    TRENDYOL = "trendyol"
    HEPSIBURADA = "hepsiburada"
    N11 = "n11"
    SHOPIFY = "shopify"
    MANUAL = "manual"  # Alessi D2B / kurumsal satış


class UserRole(StrEnum):
    """Marka bazlı yetki (spec §3A.3)."""

    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class CostSource(StrEnum):
    """`sku_costs.source` (spec §5.2, §12C.2)."""

    MANUAL = "manual"
    INVOICE = "invoice"
    ERP = "erp"
    INVOICE_WAC = "invoice_wac"


class CommissionScope(StrEnum):
    """`commission_rates.scope` (spec §5.2)."""

    PRODUCT = "product"
    CATEGORY = "category"


class CommissionSource(StrEnum):
    """Komisyon çözümleme hiyerarşisi (spec §12B.1) — sıra önem taşır."""

    SETTLEMENT_ACTUAL = "settlement_actual"
    API_PRODUCT = "api_product"
    API_CATEGORY = "api_category"
    MANUAL_TARIFF_UPLOAD = "manual_tariff_upload"
    MANUAL = "manual"


class OrderStatus(StrEnum):
    """Normalize sipariş statüsü (spec §4)."""

    CREATED = "created"
    PICKING = "picking"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class CostState(StrEnum):
    """Maliyet kalemi state machine (spec §3.4)."""

    ESTIMATED = "estimated"
    ACTUAL = "actual"


class SettlementRecordType(StrEnum):
    """`settlement_records.record_type` (spec §5.3)."""

    SALE = "sale"
    COMMISSION = "commission"
    CARGO = "cargo"
    SERVICE_FEE = "service_fee"
    PENALTY = "penalty"
    AD_SPEND = "ad_spend"
    REFUND = "refund"
    OTHER = "other"


class DiffStatus(StrEnum):
    """`reconciliation_diffs.status` (spec §5.4)."""

    OPEN = "open"
    EXPLAINED = "explained"
    RESOLVED = "resolved"


class AlertSeverity(StrEnum):
    """Uyarı seviyesi — tasarım brief'i: bilgi / dikkat / kritik."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class InvoiceStatus(StrEnum):
    """`purchase_invoices.status` (spec §12C.2)."""

    PARSED = "parsed"
    REVIEW = "review"
    CONFIRMED = "confirmed"


class MatchStatus(StrEnum):
    """`purchase_invoice_lines.match_status` (spec §12C.2)."""

    AUTO = "auto"
    MANUAL = "manual"
    UNMATCHED = "unmatched"


class InventoryMovement(StrEnum):
    """`inventory_ledger.movement` (spec §12C.2, §12C.10)."""

    OPENING = "opening"
    PURCHASE_IN = "purchase_in"
    SALE_OUT = "sale_out"
    RETURN_IN = "return_in"
    RETURN_OUT = "return_out"
    ADJUSTMENT = "adjustment"
    DAMAGE = "damage"


class ImportFileStatus(StrEnum):
    """`import_files.status` (spec §12C.7)."""

    OPEN = "open"
    CONFIRMED = "confirmed"


class ImportCostItemType(StrEnum):
    """`import_cost_items.item_type` (spec §12C.7).

    İthalat KDV'si burada YOKTUR — indirilecek KDV'dir, landed cost'a girmez.
    """

    MAL_BEDELI = "mal_bedeli"
    NAVLUN = "navlun"
    SIGORTA = "sigorta"
    GUMRUK_VERGISI = "gumruk_vergisi"
    GUMRUK_MUSAVIRLIGI = "gumruk_musavirligi"
    ARDIYE_LIMAN = "ardiye_liman"
    DIGER = "diger"


class DraftStatus(StrEnum):
    """`product_drafts.status` (spec §12A.3)."""

    DRAFT = "draft"
    PROMOTED = "promoted"
    DISCARDED = "discarded"


class ShippingPayer(StrEnum):
    """`pricing_scenarios.kargo_kim_oder` (spec §12A.4)."""

    SATICI = "satici"
    ALICI = "alici"
    PLATFORM = "platform"


class CommissionMode(StrEnum):
    """`pricing_scenarios.commission_mode` (spec §12B.4)."""

    CURRENT = "current"
    PINNED = "pinned"
    FUTURE_TARIFF = "future_tariff"
