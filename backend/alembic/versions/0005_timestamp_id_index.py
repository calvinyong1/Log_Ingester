"""index log_events on (timestamp, id) for keyset paging

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-23

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # GET /logs pages with (timestamp, id) < cursor ORDER BY timestamp DESC, id DESC.
    # timestamp leads the new index, so it also serves the old single-column lookups
    # (range filters, the retention prune) and ix_log_events_timestamp is redundant.
    op.create_index("ix_log_events_timestamp_id", "log_events", ["timestamp", "id"])
    op.drop_index("ix_log_events_timestamp", table_name="log_events")


def downgrade() -> None:
    op.create_index("ix_log_events_timestamp", "log_events", ["timestamp"])
    op.drop_index("ix_log_events_timestamp_id", table_name="log_events")
