from sweep.scenarios import CORE_SCENARIOS, Scenario, assert_expected


def test_core_scenarios_cover_minimum_seven():
    keys = {s.key for s in CORE_SCENARIOS}
    assert {"S1", "S2", "S4", "S6", "S8", "S9", "S10"} <= keys


def test_each_scenario_has_utterances_and_expected():
    for s in CORE_SCENARIOS:
        assert s.utterances, f"{s.key} 발화 없음"
        assert s.expected_card_type in {"vote_card", "maedeup_card", "place_recommendation"}


def test_assert_expected_detects_wrong_card():
    s = next(s for s in CORE_SCENARIOS if s.key == "S1")  # vote_card 기대
    fails = assert_expected(s, observed_cards=[{"type": "maedeup_card"}])
    assert fails  # 기대와 다른 카드 → 실패 메시지

    ok = assert_expected(s, observed_cards=[{"type": "vote_card",
                                             "time_options": [{"label": "x"}]}])
    assert ok == []


def test_s2_checks_excluded_day():
    s = next(s for s in CORE_SCENARIOS if s.key == "S2")
    bad = assert_expected(s, observed_cards=[{
        "type": "vote_card",
        "time_options": [{"label": "월요일 저녁", "start_at": "2026-06-08T18:00:00"}],
    }])
    assert any("월" in f for f in bad)
