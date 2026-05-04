"""add_meeting_google_event_ids

Revision ID: e1f2a3b4c5d6
Revises: d9e0f1a2b3c4
Create Date: 2026-05-04 22:00:00.000000

Adds `google_event_ids` JSON column to meeting_schedules.

Maps room member user_id (str) → Google Calendar event id (str) for events
created at confirm time. Used for idempotent re-runs and future updates
(e.g. propagating a place change to existing calendar events).

- Defaults to '{}' so re-confirming an already-confirmed meeting is a no-op
- nullable=False to avoid None checks throughout the codebase
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("meeting_schedules"):
        return

    cols = [c["name"] for c in inspector.get_columns("meeting_schedules")]
    if "google_event_ids" not in cols:
        op.add_column(
            "meeting_schedules",
            sa.Column(
                "google_event_ids",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("meeting_schedules"):
        return
    cols = [c["name"] for c in inspector.get_columns("meeting_schedules")]
    if "google_event_ids" in cols:
        op.drop_column("meeting_schedules", "google_event_ids")
