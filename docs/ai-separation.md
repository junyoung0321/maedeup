<!-- /autoplan restore point: /c/Users/cyun0/.gstack/projects/junyoung0321-maedeup/feature-ai-improvements-autoplan-restore-20260420-120916.md -->
# AI 분리 구조 설계: Private-by-default + 명시적 공유

> 상태: Draft · 2026-04-20 · 작성: 김창윤
> 대상 브랜치: `feature/ai-improvements`
> 관련: `backend/app/services/langgraph_pipeline.py`, `backend/app/api/ws/agent.py`, `frontend/src/components/meeting/AiAssistantPane.tsx`

---

## 1. 배경 & 문제 (Phase 1 CEO 재프레이밍 반영)

### 1.1 장기 비전: AI는 조율 오퍼레이터

**AI의 역할은 '그룹 채팅의 두 번째 말동무'가 아니다.** 모임 조율에 필요한 신호(일정·장소·인원·결정)를 추출해 구조화된 카드·투표로 만드는 **코디네이터(조정자)**다. Slack AI/Discord/카카오가 공통적으로 가는 방향 — AI는 라이브 대화가 아니라 요약·제안·액션 형태로 기존 화면에 녹아든다.

### 1.2 이번 작업 범위: 프라이버시 가드레일

조율 오퍼레이터로 가기 전에 **현재 구조의 프라이버시 누출을 먼저 막는다.** 본 작업은 UI/출력 스타일 변경이 아니라 **인프라 레벨 분리**가 목표. AI 출력 형태가 대화형→요약형으로 바뀌는 건 별도 후속 PR.

### 1.3 현재 AI 패널(`/ws/agent/{room_id}`)의 문제

- Redis 채널: `agent:{room_id}` 하나
- 같은 방의 유저 A가 AI에게 물은 내용·응답이 **B, C에게도 실시간으로 전달**됨
- `ChatMessage.pane_type=agent` 레코드에 `user_id`가 없어 "누가 물었는지" 구분 불가
- `slot_context`는 WebSocket 연결별(= 유저별)로 유지되지만, 결과 메시지·카드는 모두 공유됨

### 1.4 이로 인한 문제

| 문제 | 예시 |
|---|---|
| **개인정보 노출** | A가 "나 금요일 약속 있어서 빠질게"를 AI에 물음 → B, C에게도 보임 |
| **동시 요청 혼선** | A는 "일정 추천", B는 "장소 추천"을 동시에 → DB의 `recent_messages`가 섞여 파이프라인 혼란 |
| **기획 원안과 불일치** | 원래 2단계 하이브리드 분리형 AI 구조를 목표로 했으나 현재는 완전 공용 |

---

## 2. 결정사항 (alignment 완료)

### 2.1 UX 모델: Private-by-default + 응답별 공유

- **기본값: 모든 개인 AI 대화는 본인만 봄.** 별도 모드 토글 UI 없음 → 유저는 "혼자 AI랑 대화한다"는 단일 멘탈 모델만 가짐.
- **공유 버튼**: 각 AI 응답(카드 + 일반 텍스트) 옆에 🌐 공유 버튼. 클릭 시 그 응답이 공용 영역에 삽입됨.
- **자동 트리거** (교착 감지 → 투표·장소 카드)는 처음부터 공용. 룸 전체 이벤트니까.

### 2.2 시각 구분

AI 패널 타임라인은 한 공간에 개인/공용을 섞어서 표시한다. 구분은 **색 + 라벨**로:

| 메시지 종류 | 시각 | 라벨 |
|---|---|---|
| 개인 AI 응답 (본인만 봄) | 기본 (중립) | 없음 |
| 자동 트리거 / 시스템 공용 응답 | 기본 또는 약간 강조 | `AI` |
| 유저가 공유한 응답 | **다른 색 (하이라이트)** | `OO님 공유` 배지 |

### 2.3 동시성

- 개인 요청: 유저별 채널·slot_context → 충돌 0
- 공용 요청(자동 트리거): 기존 `_AUTO_TRIGGER_DEBOUNCE_SECONDS=60` 유지

---

## 3. 데이터 모델 변경

### 3.1 `ChatMessage` 확장

```python
# backend/app/models/chat.py
class Visibility(str, Enum):
    private = "private"   # owner만
    shared = "shared"     # room 전체

class ChatMessage(SQLModel, table=True):
    # ... 기존 필드 유지
    user_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        nullable=True,  # legacy/system은 NULL
    )
    visibility: str = Field(
        sa_column=sa.Column(sa.String(16), index=True, nullable=False, server_default="shared"),
    )
    shared_from_id: Optional[int] = Field(
        default=None,
        foreign_key="chat_messages.id",
        index=True,
        nullable=True,  # 공유 시 원본 메시지 id 참조
    )
```

- `user_id`: 메시지 소유자. 개인 AI 응답/질문은 해당 유저 id. `NULL`은 "레거시 또는 시스템 공용".
- `visibility`:
  - `private` → 본인만 조회 가능
  - `shared` → 룸 전체 조회 가능
- `shared_from_id`: 공유된 메시지가 어떤 개인 메시지에서 파생됐는지 추적 (공유 복제 모델, 아래 4.3 참고)

### 3.2 Alembic 마이그레이션

- idempotent하게 (CLAUDE.md 컨벤션: `inspector.has_column` 체크)
- `ChatMessage.user_id`, `visibility`, `shared_from_id` 컬럼 추가
- **기존 pane_type=agent 레코드**:
  - `user_id` = `NULL`
  - `visibility` = `shared`
  - `shared_from_id` = `NULL`
  - 이유: 이미 전원에게 브로드캐스트된 상태라 사실관계상 `shared`. `sender` 필드로 역추적 가능하나 unmatched 케이스 많아 비신뢰. `NULL`을 "레거시·시스템 공용"으로 단순화.
