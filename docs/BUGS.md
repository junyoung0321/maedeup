# BUGS — 매듭 프로젝트 발견 버그 인벤토리

**최종 갱신**: 2026-05-15
**기준**: PR-V1.5.2 + QA dry-run v1 후

---

## 우선순위 정의

- **🔴 P0** — 시연 차단·정상 사용 불가
- **🟠 P1** — 운영·시연 영향 가능
- **🟡 P2** — 테스트 인프라·UX 미세
- **⚪ Non-bug** — 의도된 동작 또는 환경 한계

---

## 🟢 해소된 버그 (이번 세션)

### Codex P1 — disliked food 페널티 fast path 회귀 ✅
- **위치**: `nodes/place.py:263-270` `<=3 후보` fast path
- **문제**: disliked 매장에 `score=0.1` 설정해도 `final_score`는 `distance_score`만 사용 → 가까우면 1위 유지
- **해소**: PR-V1.5 hotfix — disliked 발견 시 `place_copy["final_score"] = 0.0` 명시 (`90131f2`)
- **검증**: `test_score_integration.py` 12 케이스 PASS

### Codex P2 — Q7-c C3 비교가 refresh route에서 발동 안 함 ✅
- **위치**: `helpers/preference_toggle.py:53-58` + `routes/meetings.py` refresh probe_state
- **문제**: `_lightweight_speaker_matches_group`이 `default_place_hint`·`preference_common_foods` 필요하나 refresh probe_state는 requester-only
- **해소**: `_load_group_preference_context` 헬퍼 추가 → probe_state에 group 데이터 주입 (`90131f2`)
- **검증**: `test_refresh_c3_blocks_when_group_matches_speaker` PASS

### QA P2-1 — alembic env.py sqlite 비호환 ✅
- **위치**: `backend/alembic/env.py`
- **문제**: `create_async_engine` 강제 → sqlite(`pysqlite`) `InvalidRequestError: ... not async`
- **해소**: PR-V1.5.1 — `_is_sqlite_url` 분기 + 동기 `run_sync_migrations` (`1892b50`)
- **검증**: test_user_consent_default 2/6 → unblock (잔존 4건은 별개 alembic ALTER 이슈, P3로 해소)

### QA P2-2 — `is_ai_filled` JSON server_default postgres-only ✅
- **위치**: `models/user.py:35` (+ `models/meeting.py:39` `google_event_ids`)
- **문제**: `'{}'::json` postgres-only cast → sqlite `unrecognized token: ":"`
- **해소**: PR-V1.5.1 — `'{}'` 단순화 (postgres·sqlite 양쪽 valid, `1892b50`)
- **추가 정리**: PR-V1.5.2 — alembic versions 3 파일에도 동일 패턴 적용 (`aaec29d`)
- **검증**: `test_refresh_route.py` 10/10 PASS

### QA P2-3 — `_make_state` factory가 prefs=None 덮어쓰기 ✅
- **위치**: `tests/unit/test_preference_toggle.py`
- **문제**: `prefs=None` 명시 호출이 default `{"food_preferences":[...]}`로 덮어쓰여 C4 케이스 테스트 불가
- **해소**: PR-V1.5.1 — `_SENTINEL = object()` 패턴 적용 (`1892b50`)
- **검증**: `test_preference_toggle.py` 18/18 PASS

### QA P3 — alembic 마이그 ALTER constraints sqlite 미지원 ✅
- **문제**: 7 마이그 파일이 `op.alter_column`·`op.drop_constraint`·`op.create_unique_constraint` 직접 사용 → sqlite `NotImplementedError: No support for ALTER of constraints in SQLite dialect`
- **해소**: PR-V1.5.2 — 7 파일 `with op.batch_alter_table(...) as batch_op:` 패턴 적용 + test seed NOT NULL 보강 (`aaec29d`)
- **검증**: **pytest 12 파일 91/91 PASS** (이전 19/30 → 91/91)

---

## 🟠 잔존 P1 (사용자 결정)

