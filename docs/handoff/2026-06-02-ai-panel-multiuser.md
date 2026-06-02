# AI 패널 멀티유저 동작 — 화자 귀속·동시성·공유 토글 (2026-06-02)

브랜치: `fix/speaker-attribution-concurrency` (main 미머지)
커밋: `9e4ce93`(B+C), `2d82886`(토글+블록+isMe)
관련: [[project_pipeline_status]], `docs/ai-separation.md`

---

## 0. 배경 — "AI 패널은 사용자별인가 공유인가?"

한 방에 여러 명이 있을 때 AI 패널 동작을 추적한 결과(코드 기준):

- **기본은 방(room) 단위 공유·동기화.** vote_card·agent 메시지·투표 집계는 같은 방
  모든 멤버에게 broadcast. 사용자별인 건 "내가 찍은 항목 하이라이트"(`current_user_vote`)뿐.
- 채널: `agent:{room}`(shared) vs `agent:{room}:user:{uid}`(private). 비멤버는 WS
  연결 차단(`code=4003`). 모든 채널·락이 room_id로 격리 → **방 격리는 견고**.
- 직접입력(direct_request)의 입출력은 **비대칭**이었다: 입력 private(본인만) ·
  출력 shared(전원). → B가 "맥락 없는 카드"를 보는 혼란. 이걸 토글로 해소(아래 §3).

> 자유체험존 권고: **방문자/그룹마다 별도 room** 발급이면 출력 공유 혼선이 코드 변경
> 없이 사라진다(채널·락·F-1 모두 room 단위).

---

## 1. B — 다화자 일정 화자 귀속 (`9e4ce93`)

### 문제 (코드 확정)
`date_classify`가 모든 화자 제약을 화자 구분 없이 평평한 날짜 set으로 병합:
1. **다화자 정정 버그**: `_resolve`의 전역 `rejected -= available` → A의 "수목금 안돼"를
   B의 "수요일 돼"가 지워버림 (A가 여전히 바쁜데 그룹 rejected에서 수요일 빠짐).
2. **귀속 버그**: `to_rejected_dates`의 user가 전부 None → `CHAT_UNAVAIL_SYNC`가
   `speaker_user_id`로 fallback해 **모두의 거부를 트리거한 1명에게** 귀속.

### 수정
- `social_recent`이 이미 `"이름: 발화"` 포맷(`preferences.py:67`) → context에 화자명 존재.
- `_detect_complement_constraints`: 줄의 `X:` 화자 라벨을 `speaker`로 태그(`date_classify.py`).
- 프롬프트의 사장된 `users` 필드를 화자명으로 명확화 → LLM이 화자 귀속.
- `_resolve`: 화자별 그룹화 → 그룹마다 `rejected -= 본인 available` + per-date `rejected_by`.
- `to_rejected_dates(rejected, rejected_by)`: 화자명 출력 → 기존 `CHAT_UNAVAIL_SYNC`
  이름매핑(`agent.py:248`)이 올바르게 귀속.
- **하위호환**: 화자 라벨 없으면(eval·단일발화) None 단일그룹 → 기존 전역 동작과 동일.

### 검증
- 단위 12/12 PASS (다화자 정정·하위호환·detector·귀속).
- **eval 회귀 0** (오히려 개선): ALL F1 0.612→0.662, recall 0.578→0.671,
  complement F1 0.696→0.827. (`docs/handoff/eval/eval_after_speaker.json`)
- LLM 화자 귀속 실증: 6/3·4·5→수현, 6/8·9→예린, 민수 3명 전원 정확.

---

## 2. C — direct_request 카드 생성 블록 (`9e4ce93` 락 → `2d82886` 블록)

### 문제
auto_trigger·투표는 NX 락 보호되나 direct_request는 무방비 → 동시 요청 시 중복
vote_card·DB 경합.

