"""Compatibility shim. 실제 구현은 pipeline/ 하위 패키지로 이동됨.

신규 코드는 `from app.services.pipeline.* import ...`를 사용할 것.
이 파일은 외부 import 호환성만 위한 re-export.

분할 작업: Phase 5.2 (2026-05-13). 원본 5,301줄 → 14줄 shim.
이전 버전 (구현체 포함): git tag refactor/pre-shim-swap @ a659c9c.

외부 import 사이트:
  - agent.py:24 → KST, _analyze_conversation, run_pipeline
  - meetings.py:29 → memory_extraction, suggest_alternative_slots
  - rooms.py:741 → run_pipeline (inline)
  - scripts/qa_privacy_boundary.py:156 → run_pipeline (inline)
  - chat_cli.py:99 → classify_intent (patch.object 대상 — module attribute 필요)
"""
from __future__ import annotations

from app.services.intent_classifier import classify_intent
from app.services.pipeline.constants import KST
from app.services.pipeline.graph import run_pipeline
from app.services.pipeline.nodes.conversation_analyzer import (
    _analyze_conversation,
    suggest_alternative_slots,
)
from app.services.pipeline.nodes.memory import memory_extraction

__all__ = [
    "KST",
    "classify_intent",
    "run_pipeline",
    "_analyze_conversation",
    "memory_extraction",
    "suggest_alternative_slots",
]
