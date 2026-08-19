"""line_profit: brüt ciro kolonu (KVN-09)

Dashboard'daki "ciro" müşterinin ödediği KDV dahil tutardır; motor bunu zaten
hesaplıyordu ama yazmıyorduk, dolayısıyla SQL'de yeniden türetmek gerekiyordu —
aynı sayının iki yerde hesaplanması mutabakatı bozar. Mevcut satırlar `0` ile dolar;
`python -m app.cli recompute` bir turda gerçek değerleri yazar.

Revision ID: 7678779e38d0
Revises: e6f148a229c0
Create Date: 2026-08-19 03:05:02.377330+03:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7678779e38d0"
down_revision: str | None = "e6f148a229c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "line_profit",
        sa.Column(
            "revenue_gross",
            sa.Numeric(precision=14, scale=4),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("line_profit", "revenue_gross")