### BUG-1 — WSL python에 playwright 미설치, .gstack-demo.py 실행 불가
- **발견**: QA dry-run v1 (2026-05-15)
- **위치**: WSL `/usr/bin/python3` (호스트 Python)
- **재현**: `python3 .gstack-browser-launch.py` (WSL 셸)
- **기대**: chromium이 CDP 9222로 띄워짐
- **실제**: `ModuleNotFoundError: No module named 'playwright'`
- **원인**: `.venv`가 Windows path layout (`Scripts/`), WSL `/usr/bin/python3`에 playwright·pip 모두 없음, sudo 권한 부재
- **처리 방향 (사용자 결정 2026-05-15)**:
  - **WSL에서 강제로 환경 정리 X**
  - 시연은 Windows PowerShell + `.venv\Scripts\python.exe`로 진행
  - QA agent는 Playwright MCP·CLI로 대체 검증
- **상태**: 해결 안 함 (의도된 환경 분리). 메모리에 운영 규칙으로 영구 저장 (`feedback_qa_runtime_role.md`)
- **심각도**: P1 (시연 영향 없음, 단 WSL 환경 dry-run 차단)

---

## 🟡 잔존 P2 / 알려진 한계

### LIMIT-1 — pytest-asyncio event_loop fixture deprecation
- **위치**: `backend/tests/conftest.py:19`
- **증상**: pytest 실행 시 `DeprecationWarning: event_loop fixture has been redefined`
- **영향**: 현재 동작 정상, future pytest 버전에서 에러 가능
- **해소 방법**: fixture에 `scope` 인자 사용 또는 `event_loop_policy` fixture
- **우선순위**: v1.6 backlog
- **심각도**: P2 (warning, 동작 영향 없음)

### LIMIT-2 — Q7-c C3 lightweight 비교 (휴리스틱)
- **위치**: `helpers/preference_toggle.py:_lightweight_speaker_matches_group`
- **증상**: home_base 일치 + food Jaccard ≥ 70%만 검사. 정확한 group vs speaker 결과 비교 X
- **영향**: false positive 가능 (실제로 다른 결과인데 동일로 간주 → 토글 차단)
- **해소 방법**: refresh 라우트에서 두 페이로드 계산 후 top-1 place_id 비교 (비용 ↑)
- **우선순위**: v1.6 backlog
- **심각도**: P2 (보수적 차단, 사용자 경험에는 영향 적음)

### LIMIT-3 — F1 외 0 슬롯 케이스 (현재 2개만)
- **위치**: `nodes/function_call.py` 0 슬롯 분기
- **증상**: PR-V1.5에서 `consent_zero`·`all_blocked` 2 케이스만 narrator 분기. 다른 케이스 (예: timezone 충돌) 미세분화
- **해소 방법**: spec §6.x 추가 케이스 식별 + 분기 추가
- **우선순위**: v1.6 backlog
- **심각도**: P2 (시연 외 corner case)

### LIMIT-4 — `_resolve_place_hint` 4-step이 단일 함수에 응축
- **위치**: `helpers/places.py:_resolve_place_hint`
- **증상**: spec §6.17은 4-step 명확 분기 권고하지만 코드는 단일 함수
- **영향**: 디버깅 시 어떤 step에서 결정됐는지 추적 어려움
- **해소 방법**: 4 step을 별도 함수 분리·로깅 추가
- **우선순위**: v1.6 backlog
- **심각도**: P2 (가독성)

### LIMIT-5 — Gemini 분기 disliked food defense-in-depth
- **위치**: `nodes/place.py` Gemini scoring 분기 (`>3 후보`)
- **증상**: Gemini가 prompt 무시 시 disliked 매장 점수 높게 줄 가능성
- **해소 방법**: Gemini 결과에도 disliked 검사 후 `final_score=0.0` 강제 가드 (P1 fast path와 동일)
- **우선순위**: v1.6 backlog
- **심각도**: P2 (Gemini 신뢰도 의존)

### LIMIT-6 — Playwright MCP가 자동 chromium 경로 발견 못 함 (해결됨)
- **상태**: 사용자가 2026-05-15 셋업 완료 (MCP 경로 재지정 + headless 등록 검토)
- **확인**: `browser_navigate http://localhost:3000` 성공, Page Title "매듭 (Maedeup)" 정상
- **QA v2 풀 검증 완료**: ACT 1→2→4→5 시나리오 자동 재현 PASS (room 72, meeting 88, 수담한정식 강남점 확정). 스크린샷 6장 저장.

