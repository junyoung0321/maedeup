"""add_intent_examples

Revision ID: e3f2a1b0c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-04-21 17:40:00.000000

RAG 기반 의도 분류에 쓰는 intent_examples 테이블을 생성.
원래 main-stack DB에는 create_all 시점에 만들어졌지만 마이그레이션 파일이
빠져 있어 fresh DB(cr-stack 등)에서는 없음 → 파이프라인이 intent_detection_error로 실패.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f2a1b0c4d5"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("intent_examples"):
        return
    op.create_table(
        "intent_examples",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("text", sa.String(length=1024), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_intent_examples_intent",
        "intent_examples",
        ["intent"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("intent_examples"):
        return
    indexes = [i["name"] for i in inspector.get_indexes("intent_examples")]
    if "ix_intent_examples_intent" in indexes:
        op.drop_index("ix_intent_examples_intent", table_name="intent_examples")
    op.drop_table("intent_examples")
