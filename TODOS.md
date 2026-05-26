# TODOS — 매듭 프로젝트

> 최종 갱신: 2026-05-16
> 기준: Option C 라운드 1~9 완성 + CalendarPane 배지 제거 + ACT 2 자연 표현 + 시나리오 정합성 7건 fix (HEAD `4a98d2f`) push 완료
> 이전 버전(When2Meet 1건만) 폐기.

---

## 0. 시연 준비 [P0 최우선 — 시연 D-6]

**시연 일정**: 2026-05-22 (금) 점심 발표 (D-6 기준, 2026-05-16 현재)
**영상 촬영**: 2026-05-18 (월) 예정

### 시연 D-1 체크리스트 (2026-05-21 목 실행)

- [ ] Docker 4 컨테이너 healthy 확인 (`sg docker -c "docker compose ps"`)
- [ ] `.gstack-demo-token` 파일 최신 JWT 갱신
- [ ] Personal Data 시드: `python backend/scripts/seed_demo_personal_data.py --room <ID>`
- [ ] 캘린더 busy 시드: `python backend/scripts/seed_demo_calendar_busy.py`
- [ ] 전체 시연 dry-run 1회 (`.gstack-demo.py`)
- [ ] ACT 2 날짜 표현 발표일 기준 수정 확인 (`DEMO_TARGET_DATE`, `8b03c04`)
- [ ] 스크린샷 확인 (TimeBar + "이 시간으로 확정" 버튼 노출)

---

## 1. v2 spec 본문 작성 [P0 — 시연 통과 후 즉시]

**의존**: 시연(2026-05-22) 통과 → retrospective 회의 → Q18~Q25 결정 라운드 후 시작 권고.
**SoT**: `docs/handoff/2026-05-14-spec-v2-plan.md` (38항목, 10 카테고리, PR-v2.0~v2.5 분할안)

| PR 단계 | 내용 | 예상 분량 | 신규 Q |
|---|---|---|---|
| PR-v2.0 | §1 개요·변경 사항·§7 Q18~Q25 후보 등록 | ~150줄 | — (시연 회고 후) |
| PR-v2.1 | §3 시연 후 보완 (해결점 P·O·ACT 4·5) + 회귀 테스트 I2 | ~200줄 | Q18·Q19·Q20·Q21 결정 |
| PR-v2.2 | §4 PIPA·보안 (계정삭제·GCal revoke·k-anonymity·audit_log·OAuth 암호화) | ~300줄 | Q22·Q23 결정 |
| PR-v2.3 | §5 추천 plumbing P1 (room_member_home_bases·previous_recommendations·urgency·score 공식) | ~200줄 | Q25 결정 |
| PR-v2.4 | §6 Out of scope 일부 (recurring·다중 모임 겹침·영어 fallback) | ~250줄 | Q24 결정 |
| PR-v2.5 | §9 v3 backlog (P2 12건) + §10 부록 v1↔v2 매핑 | ~150줄 | — |

신규 Q-시리즈 요약 (Q18~Q25): `spec-v2-plan.md §4` 참조 (번복 정책·게스트 매핑·정규식 fix 방향·confirm 후속 분류·audit_log 스키마·OAuth 암호화 방식·recurring 스키마·점수 가중치)

---

## 2. 해결점 O 구현 [P0 — 시연 후 우선]

**문제**: AI 패널 직접 요청 경로에서 채팅방 누적 거부 발언이 vote_card 후보 필터에 반영 안 됨.
**원인**: `_pattern_extract_entities`가 `rejected_dates` 키를 초기화하지 않고, shortcut 조건(date_hints≥2 또는 date+place 동시 존재) 충족 시 Gemini 호출 스킵 → 거부 날짜 빈 채로 진행.
**SoT**: `docs/handoff/audit-findings.md` 해결점 O (line 971~1001)
**권고 수정안**: 옵션 B — shortcut 조건에 "context에 거부 키워드(`안 돼`/`못 가`/`힘들어`/`패스`) 없을 때" AND 조건 추가 (~10분, completeness 9/10).
**연관 테스트**: spec §10.8 I2 (해결점 O 회귀 케이스) — `spec-v2-plan.md` I2 항목

---

## 3. 해결점 P 정교화 [P0 — 시연 후 우선]

