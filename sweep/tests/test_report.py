from sweep.report import percentile, aggregate, go_no_go, SweepReport
from sweep.transcript import RoomTranscript, Turn
from sweep.invariants import Violation


def test_percentile_nearest_rank():
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([1, 2, 3, 4], 95) == 4
    assert percentile([], 95) == 0.0


def _passing_room(rid, lat):
    t = RoomTranscript(room_id=rid, persona_keys=["host"])
    t.add_turn(Turn("host", "x", "direct_request", [{"type": "vote_card"}], lat))
    return t


def test_aggregate_counts_and_latency():
    rooms = [_passing_room(1, 2.0), _passing_room(2, 4.0)]
    rooms[1].violations.append(Violation("http_5xx", "500"))
    rep = aggregate(rooms)
    assert rep.total == 2
    assert rep.passed == 1
    assert rep.failed == 1
    assert rep.p95_latency_s == 4.0
    assert "http_5xx" in rep.violation_counts


def test_go_no_go_blocks_on_failure():
    rooms = [_passing_room(1, 2.0)]
    rooms[0].violations.append(Violation("stale_cards_after_finalize", "x"))
    rep = aggregate(rooms)
    summary = go_no_go(rep)
    assert "NO-GO" in summary


def test_go_no_go_passes_when_clean():
    rep = aggregate([_passing_room(1, 2.0), _passing_room(2, 3.0)])
    assert "GO" in go_no_go(rep) and "NO-GO" not in go_no_go(rep)


# --- GOAL 2: scenario_results in SweepReport ---

def test_aggregate_stores_scenario_results():
    rooms = [_passing_room(1, 2.0)]
    sr = {"S1": [], "S2": ["S2: 기대 vote_card, 관측 []"]}
    rep = aggregate(rooms, scenario_results=sr)
    assert rep.scenario_results == sr


def test_aggregate_scenario_results_defaults_empty():
    rooms = [_passing_room(1, 2.0)]
    rep = aggregate(rooms)
    assert rep.scenario_results == {}


def test_go_no_go_blocks_on_failing_scenario():
    """실패한 시나리오가 1개 이상이면 NO-GO + 차단 사유에 포함."""
    rooms = [_passing_room(1, 2.0)]
    sr = {"S1": [], "S2": ["S2: 기대 vote_card, 관측 []"]}
    rep = aggregate(rooms, scenario_results=sr)
    summary = go_no_go(rep)
    assert "NO-GO" in summary
    assert "정확성 시나리오" in summary
    assert "S2" in summary
    assert "FAIL" in summary


def test_go_no_go_scenario_all_pass():
    """모든 시나리오 통과 시 GO 유지."""
    rooms = [_passing_room(1, 2.0)]
    sr = {"S1": [], "S2": [], "S4": []}
    rep = aggregate(rooms, scenario_results=sr)
    summary = go_no_go(rep)
    assert "GO" in summary and "NO-GO" not in summary
    # 통과한 시나리오도 PASS로 나열되어야 한다
    assert "S1" in summary
    assert "PASS" in summary


# --- --scenarios=off (기본) 동작: 시나리오 없을 때 섹션·차단 없음 ---

def test_go_no_go_empty_scenario_results_no_section():
    """scenario_results={}이면 정확성 시나리오 섹션이 출력에 없어야 한다."""
    rooms = [_passing_room(1, 2.0)]
    rep = aggregate(rooms)  # scenario_results 미전달 → {}
    summary = go_no_go(rep)
    assert "정확성 시나리오" not in summary


def test_go_no_go_empty_scenario_results_no_blocker():
    """scenario_results={}이면 GO이고 시나리오 관련 차단 사유가 없어야 한다."""
    rooms = [_passing_room(1, 2.0)]
    rep = aggregate(rooms, scenario_results={})
    summary = go_no_go(rep)
    assert "GO" in summary and "NO-GO" not in summary
    assert "정확성 시나리오" not in summary


def test_go_no_go_nonempty_failing_scenario_has_section_and_blocker():
    """실패 시나리오가 있으면 섹션과 차단 사유 모두 존재해야 한다."""
    rooms = [_passing_room(1, 2.0)]
    sr = {"S1": ["S1: 기대 vote_card, 관측 []"]}
    rep = aggregate(rooms, scenario_results=sr)
    summary = go_no_go(rep)
    assert "NO-GO" in summary
    assert "정확성 시나리오" in summary
    assert "차단 사유" in summary
