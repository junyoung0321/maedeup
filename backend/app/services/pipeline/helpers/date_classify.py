"""날짜 가용성 추출 — 2단계 구조(structured intent → 코드 확장).

문제: 단일 LLM이 의도이해 + 날짜계산 + 여집합생성을 한 번에 하면 brittle
(특히 'X 빼고 다 바빠' 여집합·범위·상대표현에서 recall 급락).

해결: LLM은 '가용성 제약(constraint)'의 *구조*만 추출하고(범위·요일·극성·예외),
날짜 enumerate/여집합 확장은 코드가 결정적으로 수행. 라벨 달력을 제공해 LLM의
날짜 산술 환각도 제거.

eval(docs/handoff/eval/): rejected_dates F1 0.22→0.66, exact 0.34→0.66,
여집합(complement) exact 0.10→0.65. (2026-06-02 기준, gpt-4o-mini)

반환: {"rejected": set[iso], "preferred": set[iso], "available": set[iso]}
잔여 오류는 상위의 reflect-back 확인 단계가 사용자 교정으로 보완.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.services.llm import call_llm
from app.services.pipeline.helpers.json_extract import _extract_json_object

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_WD = ["월", "화", "수", "목", "금", "토", "일"]
_WD_CODE = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_WINDOW = 21  # 후보 달력 길이(일). 이번주+다음주+다다음주 커버.


def _week_bounds(today: datetime, which: str):
    this_mon = today - timedelta(days=today.weekday())
    base = {
        "this_week": this_mon,
        "next_week": this_mon + timedelta(days=7),
        "week_after": this_mon + timedelta(days=14),
    }.get(which)
    if base is None:
        return None
    return base, base + timedelta(days=6)


def _resolve(constraints: list, today: datetime, window: int = _WINDOW) -> dict:
    """LLM이 뽑은 구조 제약을 결정적으로 ISO 날짜 집합으로 확장."""
    cal = [today + timedelta(days=i) for i in range(window)]
    cal_iso = {d.strftime("%Y-%m-%d") for d in cal}
    today_iso = today.strftime("%Y-%m-%d")
    rejected: set[str] = set()
    preferred: set[str] = set()
    available: set[str] = set()

    for c in constraints or []:
        if not isinstance(c, dict):
            continue
        scope = c.get("scope")
        dates: list[datetime] = []
        if scope in ("this_week", "next_week", "week_after"):
            b = _week_bounds(today, scope)
            if b:
                lo, hi = b
                dates = [d for d in cal if lo <= d <= hi]
        elif scope == "range":
            try:
                fr = datetime.strptime(c.get("range_from"), "%Y-%m-%d").replace(tzinfo=KST) if c.get("range_from") else None
                to = datetime.strptime(c.get("range_to"), "%Y-%m-%d").replace(tzinfo=KST) if c.get("range_to") else None
            except (ValueError, TypeError):
                fr = to = None
            if fr and to:
                dates = [d for d in cal if fr <= d <= to]
        elif scope == "explicit":
            for iso in (c.get("dates") or []):
                if iso in cal_iso:
                    try:
                        dates.append(datetime.strptime(iso, "%Y-%m-%d").replace(tzinfo=KST))
                    except ValueError:
                        pass

        days = c.get("days", "all")

        def _wd_ok(d: datetime) -> bool:
            wd = d.weekday()
            if days == "weekdays":
                return wd <= 4
            if days == "weekend":
                return wd >= 5
            if isinstance(days, list):
                return wd in {_WD_CODE.get(x) for x in days}
            return True  # "all" 또는 미상

        sel = [d for d in dates if _wd_ok(d)]

        ex_wd = c.get("exclude_weekdays") or []
        if ex_wd == "weekend":
            ex_codes = {5, 6}
        elif ex_wd == "weekdays":
            ex_codes = {0, 1, 2, 3, 4}
        elif isinstance(ex_wd, list):
            ex_codes = {_WD_CODE.get(x) for x in ex_wd}
        else:
            ex_codes = set()
        ex_dates = set(c.get("exclude_dates") or [])
        sel = [d for d in sel if d.weekday() not in ex_codes and d.strftime("%Y-%m-%d") not in ex_dates]

        iso_set = {d.strftime("%Y-%m-%d") for d in sel if d.strftime("%Y-%m-%d") >= today_iso}
        pol = c.get("polarity")
        if pol == "unavailable":
            rejected |= iso_set
        elif pol == "preferred":
            preferred |= iso_set
        elif pol == "available":
            available |= iso_set

    rejected.discard(today_iso)  # 오늘은 발화에서 보통 미언급 — 과확장 방지
    return {"rejected": rejected, "preferred": preferred, "available": available}


def _cal_lines(today: datetime, n: int = _WINDOW) -> str:
    this_mon = today - timedelta(days=today.weekday())
    out = []
    for i in range(n):
        d = today + timedelta(days=i)
        wk = (d - this_mon).days // 7
        wtag = {0: "이번주", 1: "다음주", 2: "다다음주"}.get(wk, "")
        rel = {0: "오늘", 1: "내일", 2: "모레"}.get(i, "")
        tags = " ".join(t for t in (wtag, rel) if t)
        out.append(f"  {d.strftime('%Y-%m-%d')} ({_WD[d.weekday()]}) [{tags}]")
    return "\n".join(out)


def _build_prompt(context: str, today: datetime) -> str:
    twd = _WD[today.weekday()]
    b1 = _week_bounds(today, "this_week"); b2 = _week_bounds(today, "next_week"); b3 = _week_bounds(today, "week_after")
    return (
        f"오늘은 {today.strftime('%Y-%m-%d')} ({twd})입니다. 주는 월요일 시작.\n"
        f"- this_week(이번주) = {b1[0].strftime('%m-%d')}~{b1[1].strftime('%m-%d')}\n"
        f"- next_week(다음주/담주) = {b2[0].strftime('%m-%d')}~{b2[1].strftime('%m-%d')}\n"
        f"- week_after(다다음주) = {b3[0].strftime('%m-%d')}~{b3[1].strftime('%m-%d')}\n\n"
        f"참조 달력 (날짜는 반드시 이 목록에서 조회해서 쓰세요. 직접 계산 금지):\n{_cal_lines(today)}\n\n"
        f"대화:\n{context or '(없음)'}\n\n"
        "작업: 대화 속 '가용성 제약'을 구조화해 추출하세요. 날짜를 직접 나열하지 말고 '구조'만 — 확장은 코드가 합니다.\n\n"
        "■■ 0순위 멘탈모델: 각 날짜에 '그 사람이 나올 수 있나?'를 판단하라 ■■\n"
        "  · 나올 수 있는 날(가능/선호/좋아/콜/'~만 돼'의 그 날/'빼고'의 빼는 대상) = available 또는 preferred. 절대 unavailable 아님!\n"
        "  · 못 나오는 날(바빠/안 돼/일정/패스/'~만 가능'의 나머지) = unavailable.\n"
        "  · 헷갈리면: '토일만 시간 남아'=토일은 나올 수 있음(unavailable 아님), 나머지가 unavailable. '후반만 가능'=후반 나올 수 있음, 전반이 unavailable.\n\n"
        "■■ '여집합'과 '직접 거부'를 구분하라 ■■\n"
        "여집합(days=all + exclude)은 오직 '빼고/제외/말고' 또는 'X만 돼/가능(=X 외엔 못 옴)'이 있을 때만!\n"
        "그런 단서가 없으면 언급된 요일/날짜를 그대로 days/dates에 넣어라(절대 exclude로 뒤집지 마라).\n"
        "  · '금요일 안 돼'         → days:[\"fri\"]\n"
        "  · '금요일 빼고 다 안 돼' → days:all, exclude_weekdays:[\"fri\"]\n"
        "  · '수목금 안 돼'         → days:[\"wed\",\"thu\",\"fri\"]\n"
        "  · '06-10 못 가'          → scope:explicit, dates:[\"2026-06-10\"]\n"
        "  · '내일 안 돼'           → scope:explicit, dates:[위 달력의 '내일' ISO]\n"
        "특정 날짜·내일·모레·'6/13'·'06-10' 처럼 한 날짜를 콕 집으면 반드시 scope=explicit + dates=[달력에서 조회한 ISO]. 절대 주 전체로 퍼뜨리지 마라.\n\n"
        "각 제약(constraint) 필드:\n"
        "- polarity: \"unavailable\" | \"preferred\" | \"available\"\n"
        "- scope: \"this_week\" | \"next_week\" | \"week_after\" | \"range\" | \"explicit\"\n"
        "- range_from, range_to: scope=range일 때 YYYY-MM-DD\n"
        "- dates: scope=explicit일 때 [YYYY-MM-DD]\n"
        "- days: \"all\" | \"weekdays\" | \"weekend\" | [\"mon\",\"wed\"...]\n"
        "- exclude_weekdays: [\"sat\"] 또는 \"weekend\"/\"weekdays\"\n"
        "- exclude_dates: [YYYY-MM-DD]\n"
        "- users, reason\n\n"
        "규칙:\n"
        "1) 'X는/X요일 안 돼·못 가·패스·일정 있어'(빼고/만 없음) → unavailable, days=[그 요일들] 또는 scope=explicit,dates. scope는 '담주/다음주'면 next_week, 아니면 this_week.\n"
        "2) 'X 빼고 다 바빠/안 돼' → unavailable, scope=그 주, days=all, exclude_weekdays=[X].\n"
        "3) 'X만 돼/가능'(X 외엔 못 옴) → unavailable, days=all, exclude_weekdays=[X]. '평일만 가능'→exclude_weekdays=\"weekdays\"; '주말만 돼'→exclude_weekdays=\"weekend\".\n"
        "4) '평일/주중 빼고 다 가능' → unavailable, days=weekdays. '주말은 안 돼/패스'→days=weekend.\n"
        "5) '이번주 내내/다 바빠/다 패스/글렀어' → unavailable, scope=this_week, days=all. ('다음주'면 next_week)\n"
        "6) 'A부터 B까지 바빠' → scope=range, range_from=A, range_to=B.\n"
        "7) 선호('좋아/끌려/낫다/편해/선호/젤')는 preferred만. '다 돼/아무때나/언제든'은 제약 없음(빈 배열).\n"
        "8) 'X 빼고 다 돼/가능'(긍정) → X만 unavailable(days=[X]), 나머지 건드리지 마라.\n"
        "9) 한 발화에 거부+선호가 같이 있으면 제약을 2개로 나눠라.\n\n"
        "예: '나 다음주 토욜 빼고 다 바빠' → [{polarity:unavailable, scope:next_week, days:all, exclude_weekdays:[\"sat\"]}]\n"
        "예: '담주 화요일 패스' → [{polarity:unavailable, scope:next_week, days:[\"tue\"]}]\n"
        "예: '주말은 본가라 패스, 화요일 좋아' → [{polarity:unavailable, scope:this_week, days:weekend},{polarity:preferred, scope:this_week, days:[\"tue\"]}]\n\n"
        "제출 전 자기검증: 각 unavailable 제약에 '정말 그 사람이 그 날 못 나오나?'를 되물어라. "
        "'~만 가능/돼/좋아/남아'의 그 요일이나 '빼고'의 대상이 unavailable에 들어갔으면 잘못 — 빼라.\n\n"
        "출력 JSON만: {\"constraints\": [ ... ]}\n"
    )


async def classify_availability(context: str, now_kst: datetime | None = None) -> dict:
    """대화 context → {rejected, preferred, available} (ISO set).

    LLM/파싱 실패 시 빈 집합 반환(상위 흐름 비차단).
    """
    today = (now_kst or datetime.now(KST))
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)
    if today.tzinfo is None:
        today = today.replace(tzinfo=KST)
    try:
        raw = await call_llm(_build_prompt(context, today), provider=settings.LLM_PROVIDER_FOR_ENTITY)
        obj = _extract_json_object(raw) or {}
        return _resolve(obj.get("constraints"), today)
    except Exception:
        logger.warning("classify_availability failed", exc_info=True)
        return {"rejected": set(), "preferred": set(), "available": set()}


def to_rejected_dates(rejected: set, users: list | None = None) -> list[dict[str, Any]]:
    """rejected ISO set → 기존 rejected_dates 포맷 [{date, user, reason}]."""
    u = (users or [None])[0] if users else None
    return [{"date": d, "user": u, "reason": None} for d in sorted(rejected)]


# reflect-back 메시지 머리말 — 중복 발행 dedupe 마커로도 사용.
REFLECT_BACK_PREFIX = "📅 일정을 이렇게 이해했어요"


def _fmt_md(iso: str) -> str:
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return f"{d.month}/{d.day}({_WD[d.weekday()]})"
    except ValueError:
        return iso


def build_reflect_back(rejected: set, preferred: set | None = None, *, max_show: int = 8) -> str | None:
    """추출한 가용성 해석을 사람이 읽을 한 줄 확인 메시지로. 사소하면(거부<2) None.

    잔여 추출 오류를 '조용히 반영'하는 대신 사용자에게 보여 교정 기회를 준다(reflect-back).
    """
    rejected = sorted(rejected or [])
    preferred = sorted(preferred or [])
    if len(rejected) < 2:
        return None  # 단일 거부 등 사소한 해석은 확인 생략(노이즈 방지)
    parts = [REFLECT_BACK_PREFIX]
    shown = rejected[:max_show]
    more = len(rejected) - len(shown)
    rej_str = "·".join(_fmt_md(d) for d in shown) + (f" 외 {more}일" if more > 0 else "")
    parts.append(f" — 어려운 날: {rej_str}")
    if preferred:
        parts.append(f" / 가능: {'·'.join(_fmt_md(d) for d in preferred[:max_show])}")
    parts.append(". 제가 잘못 봤으면 편하게 알려주세요!")
    return "".join(parts)