- `pane_type=social` 레코드는 기존 컨벤션 유지 (룸 채팅은 원래 공용)

---

## 4. WebSocket 채널 구조

### 4.1 채널 분리

| 채널 | 용도 | 구독자 |
|---|---|---|
| `agent:{room_id}` | 공용 이벤트 (자동 트리거, 유저가 공유한 메시지) | 룸 전원 |
| `agent:{room_id}:user:{user_id}` | 개인 AI 대화 (본인 질문·응답) | 해당 유저만 |

### 4.2 엔드포인트

```
GET /ws/agent/{room_id}?token=...
```

- 기존 경로 유지. 서버가 token에서 `user_id` 꺼내 **두 채널 모두 subscribe**:
  - `agent:{room_id}` (공용 수신)
  - `agent:{room_id}:user:{user_id}` (개인 수신)
- 클라이언트는 채널 구분 신경 안 씀. 서버가 합쳐서 내려줌.

### 4.3 Publish 경로

| 이벤트 | 발행 채널 |
|---|---|
| 유저가 AI에 질문 → AI 응답 | `agent:{room}:user:{user_id}` (개인) |
| 자동 트리거 → 교착 감지 → 응답·카드 | `agent:{room}` (공용) |
| 유저가 "공유" 버튼 클릭 (텍스트) | 새 메시지 **복제** (content/role 복사) → `agent:{room}` 발행 |
| 유저가 "공유" 버튼 클릭 (카드) | 새 메시지에 `vote_id`/`place_id` 등 **참조 계승** (content 복제 X) → `agent:{room}` 발행 |

**공유 모델: 하이브리드 (텍스트=복제 / 카드=참조)** — Phase 1 리뷰 반영

| 메시지 유형 | 공유 방식 | 이유 |
|---|---|---|
| 일반 텍스트 AI 응답 | **복제** (content 전체 복사) | 캡처·스냅샷 의미 — "AI가 이렇게 말했었음" 보존. 원본 수정돼도 공유본 불변. |
| 투표 카드 | **참조** (`vote_id` 계승) | 원본·공유본 모두 같은 Vote 레코드 조회 → 투표 상태 자동 동기화. UI 비일관 방지. |
| 장소 추천 카드 | **참조** (`place_id` 계승) | 장소 메타는 변경 없음, 참조로 충분. |
| 매듭 카드 | **참조** (`maedeup_id` 계승) | 확정/취소 상태 변경 시 원본·공유본 모두 반영. |

**공유 메시지 공통 필드:**
- `shared_from_id`: 원본 ChatMessage id (감사용)
- `shared_by_user_id`: 공유자 id (= `user_id`)
- `visibility`: `shared`

**중복 공유 방지 — 앱 레벨 멱등성** (§9.1 변경):
- DB UNIQUE 제약 제거 (Phase 1에서 "product rule을 DB 레벨에 올리는 건 잘못된 레이어" 지적)
- 대신 공유 API 엔드포인트에서 `SELECT WHERE shared_from_id = ? LIMIT 1` 먼저 조회 후 기존 있으면 해당 id 반환
- 프론트는 `is_shared=true` 플래그 보고 버튼 비활성화
- 효과 동일, 향후 "edit & re-share" 확장 여지 남김

### 4.4 slot_context 격리

현재 `slot_context`는 WebSocket 연결 수명 동안만 유지 (process 메모리).

- 개인 모드: 그대로 연결별 = 유저별로 유지. 충돌 없음.
- 공용 모드(자동 트리거): 룸 레벨 slot_context가 필요하다면 **Redis hash**로 이관 검토. 현재는 자동 트리거만 공용이라 slot_context가 크게 필요 없음 → 우선 개인별만 유지하고, 공용 필요 시 후속 작업.

---

## 5. 파이프라인 흐름

### 5.1 개인 요청 (기본)

```
유저 A 메시지 → WS receive
  → user_id=A로 ChatMessage 저장 (visibility=private, user_id=A)
  → recent_messages 조회 시 where user_id=A AND visibility='private' OR visibility='shared'
  → run_pipeline 실행
  → 응답 메시지도 visibility=private, user_id=A로 저장
  → agent:{room}:user:A 로만 publish
```

**핵심**: 개인 모드 파이프라인은 `recent_messages`를 **본인 개인 메시지 + 공용 메시지만** 가져온다. 다른 유저의 개인 메시지는 보지 않음.

### 5.2 자동 트리거 (공용)

```
social 채팅 intent 감지 → ai_auto_trigger 발행
  → run_pipeline (user_id=NULL, visibility=shared)
  → 응답 카드/메시지는 visibility=shared로 저장
  → agent:{room} 로 publish (룸 전원 수신)
```

### 5.3 공유 액션

```
POST /api/v1/chat/messages/{id}/share
  → 원본 메시지 조회 (owner == 요청자 검증)
  → 새 메시지 INSERT: user_id=요청자, visibility=shared, shared_from_id=원본id, role/content 복사
  → agent:{room} 로 새 메시지 publish
```

---

## 6. 프론트엔드 UI

### 6.1 AiAssistantPane 변경 (Phase 2 Design Review 반영)