### 수정 (최종: 블록 방식)
- `_room_card_generating: set[str]` — 방별 카드 생성 중 플래그(`agent.py`).
- 이미 카드 생성 중인 방엔 새 카드 요청을 **대기가 아니라 차단**: "AI가 이미 일정·장소
  카드를 만들고 있어요" 안내 후 skip. 불필요한 2차 파이프라인 실행 제거.
- 첫 요청 카드는 shared로 모두에게 가므로 막힌 사용자도 곧 같은 카드를 본다.
- check+add 사이 await 없음 → 원자적(TOCTOU 방지). finally에서 discard.
- **단일 uvicorn 워커 가정**(`backend/Dockerfile`). 다중 워커 확장 시 Redis 플래그 필요.

### 검증
- 동시 2 direct_request → 직렬화(완료 17s→18s) + pending meeting 1개(중복 0).
- 블록: B(A 생성 1.2s 후 요청) → "이미 만들고 있어요" 안내 수신 PASS.

---

## 3. 공유/나만 토글 (`2d82886`)

### 설계 (방향1 + A안)
입력/출력 공유의 비대칭을 토글로 일관화.
- **public(기본)**: 입력을 방 전체에 **화자명과 함께** broadcast + 텍스트 응답도 공유.
  → "🙋 지민: 강남 맛집? / 🤖 AI: …" 가 모두에게. 맥락 복원.
- **private(나만)**: 입력·텍스트 응답이 본인 채널만.
- **투표/장소 카드는 그룹 결정 자산이라 토글 무관하게 항상 shared** (A안).

### 구현
- backend `agent.py`: payload `visibility`(기본 public) 읽기 → 입력 에코·ChatMessage
  visibility·텍스트 응답을 shared/user 채널로 분기. 카드는 shared 유지(`vote_card` 1319 등).
- frontend `AiAssistantPane.tsx`: 입력창 옆 토글(Globe "공유" / Lock "나만") + `isPrivate` 상태.
  **isMe 판정을 `msg.role==="user" && user_id===currentUserId`로 수정** — 공유된 남의
  입력이 '나'로 우측정렬되던 버그 해결.
- `useAgentWebSocket.sendMessage(content, visibility="public")` 확장(하위호환).

### 검증 (qa-runtime 실제 Chromium)
- 토글 렌더/동작(공유↔나만) PASS, 공유 모드 전송(우측정렬) PASS.
- **cross-user 렌더**: 게스트 public 입력이 호스트 패널에 "게스트B" 화자명 + 좌측정렬 PASS.
- 백엔드 WS: B가 A의 public 입력만 수신·private 미수신 PASS.
- 콘솔 에러 0.

---

## 4. 알려진 미해결 / 후속

- **모바일 토글 미적용**: `/m/chat/ai`는 `sendMessage(content)` 기본 public으로만 동작
  (토글 UI 없음). 데모/전시는 데스크탑이라 무방. 필요 시 모바일에도 토글 추가.
- **선호 모달 오버레이 (P2)**: 선호 미입력 방 진입 시 "이번 모임 선호 정보" 모달
  (z-index:1000)이 AI 패널 전체를 덮어, 닫기 전엔 AI 패널 조작 불가. 자유체험존에서
  신규 사용자가 모달을 안 닫으면 AI 패널을 못 만지는 흐름 → 모달 우선순위/안내 검토 권장.
- **단일 워커 가정**: 카드 블록 플래그는 in-process. Lightsail 등 배포가 단일 워커인지 확인.
  다중 워커면 Redis 플래그로 교체 필요(블록·B는 무관, 블록만 영향).
- **location_first 장소추천**은 여전히 user_channel(private 탐색). 토글 public 모드에서도
  shared로 바꿀지는 미결정(현재 보수적으로 private 유지).

---

## 5. 다음 단계

- 데스크탑 ACT1~5 전체 데모 스모크(전시 전 최종) → 이상 없으면 main 머지 후보.
- 머지 시 `git checkout main && git merge --no-ff fix/speaker-attribution-concurrency`.
- 현재 실행 백엔드는 이 브랜치 코드. 데모를 main으로 돌리려면 checkout main + restart.
