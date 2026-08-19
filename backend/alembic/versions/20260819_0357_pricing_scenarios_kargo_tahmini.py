"""pricing_scenarios kargo tahmini (KVN-12)

Kargo varsayımı saklanmazsa kayıtlı senaryo, kaydedildiği andakinden farklı bir kâr
gösterir. Desi bazlı tarife KVN-14"te gelecek; o zamana kadar kullanıcının verdiği
tahmin senaryonun parçasıdır.

Revision ID: f1820e99ff0d
Revises: 21876d415bc0
Create Date: 2026-08-19 03:57:58.987653+03:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1820e99ff0d"
down_revision: str | None = "21876d415bc0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pricing_scenarios",
        sa.Column("kargo_tahmini", sa.Numeric(precision=14, scale=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pricing_scenarios", "kargo_tahmini")
