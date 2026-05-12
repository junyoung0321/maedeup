"""
매듭 AI 채팅 CLI — DB/백엔드 없이 LangGraph + ML 직접 테스트

실행:
    backend\\.venv\\Scripts\\python.exe chat_cli.py
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
DATA = ROOT / "data"

# Windows 터미널 인코딩 UTF-8 강제
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
if sys.stdin.encoding != "utf-8":
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

# sys.path 설정 (backend 패키지 및 data/serving 접근)
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(DATA))

# pydantic-settings가 cwd 기준 .env 를 읽으므로 backend/로 이동
os.chdir(BACKEND)


# ── Mock DB ─────────────────────────────────────────────────────────────────
class _MockScalars:
    def all(self): return []
    def first(self): return None

class _MockResult:
    def scalars(self): return _MockScalars()

class MockDB:
    async def commit(self): pass
    async def refresh(self, obj): obj.id = None
    def add(self, obj): pass
    async def execute(self, *a, **kw): return _MockResult()


# ── Gemini 직접 intent 분류 (DB 없이) ───────────────────────────────────────
async def _gemini_classify(text: str) -> dict:
    from app.services.gemini import call_gemini
    prompt = (
        "아래 메시지의 의도를 분류하세요.\n"
        "반드시 다음 중 하나만 출력하세요: meeting_schedule, place_suggestion, general\n\n"
        f"메시지: \"{text}\"\n\n답변:"
    )
    raw = (await call_gemini(prompt)).strip().lower()
    intent = raw.split()[0] if raw else "general"
    if intent not in {"meeting_schedule", "place_suggestion", "general"}:
        intent = "general"
    return {"intent": intent, "confidence": 0.9, "method": "gemini_direct"}


TOP_K = 15  # 추천 장소 수


async def _ml_place_search_15(location, meeting_type, headcount, top_k=5):
    from app.services.ml_recommend import ml_place_search
    return await ml_place_search(location=location, meeting_type=meeting_type, headcount=headcount, top_k=TOP_K)


async def main():
    # langgraph_pipeline 임포트 후 classify_intent / ml_place_search 교체
    import app.services.langgraph_pipeline as _pipeline
    from unittest.mock import patch

    db = MockDB()
    room_id = "test"   # int 변환 불가 → room_pk=None → DB 쓰기 전체 우회
    messages: list[dict] = []
    slot_context: dict = {}
    shown_ai: set[str] = set()

    print("=" * 58)
    print("  매듭 AI 채팅 CLI  (종료: Ctrl+C)")
    print("  예시: '강남 근처에서 다음주 금요일 저녁 4명 식사 모임'")
    print("=" * 58)

    while True:
        try:
            user_input = input("\n나: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n종료")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        print("처리 중...", flush=True)

        try:
            with patch.object(_pipeline, "classify_intent", _gemini_classify), \
                 patch.object(_pipeline, "ml_place_search", _ml_place_search_15):
                result = await _pipeline.run_pipeline(
                    room_id=room_id,
                    messages=messages,
                    db=db,
                    slot_context=slot_context,
                )
        except Exception as exc:
            import traceback
            print(f"\n[오류] {exc}")
            traceback.print_exc()
            continue

        # 새 어시스턴트 메시지 파싱 (recent_messages = ["role: content", ...])
        for line in result.get("recent_messages", []):
            if line.startswith("assistant:"):
                content = line[len("assistant:"):].strip()
                if content and content not in shown_ai:
                    print(f"\nAI: {content}")
                    shown_ai.add(content)
                    messages.append({"role": "assistant", "content": content})

        # 상태 요약
        slots = result.get("slots", {})
        print(f"\n[intent={result.get('intent')} | {result.get('status')}]")
        print(f"[날짜={slots.get('date_hint')} | 장소={slots.get('place_hint')} | 인원={slots.get('headcount')} | 종류={slots.get('meeting_type')}]")

        # ML 장소 추천 결과 (pipeline은 [:5] 고정이므로 quick_recommend 직접 호출)
        if result.get("place_recommendation_payload"):
            from serving.quick_recommend import quick_recommend
            qr = quick_recommend(
                location=result.get("place_hint"),
                meeting_type=result.get("meeting_type") or "모임",
                headcount=result.get("headcount") or 4,
                top_k=TOP_K,
            )
            recs = qr.get("recommendations", [])
            print(f"\n{'─'*50}")
            print(f"  ML 장소 추천 ({len(recs)}곳, top_k={TOP_K})")
            print(f"{'─'*50}")
            for i, p in enumerate(recs, 1):
                img = "(이미지O)" if p.get("image_url") else ""
                print(f"  {i}. {p.get('place_name')} | score={p.get('score',0):.4f} | {p.get('distance_label','')} {img}")
                if p.get("reasons"):
                    print(f"     {' / '.join(p['reasons'][:3])}")
            print(f"{'─'*50}")

        # 슬롯 컨텍스트 다음 턴 전달
        slot_context = {k: result.get(k) for k in ("date_hint", "place_hint", "headcount", "meeting_type", "slot_filling_turns")}


asyncio.run(main())
