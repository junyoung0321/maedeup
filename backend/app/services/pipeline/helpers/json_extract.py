"""JSON 추출 헬퍼 — Gemini 응답 등 unreliable text에서 JSON 안전 추출.

원본 위치: langgraph_pipeline.py 라인 482~552.
Phase 2 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.
"""
from __future__ import annotations

import json
import re
from typing import Any


def _extract_json_object(text: str | None) -> dict[str, Any]:
    if not isinstance(text, str):
        return {}
    stripped = text.strip()
    if stripped.startswith("```"):
        chunks = [chunk.strip() for chunk in stripped.split("```") if chunk.strip()]
        if chunks:
            stripped = chunks[0].removeprefix("json").strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_json_array(text: str | None) -> list[dict[str, Any]]:
    if not isinstance(text, str):
        return []
    stripped = text.strip()
    if stripped.startswith("```"):
        chunks = [chunk.strip() for chunk in stripped.split("```") if chunk.strip()]
        if chunks:
            stripped = chunks[0].removeprefix("json").strip()

    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _extract_loose_json_object(text: str | None) -> dict[str, Any]:
    parsed = _extract_json_object(text)
    if parsed:
        return parsed
    if not isinstance(text, str):
        return {}

    stripped = text.strip()
    if stripped.startswith("```"):
        chunks = [chunk.strip() for chunk in stripped.split("```") if chunk.strip()]
        if chunks:
            stripped = chunks[0].removeprefix("json").strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]

    normalized = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r'\1"\2"\3', stripped)
    normalized = normalized.replace("'", '"')

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
