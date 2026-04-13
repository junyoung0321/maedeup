"""add_home_base_and_meeting_end_at

Revision ID: e7f8a9b0c1d2
Revises: d1e2f3a4b5c6
Create Date: 2026-04-13 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = [c["name"] for c in inspector.get_columns("users")]
    ms_cols = [c["name"] for c in inspector.get_columns("meeting_schedules")]
    if "home_base" not in user_cols:
        op.add_column("users", sa.Column("home_base", sa.String(length=128), nullable=True))
    if "end_at" not in ms_cols:
        op.add_column("meeting_schedules", sa.Column("end_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("meeting_schedules", "end_at")
    op.drop_column("users", "home_base")
