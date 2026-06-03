"""
Unit tests for quick_classify (AI 패널 입력 1차 분류).

핵심 회귀 방지: regex에 안 걸리는 자연어 장소/일정 요청은 LLM fallback으로
분류돼야 한다. LLM(tier=low, gemini)의 실측 지연은 ~2.3–3.0s이므로 wait_for
타임아웃이 그보다 짧으면(이전 1.5s) 정답('place')이 잘려 'general'로 떨어지고
파이프라인이 안 돌아 카드가 안 뜬다 (2026-06-03 bug). 타임아웃은 실측 지연을
충분히 덮어야 한다.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services import quick_classify as qc


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Regex fast-path (LLM 불필요) — 데모 happy-path 표현은 즉시 분류돼야 한다.
# ---------------------------------------------------------------------------


async def test_regex_place_with_category_word(monkeypatch):
    """'장소 ... 추천'은 regex로 즉시 place 분류 (LLM 호출 안 함)."""
    async def _boom(*a, **k):  # LLM이 호출되면 실패시켜 regex 경로임을 보장
        raise AssertionError("LLM should not be called for regex-matching input")

    monkeypatch.setattr(qc, "call_llm_tier", _boom)
    res = await qc.quick_classify("장소 천안 신부동 추천해줘")
    assert res["kind"] == "place"
    assert res["method"] == "regex"


async def test_regex_schedule_natural_language(monkeypatch):
    async def _boom(*a, **k):
        raise AssertionError("LLM should not be called for regex-matching input")

    monkeypatch.setattr(qc, "call_llm_tier", _boom)
    res = await qc.quick_classify("토요일 시간 잡아줘")
    assert res["kind"] == "schedule"
    assert res["method"] == "regex"


# ---------------------------------------------------------------------------
# LLM fallback — regex에 안 걸리는 입력. 핵심 버그 케이스.
# ---------------------------------------------------------------------------


async def test_non_regex_place_survives_realistic_llm_latency(monkeypatch):
    """regex 미스 + LLM이 현실 지연(2.5s)으로 'place' 응답.

    이전 1.5s 타임아웃에선 잘려 'general'이 됐다(버그). 타임아웃이 실측
    지연(2.3–3.0s)을 덮어야 'place'가 살아남는다.
    """
    async def _slow_place(*a, **k):
        await asyncio.sleep(2.5)
        return "place"

    monkeypatch.setattr(qc, "call_llm_tier", _slow_place)
    res = await qc.quick_classify("천안 신부동 추천해줘")
    assert res["kind"] == "place", (
        "regex 미스 장소 요청이 LLM 지연 때문에 general로 떨어지면 안 됨"
    )
    assert res["method"] == "gemini"


async def test_llm_timeout_falls_back_to_general(monkeypatch):
    """LLM이 정말로 응답 못 하면(타임아웃 한참 초과) general로 fail-safe."""
    async def _too_slow(*a, **k):
        await asyncio.sleep(30)
        return "place"

    monkeypatch.setattr(qc, "call_llm_tier", _too_slow)
    res = await qc.quick_classify("거시기 그거 좀")
    assert res["kind"] == "general"