**문제**: 채팅 자연어 거부(`"5월 8일 안돼"`)가 vote_card 후보에서는 제외되지만 캘린더 UI의 "X/Y 가능" 카운트는 갱신 안 됨. "AI가 채팅 읽고 캘린더까지 자동 갱신" 데모 가치가 높아 v2 magical moment 후보.
**위치**: `_analyze_conversation`이 이미 `signals.rejected_dates` 추출 중. 이를 `record_unavailable_toggle(room_id, user_id, date, unavailable=True)`에 매핑하는 호출 없음.
**SoT**: `docs/handoff/audit-findings.md` 해결점 P (line 1004~1029)
**결정 필요**:
- Q18: 번복 처리 — "아 8일 되네" 발언 시 자동 clear(A) vs 명시 토글(B) vs hybrid(C)
- Q19: 이름→user_id 매핑 실패 시 — skip(A) vs 전체 멤버 적용(B) vs 호스트만(C)
**연관 테스트**: spec §10.8 I2 (해결점 P 회귀 케이스)

---

## 4. ACT 4 confirm 후속 메시지 / ACT 5 quick_classify 보강 [P1 — 다음 세션]

**문제 1 (ACT 4)**: maedeup_card 발행 후 사용자가 "취소할게요" / "장소 바꾸고 싶어" 등을 입력하면 현재 파이프라인이 confirm 이후 의도 분류 분기 없음.
**문제 2 (ACT 5)**: `quick_classify` 정규식이 SCHEDULE/PLACE 2종만. "강남 한식 추천해줘" 같은 합성 표현에서 분류 실패 시 일반 응답으로 fallback.
**SoT**: `CLAUDE.md` 미해결 backlog, `spec-v2-plan.md` A3 항목
**결정 필요**: Q21 — confirm 후속 분류 방식 (A: 새 직진 분기 / B: quick_classify 확장 / C: confirm_followup 노드 신설)

---

## 5. LIMIT-7 free-slots 캐싱 / LIMIT-8 favicon [P1/P3]

**LIMIT-7** [P1]: `/api/v1/calendar/free-slots` 응답 1095ms (QA v2 발견). Google Calendar 25 events fetch 비용.
- **해소 방향**: Redis 캐싱 (TTL 5~10분) 또는 월별 prefetch
- **SoT**: `docs/BUGS.md` LIMIT-7, `docs/TODO.md` v1.6 backlog #10

**LIMIT-8** [P3]: `frontend/public/favicon.ico` 없음 → console error 1건 (cosmetic).
- **해소**: 아이콘 파일 추가 (`frontend/public/favicon.ico`)
- **SoT**: `docs/BUGS.md` LIMIT-8

---

## 6. F4 narrator 백엔드 구현 (LIMIT-9) [P1 — 다음 세션]

**문제**: `spec-common.md` Q17=A로 "OOO님 캘린더 권한이 만료됐어요" narrator 문구 확정됐으나, `backend/app/api/routes/meetings.py` 캘린더 sync 분기에 해당 emit 코드 존재하지 않음 (grep 0건).
**해소**: `meetings.py` sync 분기에 `f"{name}님 캘린더 권한이 만료됐어요"` narrator emit 추가 (Q15=A 일관, 기존 narrator emit 헬퍼 재사용, ~5줄).
**SoT**: `docs/BUGS.md` LIMIT-9, `docs/TODO.md` v1.6 backlog #13, `spec-v2-plan.md` F1 항목

---

## 7. v1.6 backlog (Codex·QA 후속 권고) [P1~P3]

`docs/TODO.md` v1.6 backlog 15항목 참조 (이 파일이 상세 SoT). 주요 항목 요약:

| # | 항목 | 우선순위 |
|---|---|---|
| 1 | Gemini 분기 disliked food final_score=0.0 가드 | P1 |
| 2 | `preference_common_foods` union → 70% 교집합 | P1 |
| 3 | `_load_group_preference_context` helpers/preferences.py 이동 | P1 |
| 6 | `rejected_places` cap 적용 (메모리 leak 방지) | P1 |
| 10 | free-slots 1095ms — Redis 캐싱 (LIMIT-7) | P1 |
| 13 | F4 narrator 백엔드 구현 (LIMIT-9, → 본 문서 §6) | P1 |
| 4,5 | alembic '{}'::json 패턴 잔존 + pytest-asyncio deprecation | P2 |
| 12 | favicon.ico 추가 (LIMIT-8) | P3 |

---

## 8. When2Meet 프라이버시 [P2 backlog — InfoPane 대개편 후]

