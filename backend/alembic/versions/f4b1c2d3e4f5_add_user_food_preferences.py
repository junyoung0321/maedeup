"""add_user_food_preferences

Revision ID: f4b1c2d3e4f5
Revises: e7f8a9b0c1d2
Create Date: 2026-04-13 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4b1c2d3e4f5"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("users")]
    if "food_preferences" not in cols:
        op.add_column("users", sa.Column("food_preferences", sa.JSON(), nullable=True))
    if "food_preference_note" not in cols:
        op.add_column("users", sa.Column("food_preference_note", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "food_preference_note")
    op.drop_column("users", "food_preferences")
