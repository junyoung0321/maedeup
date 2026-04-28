"""add_sender_to_chat_messages

Revision ID: 04a69892075f
Revises: 
Create Date: 2026-03-11 07:11:22.344219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '04a69892075f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("chat_messages"):
        return
    existing = [c["name"] for c in inspector.get_columns("chat_messages")]
    if "sender" not in existing:
        op.add_column('chat_messages', sa.Column('sender', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("chat_messages"):
        return
    existing = [c["name"] for c in inspector.get_columns("chat_messages")]
    if "sender" in existing:
        op.drop_column('chat_messages', 'sender')