**공유 버튼 (§2.3 decisions 반영):**
- **항상 표시** (호버 전용 X). 메시지 버블 **아래 footer row**에 저강도 배치
- `visibility=private` 메시지에만 노출
- `is_shared=true` 플래그 시 `공유됨` 비활성 상태 (숨기지 X)
- 최소 44×44 tap target. 키보드 focus ring 필수
- 클릭 → 공유 API → 낙관적 업데이트
  - 공유 중: 버튼 자리 스피너
  - 실패: 토스트 + 롤백

**메시지 버블 스타일 — Triple-code:**
| 타입 | 배경 | 배지 + 아이콘 | Accent rail |
|---|---|---|---|
| `visibility=private` | 기본 (중립) | 없음 | 없음 |
| `visibility=shared` + `user_id=NULL` (시스템 공용) | 기본 | `AI` | 없음 |
| `visibility=shared` + `user_id=self` (내가 공유) | 약간 강조 | `🌐 내가 공유 · HH:mm` | **좌측 3px bar** |
| `visibility=shared` + `user_id=other` (타인 공유) | 다른 배경색 | `🌐 OO님이 공유 · HH:mm` | **좌측 3px bar (다른 색)** |

색맹 내성: 아이콘(🌐) + accent rail로 색에 의존하지 않음.

**긴 메시지 처리:**
- `overflow-wrap: anywhere`
- 공유 버튼은 버블 아래 footer에 있으므로 텍스트와 충돌 없음

**원본 삭제된 공유 메시지:**
- 공유 스냅샷 자체는 유지 (shared 복제본은 독립)
- 카드(참조형)의 경우 원본 `vote_id` 유효 여부 조회 → 없으면 `[원본 삭제됨]` 메타 표시
- 카드 content 표시는 shared 레코드에 캐시된 snapshot 사용

**공유 버튼 카드(투표·장소·매듭)에도 동일 적용:**
- 카드 footer에 공유 버튼
- 공유 시 `vote_id`/`place_id` 참조 계승 (content 복제 X — §4.3 hybrid)

### 6.2 `useAgentWebSocket` 훅

- 서버가 채널 분리를 숨겨주므로 훅 API는 그대로
- 단, 메시지 배열 element에 `visibility`, `user_id`, `sender` 필드를 전달받도록 타입 확장

---

## 7. 마이그레이션 전략

### 7.1 스키마

Alembic revision 1개. idempotent:

```python
def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("chat_messages")]
    if "user_id" not in cols:
        op.add_column("chat_messages", sa.Column("user_id", sa.Integer, nullable=True, index=True))
        op.create_foreign_key(None, "chat_messages", "users", ["user_id"], ["id"])
    if "visibility" not in cols:
        op.add_column(
            "chat_messages",
            sa.Column("visibility", sa.String(16), nullable=False, server_default="shared", index=True),
        )
    if "shared_from_id" not in cols:
        op.add_column("chat_messages", sa.Column("shared_from_id", sa.Integer, nullable=True, index=True))
        op.create_foreign_key(None, "chat_messages", "chat_messages", ["shared_from_id"], ["id"])
```

### 7.2 기존 데이터

- `pane_type=agent`: 전부 `visibility=shared, user_id=NULL` (server_default 덕에 자동)
- `pane_type=social`: 영향 없음 (visibility는 `shared` default)

### 7.3 롤백 전략

- Alembic downgrade로 컬럼 drop
- 프론트 코드는 `visibility` 없으면 전부 shared로 취급하는 fallback 두면 롤백 중에도 동작 유지

---

## 8. 구현 단계 (6-step Hybrid — Phase 1 반영)

| 순서 | 작업 | 파일 |
|---|---|---|
| 1 | DB 모델 + Alembic 마이그레이션 (`user_id`, `visibility`, `shared_from_id`, `shared_by_user_id` 컬럼 추가. **UNIQUE 제약 없음**) | `backend/app/models/chat.py`, `backend/alembic/versions/` |
| 2 | WS 채널 분리 + publish 경로 분기 | `backend/app/api/ws/agent.py`, `backend/app/api/ws/manager.py` |
| 3 | 파이프라인 `recent_messages` 쿼리 필터 + LLM 컨텍스트 필터링 단위 테스트 | `backend/app/services/langgraph_pipeline.py`, `backend/tests/` |
| 4 | 공유 API 엔드포인트 (앱 레벨 멱등성 체크 포함) | `backend/app/api/routes/chat.py` (`POST /messages/{id}/share`) |
| 5 | `Vote`/`Place`/`Maedeup` 모델 확인 + 카드 참조 공유 로직 (`vote_id` 등 계승) | `backend/app/models/*.py`, 공유 API |
| 6 | 프론트: 공유 버튼 + `is_shared` 비활성화 + 스타일 분기 + 훅 타입 확장 + 수동 QA (2유저 세션) | `AiAssistantPane.tsx`, `useAgentWebSocket.ts`, 카드 컴포넌트들 |

**Follow-up PRs (이번 범위 밖):**
- Redis slot_context 이관 — WS 재연결 내구성. 시연에서 거의 안 만나는 시나리오.
- AI 출력 스타일 재편 — 대화형 → 요약·제안형. 본 작업과 독립적으로 진행 가능.
- 재공유 / edit-and-reshare — 현 앱 레벨 멱등성 덕에 향후 확장 가능.

---

## 9. 추가 요구사항 (스코프 내)

초기 설계에서 오픈 이슈로 분류했던 항목을 본 작업 범위에 포함한다.

### 9.1 중복 공유 방지 (Phase 1 반영 — 레이어 변경)
- ~~DB UNIQUE 제약~~ → **앱 레벨 멱등성**으로 변경
  - Phase 1 지적: "product rule을 DB 레벨로 올리는 건 잘못된 레이어 — 향후 edit-and-reshare 확장 차단"
