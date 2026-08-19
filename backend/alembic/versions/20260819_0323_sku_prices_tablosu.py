"""sku_prices tablosu — versiyonlu satış fiyatı (KVN-10)

Spec §12A.1 fiyat listesinin upsert anahtarı `(SKU, Kanal)`; yani satış fiyatı
ürün-kanal çiftinin özelliğidir. Maliyet gibi versiyonlanır — geçmiş kayıt
güncellenmez, yeni `effective_from` eklenir.

Revision ID: 5bbc0933e0a3
Revises: 7678779e38d0
Create Date: 2026-08-19 03:23:21.595310+03:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5bbc0933e0a3"
down_revision: str | None = "7678779e38d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sku_prices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("price", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_sku_prices_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name=op.f("fk_sku_prices_store_id_stores"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sku_prices")),
    )
    op.create_index(
        op.f("ix_sku_prices_effective_from"), "sku_prices", ["effective_from"], unique=False
    )
    op.create_index(op.f("ix_sku_prices_product_id"), "sku_prices", ["product_id"], unique=False)
    op.create_index(op.f("ix_sku_prices_store_id"), "sku_prices", ["store_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sku_prices_store_id"), table_name="sku_prices")
    op.drop_index(op.f("ix_sku_prices_product_id"), table_name="sku_prices")
    op.drop_index(op.f("ix_sku_prices_effective_from"), table_name="sku_prices")
    op.drop_table("sku_prices")
