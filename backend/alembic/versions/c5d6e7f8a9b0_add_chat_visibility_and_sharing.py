"""add_chat_visibility_and_sharing

Revision ID: c5d6e7f8a9b0
Revises: b2c3d4e5f6a7
Create Date: 2026-04-20 12:20:00.000000

AI 분리 구조 (docs/ai-separation.md step 1):
- user_id: 메시지 소유자. private=개인, NULL=레거시/시스템 공용
- visibility: 'private' | 'shared' (server_default='shared')
- shared_from_id: 공유된 메시지가 어떤 원본에서 파생됐는지 (FK to self)
- shared_by_user_id: 공유 실행자 (FK to users)

단일 단계 마이그레이션 (PG11+ ADD COLUMN NOT NULL DEFAULT = O(1)).
기존 pane_type=agent 레코드는 server_default 덕에 visibility='shared'로 자동 설정됨.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("chat_messages"):
        return

    cols = [c["name"] for c in inspector.get_columns("chat_messages")]

    if "user_id" not in cols:
        with op.batch_alter_table("chat_messages") as batch_op:
            batch_op.add_column(
                sa.Column("user_id", sa.Integer(), nullable=True),
            )
            batch_op.create_index(
                "ix_chat_messages_user_id",
                ["user_id"],
                unique=False,
            )
            batch_op.create_foreign_key(
                "fk_chat_messages_user_id_users",
                "users",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if "visibility" not in cols:
        with op.batch_alter_table("chat_messages") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "visibility",
                    sa.String(length=16),
                    nullable=False,
                    server_default="shared",
                ),
            )
            batch_op.create_index(
                "ix_chat_messages_visibility",
                ["visibility"],
                unique=False,
            )

    if "shared_from_id" not in cols:
        with op.batch_alter_table("chat_messages") as batch_op:
            batch_op.add_column(
                sa.Column("shared_from_id", sa.Integer(), nullable=True),
            )
            batch_op.create_index(
                "ix_chat_messages_shared_from_id",
                ["shared_from_id"],
                unique=False,
            )
            batch_op.create_foreign_key(
                "fk_chat_messages_shared_from_id_chat_messages",
                "chat_messages",
                ["shared_from_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if "shared_by_user_id" not in cols:
        with op.batch_alter_table("chat_messages") as batch_op:
            batch_op.add_column(
                sa.Column("shared_by_user_id", sa.Integer(), nullable=True),
            )
            batch_op.create_index(
                "ix_chat_messages_shared_by_user_id",
                ["shared_by_user_id"],
                unique=False,
            )
            batch_op.create_foreign_key(
                "fk_chat_messages_shared_by_user_id_users",
                "users",
                ["shared_by_user_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("chat_messages"):
        return

    cols = [c["name"] for c in inspector.get_columns("chat_messages")]
    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("chat_messages")}
    idx_names = {ix["name"] for ix in inspector.get_indexes("chat_messages")}

    if "shared_by_user_id" in cols:
        with op.batch_alter_table("chat_messages") as batch_op:
            if "fk_chat_messages_shared_by_user_id_users" in fk_names:
                batch_op.drop_constraint(
                    "fk_chat_messages_shared_by_user_id_users",
                    type_="foreignkey",
                )
            if "ix_chat_messages_shared_by_user_id" in idx_names:
                batch_op.drop_index("ix_chat_messages_shared_by_user_id")
            batch_op.drop_column("shared_by_user_id")

    if "shared_from_id" in cols:
        with op.batch_alter_table("chat_messages") as batch_op:
            if "fk_chat_messages_shared_from_id_chat_messages" in fk_names:
                batch_op.drop_constraint(
                    "fk_chat_messages_shared_from_id_chat_messages",
                    type_="foreignkey",
                )
            if "ix_chat_messages_shared_from_id" in idx_names:
                batch_op.drop_index("ix_chat_messages_shared_from_id")
            batch_op.drop_column("shared_from_id")

    if "visibility" in cols:
        with op.batch_alter_table("chat_messages") as batch_op:
            if "ix_chat_messages_visibility" in idx_names:
                batch_op.drop_index("ix_chat_messages_visibility")
            batch_op.drop_column("visibility")

    if "user_id" in cols:
        with op.batch_alter_table("chat_messages") as batch_op:
            if "fk_chat_messages_user_id_users" in fk_names:
                batch_op.drop_constraint(
                    "fk_chat_messages_user_id_users",
                    type_="foreignkey",
                )
            if "ix_chat_messages_user_id" in idx_names:
                batch_op.drop_index("ix_chat_messages_user_id")
            batch_op.drop_column("user_id")
