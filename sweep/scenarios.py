"""S1~S10 다자 결정적 시나리오 + 기대 카드 assert (스펙 §7)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScriptedUtterance:
    persona_key: str
    text: str


@dataclass(frozen=True)
class Scenario:
    key: str
    description: str
    utterances: tuple[ScriptedUtterance, ...]
    trigger_reason: str
    expected_card_type: str
    must_exclude_substr: tuple[str, ...] = ()   # 옵션 라벨에 있으면 안 되는 문자열
    must_include_substr: tuple[str, ...] = ()   # assistant 메시지에 있어야 하는 문자열


def _u(k: str, t: str) -> ScriptedUtterance:
    return ScriptedUtterance(k, t)


CORE_SCENARIOS: list[Scenario] = [
    Scenario("S1", "기본 시간 투표",
             (_u("host", "다음주에 다 같이 모이자"),),
             "direct_request", "vote_card"),
    Scenario("S2", "거절 누적 — 월요일 제외",
             (_u("host", "다음주에 모이자"), _u("rejector", "월요일은 안돼")),
             "direct_request", "vote_card", must_exclude_substr=("월",)),
    Scenario("S4", "다음주 확장",
             (_u("host", "이번주에 모이자"), _u("rejector", "이번주는 다 바빠")),
             "direct_request", "vote_card", must_include_substr=("확장",)),
    Scenario("S6", "TimeBar 합의",
             (_u("host", "다들 TimeBar에서 시간 골라줘"),),
             "all_members_selected", "vote_card"),
    Scenario("S8", "다수결 fallback",
             (_u("host", "다음주 모이자"), _u("rejector", "난 평일 다 안돼"),
              _u("guest", "저도 주말만 돼요")),
             "direct_request", "vote_card", must_include_substr=("전원",)),
    Scenario("S9", "시간 단독 partial",
             (_u("host", "다음주 화요일 6시에 보자"),),
             "direct_request", "maedeup_card"),
    Scenario("S10", "결론 자동감지",
             (_u("host", "그럼 토요일 7시 강남으로 확정하자"),
              _u("terse", "ㅇㅋ"), _u("guest", "좋아요")),
             "conclusion_detected", "maedeup_card"),
]


def assert_expected(scenario: Scenario, observed_cards: list[dict],
                    assistant_text: str = "") -> list[str]:
    """기대 위반 메시지 리스트(비어있으면 통과)."""
    fails: list[str] = []
    types = [c.get("type") for c in observed_cards]
    if scenario.expected_card_type not in types:
        fails.append(f"{scenario.key}: 기대 {scenario.expected_card_type}, 관측 {types}")
        return fails  # 카드 자체가 다르면 하위 검사 무의미

    card = next(c for c in observed_cards if c.get("type") == scenario.expected_card_type)
    labels = " ".join(o.get("label", "") for o in card.get("time_options", []))
    for bad in scenario.must_exclude_substr:
        if bad in labels:
            fails.append(f"{scenario.key}: 제외돼야 할 '{bad}'가 옵션에 존재")
    for need in scenario.must_include_substr:
        if need not in assistant_text:
            fails.append(f"{scenario.key}: assistant 메시지에 '{need}' 없음")
    return fails
