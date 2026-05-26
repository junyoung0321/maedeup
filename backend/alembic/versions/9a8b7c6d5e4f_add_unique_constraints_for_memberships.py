"""add_room_member_uniqueness_and_calendar_consent_index

Revision ID: 9a8b7c6d5e4f
Revises: f4b1c2d3e4f5
Create Date: 2026-04-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9a8b7c6d5e4f"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _unique_constraint_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("room_members"):
        return
    room_member_constraints = _unique_constraint_names("room_members")
    if "uq_room_members_room_id_user_id" not in room_member_constraints:
        with op.batch_alter_table("room_members") as batch_op:
            batch_op.create_unique_constraint(
                "uq_room_members_room_id_user_id",
                ["room_id", "user_id"],
            )
    if inspector.has_table("users"):
        user_indexes = _index_names("users")
        if "ix_users_calendar_consent" not in user_indexes:
            op.create_index("ix_users_calendar_consent", "users", ["calendar_consent"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("users"):
        user_indexes = _index_names("users")
        if "ix_users_calendar_consent" in user_indexes:
            op.drop_index("ix_users_calendar_consent", table_name="users")

    if inspector.has_table("room_members"):
        room_member_constraints = _unique_constraint_names("room_members")
        if "uq_room_members_room_id_user_id" in room_member_constraints:
            with op.batch_alter_table("room_members") as batch_op:
                batch_op.drop_constraint(
                    "uq_room_members_room_id_user_id",
                    type_="unique",
                )