### LIMIT-7 — `/api/v1/calendar/free-slots` 응답 1095ms (QA v2 발견)
- **위치**: backend free-slots 엔드포인트
- **증상**: Google Calendar 25 events fetch 시 1초+ 응답, 시연 시 첫 로드 지연
- **해소 방법**: Redis 캐싱 또는 월별 prefetch
- **우선순위**: v1.6 backlog
- **심각도**: P2 (시연 영향 적음, UX 한 박자 늦음)

### LIMIT-8 — favicon.ico 404로 console error 1건 (QA v2 발견)
- **위치**: `localhost:3000/favicon.ico`
- **이전 NON-BUG-3과 중복**, QA v2에서 시연 영상 cleanliness 관점 P3로 재확인
- **해소 방법**: `frontend/public/favicon.ico` 추가
- **우선순위**: v1.7 또는 무시

### LIMIT-9 — F4 narrator 백엔드 미구현 (Q17=A spec only, QA v3 발견)
- **위치**: `backend/app/api/routes/meetings.py` 캘린더 sync 분기 + spec `spec-common.md` Q17·§9.7
- **증상**: spec/DECISIONS는 Q17=A 실명 narrator "OOO님 캘린더 권한이 만료됐어요"를 확정으로 등록했으나, 실제 백엔드에 해당 문자열이 **존재하지 않음** (grep 결과 0건)
- **영향**: 시연 시 F4 시나리오에서 narrator 말풍선이 자동으로 안 뜸. 발표자 멘트로만 흡수 가능
- **해소 방법**: `meetings.py` 캘린더 sync 분기에 `f"{name}님 캘린더 권한이 만료됐어요"` narrator emit 추가 (Q15=A 일관, narrator emit 헬퍼 재사용)
- **우선순위**: **v1.6 backlog #13** (시연 후 우선 작업 후보)
- **심각도**: P2 (시연 영향 적음, spec 결정과 코드 불일치)

---

## ⚪ Non-bug (의도된 동작)

### NON-BUG-1 — Stalemate 후 agent 응답 미발생 (구독자 없을 때)
- **현상**: agent WS 미구독 상태에서 stalemate trigger → Redis pubsub publish는 발생하나 consumer 없으면 vote_card 미생성
- **이유**: Redis pubsub은 휘발성, 영속화 안 함. 시연 시 브라우저 항상 떠있어서 항상 구독자 있음
- **시연 영향**: 0 (시연자 브라우저 = 구독자)
- **개선 후보 (v2)**: trigger 영속화 (DB outbox 패턴) — 단 시연 통과 우선

### NON-BUG-2 — `KAKAO_API_KEY is not set` 경고
- **위치**: `docker compose ps` 시 stdout
- **이유**: docker-compose.yml의 `${KAKAO_API_KEY}` 호스트 변수 참조 — 호스트 환경에 없음
- **실제**: 컨테이너 내부 `.env`에 `KAKAO_REST_API_KEY` 설정됨 (시연 동작 OK)
- **해소 옵션**: docker-compose.yml에서 `KAKAO_API_KEY` 참조 제거 또는 사용자 호스트 환경변수 추가

### NON-BUG-3 — favicon.ico 404
- **위치**: `localhost:3000/favicon.ico`
- **영향**: cosmetic, 시연 화면에 안 보임
- **우선순위**: v1.7 또는 무시

### NON-BUG-4 — `0.1 -> 0.0` 점수 변경 (PR-V1.5 hotfix)
- **위치**: `nodes/place.py:263-270`
- **현상**: disliked 매장 점수가 0.1 → 0.0으로 강화
- **이유**: Codex P1 수정으로 final_score 정렬 보장
- **영향**: 사용자에게 표시되는 score 약간 변경, 정렬 효과만 강화

---

## 수정 우선순위 종합

### 시연 직전 (P0): 없음 ✅

### 시연 후 (P1):
- BUG-1 환경 정리 (사용자 영역, WSL 시도 X)

### v1.6 backlog (P2):
- LIMIT-1 pytest-asyncio fixture
- LIMIT-2 C3 정확한 비교
- LIMIT-3 0 슬롯 케이스 추가
- LIMIT-4 `_resolve_place_hint` 분기 분리
- LIMIT-5 Gemini disliked 가드

---

## QA dry-run v2 진행 중 (백그라운드)

Playwright MCP로 ACT 1·2·4·5 단계별 재현 검증. 도착 시 추가 버그 발견 가능. 본 문서 갱신 예정.
