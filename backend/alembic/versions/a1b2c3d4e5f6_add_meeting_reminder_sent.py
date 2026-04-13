"""add_meeting_reminder_sent

Revision ID: a1b2c3d4e5f6
Revises: f4b1c2d3e4f5
Create Date: 2026-04-13 20:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f4b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("meeting_schedules")]
    if "reminder_sent" not in cols:
        op.add_column(
            "meeting_schedules",
            sa.Column("reminder_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    op.drop_column("meeting_schedules", "reminder_sent")
