"""product_drafts kategori kolonu (KVN-11)

Taslağın komisyon tahmini kategori tarifesinden çözülüyor; kategori olmadan oran
bulunamıyordu. `promote` sırasında ürüne de taşınır.

Revision ID: 21876d415bc0
Revises: 5bbc0933e0a3
Create Date: 2026-08-19 03:41:32.508524+03:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "21876d415bc0"
down_revision: str | None = "5bbc0933e0a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("product_drafts", sa.Column("kategori", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("product_drafts", "kategori")
