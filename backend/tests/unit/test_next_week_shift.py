"""next-week 확장 horizon 캡 (free-use audit 2026-06-03).

date_hint가 slot_context로 이월되며 재트리거마다 +7일씩 무한 climb(2026→2030)
하던 폭주 버그 방지. _next_week_shift는 절대 horizon(today+35일)을 넘으면 None을
반환해 확장을 중단시킨다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.pipeline.nodes.function_call import _next_week_shift

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)  # horizon = 2026-07-08


def test_shift_within_horizon_advances_one_week():
    assert _next_week_shift("2026-06-10", NOW) == "2026-06-17"


def test_shift_far_future_returns_none():
    # 회귀: 이월된 date_hint가 2030이면 확장 중단(None) — 무한 climb 차단.
    assert _next_week_shift("2030-01-02", NOW) is None


def test_shift_horizon_edge():
    # horizon = today+35 = 2026-07-08.
    assert _next_week_shift("2026-06-30", NOW) == "2026-07-07"  # +7 = 07-07 ≤ 07-08
    assert _next_week_shift("2026-07-05", NOW) is None          # +7 = 07-12 > 07-08


def test_no_hint_uses_next_week_start_within_horizon():
    assert _next_week_shift(None, NOW) == "2026-06-11"  # now+8일
