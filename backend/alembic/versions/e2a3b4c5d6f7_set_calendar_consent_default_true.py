"""set_calendar_consent_default_true

PR-X: 모든 non-guest 사용자의 calendar_consent를 일괄 True로 전환.

- server_default를 sa.false() → sa.true()로 변경 (이후 INSERT 기본값)
- 기존 row 일괄 UPDATE: is_guest=FALSE인 사용자의 calendar_consent를 TRUE로
- 게스트(is_guest=TRUE)는 보호: rooms.py가 명시적으로 False를 부여하므로 그대로 둠
- opt-out 모델은 유지: 사용자가 /api/v1/users/consent로 이후 False 설정 가능

downgrade는 server_default만 false로 되돌리고 데이터는 보존
(이미 동의한 사실을 임의로 무효화하지 않음).

Revision ID: e2a3b4c5d6f7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e2a3b4c5d6f7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    cols = {c["name"] for c in inspector.get_columns("users")}

    # 칼럼이 없으면 True 기본으로 새로 추가 후 종료 (idempotent / fresh DB 대응)
    if "calendar_consent" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "calendar_consent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )
        return

    # 1) server_default를 true로 변경 (이후 INSERT 기본값)
    op.alter_column(
        "users",
        "calendar_consent",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.true(),
    )

    # 2) 기존 row 일괄 UPDATE — 게스트 제외
    #    COALESCE로 is_guest NULL(과거 마이그레이션 잔존) 대비
    if "is_guest" in cols:
        op.execute(
            "UPDATE users SET calendar_consent = TRUE "
            "WHERE COALESCE(is_guest, FALSE) = FALSE "
            "AND calendar_consent = FALSE"
        )
    else:
        # is_guest 칼럼이 아직 추가되지 않은 비정상 상태 → 전체 True
        # (d9e0f1a2b3c4가 head 체인에 포함되어 정상 시퀀스에서는 도달 불가)
        op.execute(
            "UPDATE users SET calendar_consent = TRUE "
            "WHERE calendar_consent = FALSE"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    cols = {c["name"] for c in inspector.get_columns("users")}
    if "calendar_consent" not in cols:
        return

    # server_default만 false로 복귀. 기존 동의 데이터는 보존.
    op.alter_column(
        "users",
        "calendar_consent",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.false(),
    )
