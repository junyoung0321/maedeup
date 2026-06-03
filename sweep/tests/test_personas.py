import random
from sweep.personas import PERSONAS, Persona, random_personas, fallback_utterance


def test_seven_personas_defined():
    keys = {p.key for p in PERSONAS}
    assert keys == {
        "host", "lurker", "rejector", "vague_time",
        "guest", "terse", "off_topic",
    }
    for p in PERSONAS:
        assert isinstance(p, Persona)
        assert p.system_prompt.strip()
        assert len(p.fallback_bank) >= 3


def test_random_personas_always_includes_host_and_count():
    rng = random.Random(42)
    chosen = random_personas(4, rng)
    assert len(chosen) == 4
    assert any(p.key == "host" for p in chosen), "방엔 항상 추진할 host가 1명 필요"
    rng2 = random.Random(42)
    assert [p.key for p in random_personas(4, rng2)] == [p.key for p in chosen]


def test_fallback_utterance_is_deterministic_and_nonempty():
    p = next(p for p in PERSONAS if p.key == "rejector")
    u0 = fallback_utterance(p, 0)
    u1 = fallback_utterance(p, 1)
    assert u0 and u1
    assert u0 != u1
    assert fallback_utterance(p, len(p.fallback_bank)) == p.fallback_bank[0]
