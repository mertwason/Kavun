"""Uyarı şemaları (spec §10.6)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AlertSeverity


class AlertOut(BaseModel):
    """Tek uyarı."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    severity: AlertSeverity
    message: str
    entity_ref: str | None
    created_at: datetime
    acknowledged_at: datetime | None


class AlertCountsOut(BaseModel):
    """Uyarı özeti: seviye bazlı açık sayımlar + markada geçen türler."""

    open: int
    acknowledged: int
    critical_open: int
    warning_open: int
    info_open: int
    total: int
    types: list[str]
