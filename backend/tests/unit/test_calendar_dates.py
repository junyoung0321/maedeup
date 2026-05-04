"""
Unit tests for app.api.routes.calendar — date/slot aggregation helpers.

게스트(캘린더 미연동 멤버)는 기본 "가능"으로 카운트되고, 본인이 명시적으로
"불가능 날짜"를 토글한 경우에만 해당 날의 집계에서 제외되어야 한다.

모든 멤버 식별은 `_calendar_user_key()`(`"{id}:{name}"`) 기반 — 동일 이름 멤버가
중복 제거되거나 차단이 잘못 전파되는 것을 방지.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.api.routes.calendar import (
    KST,
    _calendar_user_key,
    _compute_dates,
    _compute_free_slots,
)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _user_key(uid: int, name: str) -> str:
    """`_calendar_user_key`와 동일한 포맷의 키를 만든다."""
    class _Stub:
        pass

    stub = _Stub()
    stub.id = uid
    stub.name = name
    return _calendar_user_key(stub)


def _kst_to_utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=KST).astimezone(ZoneInfo("UTC"))


# ---------------------------------------------------------------------------
# _compute_dates
# ---------------------------------------------------------------------------


def test_compute_dates_guest_default_available():
    """게스트는 기본적으로 '가능'으로 잡혀 count/total/available 모두에 들어가야 한다."""
    today = date(2026, 5, 1)
    busy_by_user = {_user_key(1, "Alice"): []}  # 동의자 1, 일정 없음
    unconnected_keys = [_user_key(2, "GuestBob"), _user_key(3, "GuestCarol")]

    dates = _compute_dates(busy_by_user, today, lookahead_days=2, unconnected_keys=unconnected_keys)

    iso = today.isoformat()
    info = dates[iso]
    assert info.total == 3, "동의자 1 + 게스트 2 = 3"
    assert info.count == 3, "전원 가능"
    assert set(info.available) == {"Alice", "GuestBob", "GuestCarol"}
    assert info.busy == []
    assert set(info.unconnected) == {"GuestBob", "GuestCarol"}
    assert info.blocked == []


def test_compute_dates_guest_blocked_excluded():
    """게스트가 '불가능' 토글한 날에는 available/unconnected에서 제외되고 blocked로 분류."""
    today = date(2026, 5, 1)
    next_day = today + timedelta(days=1)
    busy_by_user = {_user_key(1, "Alice"): []}
    guest_bob_key = _user_key(2, "GuestBob")
    blocked_by_date = {today.isoformat(): {guest_bob_key}}

    dates = _compute_dates(
        busy_by_user, today, lookahead_days=2,
        unconnected_keys=[guest_bob_key],
        blocked_by_date=blocked_by_date,
    )

    today_info = dates[today.isoformat()]
    assert today_info.total == 2
    assert today_info.count == 1, "GuestBob 차단 → Alice만 가능"
    assert today_info.available == ["Alice"]
    assert today_info.unconnected == []
    assert today_info.blocked == ["GuestBob"]

    # 다음 날은 차단 안 됨 → 게스트 다시 가능
    next_info = dates[next_day.isoformat()]
    assert next_info.count == 2
    assert "GuestBob" in next_info.available


def test_compute_dates_consenting_member_blocked_excluded():
    """동의자가 본인 날 차단했을 때도 blocked 분류되고 available/busy에서 빠진다."""
    today = date(2026, 5, 1)
    alice_key = _user_key(1, "Alice")
    busy_by_user = {alice_key: []}
    blocked_by_date = {today.isoformat(): {alice_key}}

    dates = _compute_dates(
        busy_by_user, today, lookahead_days=1,
        blocked_by_date=blocked_by_date,
    )

    info = dates[today.isoformat()]
    assert info.total == 1
    assert info.count == 0
    assert info.available == []
    assert info.busy == []
    assert info.blocked == ["Alice"]


def test_compute_dates_no_guests_unchanged():
    """게스트 없을 때 기존 동작과 동일해야 한다 (회귀 가드)."""
    today = date(2026, 5, 1)
    busy_by_user = {
        _user_key(1, "Alice"): [],
        _user_key(2, "Bob"): [],
    }

    dates = _compute_dates(busy_by_user, today, lookahead_days=1)

    info = dates[today.isoformat()]
    assert info.total == 2
    assert info.count == 2
    assert set(info.available) == {"Alice", "Bob"}
    assert info.unconnected == []
    assert info.blocked == []


def test_compute_dates_duplicate_guest_names_counted_separately():
    """동일 display name 게스트 두 명 → user_key 다르므로 각각 독립적으로 카운트."""
    today = date(2026, 5, 1)
    busy_by_user = {_user_key(1, "Alice"): []}
    # 동일 이름 "박지민" 게스트 2명 (id 다름)
    guest1_key = _user_key(10, "박지민")
    guest2_key = _user_key(11, "박지민")
    unconnected_keys = [guest1_key, guest2_key]

    dates = _compute_dates(busy_by_user, today, lookahead_days=1, unconnected_keys=unconnected_keys)

    info = dates[today.isoformat()]
    assert info.total == 3, "Alice + 박지민 2명 = 3"
    assert info.count == 3, "전원 기본 가능"
    # available에 박지민이 두 번 들어가야 함 (이름이 같아도 별개 멤버)
    pjm_count = sum(1 for n in info.available if n == "박지민")
    assert pjm_count == 2
    pjm_unconn = sum(1 for n in info.unconnected if n == "박지민")
    assert pjm_unconn == 2


def test_compute_dates_block_one_duplicate_name_only():
    """동일 이름 게스트 중 한 명만 차단 → 다른 한 명은 영향 없음."""
    today = date(2026, 5, 1)
    busy_by_user = {_user_key(1, "Alice"): []}
    guest1_key = _user_key(10, "박지민")
    guest2_key = _user_key(11, "박지민")
    blocked_by_date = {today.isoformat(): {guest1_key}}

    dates = _compute_dates(
        busy_by_user, today, lookahead_days=1,
        unconnected_keys=[guest1_key, guest2_key],
        blocked_by_date=blocked_by_date,
    )

    info = dates[today.isoformat()]
    assert info.total == 3
    assert info.count == 2, "박지민(10) 차단, Alice + 박지민(11) 가능"
    pjm_unconn = sum(1 for n in info.unconnected if n == "박지민")
    assert pjm_unconn == 1, "차단 안 된 박지민 한 명만 unconnected"
    pjm_blocked = sum(1 for n in info.blocked if n == "박지민")
    assert pjm_blocked == 1, "차단된 박지민 한 명만 blocked"


def test_compute_dates_same_name_consenting_and_guest_block_isolation():
    """동일 이름의 동의자와 게스트가 공존할 때 한쪽 차단이 다른 쪽으로 전파되지 않아야 한다."""
    today = date(2026, 5, 1)
    consenting_alice = _user_key(1, "Alice")
    guest_alice = _user_key(2, "Alice")
    busy_by_user = {consenting_alice: []}
    # 동의자 Alice만 차단, 게스트 Alice는 정상
    blocked_by_date = {today.isoformat(): {consenting_alice}}

    dates = _compute_dates(
        busy_by_user, today, lookahead_days=1,
        unconnected_keys=[guest_alice],
        blocked_by_date=blocked_by_date,
    )

    info = dates[today.isoformat()]
    assert info.total == 2
    assert info.count == 1, "동의자 Alice 차단 → 게스트 Alice만 가능"
    assert info.available == ["Alice"], "게스트 Alice"
    assert info.unconnected == ["Alice"], "게스트 Alice는 unconnected에 남음"
    assert info.blocked == ["Alice"], "동의자 Alice 차단"


# ---------------------------------------------------------------------------
# _compute_free_slots
# ---------------------------------------------------------------------------


def test_compute_free_slots_guest_counts_in_total():
    """시간 슬롯 추천에서 게스트도 total/available_count에 포함되어야 한다."""
    busy_by_user = {_user_key(1, "Alice"): []}
    unconnected_keys = [_user_key(2, "GuestBob")]
    time_min = _kst_to_utc(2026, 5, 1, 9)
    time_max = _kst_to_utc(2026, 5, 1, 11)

    slots = _compute_free_slots(busy_by_user, time_min, time_max, unconnected_keys=unconnected_keys)

    assert len(slots) > 0
    for slot in slots:
        assert slot.total_count == 2, "동의자 1 + 게스트 1"
        assert slot.available_count == 2
        assert slot.is_recommended is True


def test_compute_free_slots_guest_blocked_excluded():
    """게스트가 차단한 날의 슬롯에서는 available_count에서 빠진다."""
    busy_by_user = {_user_key(1, "Alice"): []}
    guest_key = _user_key(2, "GuestBob")
    target_date = date(2026, 5, 1)
    blocked_by_date = {target_date.isoformat(): {guest_key}}

    time_min = _kst_to_utc(2026, 5, 1, 9)
    time_max = _kst_to_utc(2026, 5, 1, 11)

    slots = _compute_free_slots(
        busy_by_user, time_min, time_max,
        unconnected_keys=[guest_key],
        blocked_by_date=blocked_by_date,
    )

    for slot in slots:
        assert slot.total_count == 2, "total은 변하지 않음"
        assert slot.available_count == 1, "GuestBob 차단 → Alice만"
        assert slot.is_recommended is False


def test_compute_free_slots_blocked_per_date():
    """차단은 날짜 단위 — 다른 날 슬롯에는 영향 없다."""
    busy_by_user = {_user_key(1, "Alice"): []}
    guest_key = _user_key(2, "GuestBob")
    blocked_by_date = {"2026-05-01": {guest_key}}

    # 2026-05-01 09:00 ~ 2026-05-02 11:00 (이틀 분량 슬롯 생성)
    time_min = _kst_to_utc(2026, 5, 1, 9)
    time_max = _kst_to_utc(2026, 5, 2, 11)

    slots = _compute_free_slots(
        busy_by_user, time_min, time_max,
        unconnected_keys=[guest_key],
        blocked_by_date=blocked_by_date,
    )

    found_blocked_day = False
    found_open_day = False
    for slot in slots:
        if "5월 1일" in slot.label:
            assert slot.available_count == 1
            found_blocked_day = True
        elif "5월 2일" in slot.label:
            assert slot.available_count == 2
            found_open_day = True

    assert found_blocked_day, "차단된 날 슬롯이 검출돼야 한다"
    assert found_open_day, "차단 안 된 날 슬롯이 검출돼야 한다"


def test_compute_free_slots_no_guests_unchanged():
    """게스트 없을 때 기존 동작 유지 (회귀 가드)."""
    busy_by_user = {
        _user_key(1, "Alice"): [],
        _user_key(2, "Bob"): [],
    }
    time_min = _kst_to_utc(2026, 5, 1, 9)
    time_max = _kst_to_utc(2026, 5, 1, 11)

    slots = _compute_free_slots(busy_by_user, time_min, time_max)

    assert len(slots) > 0
    for slot in slots:
        assert slot.total_count == 2
        assert slot.available_count == 2
        assert slot.is_recommended is True


def test_compute_free_slots_duplicate_guest_names_counted_separately():
    """동일 이름 게스트 두 명도 각각 카운트되어야 한다."""
    busy_by_user = {_user_key(1, "Alice"): []}
    guest1_key = _user_key(10, "박지민")
    guest2_key = _user_key(11, "박지민")

    time_min = _kst_to_utc(2026, 5, 1, 9)
    time_max = _kst_to_utc(2026, 5, 1, 11)

    slots = _compute_free_slots(
        busy_by_user, time_min, time_max,
        unconnected_keys=[guest1_key, guest2_key],
    )

    for slot in slots:
        assert slot.total_count == 3, "Alice + 박지민 2명"
        assert slot.available_count == 3
        assert slot.is_recommended is True


def test_compute_free_slots_same_name_consenting_blocked_does_not_block_guest():
    """동의자와 동일 이름의 게스트가 있을 때 동의자 차단이 게스트로 전파되지 않는다."""
    consenting_alice = _user_key(1, "Alice")
    guest_alice = _user_key(2, "Alice")
    busy_by_user = {consenting_alice: []}
    blocked_by_date = {"2026-05-01": {consenting_alice}}

    time_min = _kst_to_utc(2026, 5, 1, 9)
    time_max = _kst_to_utc(2026, 5, 1, 11)

    slots = _compute_free_slots(
        busy_by_user, time_min, time_max,
        unconnected_keys=[guest_alice],
        blocked_by_date=blocked_by_date,
    )

    for slot in slots:
        assert slot.total_count == 2
        assert slot.available_count == 1, "동의자 Alice 차단, 게스트 Alice 가능"


def test_compute_free_slots_work_hour_boundary():
    """work hour 경계: 21:30~22:00은 포함, 22:00~22:30은 제외."""
    busy_by_user = {_user_key(1, "Alice"): []}
    time_min = _kst_to_utc(2026, 5, 1, 21, 30)
    time_max = _kst_to_utc(2026, 5, 1, 22, 30)

    slots = _compute_free_slots(busy_by_user, time_min, time_max)

    # 21:30~22:00 슬롯만 있어야 함 (22:00 슬롯은 22:00 < 22 거짓이라 스킵)
    labels = [s.label for s in slots]
    assert any("9:30 ~ 10:00" in lbl for lbl in labels), f"21:30-22:00 슬롯 누락: {labels}"
    # 22:00 슬롯이 있으면 안 됨 — 22 시간이 22 < 22 거짓
    assert not any("10:00 ~ 10:30" in lbl for lbl in labels), f"22:00-22:30 슬롯 포함됨: {labels}"


def test_compute_dates_empty_membership():
    """멤버 0명 — total/count 모두 0, 필드 비어있음."""
    today = date(2026, 5, 1)

    dates = _compute_dates({}, today, lookahead_days=1)

    info = dates[today.isoformat()]
    assert info.total == 0
    assert info.count == 0
    assert info.available == []
    assert info.busy == []
    assert info.unconnected == []
    assert info.blocked == []


def test_compute_free_slots_empty_membership():
    """멤버 0명 — 추천 슬롯 빈 리스트, total 0."""
    time_min = _kst_to_utc(2026, 5, 1, 9)
    time_max = _kst_to_utc(2026, 5, 1, 11)

    slots = _compute_free_slots({}, time_min, time_max)

    # available_count == 0 인 슬롯은 추가 안 됨 → 빈 리스트
    assert slots == []


def test_compute_free_slots_adjacent_busy_windows():
    """인접한 두 busy window가 슬롯 boundary에서 정확히 끊겨도 strict overlap이 일관되게 동작."""
    user_key = _user_key(1, "Alice")
    # busy 9:00~10:00, busy 10:00~11:00 — 정확히 boundary에서 인접
    busy_periods = [
        {
            "start": _kst_to_utc(2026, 5, 1, 9, 0),
            "end": _kst_to_utc(2026, 5, 1, 10, 0),
        },
        {
            "start": _kst_to_utc(2026, 5, 1, 10, 0),
            "end": _kst_to_utc(2026, 5, 1, 11, 0),
        },
    ]
    busy_by_user = {user_key: busy_periods}

    time_min = _kst_to_utc(2026, 5, 1, 9, 0)
    time_max = _kst_to_utc(2026, 5, 1, 11, 0)

    slots = _compute_free_slots(busy_by_user, time_min, time_max)

    # 9:00~11:00 전 구간이 busy로 채워짐 → available_count > 0 인 슬롯 없어 빈 리스트
    assert slots == [], f"인접 busy window가 빈 슬롯을 만들면 안 됨: {slots}"


def test_compute_free_slots_busy_meets_slot_boundary_exact():
    """busy.end가 슬롯 시작과 정확히 같으면 그 슬롯은 가능 (strict overlap 검증)."""
    user_key = _user_key(1, "Alice")
    # busy 9:00~9:30 — 9:30~10:00 슬롯과는 겹치지 않음 (end == slot_start)
    busy_periods = [
        {
            "start": _kst_to_utc(2026, 5, 1, 9, 0),
            "end": _kst_to_utc(2026, 5, 1, 9, 30),
        },
    ]
    busy_by_user = {user_key: busy_periods}

    time_min = _kst_to_utc(2026, 5, 1, 9, 30)
    time_max = _kst_to_utc(2026, 5, 1, 10, 0)

    slots = _compute_free_slots(busy_by_user, time_min, time_max)

    # 9:30~10:00 슬롯은 가능해야 함
    assert len(slots) >= 1
    assert slots[0].available_count == 1


def test_compute_free_slots_aware_busy_period_required():
    """입력 busy period datetime은 aware여야 한다 — naive 입력 시 비교 자체가 불가능.

    실제 호출부(`_get_busy_periods`)는 항상 aware datetime만 만드므로 회귀 가드.
    """
    import pytest

    user_key = _user_key(1, "Alice")
    # naive datetime을 일부러 넣음 → 비교 시 TypeError 또는 의도와 다른 동작
    naive_busy = [
        {
            "start": datetime(2026, 5, 1, 9, 0),  # naive
            "end": datetime(2026, 5, 1, 10, 0),   # naive
        },
    ]
    busy_by_user = {user_key: naive_busy}

    time_min = _kst_to_utc(2026, 5, 1, 9, 0)
    time_max = _kst_to_utc(2026, 5, 1, 10, 0)

    # aware vs naive 비교는 TypeError. 이 테스트는 입력 계약이 깨졌을 때 침묵하지 않음을 보장.
    with pytest.raises(TypeError):
        _compute_free_slots(busy_by_user, time_min, time_max)
