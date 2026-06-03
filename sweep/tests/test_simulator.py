import asyncio
from sweep.personas import PERSONAS
from sweep.simulator import generate_utterance


def _persona(key):
    return next(p for p in PERSONAS if p.key == key)


def test_uses_gemini_when_available():
    async def fake_gemini(prompt: str) -> str:
        return "  생성된 발화  "
    out = asyncio.run(generate_utterance(_persona("host"), ["이전 대화"], 0,
                                         gemini_call=fake_gemini))
    assert out == "생성된 발화"


def test_falls_back_on_gemini_error():
    async def boom(prompt: str) -> str:
        raise RuntimeError("rate limit")
    p = _persona("rejector")
    out = asyncio.run(generate_utterance(p, [], 1, gemini_call=boom))
    assert out == p.fallback_bank[1 % len(p.fallback_bank)]


def test_falls_back_on_empty_gemini():
    async def empty(prompt: str) -> str:
        return "   "
    p = _persona("host")
    out = asyncio.run(generate_utterance(p, [], 0, gemini_call=empty))
    assert out == p.fallback_bank[0]
