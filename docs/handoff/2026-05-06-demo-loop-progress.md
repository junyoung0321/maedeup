# 2026-05-06 — 시연 루프 진행 + 자동화 + 해결점 P

## 세션 요약

- 아키텍처 감사(A~M) 코드 적용 완료 + 브라우저 시연 루프(ACT 1~5) 검증
- Codex 하청 + 검수 루프 패턴으로 E·I·J·K 적용
- **해결점 P 임시 구현**: 채팅 자연어 거부 → 캘린더 unavailability 동기화
- **시연 자동화 도구 완비**: Playwright + CDP 9222 + 풀 시나리오 1-shot 스크립트
- 모든 작업 origin/main에 push 완료 (15개 커밋)

## 커밋된 작업 (시간순)

### 1차 — 감사 해결점 적용
- `c41bd43` phase 1 — A·D·F·G·H·L·M
- `e46b756` phase 2 — B·C
- `e280c60` phase 3-E — quick_classify direct_request 단축
- `94768f5` phase 3-I — slot_filling 트리거별 분기
- `8883059` phase 3-J — meeting_id Map upsert
- `2f20e85` phase 3-K — partial 카드 + PATCH 엔드포인트

### 2차 — 시연 루프 버그픽스 + UI 정리
- `13d8cdc` 시연 흐름 자동 직진 차단 (자동추천 + 합성메시지 + 자동전송 제거)
- `3e899e2` rejected 후보 소진 시 다음주 확장 + 라우팅 보정
- `1412ed0` 장소 추천 카드 AI 패널 단일 렌더
- `84561b3` schemas/__init__ 누락 보완
- `928f4fa` 본 핸드오프 문서 + 시뮬 스크립트
- `2f948b1` 감사 핸드오프 + 확정 이슈 + 다이어그램 SoT

### 3차 — 해결점 P + 시연 자동화
- `db6ea31` **해결점 P 임시** — 채팅 거부 → 캘린더 unavailability 동기화
- `1602684` **시연 자동화 도구** — chromium CDP + 풀 시나리오 1-shot
- `52bc445` 해결점 O·P 등록 + 시연 시나리오 SoT

## 검증된 시연 흐름 (브라우저 자동화)

| ACT | 검증 사항 | 해결점 |
|---|---|---|
| ACT 1 | 방 생성 + 게스트 가입 + 선호도 입력 | — |
| ACT 2 | 4메시지 자동 트리거 / 분석중 메시지 즉시 | A·B |
| ACT 2 | rejected_dates LLM 추출 (5/8-민수, 5/9-수현) | F |
| ACT 2 | vote_card 후보에서 5/8, 5/9 자동 제외 | F |
| ACT 2 | 다음주 평일 후보 expand (5/11, 5/12, 5/13) | N |
| **ACT 2** | **채팅 거부 → 캘린더 카운트 자동 갱신 (2/3 빨간 표시)** | **P (임시)** |
| ACT 4 | vote_card 확정 → meeting 생성 | — |
| ACT 5 | 장소 추천 카드 발행 (강남 인근) | — |
| ACT 5 | 장소명 클릭 → 캘린더 패널 PlaceDetailPane | — |
| ACT 5 | 장소 확정 → maedeup_card → 모임 완료 페이지 | J |

전체 자동화: `python .gstack-demo.py` → 약 1분 11초 (3초 view_pause 3구간 포함).

## 시연용 환경 (너 혼자 실행)

### 1회 셋업
```bash
# .gstack-demo-token 파일에 본인 JWT 저장 (gitignore됨)
# 평소 Chrome → localhost:3000 로그인 → F12 → localStorage.getItem('auth_token') 결과
echo 'eyJhbGc...' > .gstack-demo-token
```

### 매 시연
```bash
# 터미널 1
docker compose up -d
python .gstack-browser-launch.py     # chromium 뜨고 토큰 자동 주입

# 터미널 2
python .gstack-demo.py               # 시연 페이스
python .gstack-demo.py --fast        # 빠른 검증
```

같은 chromium 그대로 두고 demo 스크립트 반복 실행 가능 (매번 새 방).

## 시연 후 보완 항목 (시연 후로 미룸)

### 1. 해결점 P 보완 (현재 임시 구현)
- 번복 처리 — "아 8일 되네" 시 unavailability에서 자동 제거
- 게스트 매핑 정책 정교화 (현재 임시로 게스트 포함)
- 이름 충돌 시 발신자 ID 활용 (chat message에 user_id 있음)
- `_maybe_emit_proposal` 재집계 호출 (멤버 finalization 영향 시)

### 2. 해결점 O — 정규식 단축 경로 사각지대
**증상**: AI 패널 직접 요청 시 social_recent 누적 거부 발언이 vote_card 후보 필터에 반영 안 됨 (정규식 다중 날짜 잡으면 Gemini 스킵).
**시연 영향**: 미미 (auto-trigger 경로로 들어오는 시연 시나리오에선 안 터짐).
**수정 후보**: `audit-findings.md` 해결점 O 옵션 B 추천 (shortcut 조건에 거부 키워드 부재 AND 추가).

### 3. ACT 4 confirm 후 후속 안내 메시지 미표시
vote_card 사라지지만 "일정이 확정되었습니다 — 5/6 (수) 6:00" 박스 미표시. 백엔드 confirm은 정상 처리되어 ACT 5 흐름 영향 없음. 시연 임팩트 작아 후순위.

### 4. ACT 5 quick_classify 단축 미발동
"강남역 근처 한식 맛집 추천해줘" → entity_extraction 6초 (Gemini 경로). 정규식이 의도 인식 못함. quick_classify 패턴 보강 필요. 시연 시간 영향 작음.

### 5. PlaceDetailPane meetingId prop 누락
"일정을 먼저 확정해주세요" 버튼 비활성 — meetingId 흘러들어가지 않음. 별도 이슈.

### 6. ACT 3 (TimeBar) / ACT 6 (partial) 자동화
현재 demo 스크립트는 ACT 3·6 스킵. 시연 후 자동화 확장 가능.

## 참고

- 시연 시나리오 SoT: `docs/handoff/demo-scenario.md`
- 확정 이슈 누적: `docs/handoff/audit-findings.md` (해결점 A~P)
- 다이어그램: `docs/handoff/diagrams/`
- 이전 세션: `docs/handoff/2026-05-05-architecture-audit-progress.md`
