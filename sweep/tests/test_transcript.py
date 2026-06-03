import json
from sweep.transcript import Turn, RoomTranscript
from sweep.invariants import Violation


def test_room_transcript_roundtrips_json():
    t = RoomTranscript(room_id=7, persona_keys=["host", "rejector"])
    t.add_turn(Turn(speaker="host", text="모이자", trigger_reason="direct_request",
                    cards=[{"type": "vote_card"}], latency_s=2.5))
    t.violations.append(Violation("ws_error_frame", "boom"))
    blob = t.to_json()
    parsed = json.loads(blob)
    assert parsed["room_id"] == 7
    assert parsed["turns"][0]["latency_s"] == 2.5
    assert parsed["violations"][0]["code"] == "ws_error_frame"


def test_passed_property_reflects_violations():
    t = RoomTranscript(room_id=1, persona_keys=["host"])
    assert t.passed is True
    t.violations.append(Violation("http_5xx", "500"))
    assert t.passed is False


def test_markdown_contains_room_and_violation():
    t = RoomTranscript(room_id=3, persona_keys=["host"])
    t.add_turn(Turn(speaker="host", text="안녕", trigger_reason=None,
                    cards=[], latency_s=None))
    t.violations.append(Violation("latency_p95_exceeded", "p95=9s"))
    md = t.to_markdown()
    assert "room 3" in md and "latency_p95_exceeded" in md
