"""add_google_tokens_and_consent

Revision ID: b3c4d5e6f7a8
Revises: 5c2d88f8a524
Create Date: 2026-03-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "5c2d88f8a524"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return
    cols = [c["name"] for c in inspector.get_columns("users")]
    if "google_access_token" not in cols:
        op.add_column("users", sa.Column("google_access_token", sa.Text(), nullable=True))
    if "google_refresh_token" not in cols:
        op.add_column("users", sa.Column("google_refresh_token", sa.Text(), nullable=True))
    if "calendar_consent" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "calendar_consent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return
    cols = [c["name"] for c in inspector.get_columns("users")]
    if "calendar_consent" in cols:
        op.drop_column("users", "calendar_consent")
    if "google_refresh_token" in cols:
        op.drop_column("users", "google_refresh_token")
    if "google_access_token" in cols:
        op.drop_column("users", "google_access_token")
