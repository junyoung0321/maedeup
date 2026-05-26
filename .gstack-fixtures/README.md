# .gstack-fixtures — 매듭 측정 인프라 fixture

매듭 졸업 전시 (2026-06-04) 안정성 spec 의 Phase 1 측정용 fixture.
spec: `docs/superpowers/specs/2026-05-27-exhibition-stability-k1-k2-k3-design.md`

## k2-free-inputs.json

자유 입력 50개. 5 카테고리 × 10개.

### 카테고리
- 반말 (banmal) — 반말체, 비격식
- 줄임말 (jurimmal) — "ㄱㄱ", "ㅇㅋ", "ㄴㄴ" 등 한글 자모 단축
- 이모지 (emoji) — 이모지 단독 또는 혼합
- 오타 (otta) — 흔한 오타 (받침/모음 실수)
- 은어 (eono) — 신조어, 인터넷 은어

### 스키마

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | str | `k2-NNN` 형식 (NNN = 001~050) |
| `category` | str | banmal / jurimmal / emoji / otta / eono |
| `input` | str | 사용자가 채팅창에 입력할 자연어 |
| `expected_intent` | str | backend intent_classifier 가 분류해야 할 라벨 |
| `expected_slot` | dict | entity_extraction 이 추출해야 할 슬롯. `{}` 도 가능 |
| `should_trigger` | bool | AI 패널 트리거 발화가 발생해야 하는지 |

### expected_intent 라벨

backend `_SEED_EXAMPLES` (`backend/app/api/routes/intents.py`) 기준 3개 라벨:

| 라벨 | 설명 |
|---|---|
| `meeting_schedule` | 모임 날짜/시간 조율, 제안, 거부, 확정 |
| `place_suggestion` | 장소 추천, 맛집 질문, 지역 언급 |
| `general` | 잡담, 단순 호응, 비관련 대화 |

### should_trigger 기준

- `true`: 명확한 모임 제안/거부/확정/장소 질문 → stalemate_judge 또는 intent 매칭 발동 예상
- `false`: 단순 호응, 잡담, 일상 대화 → AI 패널 개입 불필요

### expected_slot 키 목록

| 키 | 설명 | 예시 값 |
|---|---|---|
| `date_hint` | 날짜 표현 | `"next week"`, `"tomorrow"`, `"this Friday"` |
| `meal_type` | 식사 타입 | `"lunch"`, `"dinner"` |
| `area` | 장소/지역 | `"강남"`, `"홍대"`, `"성수"` |
| `category` | 음식/업종 카테고리 | `"한식"`, `"카페"`, `"고기"` |
| `rejection` | 거부 표현 | `true` |

### 예시

```json
[
  {
    "id": "k2-001",
    "category": "banmal",
    "input": "야 다음주 점심 어때",
    "expected_intent": "meeting_schedule",
    "expected_slot": {"date_hint": "next week", "meal_type": "lunch"},
    "should_trigger": true
  }
]
```

### fixture 분포 요약

| 카테고리 | ID 범위 | should_trigger=true | should_trigger=false |
|---|---|---|---|
| banmal | k2-001 ~ k2-010 | 7 | 3 |
| jurimmal | k2-011 ~ k2-020 | 7 | 3 |
| emoji | k2-021 ~ k2-030 | 8 | 2 |
| otta | k2-031 ~ k2-040 | 8 | 2 |
| eono | k2-041 ~ k2-050 | 8 | 2 |
| **합계** | | **38** | **12** |

---

## k3-concurrency-scenarios.json

(Task 4 에서 작성)

## k3-onboarding-users.json

(Task 5 에서 작성)