- 공유 API에서 `SELECT WHERE shared_from_id = ? LIMIT 1` 선행 조회 → 기존 shared 있으면 해당 id 반환 (삽입 안 함)
- 프론트: `is_shared=true` 플래그 응답 받아 버튼 비활성화
- 효과 동일, 확장 여지 보존

### 9.2 공유된 카드의 상호작용 동기화
- **투표 카드**: 기존 `vote_id`를 참조 방식으로 공유. 복제하지 않음.
  - `shared_from_id`는 원본 ChatMessage를 가리키지만, 카드의 `vote_id`는 그대로 계승 → 원본·공유본 양쪽에서 투표 시 같은 `Vote` 레코드로 집계
  - 프론트는 `vote_id` 기준으로 상태 동기화
- **장소 추천 카드**: 정적 페이로드. 참조·복제 구분 불필요.
- **매듭 카드**: 참조. 상태 변경(확정/취소) 시 원본·공유본 모두 갱신.
- 구현 위치: `backend/app/models/vote.py` 확인 후 payload 직렬화 로직 공유. 프론트는 `vote_id` 기반 구독으로 통일.

### 9.3 slot_context Redis 이관 — **이번 범위 제외 (Follow-up PR)**

Phase 1 리뷰: "premature — 캐시 일관성 문제 추가, 10분 시연에선 만날 확률 낮음"
- 이번 PR: 현행 in-memory dict 유지 (WS 연결 수명)
- Follow-up: Redis hash로 이관 — 서버 재시작 / WS 재연결 내구성
- 긴급도: 낮음. 시연 시나리오에선 WS 유지 안정적.

### 9.4 LLM 컨텍스트 필터링 — **타입 레벨 강제 (Phase 3 반영)**

Phase 3 리뷰 결과: "add .where() 정책은 하나만 잊어도 유출" → 타입 레벨 강제로 업그레이드.

**구현:**
1. 새 파일 `backend/app/repositories/messages.py`:
   ```python
   from dataclasses import dataclass
   from sqlalchemy import and_, or_, select
   from sqlmodel.ext.asyncio.session import AsyncSession

   @dataclass(frozen=True)
   class AgentContextMessages:
       """run_pipeline이 받을 수 있는 유일한 메시지 컨테이너 (branded type)."""
       messages: list[ChatMessage]
       viewer_user_id: int | None  # None = shared-only (auto-trigger path)

   class MessageReader:
       @staticmethod
       async def load_agent_context(
           session: AsyncSession,
           room_id: int,
           viewer_user_id: int | None,
           limit: int = 20,
       ) -> AgentContextMessages:
           q = (
               select(ChatMessage)
               .where(ChatMessage.room_id == room_id)
               .where(ChatMessage.pane_type == PaneType.agent)
           )
           if viewer_user_id is None:
               q = q.where(ChatMessage.visibility == "shared")
           else:
               q = q.where(
                   or_(
                       ChatMessage.visibility == "shared",
                       and_(
                           ChatMessage.visibility == "private",
                           ChatMessage.user_id == viewer_user_id,
                       ),
                   )
               )
           q = q.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit)
           result = await session.execute(q)
           rows = list(reversed(result.scalars().all()))
           return AgentContextMessages(messages=rows, viewer_user_id=viewer_user_id)
   ```

2. `run_pipeline` 시그니처 변경:
   ```python
   async def run_pipeline(
       room_id: str,
       context: AgentContextMessages,  # branded type — list[ChatMessage] 받지 않음
       db: AsyncSession,
       slot_context: dict | None = None,
   ) -> ...:
   ```

3. `agent.py`의 3 call site (280, 406, 547)를 모두 `MessageReader.load_agent_context`로 교체.

4. CI lint 규칙 (pytest AST scan 또는 grep):
   - `backend/app/` 하위 파일 중 `backend/app/repositories/messages.py`를 제외한 모든 파일에서 `select(ChatMessage)` 직접 사용 금지 → 빌드 실패
   - 신규 엔드포인트 작성자는 자동으로 `MessageReader`를 쓰게 됨

**테스트 매트릭스 (§3.4와 연계):** T1, T2, T3, T4, T7. 최소 5개.

**이 필터/타입 구조 누락 시 개인정보 분리 효과 전체가 무너짐 → PR 리뷰 절대 체크포인트.**

---

## 10. 승인 포인트

- [ ] 위 설계로 진행 동의 — 김창윤
- [ ] 8번 단계 순서대로 구현 시작

---

## 11. /autoplan 리뷰 결과

### Phase 1 — CEO Review (Strategy & Scope)

#### 1.1 Dual Voices

**CODEX SAYS (CEO — strategy challenge):**

1. Weakest premise: "privacy leak is the main problem." Critical. Real failure is that AI pane is treated as a second chat stream, not a coordination operator. Fix: reframe around coordination signal extraction with privacy guardrails.
2. Wrong problem definition. Critical. Slack AI/Discord/Kakao all converge on summaries/recaps in existing surfaces, not hidden private AI. Current plan keeps the noisy architecture, just hidden.
3. Panel-split UX dismissed too quickly. High. The frontend already splits across AiAssistantPane vs InfoPane cards — split is not extra complexity.
4. Competitive risk under-modeled. High. No wedge defined. Could become a worse ChatGPT sidecar with extra taps.
5. Scope decisions age badly. High. `shared_from_id` UNIQUE blocks re-share/versioning; share-as-copy causes card divergence; Redis slot_context premature.
6. 9-step scope too big for mid-cycle grad MVP. Medium. Reduce to 4 steps; rest follow-up.

