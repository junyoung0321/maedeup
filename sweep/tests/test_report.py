from sweep.report import percentile, aggregate, go_no_go
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
