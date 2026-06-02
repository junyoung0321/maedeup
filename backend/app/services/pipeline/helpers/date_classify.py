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
import re
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

# 여집합 결정적 감지 — LLM이 다인 대화에서 'X 빼고 다 바빠'를 반전/누락하는 사각 보완.
_KWD_CODE = {"월": "mon", "화": "tue", "수": "wed", "목": "thu", "금": "fri", "토": "sat", "일": "sun"}
_SCOPE_PREFIX = [
    (r"다다음\s*주|담담\s*주", "week_after"),
    (r"다음\s*주|담주|차주", "next_week"),
    (r"이번\s*주|금주", "this_week"),
]
# 'X 빼고/제외/말고 다 (바빠/안 돼/일정/패스...)' — X만 빼고 다 불가
_COMPLEMENT_WD = re.compile(
    r"((?:월|화|수|목|금|토|일)(?:요일|욜)?(?:\s*[·,]?\s*(?:월|화|수|목|금|토|일)(?:요일|욜)?)*)\s*"
    r"(?:빼고|제외|말고)\s*(?:다|전부|모두|는)?\s*"
    r"(?:바[쁘빠]|안\s*[돼되]|일정|약속|불가|힘들|어렵|패스|못)"
)
# 'X만 (가능/돼/시간 남아...)' — X 외 전부 불가
_ONLY_WD = re.compile(
    r"((?:월|화|수|목|금|토|일)(?:요일|욜)?(?:\s*[·,]?\s*(?:월|화|수|목|금|토|일)(?:요일|욜)?)*)\s*만\s*"
    r"(?:가능|돼|되|시간|남|ok|콜|좋|비)"
)
# 평일/주말 여집합
_WEEKEND_ONLY = re.compile(r"(?:주말|토일)\s*만\s*(?:가능|돼|되|시간|남|ok|콜|좋)|(?:평일|주중)\s*(?:빼고|제외|말고)\s*다")
_WEEKDAY_ONLY = re.compile(r"(?:평일|주중)\s*만\s*(?:가능|돼|되|시간|남|ok|콜|좋)|(?:주말|토일)\s*(?:빼고|제외|말고)\s*다")
# "이름: 발화" 화자 라벨 분리 (social_recent 포맷 `{sender}: {content}`). B: 화자 귀속.
_SPEAKER_LINE = re.compile(r"^\s*([^:\n]{1,20}?)\s*:\s*(.*)$")


def _detect_complement_constraints(context: str) -> list[dict]:
    """'X 빼고 다 바빠'·'X만 가능' 여집합을 줄 단위로 결정적 추출.

    LLM이 다인 대화에서 이 패턴을 반전(X를 거부)하거나 누락하는 사각을 보완.
    명시적 주 범위(이번주/다음주/다다음주)가 있을 때만 — 범위 모호 시 LLM에 위임.
    반환: constraints(_resolve 입력). 불가(scope+all+exclude) + 예외요일 available 쌍.
    줄의 'X:' 화자 라벨을 speaker로 태그해 _resolve가 화자별로 정정/여집합을 적용한다.
    """
    out: list[dict] = []
    for line in (context or "").splitlines():
        # 화자 라벨 분리 — body(발화 본문) 기준으로 패턴 검사, speaker로 귀속.
        speaker = None
        body = line
        ms = _SPEAKER_LINE.match(line)
        if ms:
            speaker, body = (ms.group(1).strip() or None), ms.group(2)

        scope = None
        for pat, sc in _SCOPE_PREFIX:
            if re.search(pat, body):
                scope = sc
                break
        if scope is None:
            continue  # 주 범위 모호 → LLM에 맡김(잘못된 scope 방지)

        def _emit(exclude_codes):
            out.append({"polarity": "unavailable", "scope": scope, "days": "all", "exclude_weekdays": list(exclude_codes), "speaker": speaker})
            # 예외 요일은 명시적 가능 → 거부 반전 교정(같은 화자의 rejected -= available)
            out.append({"polarity": "available", "scope": scope, "days": list(exclude_codes), "speaker": speaker})

        m = _COMPLEMENT_WD.search(body) or _ONLY_WD.search(body)
        if m:
            # "토요일"의 '일'을 일요일로 오인하지 않게 'X요일' 토큰 단위로 추출.
            toks = re.findall(r"(월|화|수|목|금|토|일)(?:요일|욜)?", m.group(1))
            codes = [_KWD_CODE[t] for t in toks if t in _KWD_CODE]
            if codes:
                _emit(codes)
                continue
        if _WEEKEND_ONLY.search(body):
            out.append({"polarity": "unavailable", "scope": scope, "days": "weekdays", "speaker": speaker})
            out.append({"polarity": "available", "scope": scope, "days": "weekend", "speaker": speaker})
        elif _WEEKDAY_ONLY.search(body):
            out.append({"polarity": "unavailable", "scope": scope, "days": "weekend", "speaker": speaker})
            out.append({"polarity": "available", "scope": scope, "days": "weekdays", "speaker": speaker})
    return out


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


def _constraint_speaker(c: dict) -> str | None:
    """제약을 말한 화자 키. LLM의 users[0] 또는 detector의 speaker. 없으면 None.

    None(미상)은 단일 그룹으로 묶이므로 화자 라벨 없는 입력(eval·단일발화)은
    기존 전역 동작과 완전히 동일하다(하위호환).
    """
    u = c.get("users")
    if isinstance(u, list) and u:
        s = str(u[0]).strip()
        return s or None
    if isinstance(u, str) and u.strip():
        return u.strip()
    sp = c.get("speaker")
    if isinstance(sp, str) and sp.strip():
        return sp.strip()
    return None


