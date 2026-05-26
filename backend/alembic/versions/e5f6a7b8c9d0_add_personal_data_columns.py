"""add_personal_data_columns

Add 6 personal-data columns to users (food_restrictions, liked_areas,
disliked_areas, time_preference, transport_mode, is_ai_filled JSON).
Add source_message_id FK column to ai_memories with ondelete=SET NULL.

Idempotent — checks `inspector.has_column` before each add.

Revision ID: e5f6a7b8c9d0
Revises: d2e3f4a5b6c7
Create Date: 2026-04-27 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── users: 6 personal-data columns ──
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "food_restrictions" not in user_cols:
        op.add_column(
            "users",
            sa.Column("food_restrictions", sa.JSON(), nullable=True),
        )
    if "liked_areas" not in user_cols:
        op.add_column(
            "users",
            sa.Column("liked_areas", sa.JSON(), nullable=True),
        )
    if "disliked_areas" not in user_cols:
        op.add_column(
            "users",
            sa.Column("disliked_areas", sa.JSON(), nullable=True),
        )
    if "time_preference" not in user_cols:
        op.add_column(
            "users",
            sa.Column("time_preference", sa.String(length=255), nullable=True),
        )
    if "transport_mode" not in user_cols:
        op.add_column(
            "users",
            sa.Column("transport_mode", sa.String(length=32), nullable=True),
        )
    if "is_ai_filled" not in user_cols:
        # dialect-agnostic server_default: postgres·sqlite 양쪽에서 JSON 컬럼에 '{}' valid.
        # postgres `::json` cast는 불필요, sqlite는 토큰 인식 못함.
        op.add_column(
            "users",
            sa.Column(
                "is_ai_filled",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
        )

    # ── ai_memories: source_message_id with ondelete=SET NULL ──
    mem_cols = {c["name"] for c in inspector.get_columns("ai_memories")}
    if "source_message_id" not in mem_cols:
        with op.batch_alter_table("ai_memories") as batch_op:
            batch_op.add_column(
                sa.Column("source_message_id", sa.Integer(), nullable=True),
            )
            batch_op.create_foreign_key(
                "fk_ai_memories_source_message_id_chat_messages",
                "chat_messages",
                ["source_message_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_index(
                "ix_ai_memories_source_message_id",
                ["source_message_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    mem_cols = {c["name"] for c in inspector.get_columns("ai_memories")}
    if "source_message_id" in mem_cols:
        # 인덱스/FK가 실제로 존재할 때만 drop (idempotent)
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("ai_memories")}
        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("ai_memories")}
        with op.batch_alter_table("ai_memories") as batch_op:
            if "ix_ai_memories_source_message_id" in existing_indexes:
                batch_op.drop_index("ix_ai_memories_source_message_id")
            if "fk_ai_memories_source_message_id_chat_messages" in existing_fks:
                batch_op.drop_constraint(
                    "fk_ai_memories_source_message_id_chat_messages",
                    type_="foreignkey",
                )
            batch_op.drop_column("source_message_id")

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    for col in (
        "is_ai_filled",
        "transport_mode",
        "time_preference",
        "disliked_areas",
        "liked_areas",
        "food_restrictions",
    ):
        if col in user_cols:
            op.drop_column("users", col)
