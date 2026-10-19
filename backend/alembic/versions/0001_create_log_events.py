"""create log_events table

Revision ID: 0001
Revises:
Create Date: 2026-04-25

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "log_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service", sa.String(length=128), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_log_events_service", "log_events", ["service"])
    op.create_index("ix_log_events_level", "log_events", ["level"])
    op.create_index("ix_log_events_timestamp", "log_events", ["timestamp"])
    op.create_index(
        "ix_log_events_service_level_ts",
        "log_events",
        ["service", "level", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_log_events_service_level_ts", table_name="log_events")
    op.drop_index("ix_log_events_timestamp", table_name="log_events")
    op.drop_index("ix_log_events_level", table_name="log_events")
    op.drop_index("ix_log_events_service", table_name="log_events")
    op.drop_table("log_events")
