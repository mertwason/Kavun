"""shipments kargo takip no

Revision ID: d1444dcdfe5c
Revises: a4fe24269be3
Create Date: 2026-08-19 07:35:56.186338+03:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1444dcdfe5c"
down_revision: str | None = "a4fe24269be3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("shipments", sa.Column("tracking_no", sa.String(length=120), nullable=True))
    op.create_index(op.f("ix_shipments_tracking_no"), "shipments", ["tracking_no"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_shipments_tracking_no"), table_name="shipments")
    op.drop_column("shipments", "tracking_no")
