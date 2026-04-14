"""add_vote_reminder_sent

Revision ID: a2b3c4d5e6f7
Revises: 9a8b7c6d5e51
Create Date: 2026-04-14 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "9a8b7c6d5e51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("meeting_schedules"):
        return
    cols = [c["name"] for c in inspector.get_columns("meeting_schedules")]
    if "vote_reminder_sent" not in cols:
        op.add_column(
            "meeting_schedules",
            sa.Column("vote_reminder_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("meeting_schedules"):
        return
    cols = [c["name"] for c in inspector.get_columns("meeting_schedules")]
    if "vote_reminder_sent" in cols:
        op.drop_column("meeting_schedules", "vote_reminder_sent")