**CLAUDE SUBAGENT (CEO — strategic independence):**

1. Wrong problem framing. High. Real problem is "AI is noisy in group chat", not secrecy. Fix: drop `visibility` column — use `user_id IS NULL` as shared signal. Redundant two-state enum.
2. Unstated premise "users want to share." High. No demand evidence. Share button may be dead UI. Fix: instrument a private-only version for a week; kill feature if <0.3 clicks/session.
3. 6-month regrets. Critical: `shared_from_id` UNIQUE (wrong layer for product rule). High: share=copy contradicts §9.2 vote reference model — two consistency models in one table. Medium: no mode toggle throws away "compose shared" affordance. Medium: Redis slot_context adds cache coherence problem for benefit not hit in demo.
4. Dismissed alt re-examined. Medium. Toggle above input (one-shot flag) is zero extra mental model + unlocks "ask the group" future.
5. Forward-compat risk. High. Multi-room AI memory blocked by `slot_context:{room}:{user}` keys. Cross-user Q&A blocked by share-copy. AI-initiated DMs blocked (no room channel shape).
6. Scope overscoped. High. Step 5 underspecified (admits vote.py not examined). Cut to 4 steps; 3+ tests for privacy (not 1).

#### 1.2 CEO Consensus Table

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════════════════
  Dimension                                Claude    Codex   Consensus
  ──────────────────────────────────────── ────────  ──────  ─────────
  1. Premise valid (privacy = core issue)?  NO       NO      CONFIRMED-REFRAME
  2. Right problem being solved?            NO       NO      CONFIRMED-REFRAME
  3. Scope calibration (9 steps) correct?   NO       NO      CONFIRMED-CUT
  4. share=copy model sound?                NO       NO      CONFIRMED-CHANGE
  5. No-toggle UX decision sound?           NO       NO      CONFIRMED-RECONSIDER
  6. 6-month trajectory sound?              NO       NO      CONFIRMED-CHANGE
═══════════════════════════════════════════════════════════════════════════
6/6 DIMENSIONS — both models recommend significant rework.
This is a high-confidence USER CHALLENGE signal.
```

#### 1.3 Existing Code Leverage Map

| Sub-problem | Existing code | Delta |
|---|---|---|
| ChatMessage with user_id | `backend/app/models/chat.py` (no user_id currently) | Add column |
| Room membership check | `backend/app/api/ws/agent.py:135-149` | Reuse |
| Redis pub/sub | `agent.py:26-44`, `_publish_agent_message` | Reuse + channel fork |
| WS connection manager | `backend/app/api/ws/manager.py` | Reuse as-is |
| slot_context | `agent.py:171-186` (in-memory dict per conn) | Keep in-memory (defer Redis) |
| Pipeline recent_messages filter | `agent.py:278-287, 406-413, 546-554` | Add `.where(visibility/user_id)` |

#### 1.4 NOT in scope (deferred to follow-up PRs)

- Redis slot_context migration (§9.3) — premature; in-memory works for demo
- Vote card `vote_id` sync on share (§9.2) — requires vote model analysis, separate PR
- `shared_from_id` UNIQUE constraint (§9.1) — blocks re-share/versioning; use app-level idempotency
- Share=copy model (§4.3) — consider reference model instead (flagged for redesign)

#### 1.5 Dream-state Delta

- CURRENT: AI panel broadcasts all interactions to room
- THIS PLAN: private-by-default + manual share
- 12-MONTH IDEAL: AI as coordination operator — asks private clarifying questions, posts structured group decisions (not conversation), all surfaces (social/AI) share a single "decisions feed". The current plan doesn't preclude this, but doesn't advance it either.

### Phase 2 — Design Review (UI scope)

#### 2.1 Dual Voices

**CODEX SAYS (design — UX challenge):**
1. Fatal: hover-only share button broken on touch. Always-visible trailing action slot, min 44×44 tap target, keyboard focus.
2. High: color+badge not enough for colorblind/scan. Triple-code — badge text + share icon/globe + left border.
3. Medium-High: one timeline OK but needs sticky micro-headers ("내 AI 대화" / "공유됨") to prevent scan fatigue.
4. High: missing states: loading spinner, error toast+reset, double-click → `공유됨` disabled, long-message clamp, orphan snapshot with "원본 삭제됨" meta.
5. High: info scent weak — need new/my/others distinction, timestamp on shared badge, subtle entrance highlight for newly arrived shared.

**CLAUDE SUBAGENT (design — independent review):**
1. Critical: hover-only fatal. Always-visible ghost icon at 60% opacity, or persistent footer row under each bubble.
2. Critical: affordance must be touch-discoverable. `@media (hover: none)` fallback.
3. High: info hierarchy risk — `meetingSummary`/maedeup cards currently own "eye magnet" role. Adding 4th lane dilutes. Fix: left accent rail (3px bar) + badge in sender slot, not second visual channel.
4. Critical: missing states — `isSharing[msg.id]` map, 409/500 revert, `is_shared` flag muting, footer-row button placement (not overlay), orphan "원본 삭제됨" footnote.
5. Medium: color-only fails deuteranopia — badge needs 🌐/↗ glyph + dashed/inset border (shape redundancy).
6. Medium: no hard divider (breaks chat metaphor). Annotate badge with verb ("OO님이 모두에게 공유") + accent rail.

#### 2.2 Design Consensus Table

```
DESIGN DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════════════════
  Dimension                                Claude    Codex   Consensus
  ──────────────────────────────────────── ────────  ──────  ─────────
  1. Hover-only share button acceptable?   NO        NO      CONFIRMED-FIX
  2. Color-only visual enough for a11y?    NO        NO      CONFIRMED-FIX
  3. Missing states (spinner/err/etc) OK?  NO        NO      CONFIRMED-FIX
  4. Info hierarchy preserved?             NO        NO      CONFIRMED-FIX
  5. Timeline mixing strategy?             NO DIV    DIV     DISAGREE (taste)
  6. Info scent (new/my/others) clear?     PARTIAL   NO      CONFIRMED-FIX
