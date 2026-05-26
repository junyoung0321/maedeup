"""
PR-X: calendar_consent 일괄 True 마이그레이션 통합 테스트.

검증 항목:
- 마이그레이션 e2a3b4c5d6f7_set_calendar_consent_default_true의 upgrade/downgrade
  * 기존 non-guest user는 calendar_consent=True로 일괄 전환
  * 게스트(is_guest=True)는 False 보존
  * 이미 True인 user는 영향 없음 (idempotent)
  * downgrade 시 데이터는 보존, server_default만 false 복귀
- 모델 default 변경
  * User() 새 인스턴스 calendar_consent=True
  * rooms.py 게스트 생성 경로는 여전히 calendar_consent=False (코드 변경 영향 없음)

alembic upgrade/downgrade는 별도 sqlite 파일 DB에서 실행 (env.py가
DATABASE_URL 환경변수를 우선 사용함). conftest.py의 db_engine fixture와
충돌하지 않도록 본 모듈은 자체 임시 파일 기반 sqlite를 사용한다.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import command
from alembic.config import Config


MIGRATION_REV = "e2a3b4c5d6f7"
PREV_REV = "e1f2a3b4c5d6"


# ---------------------------------------------------------------------------
# alembic helpers
# ---------------------------------------------------------------------------

def _alembic_cfg(db_url: str) -> Config:
    """backend/alembic.ini를 로드해 sqlalchemy.url을 임시 sqlite로 override."""
    # 본 파일: backend/tests/integration/test_user_consent_default.py
    # alembic.ini : backend/alembic.ini
    backend_dir = Path(__file__).resolve().parents[2]
    ini_path = backend_dir / "alembic.ini"
    cfg = Config(str(ini_path))
    # script_location은 alembic.ini가 상대경로로 "alembic"이므로 cwd 의존.
    # 절대경로로 override해 어디서 실행해도 동작하도록.
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture
def sqlite_db_url(monkeypatch):
    """임시 파일 sqlite. alembic env.py가 DATABASE_URL을 읽으므로 그것도 세팅."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    url = f"sqlite:///{tmp.name}"
    monkeypatch.setenv("DATABASE_URL", url)
    try:
        yield url
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _upgrade_to(rev: str, db_url: str) -> None:
    command.upgrade(_alembic_cfg(db_url), rev)


def _downgrade_to(rev: str, db_url: str) -> None:
    command.downgrade(_alembic_cfg(db_url), rev)


def _engine(db_url: str) -> sa.Engine:
    # alembic env.py가 async URL로 변환할 수 있으나, 본 테스트는 동기 SQLAlchemy로
    # 직접 검증한다. db_url은 항상 동기 sqlite 형태.
    return sa.create_engine(db_url, future=True)


def _seed_users(conn: Connection, rows: list[dict]) -> None:
    """users 테이블에 직접 INSERT. id를 명시해 추적 쉽게.

    NOT NULL 컬럼은 호출자가 명시 안 하면 default로 채움 (테스트 편의):
    - created_at: 현재 시각 (naive UTC, models/user.py 동일 패턴)
    - share_*_data: True (opt-out 모델 기본)
    - is_ai_filled: '{}' (빈 JSON)
    - name: row id 기반 placeholder
    """
    from datetime import datetime, timezone

    default_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
    for row in rows:
        row = dict(row)  # 복사 (caller 입력 보존)
        row.setdefault("created_at", default_created_at)
        row.setdefault("share_food_data", True)
        row.setdefault("share_location_data", True)
        row.setdefault("share_schedule_data", True)
        row.setdefault("is_ai_filled", "{}")
        cols = ", ".join(row.keys())
        placeholders = ", ".join(f":{k}" for k in row.keys())
        conn.execute(sa.text(f"INSERT INTO users ({cols}) VALUES ({placeholders})"), row)


def _fetch_user(conn: Connection, user_id: int) -> dict:
    result = conn.execute(
        sa.text("SELECT id, email, calendar_consent, is_guest FROM users WHERE id = :id"),
        {"id": user_id},
    ).mappings().first()
    assert result is not None, f"user id={user_id} not found"
    return dict(result)


# ---------------------------------------------------------------------------
# 마이그레이션 동작 검증
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("SKIP_ALEMBIC_TESTS") == "1",
    reason="alembic 마이그레이션 환경 미가용 시 스킵",
)
def test_alembic_upgrade_sets_existing_users_true(sqlite_db_url):
    """non-guest, calendar_consent=False인 user는 upgrade 후 True로 전환."""
    # 1) 직전 revision까지 올린다 (스키마는 calendar_consent=False 기본)
    _upgrade_to(PREV_REV, sqlite_db_url)

    engine = _engine(sqlite_db_url)
    with engine.begin() as conn:
        _seed_users(conn, [
            {
                "id": 100,
                "email": "non-guest@test",
                "name": "NonGuest",
                "calendar_consent": False,
                "is_guest": False,
            },
        ])

    # 2) 대상 revision으로 upgrade
    _upgrade_to(MIGRATION_REV, sqlite_db_url)

    with engine.connect() as conn:
        row = _fetch_user(conn, 100)
    assert bool(row["calendar_consent"]) is True, (
        f"non-guest user는 일괄 True로 전환되어야 함. row={row}"
    )
    assert bool(row["is_guest"]) is False


