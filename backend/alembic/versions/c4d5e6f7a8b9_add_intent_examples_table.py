"""add_intent_examples_table

Revision ID: c4d5e6f7a8b9
Revises: a2b3c4d5e6f7
Create Date: 2026-04-15 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("intent_examples"):
        return

    op.create_table(
        "intent_examples",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("intent", sa.String(), nullable=False, index=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_intent_examples_intent",
        "intent_examples",
        ["intent"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_intent_examples_intent", table_name="intent_examples")
    op.drop_table("intent_examples")