def _expand_constraint(c: dict, today: datetime, cal: list, cal_iso: set, today_iso: str) -> set:
    """단일 제약(구조) → ISO 날짜 set. (polarity 무관 — 날짜 확장만)"""
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

    return {d.strftime("%Y-%m-%d") for d in sel if d.strftime("%Y-%m-%d") >= today_iso}


def _resolve(constraints: list, today: datetime, window: int = _WINDOW) -> dict:
    """구조 제약을 결정적으로 ISO 날짜 집합으로 확장(화자별).

    B(화자 귀속): 화자별로 그룹화해 'rejected −= 본인 available'을 적용한다.
    → A의 "수목금 안돼"를 B의 "수요일 돼"가 못 지운다(다화자 정정 정확도).
    반환에 rejected_by(날짜→화자 set)를 추가 — 멤버별 unavailability 귀속에 사용.
    화자 라벨이 없으면 모두 None 그룹 → 기존 전역 동작과 동일(하위호환).
    """
    cal = [today + timedelta(days=i) for i in range(window)]
    cal_iso = {d.strftime("%Y-%m-%d") for d in cal}
    today_iso = today.strftime("%Y-%m-%d")

    groups: dict[Any, list] = {}
    for c in constraints or []:
        if not isinstance(c, dict):
            continue
        groups.setdefault(_constraint_speaker(c), []).append(c)

    rejected: set[str] = set()
    preferred: set[str] = set()
    available: set[str] = set()
    rejected_by: dict[str, set] = {}

    for spk, gcons in groups.items():
        g_rej: set[str] = set()
        g_pref: set[str] = set()
        g_avail: set[str] = set()
        for c in gcons:
            iso_set = _expand_constraint(c, today, cal, cal_iso, today_iso)
            pol = c.get("polarity")
            if pol == "unavailable":
                g_rej |= iso_set
            elif pol == "preferred":
                g_pref |= iso_set
            elif pol == "available":
                g_avail |= iso_set
        g_rej.discard(today_iso)  # 오늘은 발화에서 보통 미언급 — 과확장 방지
        # 같은 화자의 명시적 '가능(available)'만 그 화자의 거부를 이긴다.
        # preferred(좋아/선호)는 빼지 않는다 — '쉬고 싶다' 오분류가 거부를 덮지 않게.
        g_rej -= g_avail
        rejected |= g_rej
        preferred |= g_pref
        available |= g_avail
        for d in g_rej:
            rejected_by.setdefault(d, set()).add(spk)

    return {"rejected": rejected, "preferred": preferred, "available": available, "rejected_by": rejected_by}


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
        "■ AI 메시지 무시: '매듭 AI'/어시스턴트가 한 말, 특히 '📅 일정을 이렇게 이해했어요 — 어려운 날: …' 같은 "
        "확인/안내 메시지는 사람의 발화가 아니므로 절대 근거로 삼지 마라. 오직 사람 참가자가 직접 말한 가용성만 판정하라.\n"
        "■ 정정 우선: 같은 사람이 앞에서 '안 된다/바쁘다'고 한 날을 뒤에서 '아 그날은 돼/가능'으로 바꾸면, "
        "더 나중·구체적인 '가능'을 따라라(그 날은 unavailable이 아니라 available/preferred).\n\n"
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
        "- users: 이 제약을 말한 사람. 대화 줄의 'X:' 화자명 그대로 [\"X\"]. 누가 말했는지 분명할 때만, 모르면 생략.\n"
        "- reason\n\n"
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
    # 결정적 여집합 detector — LLM 호출 전에 추출(LLM 실패해도 여집합은 보장).
    det = _detect_complement_constraints(context)
    try:
        raw = await call_llm(_build_prompt(context, today), provider=settings.LLM_PROVIDER_FOR_ENTITY)
        obj = _extract_json_object(raw) or {}
        llm_constraints = obj.get("constraints") or []
    except Exception:
        logger.warning("classify_availability LLM failed — detector만으로 진행", exc_info=True)
        llm_constraints = []
    # 병합: LLM + 결정적 detector. _resolve가 rejected −= available 하므로
    # detector의 '예외요일 available'이 LLM의 반전(예외요일 거부)을 교정한다.
    if det:
        logger.info("[DATE_CLASSIFY] complement detector +%d constraints", len(det))
    return _resolve(list(llm_constraints) + det, today)


def to_rejected_dates(rejected: set, rejected_by: dict | None = None) -> list[dict[str, Any]]:
    """rejected ISO set → rejected_dates 포맷 [{date, user, reason}].

    rejected_by(날짜→화자 set)가 있으면 (날짜, 화자)별로 항목을 만들어 멤버별
    unavailability 귀속이 올바르게 되도록 한다(B: 화자 귀속). 한 날짜를 여러 명이
    거부하면 여러 항목. 화자 미상이면 user=None(기존 동작 — speaker_user_id fallback).
    """
    if rejected_by:
        out: list[dict[str, Any]] = []
        for d in sorted(rejected):
            speakers = sorted(s for s in (rejected_by.get(d) or set()) if s)
            for spk in (speakers or [None]):
                out.append({"date": d, "user": spk, "reason": None})
        return out
    return [{"date": d, "user": None, "reason": None} for d in sorted(rejected)]


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
