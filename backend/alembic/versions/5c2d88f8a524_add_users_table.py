"""add_users_table

Revision ID: 5c2d88f8a524
Revises: 04a69892075f
Create Date: 2026-03-11 07:47:03.490881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c2d88f8a524'
down_revision: Union[str, None] = '04a69892075f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("picture", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )
        inspector = sa.inspect(bind)
    user_indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_email" not in user_indexes:
        op.create_index("ix_users_email", "users", ["email"], unique=False)

    if not inspector.has_table("chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("pane_type", sa.String(length=32), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("sender", sa.String(length=64), nullable=True),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)
    chat_indexes = {index["name"] for index in inspector.get_indexes("chat_messages")}
    if "ix_chat_messages_pane_type" not in chat_indexes:
        op.create_index("ix_chat_messages_pane_type", "chat_messages", ["pane_type"])
    if "ix_chat_messages_session_id" not in chat_indexes:
        op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    if not inspector.has_table("events"):
        op.create_table(
            "events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("location_name", sa.String(length=255), nullable=True),
            sa.Column("latitude", sa.Float(), nullable=True),
            sa.Column("longitude", sa.Float(), nullable=True),
            sa.Column("starts_at", sa.DateTime(), nullable=False),
            sa.Column("ends_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)
    event_indexes = {index["name"] for index in inspector.get_indexes("events")}
    if "ix_events_starts_at" not in event_indexes:
        op.create_index("ix_events_starts_at", "events", ["starts_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("events"):
        event_indexes = {index["name"] for index in inspector.get_indexes("events")}
        if "ix_events_starts_at" in event_indexes:
            op.drop_index("ix_events_starts_at", table_name="events")
        op.drop_table("events")

    if inspector.has_table("chat_messages"):
        chat_indexes = {index["name"] for index in inspector.get_indexes("chat_messages")}
        if "ix_chat_messages_session_id" in chat_indexes:
            op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
        if "ix_chat_messages_pane_type" in chat_indexes:
            op.drop_index("ix_chat_messages_pane_type", table_name="chat_messages")
        op.drop_table("chat_messages")

    if inspector.has_table("users"):
        user_indexes = {index["name"] for index in inspector.get_indexes("users")}
        if "ix_users_email" in user_indexes:
            op.drop_index("ix_users_email", table_name="users")
        op.drop_table("users")
