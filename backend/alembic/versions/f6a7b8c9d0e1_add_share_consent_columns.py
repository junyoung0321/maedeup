"""add_share_consent_columns

QuickPreferences 토글이 실제로 작동하도록 user-level 카테고리별 share consent
3개 칼럼 추가. 기본값 True (기존 사용자도 share-on baseline). _get_room_member_constraints가 이 토글을 respect해서 OFF인 사용자의 해당 카테고리 데이터는
group recommendation 합성에서 제외.

Idempotent — `inspector.has_column` 체크 후 add.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-27 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    for col_name in ("share_food_data", "share_location_data", "share_schedule_data"):
        if col_name not in user_cols:
            op.add_column(
                "users",
                sa.Column(
                    col_name,
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("true"),
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    for col_name in (
        "share_schedule_data",
        "share_location_data",
        "share_food_data",
    ):
        if col_name in user_cols:
            op.drop_column("users", col_name)
