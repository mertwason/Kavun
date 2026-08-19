"""SQLAlchemy modelleri (spec §5, §12A, §12B, §12C).

Alembic autogenerate ve `Base.metadata` bu modülden beslenir; yeni model dosyası
eklendiğinde buraya da import edilmelidir.
"""

from app.models.catalog import (
    CargoTariff,
    CommissionChange,
    CommissionRate,
    Customer,
    Product,
    ProductChannelMap,
    SkuCost,
    SkuLogistics,
    Supplier,
)
from app.models.identity import (
    AuditLog,
    Brand,
    BrandFeature,
    Channel,
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
from app.models.workspace import (
    ImportBatch,
    PricingScenario,
    ProductDraft,
)

__all__ = [
    "AdSpend",
    "Alert",
    "AuditLog",
    "Brand",
    "BrandFeature",
    "CargoInvoice",
    "CargoTariff",
    "Channel",
    "CommissionChange",
    "CommissionRate",
    "Customer",
    "ImportBatch",
    "ImportCostItem",
    "ImportFile",
    "InventoryLedger",
    "LineProfit",
    "Order",
    "OrderLine",
    "PricingScenario",
    "Product",
    "ProductChannelMap",
    "ProductDraft",
    "ProfitRevision",
    "Promotion",
    "PurchaseInvoice",
    "PurchaseInvoiceLine",
    "RawEvent",
    "ReconciliationDiff",
    "Return",
    "SettlementRecord",
    "Shipment",
    "SkuCost",
    "SkuCostState",
    "SkuLogistics",
    "Store",
    "StoreCredential",
    "Supplier",
    "SupplierPayment",
    "SupplierProductMap",
    "Tenant",
    "User",
    "UserBrandRole",
]
