"""Mağaza ve credential şemaları (spec §5.1, §8).

Credential içeriği hiçbir yanıt şemasında yer almaz: yalnızca "var mı, ne zaman
güncellendi" bilgisi döner (CLAUDE.md §2).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ChannelCode

# Kanal başına zorunlu credential alanları (spec §4 — Trendyol Basic Auth + SellerID).
REQUIRED_CREDENTIAL_FIELDS: dict[ChannelCode, tuple[str, ...]] = {
    ChannelCode.TRENDYOL: ("api_key", "api_secret", "seller_id"),
    ChannelCode.HEPSIBURADA: ("username", "password", "merchant_id"),
    ChannelCode.N11: ("app_key", "app_secret"),
    ChannelCode.SHOPIFY: ("shop_domain", "access_token"),
    ChannelCode.MANUAL: (),
}


class StoreCreate(BaseModel):
    """Yeni mağaza."""

    channel: ChannelCode
    name: str = Field(min_length=1, max_length=200)
    external_seller_id: str | None = Field(default=None, max_length=100)
    service_fee_per_order: Decimal | None = None


class StoreUpdate(BaseModel):
    """Mağaza güncelleme — yalnızca gönderilen alanlar değişir."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    external_seller_id: str | None = Field(default=None, max_length=100)
    service_fee_per_order: Decimal | None = None
    is_active: bool | None = None


class CredentialStatus(BaseModel):
    """Credential durumu — içerik ASLA dönmez."""

    configured: bool
    created_at: datetime | None = None
    rotated_at: datetime | None = None


class StoreSummary(BaseModel):
    """Mağaza listesi satırı (spec §8: `GET /stores` + sync durumu)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    channel: ChannelCode
    external_seller_id: str | None
    is_active: bool
    service_fee_per_order: Decimal | None
    last_synced_at: datetime | None
    credentials: CredentialStatus


class SyncStatus(BaseModel):
    """Senkron tetikleme yanıtı (spec §8)."""

    store_id: uuid.UUID
    task_id: str
    queued: bool


class CredentialWrite(BaseModel):
    """Credential kaydı. Alanlar kanala göre doğrulanır; içerik şifreli saklanır."""

    values: dict[str, str] = Field(
        description="Kanala özgü alanlar (ör. Trendyol: api_key, api_secret, seller_id)"
    )

    @field_validator("values")
    @classmethod
    def _reject_empty_values(cls, values: dict[str, str]) -> dict[str, str]:
        """Boş değer kabul edilmez — yarım credential sessizce kaydedilmesin."""
        blank = sorted(key for key, value in values.items() if not str(value).strip())
        if blank:
            raise ValueError(f"Boş bırakılamaz: {', '.join(blank)}")
        return values

    def __repr__(self) -> str:
        """Credential değerleri repr'e sızmaz."""
        return f"<CredentialWrite fields={sorted(self.values)}>"

    __str__ = __repr__
