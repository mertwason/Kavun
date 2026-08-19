"""purchase_invoices ithalat dosyası bağı

Revision ID: a8595701d7b5
Revises: f1820e99ff0d
Create Date: 2026-08-19 05:38:29.029272+03:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8595701d7b5"
down_revision: str | None = "f1820e99ff0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("purchase_invoices", sa.Column("import_file_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_purchase_invoices_import_file_id"),
        "purchase_invoices",
        ["import_file_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_purchase_invoices_import_file_id_import_files"),
        "purchase_invoices",
        "import_files",
        ["import_file_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_purchase_invoices_import_file_id_import_files"),
        "purchase_invoices",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_purchase_invoices_import_file_id"), table_name="purchase_invoices")
    op.drop_column("purchase_invoices", "import_file_id")
