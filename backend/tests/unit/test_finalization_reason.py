"""
Unit tests for app.services.finalization_reason.

Gemini is mocked so the tests are deterministic and hermetic.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services import finalization_reason as fr


async def test_uses_gemini_output_when_available():
    with patch("app.services.finalization_reason.call_gemini", return_value="토요일 3시로 가실까요?"):
        result = await fr.generate_finalization_reason(
            room_id=1,
            proposed_slot={"label": "토요일 15:00"},
            alternate_slot=None,
            like_count=3,
            total_eligible_voters=5,
        )
    assert result == "토요일 3시로 가실까요?"


async def test_strips_and_takes_first_line():
    with patch(
        "app.services.finalization_reason.call_gemini",
        return_value="  첫 줄 제안입니다  \n두번째 줄은 무시",
    ):
        result = await fr.generate_finalization_reason(
            room_id=1,
            proposed_slot={"label": "15:00"},
            alternate_slot=None,
            like_count=2,
            total_eligible_voters=3,
        )
    assert result == "첫 줄 제안입니다"


async def test_falls_back_on_empty_gemini_response():
    with patch("app.services.finalization_reason.call_gemini", return_value=""):
        result = await fr.generate_finalization_reason(
            room_id=1,
            proposed_slot={"label": "토요일 15:00"},
            alternate_slot=None,
            like_count=3,
            total_eligible_voters=5,
        )
    # Template mentions both the count and the label.
    assert "5명" in result
    assert "3명" in result
    assert "토요일 15:00" in result


async def test_falls_back_on_gemini_exception():
    with patch(
        "app.services.finalization_reason.call_gemini",
        side_effect=RuntimeError("rate limited"),
    ):
        result = await fr.generate_finalization_reason(
            room_id=1,
            proposed_slot={"label": "토요일 15:00"},
            alternate_slot=None,
            like_count=3,
            total_eligible_voters=5,
        )
    # Should not raise; template kicks in.
    assert isinstance(result, str) and result
    assert "토요일 15:00" in result


async def test_tie_case_mentions_both_slots():
    with patch("app.services.finalization_reason.call_gemini", return_value=""):
        result = await fr.generate_finalization_reason(
            room_id=1,
            proposed_slot={"label": "토요일 15:00"},
            alternate_slot={"label": "일요일 14:00"},
            like_count=0,
            total_eligible_voters=4,
        )
    assert "토요일 15:00" in result
    assert "일요일 14:00" in result


async def test_slot_label_fallback_uses_start_at():
    with patch("app.services.finalization_reason.call_gemini", return_value=""):
        result = await fr.generate_finalization_reason(
            room_id=1,
            proposed_slot={"start_at": "2026-05-02T15:00:00"},
            alternate_slot=None,
            like_count=1,
            total_eligible_voters=3,
        )
    assert "2026-05-02T15:00:00" in result
