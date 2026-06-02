# 모바일 = 웹 기능 완전 일치 (2026-06-03)

브랜치: `fix/speaker-attribution-concurrency` (main 미머지, 10 커밋)
목표: 모바일(/m) 앱뷰를 데스크탑(웹)과 **기능적으로 완전히 동일**하게.
검증: qa-runtime 풀 인터랙티브 플로우 2회 → **기능 일치 PASS, 기능 결손 없음**.

---

## 0. 핵심 접근 — 데스크탑 컴포넌트 재사용

모바일용 재작성 대신, 데스크탑 컴포넌트를 **그대로** 모바일에 렌더한다. 데스크탑 모임방
(`/meeting/[id]`)은 `MeetingProvider` 안에 **ChatPane + AiAssistantPane + InfoPane 3단을
동시 렌더**한다(`meeting/[id]/page.tsx:145-147`). 모바일도 동일하게:

- `/m/chat/ai` = **통합 meeting 화면**. 한 `MeetingProvider`에 3 pane을 **모두 마운트**하고
  탭은 visibility(display)만 토글 → 상태·WS 브릿지가 데스크탑과 **동치로 공유**된다.
- 채팅방 탭 = `ChatPane`, 캘린더 탭 = `InfoPane`(캘린더 그리드·멤버 가용성·TimeBar·AI 추천시간),
  AI 탭 = `AiAssistantPane`(추천/장소/매듭 카드·공유 토글·share).
- 라우팅: `/m/chat/schedule` → `?tab=chat`, `/m/schedule` → `?tab=calendar` 리다이렉트.

> 왜 3개 다 마운트하나: ChatPane이 social WS 브릿지(`sendTimeSelection`·`scheduleConsensus`·
> 미가용·finalization)를 `MeetingContext`에 세팅한다(`ChatPane.tsx:90-162`). 이게 없으면
> TimeBar 합의·호스트 확정이 작동 안 한다(아래 버그 A). 데스크탑은 3단 동시라 항상 붙어 있음.

---

## 1. 모바일 탭 모델 ↔ 데스크탑 3단 동시표시 차이 보정 (자동 전환)

데스크탑은 3 pane 동시 표시라 흐름 진행 시 관련 pane이 항상 보인다. 모바일은 한 번에 한 탭이라,
**흐름 진행에 따라 탭을 자동 전환**해 동일 경험을 준다 (`/m/chat/ai/page.tsx` useEffect):
- `infoPanePhase==="dateConfirmed"`(시간대 변경) → **캘린더 탭**(TimeBar)
- `contextMode==="place"/"schedule"`(장소 선택 등) → **캘린더 탭**(PlaceDetailPane)
- `infoPanePhase==="timeConfirmed"`(시간 확정) → **AI 탭**(매듭 카드 + 장소 추천 안내)
- `contextMode==="done"` → **CompletionPage**(고정 480px → scale 0.8125로 390px)
- 첫 렌더는 건너뛰어 `?tab=` 초기값 존중.
- 헤더 "완료" 버튼 = 데스크탑 "생성 완료"(`setContextMode("done")`) parity.

→ 결과: 시간대조율→합의→확정→장소→확정→완료 전 구간이 **수동 탭 전환 0회**로 진행.

---

## 2. 검증 중 발견·수정한 버그

| # | 버그 | 원인 | 수정 |
|---|---|---|---|
| A (P1) | TimeBar 합의·"추천 시간 그대로 확정" 안 뜸, 호스트 시간선택이 서버에 안 올라감 | 통합 페이지가 InfoPane+AiAssistantPane만 마운트, **ChatPane 누락** → social WS 브릿지 null | ChatPane 마운트(3 pane 전부) |
| B (P2) | 완료(done) CompletionPage 모바일에 없음 | contextMode="done" 분기 미포팅 | done 분기 + scale 래핑 추가 |
| C (P1) | 시간확정·장소확정 meeting 분리, 확정 시각 유실 | qa가 버그 A 우회로(개별 확정)를 써서 발생한 부작용 | 버그 A 수정으로 정상 합의-확정 경로 복구 → 한 meeting(검증: `meeting_schedules` 1 row에 time+location) |
| P1(2차) | AI 탭 장소명 클릭 시 화면 변화 없음(PlaceDetailPane이 숨은 캘린더 탭에서 열림) | 모바일 tab이 contextMode와 분리 | contextMode/phase 기반 자동 탭 전환 |

**별도(파이프라인, 데스크탑 공통 가능성)**: place 노드(`place.py:197`)가 meeting_id를 현재 run의
vote_card에서만 찾음 → 정상 합의-확정 경로에선 한 meeting으로 수렴(검증됨). 시간확정과 완전히
분리된 별도 발화로 장소요청 시 새 meeting 생성 여지 — 별도 검토 백로그.

---

## 3. 캘린더 날짜 오적용 버그 (별개, 같은 브랜치)

사용자 관측: "다음주 토요일(13일) 빼고 다 바빠"인데 캘린더에서 10일이 빠지고 날짜 뒤죽박죽.
- 원인1: 캘린더(CHAT_UNAVAIL_SYNC)가 reflect-back/vote_card와 **다른 추출**(`_analyze_conversation`
  단일 LLM, 여집합·다화자 약함)을 씀 → 스크램블. → `_analyze_conversation`이 LLM 후
  `date_classify`로 rejected_dates 교체(화자 귀속까지). 캘린더가 reflect-back과 일치.
- 원인2: LLM이 예린 여집합을 민수에게 오귀속 + 예외일(06-13) 누락 → 06-13 가능일이 불가로 남음.
  → detector 예외일에 `complement_exception` 마커, `_resolve`가 전역 차감. LLM 정정(돼/가능)은
  화자별 유지 → A/B 케이스 보존.
- 검증: 06-10 불가 2명·06-13 전원가능 ✓, 결정적 단위 7/7, 캘린더 시각 확인 ✓.

---

## 4. 검증 결과 (qa-runtime 풀 플로우)

- 3탭 데스크탑 컴포넌트 렌더, 콘솔 에러 0.
- 버그 A/B/C 전부 PASS. 자동전환 2곳 PASS. "완료" 버튼 PASS.
- 자연 흐름(수동 우회 없이) 완료까지 도달. DB time+place 한 meeting, 확정 시각 보존.
- **종합: 기능적으로 데스크탑과 동일, 기능 결손 없음 (PASS).**
- 남은 차이: 라벨 축약("완료" vs "생성 완료"), 구조상 탭 모델 차이(자동전환으로 보정됨). 기능 결손 아님.

---

## 5. 커밋 (main 위 10개, 요약)

- `dd1aa56` AI 탭 + AiAssistantPane / `854bd5f` 통합 캘린더(InfoPane TimeBar)
- `7845dbd` ChatPane 마운트 + done(버그 A·B) / `30ad7ba` 자동 탭 전환 + 완료 버튼 / `10??` 시간확정 후 AI 복귀
- `09ce62d` 캘린더 날짜 오적용 수정
- (이전) `9e4ce93` 다화자 화자 귀속 + 동시성 / `2d82886` 공유 토글 + 카드 블록 / `b900792` 모바일 isMe

## 6. 후속 / 백로그
- place 노드 별도-발화 meeting 재사용(데스크탑 공통 의심) 별도 검토.
- 새로고침 시 timeConfirmed phase 복원(데스크탑 공통).
- 모바일 토글/카드 회귀 자동화 테스트(qa 드라이버 로직 채택 가능).
