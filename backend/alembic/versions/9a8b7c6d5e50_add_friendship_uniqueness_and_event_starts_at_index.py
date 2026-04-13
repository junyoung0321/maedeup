"""add_friendship_uniqueness_and_event_starts_at_index

Revision ID: 9a8b7c6d5e50
Revises: 9a8b7c6d5e4f
Create Date: 2026-04-14 00:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9a8b7c6d5e50"
down_revision: Union[str, None] = "9a8b7c6d5e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _unique_constraint_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    friendship_constraints = _unique_constraint_names("friendships")
    if "uq_friendships_requester_id_addressee_id" not in friendship_constraints:
        op.create_unique_constraint(
            "uq_friendships_requester_id_addressee_id",
            "friendships",
            ["requester_id", "addressee_id"],
        )

    event_indexes = _index_names("events")
    if "ix_events_starts_at" not in event_indexes:
        op.create_index("ix_events_starts_at", "events", ["starts_at"])


def downgrade() -> None:
    event_indexes = _index_names("events")
    if "ix_events_starts_at" in event_indexes:
        op.drop_index("ix_events_starts_at", table_name="events")

    friendship_constraints = _unique_constraint_names("friendships")
    if "uq_friendships_requester_id_addressee_id" in friendship_constraints:
        op.drop_constraint(
            "uq_friendships_requester_id_addressee_id",
            "friendships",
            type_="unique",
        )
