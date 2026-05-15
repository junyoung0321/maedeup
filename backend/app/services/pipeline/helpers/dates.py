"""날짜 헬퍼 — 한국 휴일, 요일, ISO 변환, 자연어 파싱.

원본 위치: langgraph_pipeline.py 라인 67~77 (_KR_HOLIDAYS, _get_korean_holiday,
  _is_weekend), 554~599 (_is_iso_date_hint, _is_specific_iso_date, _resolve_rejected_date),
  601~635 (_detect_multi_date_options), 637~666 (_weekday_from_korean, _coerce_bool,
  _next_weekday), 668~827 (_fallback_parse_natural_date, _normalize_parsed_natural_date,
  _parse_natural_date), 1323~1333 (_parse_iso_datetime), 1621~1652 (_DATE_RANGE_RE,
  _ISO_DATE_RE, _expand_date_hint).

Phase 2 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

조정 메모 (v2 §3.3 대비):
  - _coerce_bool은 v2 계획서에선 slot_state.py 배정이었으나, 본 모듈의
    _normalize_parsed_natural_date가 의존해 dates.py로 함께 이동 (Layer 0 유지).
    slot_state.py(_update_slot_state)도 이 모듈을 import해서 사용.

의존:
  - constants.KST (자연어 날짜 파싱 기준 시각)
  - json_extract._extract_loose_json_object (_parse_natural_date Gemini 응답 파싱)
  - app.services.gemini.call_gemini
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import holidays

from app.services.gemini import call_gemini
from app.services.pipeline.constants import KST
from app.services.pipeline.helpers.json_extract import _extract_loose_json_object

logger = logging.getLogger(__name__)

_KR_HOLIDAYS = holidays.KR(language="ko")


def _get_korean_holiday(dt: datetime) -> str | None:
    """해당 날짜가 한국 공휴일이면 공휴일 이름 반환, 아니면 None."""
    d = dt.date() if isinstance(dt, datetime) else dt
    return _KR_HOLIDAYS.get(d)


def _is_weekend(dt: datetime) -> bool:
    return dt.weekday() >= 5  # 토(5), 일(6)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _is_iso_date_hint(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}(~\d{4}-\d{2}-\d{2})?", normalized))


def _is_specific_iso_date(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()))


def _resolve_rejected_date(raw: str | None, now_kst: datetime | None = None) -> str | None:
    """LLM이 자연어로 반환한 거부 날짜를 ISO(YYYY-MM-DD) 문자열로 변환.

    예: "2026-05-09" → "2026-05-09" (이미 ISO)
        "금요일"      → 다음 금요일 ISO
        "다음 금요일" → 다음주 금요일 ISO
        "5월 9일"     → "{year}-05-09" (이미 지난 날이면 다음 해)
        "5/9"         → "{year}-05-09"
        변환 실패 시 None
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if _is_specific_iso_date(text):
        return text

    base = now_kst or datetime.now(KST)

    # "5/9" 같은 슬래시 형식 → "5월 9일"로 정규화 후 재시도
    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})", text)
    if slash_match:
        text = f"{int(slash_match.group(1))}월 {int(slash_match.group(2))}일"

    parsed = _fallback_parse_natural_date(text, base)
    if not parsed:
        return None
    date_value = parsed.get("date")
    if isinstance(date_value, str) and _is_specific_iso_date(date_value):
        return date_value
    return None


