"""cargo_tariffs — desi bandı bazlı kargo tarifesi (KVN-EK-04)

Revision ID: b7c21ad4e910
Revises: d1444dcdfe5c
Create Date: 2026-08-19 09:00:00.000000+03:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "b7c21ad4e910"
down_revision: str | None = "d1444dcdfe5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tarife tablosu. Kayıt yoksa motor varsayılan formüle düşer — davranış değişmez."""
    op.create_table(
        "cargo_tariffs",
        sa.Column("id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("carrier", sa.String(length=100), nullable=True),
        sa.Column("desi_min", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("desi_max", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("price", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cargo_tariffs_brand_id"), "cargo_tariffs", ["brand_id"], unique=False)
    op.create_index(
        op.f("ix_cargo_tariffs_tenant_id"), "cargo_tariffs", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_cargo_tariffs_valid_from"), "cargo_tariffs", ["valid_from"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cargo_tariffs_valid_from"), table_name="cargo_tariffs")
    op.drop_index(op.f("ix_cargo_tariffs_tenant_id"), table_name="cargo_tariffs")
    op.drop_index(op.f("ix_cargo_tariffs_brand_id"), table_name="cargo_tariffs")
    op.drop_table("cargo_tariffs")