═══════════════════════════════════════════════════════════════════════════
5/6 CONFIRMED fixes. 1 taste decision (timeline dividers vs accent rail).
```

#### 2.3 Auto-decided Design Fixes (plan updated)

1. **공유 버튼은 항상 표시** (hover-only 삭제). 저강도 아이콘 기본 → hover/focus 시 강조. 모바일 대응 필수. 44×44 tap target. 키보드 focus state.
2. **공유 메시지 시각 구분: Triple-code**
   - (a) 배지 텍스트: `OO님이 공유` / `내가 공유`
   - (b) 아이콘: 🌐 또는 ↗ (색맹 내성)
   - (c) 좌측 accent rail (3px bar) 또는 inset border
3. **상태별 UI:**
   - 공유 중: 해당 메시지 버튼 자리 스피너
   - 공유 실패: 토스트 + 버튼 리셋 + 낙관적 삽입 롤백
   - 이미 공유됨(`is_shared=true`): 버튼을 `공유됨` 비활성 상태로 교체 (숨기지 않음 — 멘탈 모델 유지)
   - 긴 메시지: 버튼을 버블 **아래 footer row**에 배치 (오버레이 X). `overflow-wrap: anywhere`
   - 원본 삭제: 공유 스냅샷은 보존, `[원본 삭제됨]` 메타 표시
4. **공유 주체 구분:** `내가 공유` vs `OO님이 공유` 별개 스타일. 배지에 공유 시각 포함.
5. **버튼 위치:** message bubble 아래 footer row (충돌 방지).

#### 2.4 Taste Decision (Final Gate로 보류)

**Timeline 구분 방식:** Codex는 sticky micro-divider 권고 ("내 AI 대화" / "공유됨"), Claude는 divider 없이 accent rail + 배지만 권고 (chat metaphor 유지). → Final gate에서 사용자 선택.

### Phase 3 — Eng Review (Architecture & Security)

#### 3.1 Dual Voices

**CLAUDE SUBAGENT (eng — independent review):**
1. **High** WS channel split: Redis `pubsub.subscribe(*channels)`는 legitimate primitive. 두 task 말고 한 pubsub에 두 채널 구독. 단, 채널 간 메시지 순서 보장 없음 → 프론트가 `created_at DESC`로 서버에서 정렬해야 함.
2. **High** Share TOCTOU: READ COMMITTED에서 "SELECT-then-INSERT" 동시 요청 시 2개 row 생성 가능. **Fix: PG advisory lock** (`SELECT pg_advisory_xact_lock(:shared_from_id)`). edit-and-reshare 확장성 유지하면서 원자성 확보.
3. **Critical** LLM 필터 강제성: 현재 3+ call site에 `.where()` 붙이는 구조는 future 엔드포인트가 하나만 잊어도 유출. **Fix: `backend/app/repositories/messages.py`에 `MessageReader.for_user(user_id)` 헬퍼**, `run_pipeline`이 branded 타입만 받도록, CI lint로 raw `select(ChatMessage)` 금지.
4. **High** Auto-trigger ownership: `_process_auto_triggers`가 연결별이라 N 유저 = N 파이프라인 실행(pre-existing bug). **Fix: Redis lock `SET NX nx_autotrigger:{room}` — 승자만 실행**. slot_context는 auto-trigger 경로에서 빈 dict.
5. **Medium** Migration: PG `ADD COLUMN ... NOT NULL DEFAULT 'shared'`는 기존 row에도 적용됨 (PG11+ O(1)). 단, Python-side `default="shared"` 추가해서 ORM insert가 DB default에 의존 안 하게.
6. **High** Test: 1개 부족. 최소 8-test matrix 제시 (private→B 제외, private→A 포함, shared→both, auto-trigger shared-only, 멱등성 2요청, 소유자 가드, legacy NULL, WS isolation).

**CODEX SAYS (eng — architecture challenge):**
1. **Critical** 필터 미스 리스크 실재 — 현재 코드가 이미 3 지점에서 filter 없이 load 중 (`agent.py:280`, `:406`, `:547`). **Fix: `load_agent_context(session, room_id, viewer_user_id, scope)` 헬퍼 + branded type `AgentContextMessages` + `run_pipeline()`이 이 타입만 수용**. assistant/user persist도 같은 서비스로 통합해 visibility 필수화.
2. **High** WS 채널 ordering race: private + 공용 auto-trigger 동시 publish 시 순서 nondeterministic → UI flicker/misthread. **Fix: 모든 이벤트에 monotonic sequence 스탬프 (`chat_message.id` 또는 `event_id`) → 클라이언트 merge/sort**.
3. **High** Share TOCTOU: READ COMMITTED에서 실제 race. **Fix: DB UNIQUE on `(shared_from_id, user_id)` 복합 인덱스 + `INSERT ... ON CONFLICT DO NOTHING RETURNING id`**. edit-and-reshare는 `superseded_at` tombstone 컬럼으로 별도 versioning.
4. **High** Auto-trigger: WS 없으면 아예 실행 안 됨. **Fix: room 단위 worker/service로 이관, WS는 delivery만**. (이 범위는 본 PR 밖일 수 있음 — 최소한 "zero WS 시 drop" 명시 필요)
5. **Medium** Migration: server_default 의존 금지. **Fix: (a) nullable 추가 → (b) explicit UPDATE 백필 → (c) NOT NULL**. 3단계 Alembic revision.
6. **Medium** Test: 1개 불충분. 최소 5 테스트.

#### 3.2 Eng Consensus Table

```
ENG DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════════════════
  Dimension                                Claude    Codex   Consensus
  ──────────────────────────────────────── ────────  ──────  ─────────
  1. WS channel split mechanically sound?  YES       YES     CONFIRMED
  2. Filter enforceability acceptable?     NO        NO      CONFIRMED-ADD-HELPER
  3. WS msg ordering race real?            PARTIAL   YES     CONFIRMED-ADD-SEQ
  4. Share TOCTOU real?                    YES       YES     CONFIRMED-FIX
  5. TOCTOU fix: advisory lock vs UNIQUE?  LOCK      UNIQUE  DISAGREE (taste)
  6. Auto-trigger ownership sound?         NO        NO      CONFIRMED-FIX
  7. Migration backfill method?            DEFAULT   UPDATE  DISAGREE (taste)
  8. Test coverage sufficient?             NO        NO      CONFIRMED-EXPAND
