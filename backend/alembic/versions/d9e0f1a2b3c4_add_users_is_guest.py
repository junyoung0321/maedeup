"""add_users_is_guest

Revision ID: d9e0f1a2b3c4
Revises: c5d6e7f8a9b0
Create Date: 2026-04-21 16:40:00.000000

Adds `is_guest` boolean column to users. Enables room-link-based guest
participation (카카오톡 링크 → 로그인 없이 방 참여).

- Defaults to FALSE so existing rows keep current semantics
- Indexed for quick filtering in guards (방 생성/친구 관련 차단)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    cols = [c["name"] for c in inspector.get_columns("users")]
    if "is_guest" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "is_guest",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.create_index(
            "ix_users_is_guest",
            "users",
            ["is_guest"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return
    indexes = [i["name"] for i in inspector.get_indexes("users")]
    if "ix_users_is_guest" in indexes:
        op.drop_index("ix_users_is_guest", table_name="users")
    cols = [c["name"] for c in inspector.get_columns("users")]
    if "is_guest" in cols:
        op.drop_column("users", "is_guest")
