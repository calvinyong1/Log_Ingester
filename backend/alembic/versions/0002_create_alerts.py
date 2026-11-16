"""create alerts table

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service", sa.String(length=128), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("error_rate", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
    )
    op.create_index("ix_alerts_fired_at", "alerts", ["fired_at"])
    op.create_index("ix_alerts_service_fired_at", "alerts", ["service", "fired_at"])


def downgrade() -> None:
    op.drop_index("ix_alerts_service_fired_at", table_name="alerts")
    op.drop_index("ix_alerts_fired_at", table_name="alerts")
    op.drop_table("alerts")
