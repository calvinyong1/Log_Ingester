"""add log_events.event_id for idempotent job retries

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-16

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: existing rows have no id, and NULLs don't collide in a unique index.
    op.add_column("log_events", sa.Column("event_id", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_log_events_event_id", "log_events", ["event_id"])


def downgrade() -> None:
    op.drop_constraint("uq_log_events_event_id", "log_events", type_="unique")
    op.drop_column("log_events", "event_id")
