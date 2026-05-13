"""포맷팅 + 사용자 식별 헬퍼.

원본 위치: langgraph_pipeline.py 라인 458~480, 829~851, 942~957.
Phase 2 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

의존:
  - dates 헬퍼: _get_korean_holiday, _is_weekend (slot label용)
  - constants: KST (confirmed_time KST 변환용)
  - User 모델 (calendar_key 용)
"""
from __future__ import annotations

from datetime import datetime

from app.models.user import User
from app.services.pipeline.constants import KST
from app.services.pipeline.helpers.dates import _get_korean_holiday, _is_weekend


def _format_slot_label(start_at: datetime, unavailable_names: list[str]) -> str:
    weekday = ["월", "화", "수", "목", "금", "토", "일"][start_at.weekday()]
    ampm = "오전" if start_at.hour < 12 else "오후"
    hour = start_at.hour if start_at.hour <= 12 else start_at.hour - 12
    holiday = _get_korean_holiday(start_at)
    day_tag = f" {holiday}" if holiday else ""
    if _is_weekend(start_at) and not holiday:
        day_tag = " 주말"
    suffix = " (전원 가능)"
    if unavailable_names:
        absent_users = ", ".join(f"@{name}" for name in unavailable_names)
        suffix = f" (N-1명 가능, {absent_users} 불참)"
    return f"{start_at.month}월 {start_at.day}일 ({weekday}){day_tag} {ampm} {hour}:{start_at.minute:02d}{suffix}"


def _format_confirmed_time(start_at: datetime | None) -> str | None:
    if start_at is None:
        return None
    start_kst = start_at.astimezone(KST)
    ampm = "오전" if start_kst.hour < 12 else "오후"
    hour = start_kst.hour % 12 or 12
    return f"{ampm} {hour}:{start_kst.minute:02d}"


def _infer_time_bucket(source_text: str | None, parsed_time_hint: str | None) -> str:
    normalized = str(source_text or "").replace(" ", "")
    if any(keyword in normalized for keyword in ("저녁", "밤")):
        return "evening"
    if any(keyword in normalized for keyword in ("오후", "점심")):
        return "afternoon"
    if any(keyword in normalized for keyword in ("오전", "아침", "새벽")):
        return "morning"

    if parsed_time_hint:
        try:
            hour = datetime.strptime(parsed_time_hint, "%H:%M").hour
        except ValueError:
            hour = -1
        if hour >= 17:
            return "evening"
        if hour >= 12:
            return "afternoon"
        if hour >= 0:
            return "morning"

    return "afternoon"


def _room_id_as_int(room_id: str) -> int | None:
    try:
        return int(room_id)
    except (TypeError, ValueError):
        return None


def _user_calendar_key(user: User) -> str:
    return f"{user.id}:{user.name}"


def _user_display_name(user_key: str) -> str:
    _, _, name = user_key.partition(":")
    return name or user_key
