"""PR-V1.5 / Q-X3 — `_build_user_context`의 캘린더 연동 메시지 토큰 체크.

calendar_consent=True여도 google_*_token이 모두 비어 있으면 "아니오" 표시.
실제 GCal 호출 가능 여부를 정확히 사용자에게 노출.
"""
from __future__ import annotations

import asyncio
import types

from app.api.routes.assistant import _build_user_context


def _make_user(
    *,
    calendar_consent: bool,
    access_token: str | None = None,
    refresh_token: str | None = None,
) -> types.SimpleNamespace:
    """User SQLModel 대신 duck-typed namespace로 테스트.

    `_build_user_context`는 getattr만 사용하므로 namespace로 충분.
    """
    return types.SimpleNamespace(
        name="테스터",
        food_restrictions=None,
        food_preferences=None,
        food_preference_note=None,
        liked_areas=None,
        disliked_areas=None,
        time_preference=None,
        transport_mode=None,
        calendar_consent=calendar_consent,
        google_access_token=access_token,
        google_refresh_token=refresh_token,
    )


def _build(user) -> str:
    return asyncio.run(_build_user_context(user))


def test_consent_true_with_access_token_shows_yes():
    """consent=True + access_token 있음 → '예'."""
    user = _make_user(calendar_consent=True, access_token="ya29.xxx")
    out = _build(user)
    assert "캘린더 연동: 예" in out


def test_consent_true_with_refresh_token_only_shows_yes():
    """consent=True + refresh_token만 있어도 → '예' (재발급 가능)."""
    user = _make_user(calendar_consent=True, refresh_token="1//0g...")
    out = _build(user)
    assert "캘린더 연동: 예" in out


def test_consent_true_no_tokens_shows_no():
    """consent=True지만 토큰 둘 다 없음 → '아니오' (Q-X3 핵심 케이스)."""
    user = _make_user(calendar_consent=True, access_token=None, refresh_token=None)
    out = _build(user)
    assert "캘린더 연동: 아니오" in out


def test_consent_false_shows_no():
    """consent=False → 토큰 유무와 무관하게 '아니오'."""
    user = _make_user(calendar_consent=False, access_token="ya29.xxx")
    out = _build(user)
    assert "캘린더 연동: 아니오" in out


def test_consent_false_no_tokens_shows_no():
    """consent=False + 토큰 없음 → '아니오'."""
    user = _make_user(calendar_consent=False)
    out = _build(user)
    assert "캘린더 연동: 아니오" in out
