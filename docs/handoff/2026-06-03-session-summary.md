# 세션 종합 핸드오프 (2026-06-03) — compaction 진입점

이 세션에서 한 일 전부. 다음 세션은 이 문서 + 아래 상세 문서부터 읽으면 된다.
**전시: 2026-06-04(수)·06-05(목). 데모는 데스크탑 고정. 모바일은 PWA + 별도 브랜치.**

---

## 0. 지금 상태 한 줄

- **origin/main**: PWA/TWA 모바일 앱 + 모바일 채팅 AI 흐름 + JWT 로그 마스킹 **머지·푸시 완료** (HEAD `0472dfb`).
- **브랜치 `fix/speaker-attribution-concurrency`** (main 위 **11 커밋, 미머지**): AI 패널 멀티유저 + **모바일=웹 기능 완전 일치** + 캘린더 날짜 오적용 수정. qa 풀검증 PASS.
- **실행 중 백엔드·프론트는 브랜치 코드** (검증 위해 restart/rebuild함). 데스크탑 데모를 main으로 돌리려면 `git checkout main && docker compose up -d --build frontend && docker restart maedeup-api`.

---

## 1. origin/main 에 머지·푸시된 것 (전시 영향, 자동배포 없음)

`.github/workflows`에 deploy 없음 → 푸시로 실서비스 자동배포 안 됨.

- **PWA/TWA 모바일 앱**(`50a6999` 머지): 설치형 PWA(`@ducanh2912/next-pwa`, manifest, SW, 오프라인, InstallPrompt) + TWA 스캐폴딩(Bubblewrap, assetlinks). SW는 prod 빌드만 활성, 동적데이터(API/WS) NetworkOnly.
- **모바일 채팅 AI 흐름**(`728cc6d`): ① `/m/chat/layout.tsx`+`AgentTriggerKeepalive` — 모바일 채팅 중 agent WS keepalive(교착 트리거 유실 수정). ② `MobileVoteCard` — `/m/chat/ai`에 추천 카드. (※ 이건 아래 브랜치 작업에서 **AiAssistantPane 재사용으로 대체**됨.)
- **JWT 로그 마스킹**(`0472dfb`): `backend/app/core/log_filters.py` `TokenMaskingFilter` → root+uvicorn 로거에 부착, WS `?token=...` → `token=***`.
- 날짜추출 여집합 detector(`1151f62`), 폰 16px/시연 22px 스코프(`c32fafb`).

배포 방법(사용자가 Lightsail 보유, 코드는 배포준비 완료): `git pull` → frontend 빌드(**`NEXT_PUBLIC_WS_URL=wss://도메인` 빌드인자 필수**, build-time 주입) → docker compose up. 코드 수정 0, env/콘솔(구글 redirect·카카오 도메인)만. 키는 **서버 .env**의 키(=사용자 계정 키) 사용 — 전시 방문자는 Google 로그인 불가(테스트모드 100명 한도)이므로 **게스트 모드(guest-join)** 동선.

---

## 2. 브랜치 fix/speaker-attribution-concurrency (미머지 11커밋) — 핵심 작업

### 2-A. AI 패널 멀티유저 (`9e4ce93`, `2d82886`, `b900792`)
- **B 다화자 화자귀속**: `date_classify._resolve`가 화자 구분 없이 병합 → ① 전역 `rejected-=available`로 A의 거부를 B의 가능이 지움 ② rejected_dates user=None. → 화자별 그룹(`rejected-=본인 available`) + per-date `rejected_by`. `social_recent`이 "이름: 발화" 라벨이라 활용. eval 회귀 0 (F1 0.62→0.66). 단위 12/12.
- **C direct_request 동시성**: auto_trigger·투표는 NX락 보호되나 direct_request 무방비. → 방별 `_room_card_generating` 플래그로 **카드 생성 중 블록**(대기 아님, "이미 만드는 중" 안내). 단일 워커 가정.
- **공유/나만 토글**: AI 패널 입력창 옆 토글. public(기본)=입력·텍스트응답 방전체 공유(화자명), private=본인만. **카드는 항상 shared**. isMe를 user_id 기준으로 수정(공유된 남의 입력이 '나'로 우측정렬되던 버그). `AiAssistantPane.tsx`, `useAgentWebSocket.sendMessage(content,visibility)`.
- 상세: `docs/handoff/2026-06-02-ai-panel-multiuser.md`

