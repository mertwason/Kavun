"""Hakediş mutabakatı şemaları (spec §7)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DiffStatus


class RunOut(BaseModel):
    """Mutabakat turunun özeti."""

    period: str
    records: int
    matched: int
    unmatched: int
    within_tolerance: int
    diffs: int
    skipped: int
    total_diff: Decimal
    match_rate_pct: Decimal
    unmatched_refs: list[str]
    dry_run: bool


class DiffOut(BaseModel):
    """Tek bir hakediş farkı."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period: str
    settlement_record_id: uuid.UUID | None
    expected: Decimal
    actual: Decimal
    diff: Decimal
    status: DiffStatus
    note: str | None
    created_at: datetime


class PeriodSummaryOut(BaseModel):
    """Dönem özeti — ekranın üst şeridi."""

    model_config = ConfigDict(from_attributes=True)

    period: str
    diff_count: int
    open_count: int
    explained_count: int
    resolved_count: int
    total_diff: Decimal


class ExplainIn(BaseModel):
    """Farkı açıklama/çözme girdisi. Not zorunludur (spec §7.4)."""

    status: DiffStatus
    note: str = Field(min_length=3, max_length=1000)