═══════════════════════════════════════════════════════════════════════════
6/8 CONFIRMED. 2 taste decisions at final gate.
```

#### 3.3 Architecture — ASCII Dependency Graph

```
                         ┌──────────────────────────┐
                         │  backend/app/repositories/│
                         │  messages.py (NEW)        │
                         │  MessageReader.for_user() │◄────── ONLY sanctioned
                         │  returns AgentContextMsgs │        query factory
                         └────────────┬──────────────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
    ┌────────────▼──────────┐  ┌──────▼──────────┐  ┌─────▼──────────────┐
    │ ws/agent.py           │  │ ws/agent.py     │  │ routes/chat.py     │
    │ user message handler  │  │ auto-trigger    │  │ POST .../share     │
    │ (lines 455-498)       │  │ (lines 202-357) │  │ (NEW)              │
    └────────────┬──────────┘  └──────┬──────────┘  └─────┬──────────────┘
                 │                    │                   │
                 │                    │                   │ pg_advisory_xact_lock
                 │                    │                   │  OR
                 │                    │                   │ INSERT ON CONFLICT
                 │                    │                   ▼
                 │                    │            ┌─────────────┐
                 │                    │            │ chat_messages│
                 │                    │            │ +user_id     │
                 │                    │            │ +visibility  │
                 │                    │            │ +shared_from │
                 │                    │            └──────────────┘
                 ▼                    ▼
    ┌─────────────────────────────────────────────┐
    │ run_pipeline(context: AgentContextMessages) │◄─── typed, cannot receive raw
    │  → langgraph_pipeline.py                     │
    └─────────────────────────────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────────────────┐
    │ Redis pub/sub                                │
    │ agent:{room}              ← shared events   │
    │ agent:{room}:user:{user}  ← private events  │
    │ + event seq (chat_message.id)                │
    └─────────────────────────────────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────────────────┐
    │ WS: single pubsub, subscribes BOTH channels  │
    │ Client sorts by chat_message.id              │
    └─────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────┐
    │ Room-singleton auto-trigger lock             │
    │ Redis SET NX nx_autotrigger:{room} TTL 60    │
    │ Winner runs pipeline, others skip exec       │
    └──────────────────────────────────────────────┘
