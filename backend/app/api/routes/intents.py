"""
의도 분류 관련 API

POST /api/v1/intents/seed   - 초기 예시 데이터 삽입 (중복 스킵)
POST /api/v1/intents/classify - 단일 발화 의도 분류 테스트
GET  /api/v1/intents/examples - 저장된 예시 목록 조회
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.db.session import AsyncSessionLocal
from app.models.intent import IntentExample
from app.services.embedding import get_embedding
from app.services.intent_classifier import classify_intent

router = APIRouter(prefix="/intents", tags=["intents"])

# ──────────────────────────────────────────────────────────────
# 초기 시드 데이터 (한국어 구어체 중심)
# ──────────────────────────────────────────────────────────────
_SEED_EXAMPLES: list[tuple[str, str]] = [
    # meeting_schedule ─────────────────────────────────────────
    ("다음 주에 모이자", "meeting_schedule"),
    ("언제 볼까?", "meeting_schedule"),
    ("우리 언제 한번 봐야지", "meeting_schedule"),
    ("슬슬 모여야 하지 않음?", "meeting_schedule"),
    ("이번 주말에 만날 수 있어?", "meeting_schedule"),
    ("회식 날짜 잡자", "meeting_schedule"),
    ("언제 시간 돼?", "meeting_schedule"),
    ("다음 달에 보자", "meeting_schedule"),
    ("모임 날짜 정해요", "meeting_schedule"),
    ("이번에 한번 만나요", "meeting_schedule"),
    ("날짜 조율해볼까요?", "meeting_schedule"),
    ("다들 언제 가능해?", "meeting_schedule"),
    ("이번 주 중으로 봐요", "meeting_schedule"),
    ("오랜만에 다같이 모이자", "meeting_schedule"),
    ("정기 모임 언제 할까요?", "meeting_schedule"),
    # place_suggestion ─────────────────────────────────────────
    ("어디서 만날까?", "place_suggestion"),
    ("장소 어디로 할까요?", "place_suggestion"),
    ("맛집 추천해줘", "place_suggestion"),
    ("어디서 먹을까?", "place_suggestion"),
    ("강남쪽이 좋을 것 같아", "place_suggestion"),
    ("근처에 괜찮은 카페 있어?", "place_suggestion"),
    ("장소 정했어?", "place_suggestion"),
    ("홍대로 갈까요?", "place_suggestion"),
    ("이번엔 어디로 갈까", "place_suggestion"),
    ("좋은 식당 알아?", "place_suggestion"),
    ("분위기 좋은 곳으로 하자", "place_suggestion"),
    ("주차 되는 곳으로 해줘", "place_suggestion"),
    # general ──────────────────────────────────────────────────
    ("밥 먹었어?", "general"),
    ("오늘 뭐해?", "general"),
    ("요즘 어때?", "general"),
    ("잘 지내고 있어?", "general"),
    ("이거 봤어?", "general"),
    ("ㅋㅋㅋ 진짜?", "general"),
    ("맞아 맞아", "general"),
    ("그거 알아?", "general"),
    ("나 요즘 바빠", "general"),
    ("좀 있다 연락할게", "general"),
]


class ClassifyRequest(BaseModel):
    text: str


class AddExampleRequest(BaseModel):
    text: str
    intent: str


@router.post("/seed", summary="초기 예시 데이터 삽입")
async def seed_examples():
    """
    기본 의도 예시 데이터를 DB에 삽입합니다.
    이미 동일한 text가 존재하면 스킵합니다.
    """
    inserted, skipped = 0, 0

    async with AsyncSessionLocal() as session:
        for text, intent in _SEED_EXAMPLES:
            existing = await session.execute(
                select(IntentExample).where(IntentExample.text == text)
            )
            if existing.scalars().first():
                skipped += 1
                continue

            embedding = await get_embedding(text)
            example = IntentExample(text=text, intent=intent, embedding=embedding)
            session.add(example)
            inserted += 1

        await session.commit()

    return {
        "message": f"시드 완료: {inserted}개 삽입, {skipped}개 스킵",
        "inserted": inserted,
        "skipped": skipped,
    }


@router.post("/classify", summary="발화 의도 분류 테스트")
async def classify(req: ClassifyRequest):
    """단일 발화에 대한 의도 분류 결과를 반환합니다."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text가 비어있습니다")

    result = await classify_intent(req.text)
    return {"text": req.text, **result}


@router.post("/examples", summary="예시 직접 추가")
async def add_example(req: AddExampleRequest):
    """의도 예시를 직접 추가합니다 (틀린 분류 보정용)."""
    valid_intents = {"meeting_schedule", "place_suggestion", "general"}
    if req.intent not in valid_intents:
        raise HTTPException(
            status_code=400, detail=f"intent는 {valid_intents} 중 하나여야 합니다"
        )

    embedding = await get_embedding(req.text)

    async with AsyncSessionLocal() as session:
        example = IntentExample(
            text=req.text, intent=req.intent, embedding=embedding
        )
        session.add(example)
        await session.commit()
        await session.refresh(example)

    return {"id": example.id, "text": example.text, "intent": example.intent}


@router.get("/examples", summary="저장된 예시 목록")
async def list_examples():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(IntentExample))
        examples = result.scalars().all()

    return [
        {"id": ex.id, "text": ex.text, "intent": ex.intent}
        for ex in examples
    ]
