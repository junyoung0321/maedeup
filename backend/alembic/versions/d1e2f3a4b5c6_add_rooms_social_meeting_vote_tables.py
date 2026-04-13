"""add_rooms_social_meeting_vote_tables

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-03-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ rooms
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rooms_id", "rooms", ["id"])

    # --------------------------------------------------------------- room_members
    op.create_table(
        "room_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_room_members_room_id", "room_members", ["room_id"])
    op.create_index("ix_room_members_user_id", "room_members", ["user_id"])

    # --------------------------------------------------------------- friendships
    op.create_table(
        "friendships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("addressee_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["addressee_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_friendships_requester_id", "friendships", ["requester_id"])
    op.create_index("ix_friendships_addressee_id", "friendships", ["addressee_id"])

    # --------------------------------------------------------- meeting_schedules
    op.create_table(
        "meeting_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("location_name", sa.String(length=255), nullable=True),
        sa.Column("location_address", sa.String(length=512), nullable=True),
        sa.Column("kakao_place_id", sa.String(length=64), nullable=True),
        sa.Column("kakao_place_url", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meeting_schedules_room_id", "meeting_schedules", ["room_id"])

    # ------------------------------------------------------- meeting_participants
    op.create_table(
        "meeting_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="invited"),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["meeting_id"], ["meeting_schedules.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meeting_participants_meeting_id", "meeting_participants", ["meeting_id"])
    op.create_index("ix_meeting_participants_user_id", "meeting_participants", ["user_id"])

    # ------------------------------------------------------------------ votes
    op.create_table(
        "votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("vote_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_votes_room_id", "votes", ["room_id"])

    # --------------------------------------------------------------- vote_options
    op.create_table(
        "vote_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vote_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.String(length=512), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["vote_id"], ["votes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vote_options_vote_id", "vote_options", ["vote_id"])

    # ------------------------------------------------------------- vote_responses
    op.create_table(
        "vote_responses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vote_id", sa.Integer(), nullable=False),
        sa.Column("option_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["vote_id"], ["votes.id"]),
        sa.ForeignKeyConstraint(["option_id"], ["vote_options.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vote_responses_vote_id", "vote_responses", ["vote_id"])
    op.create_index("ix_vote_responses_user_id", "vote_responses", ["user_id"])

    # --------------------------------------------------------------- ai_memories
    op.create_table(
        "ai_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("memory_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_room_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_room_id"], ["rooms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_memories_user_id", "ai_memories", ["user_id"])

    # -------------------------------- alter existing: chat_messages, events
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cm_cols = [c["name"] for c in inspector.get_columns("chat_messages")]
    if "room_id" not in cm_cols:
        op.add_column("chat_messages", sa.Column("room_id", sa.Integer(), nullable=True))
    cm_indexes = [i["name"] for i in inspector.get_indexes("chat_messages")]
    if "ix_chat_messages_room_id" not in cm_indexes:
        op.create_index("ix_chat_messages_room_id", "chat_messages", ["room_id"])
    cm_fks = [f["name"] for f in inspector.get_foreign_keys("chat_messages")]
    if "fk_chat_messages_room_id" not in cm_fks:
        op.create_foreign_key(
            "fk_chat_messages_room_id", "chat_messages", "rooms", ["room_id"], ["id"]
        )

    ev_cols = [c["name"] for c in inspector.get_columns("events")]
    if "room_id" not in ev_cols:
        op.add_column("events", sa.Column("room_id", sa.Integer(), nullable=True))
    ev_indexes = [i["name"] for i in inspector.get_indexes("events")]
    if "ix_events_room_id" not in ev_indexes:
        op.create_index("ix_events_room_id", "events", ["room_id"])
    ev_fks = [f["name"] for f in inspector.get_foreign_keys("events")]
    if "fk_events_room_id" not in ev_fks:
        op.create_foreign_key("fk_events_room_id", "events", "rooms", ["room_id"], ["id"])
    if "meeting_id" not in ev_cols:
        op.add_column("events", sa.Column("meeting_id", sa.Integer(), nullable=True))
    if "fk_events_meeting_id" not in ev_fks:
        op.create_foreign_key(
            "fk_events_meeting_id", "events", "meeting_schedules", ["meeting_id"], ["id"]
        )


def downgrade() -> None:
    # events
    op.drop_constraint("fk_events_meeting_id", "events", type_="foreignkey")
    op.drop_column("events", "meeting_id")
    op.drop_constraint("fk_events_room_id", "events", type_="foreignkey")
    op.drop_index("ix_events_room_id", table_name="events")
    op.drop_column("events", "room_id")

    # chat_messages
    op.drop_constraint("fk_chat_messages_room_id", "chat_messages", type_="foreignkey")
    op.drop_index("ix_chat_messages_room_id", table_name="chat_messages")
    op.drop_column("chat_messages", "room_id")

    # new tables (reverse dependency order)
    op.drop_index("ix_ai_memories_user_id", table_name="ai_memories")
    op.drop_table("ai_memories")

    op.drop_index("ix_vote_responses_user_id", table_name="vote_responses")
    op.drop_index("ix_vote_responses_vote_id", table_name="vote_responses")
    op.drop_table("vote_responses")

    op.drop_index("ix_vote_options_vote_id", table_name="vote_options")
    op.drop_table("vote_options")

    op.drop_index("ix_votes_room_id", table_name="votes")
    op.drop_table("votes")

    op.drop_index("ix_meeting_participants_user_id", table_name="meeting_participants")
    op.drop_index("ix_meeting_participants_meeting_id", table_name="meeting_participants")
    op.drop_table("meeting_participants")

    op.drop_index("ix_meeting_schedules_room_id", table_name="meeting_schedules")
    op.drop_table("meeting_schedules")

    op.drop_index("ix_friendships_addressee_id", table_name="friendships")
    op.drop_index("ix_friendships_requester_id", table_name="friendships")
    op.drop_table("friendships")

    op.drop_index("ix_room_members_user_id", table_name="room_members")
    op.drop_index("ix_room_members_room_id", table_name="room_members")
    op.drop_table("room_members")

    op.drop_index("ix_rooms_id", table_name="rooms")
    op.drop_table("rooms")