```

#### 3.4 Test Matrix (§9.4 확장)

| # | 테스트 | 유형 | 우선순위 |
|---|---|---|---|
| T1 | A private → B pipeline recent_messages 제외 | unit | MUST |
| T2 | A private → A pipeline recent_messages 포함 (regression guard) | unit | MUST |
| T3 | shared 메시지 → A, B 파이프라인 모두 포함 | unit | MUST |
| T4 | auto-trigger 파이프라인 → visibility=shared만 조회 (private 제외) | unit | MUST |
| T5 | 공유 API 동시 2요청 → 1개 row만 생성 (asyncio.gather 2tasks) | integration | MUST |
| T6 | 공유 API 소유자 아닌 유저 요청 → 403 | integration | MUST |
| T7 | legacy rows (user_id=NULL, visibility=shared) → 모든 유저 파이프라인에 포함 | unit | SHOULD |
| T8 | WS 채널 격리 — B의 WS가 agent:{room}:user:A 수신 X | integration | SHOULD |

T1, T2, T4, T6, T8이 boundary 검증의 minimum. 졸업 프로젝트 범위상 MUST 6개 + SHOULD 2개로 권고.

#### 3.5 Taste Decisions (Final Gate로 보류)

**A. Share 멱등성 메커니즘 (Claude vs Codex 불일치):**
- Option A1: **PG advisory lock** — schema 변경 없음, edit-and-reshare 확장 유지, 단 트랜잭션 범위 제한
- Option A2: **복합 UNIQUE `(shared_from_id, user_id)` + ON CONFLICT** — DB 레벨 강제, 초기 CEO의 UNIQUE 우려는 "동일 유저의 중복 공유"만 막는 거라 edit-and-reshare는 별도 `superseded_at` 컬럼으로 해결 가능

**B. Migration 백필 방법:**
- Option B1: **PG `ADD COLUMN NOT NULL DEFAULT` 단일 단계** — 간결, PG11+에서 O(1)
- Option B2: **3단계 Alembic** (nullable → UPDATE → NOT NULL) — 안전, 향후 default 제거 시에도 안전

### Phase 4 — Cross-phase Themes

두 개 이상 phase에서 독립적으로 올라온 주제 — 고신뢰 시그널:

1. **"구현 레이어 잘못됨"** (Phase 1 + Phase 3)
   - Phase 1 CEO: "product rule을 DB 레벨로 올리는 건 잘못" (UNIQUE 제약)
   - Phase 3 Eng: "filter 정책을 callsite에 의존은 잘못" (타입 레벨로 올림)
   - 공통 통찰: 제약은 올바른 레이어에서 강제해야 한다. 너무 낮으면(DB UNIQUE) 유연성 상실, 너무 높으면(callsite 정책) 망각 위험. **적절한 레이어에서 강제**하는 것이 핵심.

2. **"1개 테스트로 경계 증명 불가"** (Phase 1 + Phase 3)
   - Phase 1: "privacy 테스트 3+ 필요"
   - Phase 3: "5~8 테스트 matrix"
   - 공통: privacy boundary는 regression guard가 여러 각도로 필요. 최소 5개 MUST.

3. **"미해결 의사결정을 수면 위로 끌어올림"** (Phase 1 + Phase 3)
   - Phase 1: auto-trigger 경로의 slot_context 주인 미정
   - Phase 3: auto-trigger는 zero-WS 시 drop — room-level worker 필요 (범위 밖)
   - 공통: auto-trigger는 본 PR 완료 후에도 구조적 미해결 이슈로 남음. 문서화 필요.

### Phase 4 — Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale |
|---|---|---|---|---|---|
| 1 | CEO | 프레이밍 재정의 (coordination operator + privacy guards) | User-confirmed | P1 Completeness | 두 모델 모두 현재 프레이밍이 약하다고 지적, 사용자가 재정의 승인 |
| 2 | CEO | 9단계 → 6단계 하이브리드 | User-confirmed | P2 Lake + P3 Pragmatic | Redis slot_context/UNIQUE 제약은 premature, 시연에 손실 거의 없음 |
| 3 | CEO | 공유 모델: 하이브리드 (텍스트=복제, 카드=참조) | User-confirmed | P1 Completeness | UI 일관성 + 감사성 둘 다 확보 |
| 4 | Design | 공유 버튼 항상 표시 (hover 전용 제거) | Auto (both agree) | P1 Completeness | 모바일/터치 fatal gap |
| 5 | Design | Triple-code (배지 + 아이콘 + accent rail) | Auto (both agree) | P1 Completeness | 색맹 대응 + 빠른 scan |
| 6 | Design | 상태 UI (로딩/에러/멱등/오버플로/고아) 명시 | Auto (both agree) | P1 Completeness | 현재 happy path만 명시된 상태 |
| 7 | Design | 공유자 구분 배지 (`내가 공유` vs `OO님이 공유`) | Auto (both agree) | P1 Completeness | 정보 scent 부족 |
| 8 | Eng | `MessageReader.for_user()` 헬퍼 + branded type | Auto (both agree, critical) | P5 Explicit | 필터 망각 = 개인정보 유출. 타입 레벨 강제. |
| 9 | Eng | 이벤트 monotonic sequence (`chat_message.id`) | Auto (both agree) | P5 Explicit | WS 채널 간 ordering race 방지 |
| 10 | Eng | Auto-trigger Redis lock (`SET NX nx_autotrigger:{room}`) | Auto (both agree) | P1 Completeness | N 유저 × 중복 파이프라인 실행 방지 |
| 11 | Eng | Test matrix 1→6~8개로 확장 | Auto (both agree) | P1 Completeness | 경계 여러 각도 검증 |
| 12 | Eng | **TOCTOU 해결: PG advisory lock** | User-resolved | P3 Pragmatic | schema 변경 없이 원자성 확보 + edit-and-reshare 확장성 유지 |
| 13 | Eng | **Migration: 단일 단계 (PG ADD COLUMN NOT NULL DEFAULT)** | User-resolved | P5 Explicit | PG11+ O(1), Python-side default 병기로 ORM 안전 |
| 14 | Design | **Timeline: Accent rail만 (divider 없음)** | User-resolved | P5 Explicit | 채팅 metaphor 유지, 이미 복잡한 팡이에 divider 추가 회피 |

### Phase 4 — Final Approval State

- [x] CEO 재프레이밍 반영 (coordination operator + privacy guards)
- [x] 6-step hybrid 스코프 확정
- [x] 공유 모델: 텍스트 복제 + 카드 참조
- [x] Design auto-fix 5건 반영
- [x] Eng auto-fix 6건 반영 (MessageReader, event sequence, Redis lock, 8-test matrix)
- [x] Taste decisions 3건 모두 결정 (accent rail, advisory lock, 단일 migration)

**승인 상태: APPROVED. 구현 시작 가능.**

**구현 순서 (6-step):**
1. DB 모델 + Alembic 단일-단계 마이그레이션 + Python default 병기
2. `backend/app/repositories/messages.py` 생성 + `MessageReader.for_user()` + `AgentContextMessages` branded type
3. WS 채널 분리 (single pubsub, 2 채널 구독) + 이벤트에 `chat_message.id` sequence
4. 공유 API (`POST /messages/{id}/share`) + advisory lock + 카드 참조 계승 + Auto-trigger Redis lock
5. `run_pipeline` 시그니처 변경 + 3 call site 교체 + CI lint 규칙
6. 프론트: 공유 버튼 footer + triple-code 스타일 + 상태 UI + 수동 QA (2 유저)

**Tests (MUST):** T1, T2, T3, T4, T5, T6 — 6개.