@pytest.mark.skipif(
    os.environ.get("SKIP_ALEMBIC_TESTS") == "1",
    reason="alembic 마이그레이션 환경 미가용 시 스킵",
)
def test_alembic_upgrade_preserves_guest_false(sqlite_db_url):
    """게스트(is_guest=True, calendar_consent=False)는 upgrade 후에도 False 유지."""
    _upgrade_to(PREV_REV, sqlite_db_url)

    engine = _engine(sqlite_db_url)
    with engine.begin() as conn:
        _seed_users(conn, [
            {
                "id": 200,
                "email": "guest@maedeup.local",
                "name": "Guest",
                "calendar_consent": False,
                "is_guest": True,
            },
        ])

    _upgrade_to(MIGRATION_REV, sqlite_db_url)

    with engine.connect() as conn:
        row = _fetch_user(conn, 200)
    assert bool(row["calendar_consent"]) is False, (
        f"게스트는 False로 보존되어야 함. row={row}"
    )
    assert bool(row["is_guest"]) is True


@pytest.mark.skipif(
    os.environ.get("SKIP_ALEMBIC_TESTS") == "1",
    reason="alembic 마이그레이션 환경 미가용 시 스킵",
)
def test_alembic_upgrade_handles_already_true(sqlite_db_url):
    """이미 True인 user는 idempotent (변동 없음)."""
    _upgrade_to(PREV_REV, sqlite_db_url)

    engine = _engine(sqlite_db_url)
    with engine.begin() as conn:
        _seed_users(conn, [
            {
                "id": 300,
                "email": "already-true@test",
                "name": "AlreadyTrue",
                "calendar_consent": True,
                "is_guest": False,
            },
        ])

    _upgrade_to(MIGRATION_REV, sqlite_db_url)

    with engine.connect() as conn:
        row = _fetch_user(conn, 300)
    assert bool(row["calendar_consent"]) is True
    # 재 upgrade (no-op heads)
    _upgrade_to(MIGRATION_REV, sqlite_db_url)
    with engine.connect() as conn:
        row2 = _fetch_user(conn, 300)
    assert row2 == row, "동일 revision으로의 재 upgrade는 데이터 변동을 야기하지 말 것"


@pytest.mark.skipif(
    os.environ.get("SKIP_ALEMBIC_TESTS") == "1",
    reason="alembic 마이그레이션 환경 미가용 시 스킵",
)
def test_alembic_downgrade_preserves_data(sqlite_db_url):
    """downgrade 후 기존 동의 데이터는 True 유지(임의 무효화 X). server_default만 false로 복귀."""
    _upgrade_to(PREV_REV, sqlite_db_url)

    engine = _engine(sqlite_db_url)
    with engine.begin() as conn:
        _seed_users(conn, [
            {
                "id": 400,
                "email": "to-downgrade@test",
                "name": "Downgrade",
                "calendar_consent": False,
                "is_guest": False,
            },
        ])

    _upgrade_to(MIGRATION_REV, sqlite_db_url)
    with engine.connect() as conn:
        row_after_up = _fetch_user(conn, 400)
    assert bool(row_after_up["calendar_consent"]) is True

    # downgrade — 데이터는 그대로 True여야 함
    _downgrade_to(PREV_REV, sqlite_db_url)
    with engine.connect() as conn:
        row_after_down = _fetch_user(conn, 400)
    assert bool(row_after_down["calendar_consent"]) is True, (
        "downgrade는 동의 데이터를 임의로 무효화하지 않음"
    )


# ---------------------------------------------------------------------------
# 모델 default / 게스트 생성 경로
# ---------------------------------------------------------------------------

def test_new_user_default_true():
    """User() 새 인스턴스의 calendar_consent 기본값은 True."""
    from app.models.user import User

    u = User(email="x@test", name="X")
    assert u.calendar_consent is True, (
        "PR-X: 모델 default를 True로 변경 (모든 non-guest 일괄 동의)"
    )


def test_guest_creation_unchanged():
    """rooms.py 게스트 생성 경로는 명시 False 인자로 calendar_consent=False 유지.

    이 테스트는 코드를 직접 실행하지 않고 인자 명시 여부를 정적으로 검증한다.
    rooms.py 게스트 User 생성 시 calendar_consent=False가 빠지면 게스트도
    True가 되어 정책 위반 → 회귀 방지 목적.
    """
    from pathlib import Path
    rooms_py = Path(__file__).resolve().parents[2] / "app" / "api" / "routes" / "rooms.py"
    src = rooms_py.read_text(encoding="utf-8")
    # 게스트 생성 블록(User(... is_guest=True, calendar_consent=False)) 직접 검증
    assert "is_guest=True" in src, "게스트 생성 코드가 사라졌다 — 회귀"
    assert "calendar_consent=False" in src, (
        "게스트 생성 시 calendar_consent=False가 누락됨 — 모델 default가 True로 변경된 "
        "이상 게스트 보호를 위해 명시 False 필요"
    )

    # 동일 함수 내에서 명시 False가 짝지어 있는지 추가 보장
    # (간단한 윈도우 검사: is_guest=True 라인 ±20줄 안에 calendar_consent=False가 있어야 함)
    lines = src.splitlines()
    guest_idx = [i for i, ln in enumerate(lines) if "is_guest=True" in ln]
    assert guest_idx, "is_guest=True 줄을 찾지 못함"
    paired = False
    for i in guest_idx:
        window = lines[max(0, i - 20): i + 20]
        if any("calendar_consent=False" in w for w in window):
            paired = True
            break
    assert paired, (
        "게스트 생성 블록 근처에 calendar_consent=False가 없음 — 정책 위반"
    )
