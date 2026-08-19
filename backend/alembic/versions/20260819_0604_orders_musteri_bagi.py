"""orders musteri bagi

Revision ID: a4fe24269be3
Revises: a8595701d7b5
Create Date: 2026-08-19 06:04:59.628644+03:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4fe24269be3"
down_revision: str | None = "a8595701d7b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("customer_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_orders_customer_id"), "orders", ["customer_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_orders_customer_id_customers"),
        "orders",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_orders_customer_id_customers"), "orders", type_="foreignkey")
    op.drop_index(op.f("ix_orders_customer_id"), table_name="orders")
    op.drop_column("orders", "customer_id")