### 2-B. 모바일 = 웹 기능 완전 일치 (`dd1aa56`,`854bd5f`,`7845dbd`,`30ad7ba`,`baaf774`)
**핵심: 데스크탑 컴포넌트를 모바일에 그대로 렌더.** `/m/chat/ai`를 **통합 meeting 화면**으로 — 한 `MeetingProvider`에 데스크탑 **ChatPane + InfoPane(TimeBar) + AiAssistantPane 3 pane 모두 마운트**, 탭 visibility 토글(데스크탑 3단 동시렌더와 동치).
- 채팅방=ChatPane(social WS 브릿지 — 합의·확정의 필수), 캘린더=InfoPane(캘린더그리드·멤버가용성·**TimeBar 시간대조율**·확정·완료), AI=AiAssistantPane(카드·토글).
- 라우팅: `/m/chat/schedule`→`?tab=chat`, `/m/schedule`→`?tab=calendar` 리다이렉트.
- **자동 탭 전환**(모바일 한-탭 ↔ 데스크탑 동시표시 보정): dateConfirmed→캘린더, contextMode place/schedule→캘린더, timeConfirmed→AI, done→CompletionPage(scale 0.8125). + 헤더 "완료" 버튼(데스크탑 "생성 완료" parity).
- **검증 중 발견·수정**: 버그A(ChatPane 누락→합의·확정 안됨), 버그B(완료화면 없음), 버그C(시간·장소 meeting 분리=버그A 우회로 부작용), P1(장소클릭 자동전환 없음).
- **qa-runtime 풀 인터랙티브 2회 → "기능적으로 데스크탑과 동일, 기능 결손 없음 PASS"**: 자연흐름(수동우회 0) 합의→확정→장소→완료 완주, DB time+place 한 meeting, 콘솔에러 0, P0/P1 버그 없음.
- 상세: `docs/handoff/2026-06-03-mobile-web-parity.md`

### 2-C. 캘린더 날짜 오적용 수정 (`09ce62d`) — 사용자 리포트
관측: "다음주 토요일(13) 빼고 다 바빠"인데 캘린더에서 10일이 빠지고 날짜 뒤죽박죽.
- 원인1: 캘린더(CHAT_UNAVAIL_SYNC)가 reflect-back/vote_card와 **다른 추출**(`_analyze_conversation` 단일 LLM) 사용 → 스크램블. → `_analyze_conversation`이 LLM 후 `date_classify`로 rejected_dates 교체.
- 원인2: LLM이 예린 여집합을 민수에 오귀속+예외일 누락 → 06-13 가능일이 불가로 남음. → detector 예외일에 `complement_exception` 마커 + `_resolve` 전역 차감(LLM 정정은 화자별 유지=A/B 보존).
- 검증: 06-10 불가 2명·06-13 전원가능, 단위 7/7, 모바일 캘린더 시각확인(6/10=2/4, 6/13=4/4).

---

## 3. 알려진 이슈 / 백로그
- **place 노드 별도-발화 meeting 재사용** (`place.py:197` meeting_id를 현재 run vote_card에서만 찾음): 시간확정과 완전 분리된 발화로 장소요청 시 새 meeting 생성 여지. **데스크탑 공통 의심** — 별도 검토.
- 새로고침 시 timeConfirmed phase 복원 안 됨(데스크탑 공통).
- 모바일/데스크탑 차이(기능 아님): "완료" 라벨 축약, 탭 모델(자동전환으로 보정).
- TWA 안드로이드 빌드: HTTPS 배포 도메인 필요(스캐폴딩만 됨).

---

## 4. 다음 단계
1. **데스크탑 ACT1~5 데모 스모크** (`.gstack-browser-launch.py` + `.gstack-demo.py --fast`, CDP 9222) → 이상 없으면
2. **브랜치 main 머지·푸시**: `git checkout main && git merge --no-ff fix/speaker-attribution-concurrency`. 머지 트리가 검증분과 동일하면 리빌드 불필요. (푸시는 사용자 확인 후 — 이번 세션 PWA 머지 땐 확인받음)
3. 머지 후 데스크탑 데모 1회 재확인(브랜치가 date_classify·agent.py 등 데모 경로도 건드림).

---

## 5. dev 헬퍼 (미추적, 커밋 안 함)
`scripts/` (verify_mobile_e2e.py, mobile_live_helper.py, mobile_timebar_check.py, diag_unavail.py, cal_visual.py, mobile_parity_check.py 등 — 시나리오 재현+CDP 스크린샷), `qa_artifacts/`·`.qa-mobile/`·`.qa-artifacts/` (스크린샷 증거). 회귀 테스트 시드로 재사용 가능.

## 6. 환경 메모
- 데모 토큰 `.gstack-demo-token` (호스트 JWT sub=1, ~13h 유효, 만료 시 재발급).
- 백엔드 볼륨마운트 → `docker restart maedeup-api`로 코드 반영. 프론트는 `docker compose up -d --build frontend`.
- date_classify는 `datetime.now(KST)` 실시간 기준일. 오늘 06-03.
- 검증 규칙(메모리): chromium UI 실클릭, WS/API 주입 우회 지양. 테스트 크롬만 닫기(taskkill 금지). 리뷰 중 리빌드 금지·최종 1회.