def _detect_multi_date_options(text: str) -> bool:
    """여러 날짜 선택지를 제시하는 패턴을 감지합니다.

    예: "목요일에 볼까 금요일에 볼까", "토요일 어때 일요일 어때",
        "내일 아니면 모레", "15일이나 16일"
    """
    if not text:
        return False

    # 요일 2개 이상 언급
    weekday_mentions = re.findall(r'[월화수목금토일]요일', text)
    if len(set(weekday_mentions)) >= 2:
        return True

    # M월D일 패턴 2개 이상
    md_mentions = re.findall(r'\d{1,2}월\s*\d{1,2}일', text)
    if len(md_mentions) >= 2:
        return True

    # D일 패턴 2개 이상 (같은 문장에서)
    day_mentions = re.findall(r'(?<!\d)(\d{1,2})일', text)
    if len(set(day_mentions)) >= 2:
        return True

    # 선택 패턴: "A 아니면 B", "A이나 B", "A or B" + 날짜 키워드
    choice_patterns = [
        r'(?:볼까|어때|할까|갈까|만날까).*(?:볼까|어때|할까|갈까|만날까)',
        r'(?:내일|모레|[월화수목금토일]요일|\d{1,2}일)\s*(?:아니면|이나|or|말고)\s*(?:내일|모레|[월화수목금토일]요일|\d{1,2}일)',
    ]
    for pattern in choice_patterns:
        if re.search(pattern, text):
            return True

    return False


def _weekday_from_korean(text: str) -> int | None:
    mapping = {
        "월": 0,
        "화": 1,
        "수": 2,
        "목": 3,
        "금": 4,
        "토": 5,
        "일": 6,
    }
    match = re.search(r"([월화수목금토일])요일?", text)
    if not match:
        return None
    return mapping.get(match.group(1))


def _next_weekday(base: datetime, weekday: int, include_current_week: bool = False) -> datetime:
    days_ahead = (weekday - base.weekday()) % 7
    if days_ahead == 0 and not include_current_week:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


