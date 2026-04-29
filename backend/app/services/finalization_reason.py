"""
Reason generator for FinalizationProposalCard.

Takes a proposed slot (and optional alternate for tie cases) and produces a
short Korean narrator line like "세 분이 이 시간을 선택하셨네요. 이 시간으로 가실까요?".

The function signature matches `app.services.scheduling_round.ReasonGenerator`
so it can be injected into `scheduling_round.propose()` without importing the
LangGraph pipeline (keeps the service layer lean).

If Gemini is unavailable (rate limit, outage, empty response), falls back to
a deterministic template so the demo path always works.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.gemini import call_gemini

logger = logging.getLogger(__name__)


def _slot_label(slot: dict[str, Any]) -> str:
    """Best-effort human label for a slot: prefer explicit 'label', then
    start_at, then fallback."""
    label = slot.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    start_at = slot.get("start_at")
    if isinstance(start_at, str) and start_at.strip():
        return start_at.strip()
    return "이 시간"


def _template(
    slot: dict[str, Any],
    alternate: Optional[dict[str, Any]],
    like_count: int,
    total: int,
) -> str:
    """Deterministic fallback when Gemini is unavailable."""
    label = _slot_label(slot)
    if alternate is not None:
        alt_label = _slot_label(alternate)
        return f"{label} 또는 {alt_label} 중에 고르면 될 것 같아요."
    if total > 0 and like_count > 0:
        return f"{total}명 중 {like_count}명이 {label}를 선택했어요. 이 시간으로 가실까요?"
    if total > 0:
        return f"{total}명 중 과반이 {label}를 가능하다고 했어요. 이 시간으로 가실까요?"
    return f"{label} 어떠세요?"


def _build_prompt(
    slot: dict[str, Any],
    alternate: Optional[dict[str, Any]],
    like_count: int,
    total: int,
) -> str:
    label = _slot_label(slot)
    if alternate is not None:
        alt_label = _slot_label(alternate)
        return (
            "모임 가능 시간이 두 개로 나뉘었습니다. "
            f"후보 1: '{label}', 후보 2: '{alt_label}'. "
            f"전체 인원 {total}명, 현재까지 동의 {like_count}명. "
            "방장이 두 시간 중 하나를 고르도록 친근하게 안내하는 한 문장을 "
            "25자 이내로 만들어주세요. 인사말이나 이모지 금지."
        )
    return (
        f"모임 참여자 {total}명 중 {like_count}명이 '{label}'를 가능한 시간으로 "
        "선택했습니다. 이 시간으로 확정할지 방장에게 묻는 톤으로, "
        "참여자가 선택한 사실을 관찰한 뒤 질문 형태로 끝나는 한 문장을 "
        "30자 이내로 만들어주세요. 인사말이나 이모지 금지."
    )


async def generate_finalization_reason(
    room_id: int,
    proposed_slot: dict[str, Any],
    alternate_slot: Optional[dict[str, Any]],
    like_count: int,
    total_eligible_voters: int,
) -> str:
    """
    Matches the `ReasonGenerator` callable signature expected by
    `scheduling_round.propose()`.

    Returns a short narrator line. Never raises — Gemini failures fall back
    to the template so the happy path never blocks on LLM outages.
    """
    prompt = _build_prompt(
        proposed_slot, alternate_slot, like_count, total_eligible_voters
    )
    try:
        generated = await call_gemini(prompt)
    except Exception:
        logger.warning(
            "Gemini call unexpectedly raised for finalization reason room_id=%s",
            room_id,
            exc_info=True,
        )
        generated = ""

    if isinstance(generated, str) and generated.strip():
        # Strip surrounding whitespace; keep the first line only if the model
        # returned multiple.
        first_line = generated.strip().splitlines()[0].strip()
        if first_line:
            return first_line

    return _template(proposed_slot, alternate_slot, like_count, total_eligible_voters)
