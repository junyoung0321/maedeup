"""add_kakao_fields_to_events

Revision ID: c1d2e3f4a5b6
Revises: b3c4d5e6f7a8
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("events")]
    if "kakao_place_id" not in cols:
        op.add_column("events", sa.Column("kakao_place_id", sa.String(length=64), nullable=True))
    if "kakao_place_url" not in cols:
        op.add_column("events", sa.Column("kakao_place_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "kakao_place_url")
    op.drop_column("events", "kakao_place_id")