def _fallback_parse_natural_date(text: str, now_kst: datetime) -> dict[str, Any] | None:
    normalized = text.strip()
    if not normalized:
        return None

    compact = normalized.replace(" ", "")
    result: dict[str, Any] = {}
    target_date: datetime | None = None

    if "모레" in compact:
        target_date = now_kst + timedelta(days=2)
    elif "내일" in compact:
        target_date = now_kst + timedelta(days=1)
    elif "오늘" in compact:
        target_date = now_kst
    elif "이번주말" in compact:
        target_date = _next_weekday(now_kst, 5, include_current_week=True)
        result["is_flexible"] = True
    elif "그다음주" in compact or "다다음주" in compact:
        # "그 다음주" / "그다음주" / "다다음주" → this_week_monday + 14일
        weekday = _weekday_from_korean(normalized)
        if weekday is not None:
            this_week_monday = now_kst - timedelta(days=now_kst.weekday())
            next_next_week_base = this_week_monday + timedelta(days=14)
            target_date = next_next_week_base + timedelta(days=weekday)
    elif "다음주" in compact or "차주" in compact:
        # "다음주" / "차주" → this_week_monday + 7일
        weekday = _weekday_from_korean(normalized)
        if weekday is not None:
            this_week_monday = now_kst - timedelta(days=now_kst.weekday())
            next_week_base = this_week_monday + timedelta(days=7)
            target_date = next_week_base + timedelta(days=weekday)
    elif "이번주" in compact:
        weekday = _weekday_from_korean(normalized)
        if weekday is not None:
            this_week_monday = now_kst - timedelta(days=now_kst.weekday())
            target_date = this_week_monday + timedelta(days=weekday)
            if target_date.date() < now_kst.date():
                target_date += timedelta(days=7)
    else:
        # 요일만 있으면 (예: "목요일", "금요일") → 다음 해당 요일로
        weekday = _weekday_from_korean(normalized)
        if weekday is not None:
            days_ahead = weekday - now_kst.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            target_date = now_kst + timedelta(days=days_ahead)

        day_match = re.search(r"(?<!\d)(\d{1,2})일(?!\d)", normalized) if target_date is None else None
        if day_match:
            day = int(day_match.group(1))
            year = now_kst.year
            month = now_kst.month
            if day < now_kst.day:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            try:
                target_date = now_kst.replace(
                    year=year,
                    month=month,
                    day=day,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            except ValueError:
                target_date = None

    if target_date is None:
        return None

    normalized_no_space = normalized.replace(" ", "")
    if any(keyword in normalized_no_space for keyword in ("저녁", "밤")):
        result["time"] = "18:00"
        result["is_flexible"] = True
    elif "오후" in normalized_no_space:
        result["time"] = "13:00"
        result["is_flexible"] = True
    elif any(keyword in normalized_no_space for keyword in ("오전", "아침")):
        result["time"] = "09:00"
        result["is_flexible"] = True
    elif "점심" in normalized_no_space:
        result["time"] = "12:00"
        result["is_flexible"] = True

    result["date"] = target_date.strftime("%Y-%m-%d")
    result.setdefault("is_flexible", "time" not in result)
    result.setdefault("time", None)
    return result


def _normalize_parsed_natural_date(
    parsed: dict[str, Any],
    source_text: str,
    now_kst: datetime,
) -> dict[str, Any] | None:
    if not parsed:
        return None

    date_value = str(parsed.get("date") or "").strip()
    time_value = str(parsed.get("time") or "").strip()
    is_flexible = _coerce_bool(parsed.get("is_flexible", False))

    if date_value:
        try:
            datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError:
            date_value = ""
    if time_value:
        try:
            datetime.strptime(time_value, "%H:%M")
        except ValueError:
            time_value = ""

    fallback = _fallback_parse_natural_date(source_text, now_kst) or {}
    if not date_value:
        date_value = str(fallback.get("date") or "").strip()
    if not time_value:
        time_value = str(fallback.get("time") or "").strip()
    if not is_flexible and "is_flexible" in fallback:
        is_flexible = _coerce_bool(fallback.get("is_flexible"))

    if not date_value:
        return None

    return {
        "date": date_value,
        "time": time_value or None,
        "is_flexible": is_flexible,
    }


async def _parse_natural_date(text: str) -> dict[str, Any] | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None

    now_kst = datetime.now(KST)

    # --- OPTIMIZATION: Try pattern-based parsing first, skip Gemini if successful ---
    fallback_result = _fallback_parse_natural_date(normalized, now_kst)
    if fallback_result and fallback_result.get("date"):
        logger.info("[OPT] _parse_natural_date resolved by pattern fallback, skipping Gemini")
        return fallback_result

    today = now_kst.strftime("%Y-%m-%d")
    prompt = (
        "다음 텍스트에서 날짜/시간 정보를 추출해서 ISO 8601 형식으로 변환해줘. "
        f"오늘은 {today}입니다. 결과만 JSON으로: "
        "{date: 'YYYY-MM-DD', time: 'HH:MM', is_flexible: true/false}\n"
        f"텍스트: {normalized}"
    )

    try:
        raw = await call_gemini(prompt)
    except Exception as exc:
        logger.warning("Failed to parse natural date with Gemini: %s", exc)
        return fallback_result

    parsed = _extract_loose_json_object(raw)
    normalized_result = _normalize_parsed_natural_date(parsed, normalized, now_kst)
    if normalized_result:
        return normalized_result
    return fallback_result


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


_DATE_RANGE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2}-\d{2})$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _expand_date_hint(hint: Any) -> list[str]:
    if not isinstance(hint, str):
        return []

    if _ISO_DATE_RE.match(hint):
        try:
            return [datetime.fromisoformat(hint).date().isoformat()]
        except ValueError:
            return []

    range_match = _DATE_RANGE_RE.match(hint)
    if not range_match:
        return []

    try:
        start = datetime.fromisoformat(range_match.group(1)).date()
        end = datetime.fromisoformat(range_match.group(2)).date()
    except ValueError:
        return []

    if end < start:
        return []

    day_count = (end - start).days
    if day_count > 14:
        return []

    return [(start + timedelta(days=offset)).isoformat() for offset in range(day_count + 1)]
