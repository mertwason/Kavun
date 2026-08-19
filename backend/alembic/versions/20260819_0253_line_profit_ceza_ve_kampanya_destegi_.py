"""line_profit: ceza ve kampanya desteği kolonları (KVN-08)

Spec §5.4'teki `line_profit` listesine iki ek kolon. Gerekçe: §6.3.3 (kampanya satıcı
payı) ve §6.3.7 (ceza/tazmin) senaryolarının motor çıktısı bir yere yazılmalı, yoksa
hesaplanıp sessizce kayboluyor. Eklemeler additive ve geri alınabilir; mevcut satırlar
`0` ile dolar.

Revision ID: e6f148a229c0
Revises: 0325f904fbd8
Create Date: 2026-08-19 02:53:21.592216+03:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f148a229c0"
down_revision: str | None = "0325f904fbd8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "line_profit",
        sa.Column(
            "cost_penalty",
            sa.Numeric(precision=14, scale=4),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "line_profit",
        sa.Column(
            "revenue_campaign_support",
            sa.Numeric(precision=14, scale=4),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("line_profit", "revenue_campaign_support")
    op.drop_column("line_profit", "cost_penalty")
