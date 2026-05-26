"""add_meeting_participant_uniqueness_and_schedule_index

Revision ID: 9a8b7c6d5e51
Revises: 9a8b7c6d5e50
Create Date: 2026-04-14 00:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9a8b7c6d5e51"
down_revision: Union[str, None] = "9a8b7c6d5e50"
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
    if not inspector.has_table("meeting_participants"):
        return
    meeting_participant_constraints = _unique_constraint_names("meeting_participants")
    if "uq_meeting_participants_meeting_id_user_id" not in meeting_participant_constraints:
        with op.batch_alter_table("meeting_participants") as batch_op:
            batch_op.create_unique_constraint(
                "uq_meeting_participants_meeting_id_user_id",
                ["meeting_id", "user_id"],
            )

    if inspector.has_table("meeting_schedules"):
        meeting_indexes = _index_names("meeting_schedules")
        if "ix_meeting_schedules_scheduled_at" not in meeting_indexes:
            op.create_index("ix_meeting_schedules_scheduled_at", "meeting_schedules", ["scheduled_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("meeting_schedules"):
        meeting_indexes = _index_names("meeting_schedules")
        if "ix_meeting_schedules_scheduled_at" in meeting_indexes:
            op.drop_index("ix_meeting_schedules_scheduled_at", table_name="meeting_schedules")

    if inspector.has_table("meeting_participants"):
        meeting_participant_constraints = _unique_constraint_names("meeting_participants")
        if "uq_meeting_participants_meeting_id_user_id" in meeting_participant_constraints:
            with op.batch_alter_table("meeting_participants") as batch_op:
                batch_op.drop_constraint(
                    "uq_meeting_participants_meeting_id_user_id",
                    type_="unique",
                )
