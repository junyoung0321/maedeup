"""Module-level constants for the AI pipeline.

원본 위치: langgraph_pipeline.py 라인 52~83, 1460~1461.
Phase 2 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
GOOGLE_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
WORK_HOUR_START = 9
WORK_HOUR_END = 22
SLOT_MINUTES = 60
INTENT_CONFIDENCE_THRESHOLD = 0.7
PREFERRED_TIME_RANGES = {
    "평일오전": (9, 12),
    "평일오후": (13, 17),
    "평일저녁": (18, 21),
    "주말오전": (9, 12),
    "주말오후": (13, 17),
    "주말저녁": (18, 21),
}

RECENT_MESSAGE_LIMIT = 12
SLOT_KEYS = ("date_hint", "place_hint", "headcount", "meeting_type")
MAX_SLOT_FILLING_TURNS = 4
SUMMARY_TRIGGER_INTERVAL = 10
FRIENDLY_ERROR_MESSAGE = "잠깐, 뭔가 잘못됐어요 😅 다시 한번 말해줄래요?"

_SOCIAL_RECENT_LIMIT = 10
_SOCIAL_SUMMARY_THRESHOLD = 15  # 이 이상 누적되면 이전 부분을 요약
