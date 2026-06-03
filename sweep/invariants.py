"""스펙 §5 하드 불변조건 — 위반 시 Violation 리스트를 반환하는 순수 함수들."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str


def check_frame(frame: dict) -> list[Violation]:
    """WS 인바운드 프레임에 에러/예외 신호가 있는지."""
    out: list[Violation] = []
    ftype = frame.get("type")
    if ftype == "error" or "error" in frame:
        out.append(Violation("ws_error_frame", str(frame.get("detail") or frame.get("error"))))
    if frame.get("status_code", 200) >= 500:
        out.append(Violation("http_5xx", str(frame.get("status_code"))))
    return out


def check_card_payload(card: dict) -> list[Violation]:
    """카드 payload 정합성 (스펙 §5.4)."""
    out: list[Violation] = []
    t = card.get("type")
    if t == "vote_card":
        if not card.get("time_options"):
            out.append(Violation("vote_card_no_options", "time_options 비어있음"))
    elif t == "maedeup_card":
        # 실제 payload 키: date / selected_time(=selected_slot) / date_hint (확정 날짜),
        # place / selected_place (확정 장소). confirmed_* 는 state 키지 카드 키가 아님.
        has_date = bool(
            card.get("date") or card.get("selected_time")
            or card.get("selected_slot") or card.get("date_hint")
            or card.get("confirmed_date")
        )
        if not has_date:
            out.append(Violation("maedeup_no_date", "날짜 정보 없음"))
        # 장소는 place_pending(시간만 확정된 부분 카드)이면 비어도 정상 — 위반 아님.
        if not card.get("place_pending"):
            has_place = bool(
                card.get("place") or card.get("selected_place")
                or card.get("confirmed_place")
            )
            if not has_place:
                out.append(Violation("maedeup_no_place", "장소 정보 없음"))
    elif t == "place_recommendation":
        # 실제 payload 키는 'recommendations'. (places/results 는 폴백용)
        recs = card.get("recommendations") or card.get("places") or card.get("results")
        if not recs:
            out.append(Violation("place_reco_empty", "추천 결과 없음"))
    return out


def _percentile(values: list[float], p: float) -> float:
    """nearest-rank 퍼센타일 (values 비어있으면 0)."""
    if not values:
        return 0.0
    s = sorted(values)
    k = max(1, math.ceil(p / 100.0 * len(s)))
    return s[k - 1]


def check_latency_budget(latencies_s: list[float], *, p95_budget_s: float = 8.0) -> list[Violation]:
    """트리거→카드 지연의 p95가 예산 내인지 (스펙 §5.2, K1 SLA)."""
    p95 = _percentile(latencies_s, 95)
    if p95 > p95_budget_s:
        return [Violation("latency_p95_exceeded", f"p95={p95:.2f}s > {p95_budget_s}s")]
    return []


def check_state_consistency(
    *,
    finalized: bool,
    active_reco_cards: int,
    active_vote_cards: int,
    vote_count_drop: bool = False,
    duplicate_card: bool = False,
) -> list[Violation]:
    """확정 후 카드 소거·중복·투표수 단조 (스펙 §5.5)."""
    out: list[Violation] = []
    if finalized and (active_reco_cards > 0 or active_vote_cards > 0):
        out.append(Violation(
            "stale_cards_after_finalize",
            f"확정 후 reco={active_reco_cards} vote={active_vote_cards} 잔존",
        ))
    if duplicate_card:
        out.append(Violation("duplicate_card", "동일 카드 중복 발급"))
    if vote_count_drop:
        out.append(Violation("vote_count_decreased", "투표수 감소 발생"))
    return out


def check_vote_storm(results: list[dict]) -> list[Violation]:
    """동시 투표 결과 — 에러 없음 + total_voters 비감소 (스펙 §5.5, §6)."""
    out: list[Violation] = []
    prev = -1
    for r in results:
        if "error" in r:
            out.append(Violation("vote_error", r["error"]))
            continue
        tv = r.get("total_voters", 0)
        if tv < prev:
            out.append(Violation("vote_count_decreased", f"{prev}→{tv}"))
        prev = max(prev, tv)
    return out


def check_broadcast(per_member_card_counts: list[int]) -> list[Violation]:
    """전 멤버가 동일 카드 이벤트를 받았는지 (스펙 §5.6, K3.2).

    수신 수가 멤버마다 다르면(특히 0인 멤버) 브로드캐스트 누락.
    """
    if not per_member_card_counts:
        return []
    mx = max(per_member_card_counts)
    if mx == 0:
        return []  # 애초에 카드가 없던 구간 — 누락 아님
    missed = [i for i, c in enumerate(per_member_card_counts) if c < mx]
    if missed:
        return [Violation("broadcast_missed",
                          f"멤버 {missed}가 카드 수신 부족 (수신={per_member_card_counts})")]
    return []
