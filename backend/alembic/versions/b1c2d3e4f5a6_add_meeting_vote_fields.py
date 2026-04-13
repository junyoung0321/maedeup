"""add_meeting_vote_fields

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-04-13 20:45:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meeting_schedules",
        sa.Column("vote_options", sa.JSON(), nullable=True),
    )
    op.add_column(
        "meeting_schedules",
        sa.Column("votes", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("meeting_schedules", "votes")
    op.drop_column("meeting_schedules", "vote_options")
