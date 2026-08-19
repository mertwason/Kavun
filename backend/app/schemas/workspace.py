"""Workspace ve kimlik şemaları (spec §3A, §8)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlertSeverity, UserRole


class TokenResponse(BaseModel):
    """Giriş yanıtı."""

    access_token: str
    token_type: str = "bearer"
    active_brand: str | None = None


class SsoExchangeRequest(BaseModel):
    """ops.mokka SSO token'ı ile Kavun token'ı değişimi."""

    sso_token: str
    brand: str | None = Field(default=None, description="Açılışta seçilecek workspace")


class DevLoginRequest(BaseModel):
    """Yalnızca local/ci ortamında geçerli geliştirme girişi."""

    email: str
    brand: str | None = None


class SwitchBrandRequest(BaseModel):
    """Workspace değiştirme."""

    brand: str


class BrandAccess(BaseModel):
    """Kullanıcının bir markadaki erişimi."""

    slug: str
    name: str
    role: UserRole


class MeResponse(BaseModel):
    """Oturum bilgisi — frontend workspace switcher'ı bunu kullanır."""

    user_id: uuid.UUID
    email: str
    full_name: str
    tenant: str
    active_brand: str | None
    brands: list[BrandAccess]
    is_holding_viewer: bool
    features: dict[str, bool]


class ProductSummary(BaseModel):
    """Marka kapsamlı ürün özeti."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    category: str | None
    vat_rate: Decimal
    msrp: Decimal | None


class AlertSummary(BaseModel):
    """Marka kapsamlı uyarı."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    severity: AlertSeverity
    message: str
    created_at: datetime
    acknowledged_at: datetime | None


class ImportFileSummary(BaseModel):
    """İthalat dosyası — yalnızca `import_files` bayrağı açık markalarda görünür."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_no: str
    beyanname_no: str | None
    currency: str
    import_vat_paid: Decimal | None


class BrandTotals(BaseModel):
    """Holding görünümü satırı — marka bazlı konsolide sayımlar."""

    brand: str
    name: str
    product_count: int
    order_count: int
    open_alert_count: int


class HoldingSummary(BaseModel):
    """Markalar arası özet (salt okunur, spec §3A.3)."""

    tenant: str
    brands: list[BrandTotals]


class ConsolidatedBrandOut(BaseModel):
    """Holding konsolide satırı — marka bazlı P&L, stok, fire ve kur (spec §3A.3)."""

    model_config = ConfigDict(from_attributes=True)

    brand: str
    name: str
    product_count: int
    order_count: int
    open_alert_count: int
    revenue: Decimal
    profit: Decimal
    margin_pct: Decimal
    stock_value: Decimal
    damage_cost: Decimal
    fx_diff: Decimal
    open_fx_amount: Decimal


class ConsolidatedOut(BaseModel):
    """Holding özeti: markalar + toplamlar. Salt okunur."""

    tenant: str
    since: date
    until: date
    brands: list[ConsolidatedBrandOut]
    total_revenue: Decimal
    total_profit: Decimal
    total_stock_value: Decimal
    total_damage_cost: Decimal
    total_fx_diff: Decimal
