from sweep.invariants import (
    Violation, check_frame, check_card_payload, check_latency_budget,
    check_state_consistency,
)


def test_error_frame_flagged():
    v = check_frame({"type": "error", "detail": "boom"})
    assert any(x.code == "ws_error_frame" for x in v)


def test_clean_frame_ok():
    assert check_frame({"type": "vote_card", "meeting_id": 1}) == []


def test_vote_card_missing_options_flagged():
    v = check_card_payload({"type": "vote_card", "time_options": []})
    assert any(x.code == "vote_card_no_options" for x in v)


def test_maedeup_card_requires_date_and_place():
    v = check_card_payload({"type": "maedeup_card", "confirmed_date": None,
                            "confirmed_place": None})
    codes = {x.code for x in v}
    assert "maedeup_no_date" in codes and "maedeup_no_place" in codes


def test_place_reco_empty_results_flagged():
    v = check_card_payload({"type": "place_recommendation", "places": []})
    assert any(x.code == "place_reco_empty" for x in v)


def test_latency_budget_p95():
    assert check_latency_budget([1.0, 2.0, 3.0, 4.0], p95_budget_s=8.0) == []
    v = check_latency_budget([1.0, 2.0, 3.0, 9.0], p95_budget_s=8.0)
    assert any(x.code == "latency_p95_exceeded" for x in v)


def test_state_consistency_recos_must_clear_after_finalize():
    v = check_state_consistency(finalized=True, active_reco_cards=2, active_vote_cards=1)
    codes = {x.code for x in v}
    assert "stale_cards_after_finalize" in codes


def test_state_consistency_vote_count_monotonic():
    v = check_state_consistency(finalized=False, active_reco_cards=0,
                                active_vote_cards=1, vote_count_drop=True)
    assert any(x.code == "vote_count_decreased" for x in v)


def test_vote_storm_results_no_error_and_monotonic():
    from sweep.invariants import check_vote_storm
    good = [{"votes": {"0": 1}, "total_voters": 1},
            {"votes": {"0": 2}, "total_voters": 2}]
    assert check_vote_storm(good) == []
    bad = [{"error": "boom"}]
    assert any(v.code == "vote_error" for v in check_vote_storm(bad))


def test_broadcast_all_members_must_match():
    from sweep.invariants import check_broadcast
    assert check_broadcast([1, 1, 1]) == []
    v = check_broadcast([1, 1, 0])
    assert any(x.code == "broadcast_missed" for x in v)