**What**: `detail_date` 파라미터가 멤버별 시간대 busy periods를 노출. 상용화 시 프라이버시 동의 UI 필요.
**Why**: 현재 캘린더 API는 날짜별 이름만 노출하지만 `detail_date`는 시간대별 바쁜 시간 공개. 졸업 데모에서는 문제없지만 민감 데이터.
**Depends on**: InfoPane 대개편 완료 후 진행.
**SoT**: 구 `TODOS.md` (2026-04-14 이전 항목 계승)

---

## 9. 메타 문서 갱신 [P1 다음 세션]

| 항목 | 내용 | 우선순위 |
|---|---|---|
| `HANDOVER.md` 추가 갱신 | 시연 결과 반영 (시연 통과·실패·발견 이슈) | P1 (시연 후) |
| `CLAUDE.md` "현재 task" 갱신 | 시연 후 보완 항목 → v2 spec 작업으로 전환 | P1 (시연 후) |
| `docs/SESSION_STATE.md` 갱신 | compact 후 컨텍스트 복구 파일 최신화 | P1 (다음 세션 시작 시) |
| `chore/claude-subagents` 처리 | main 으로 PR 만들지 결정 (sub-agents + repo hygiene 통합 PR) | P2 |

---

## 10. 코덱스 P1 backlog (자동 루프 라운드 4 후속) [P1~P2]

자동 루프 라운드 4 GREEN 도달 후 코덱스가 권고한 follow-up. SoT: `docs/handoff/2026-05-15-round4-green.md` §6.

| # | 항목 | 우선순위 | 위치 |
|---|---|---|---|
| 10.1 | `vote_update` payload 의 `user_votes` 를 `current_voter_user_id` + `current_voter_option_index` 만으로 좁히기 (개인정보 최소화) | P1 | `backend/app/api/routes/meetings.py:636`, `frontend/src/hooks/useAgentWebSocket.ts:57-64`, `frontend/src/components/meeting/VoteCardSection.tsx:113-119` |
| 10.2 | VoteCardSection 회귀 테스트 — pending-vote hydration·partial null 복귀·이중 마운트 방지 | P1 | `frontend/src/components/meeting/__tests__/VoteCardSection.*.test.tsx` 신규 |
| 10.3 | VoteCardSection mount 조건에 `timeConfirmed` phase 제외 추가 | P2 | `frontend/src/components/meeting/InfoPane.tsx:357` |
| 10.4 | `seed_demo_personal_data.py` 주석 정확화 — refresh route 그룹 비교는 `User.home_base` 가 아니라 `MeetingPreference.preferred_location` (또는 `MeetingPreference` seed 별도 추가) | P2 | `backend/scripts/seed_demo_personal_data.py` |
| 10.5 | refresh rerun `slot_context` 통일 — `default_place_hint`/`preference_common_foods` 주입해 route gate (`meetings.py:1105`) vs 카드 payload (`vote_card.py:315`, `place.py:416`) toggle 드리프트 방지 | P1 | `backend/app/api/routes/meetings.py:1167` |

**연관 SoT**: 라운드 4 코덱스 리뷰 (A1·A2·A4·C 모두 P1 권고 포함). v1.6 backlog 와 묶음 PR (`PR-V1.6`) 권고.

---

## 11. 장소 추천 vote 시스템 검토 [P1 backlog — v2 spec PR-v2.1 후보]

**배경**: 현재 장소 추천 카드는 AI 단방향 추천 (호스트가 확정). 멤버 선호도를 vote로 수렴하는 시스템이 v2 spec PR-v2.1 후보로 부상.
**검토 항목**:
- 장소 vote_card 페이로드 설계 (시간 vote_card와 구분 또는 통합)
- 멤버 vote 집계 → 최종 확정 흐름
- spec-place-recommendation.md §6 확장 여부
**연관**: `docs/handoff/2026-05-14-spec-v2-plan.md` A3 항목

---

## 다음 세션 진입 순서 (권고, 2026-05-16 갱신)

1. **시연 영상 촬영** (2026-05-18 월) — Option C 라운드 9 GREEN 기준, `python .gstack-demo.py`
2. **시연 D-1 리허설** (2026-05-21 목) — 본 문서 §0 체크리스트 실행
3. **시연 진행** (2026-05-22 금 점심)
4. **시연 직후**: retrospective 회의 → Q18~Q25 결정 라운드
5. **v2 spec PR-v2.0** 착수 (시연 결과 반영 후)
6. **해결점 O·P 코드 구현** (v2 PR-v2.1과 묶음 권고)
7. **코덱스 P1 backlog** (본 문서 §10) 묶음 PR-V1.6 으로 진행
8. **v1.6 backlog** (§7) 중 P1 항목 (F4 narrator·캐싱 등)
