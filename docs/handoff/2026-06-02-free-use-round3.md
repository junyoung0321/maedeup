# 2026-06-02 — 자유 사용 감사 라운드 3 (권한·rate-limit·guest 방어 7건)

> 선행: `2026-06-02-free-use-round2.md` (Docker 검증 + safe 패치 9건).
> 본 라운드: 사용자 승인(전시용 일괄처리) 하에 product-decision 중 권한/방어 7건 적용.
> 전시 D-2(2026-06-04 수). 전부 additive·데모 happy path 불변·함수 시그니처 불변.

## 방법
멀티에이전트 워크플로우(`wf_ed563d1c-7f8`): 7개 항목별 데모-안전 패치 생성 → 적대적 데모-행위자 검증.
게이트: 데모 실제 행위자(ACT3 **방장 확정**·**게스트 투표**, ACT5 host AI패널 1건)를 통과하는가 + rate-limit/guest 임계값이 데모 호출량·게스트수를 넉넉히 초과하는가 + 시그니처 무변경.
결과: confirmed 5 + 직접 처리 2(#10/#57). 상세 `2026-06-02-free-use-round3-findings.json`.

## 적용 (7건, commit 3dd9b14 + 8207117)
| # | 심각도 | 파일 | 내용 | 데모 안전 근거 |
|---|---|---|---|---|
| #02 | P1 | `core/rate_limit.py` + `ws/agent.py` | WS LLM 진입부 per-(room,user) budget `check_ws_llm_budget`(30/분, Redis INCR+EXPIRE, fail-open) 신설+agent.py:1101 와이어링 | host ACT5 1건 ≤ 30 (30배). 게스트는 social 채널→이 가드 미통과 |
| #07 | P1 | `routes/meetings.py` | confirm_meeting: proposal 없는 경로(meeting_id 승격/fresh INSERT)에 host-only(403) | ACT3 방장이 확정 (host==created_by) |
| #24 | P2 | `routes/meetings.py` | patch_meeting_place: cancelled 가드(409) + host-only(403) | ACT5 host가 장소 확정 |
| #45 | P2 | `routes/meetings.py` | vote_meeting: votes를 현 RoomMember 집합과 교차검증(stale 키 제거) + total_voters 동일 기준. **게스트 자격 유지** | 데모 투표자=게스트, 전원 현 멤버 → 카운트 불변 |
| #51 | P2 | `routes/meetings.py` | refresh: requester_user_id 방 멤버십 서버 교차검증 — 비멤버 위장 차단 | 정상 본인/방장 토글은 requester가 멤버라 통과 |
| #10/#57 | P1/P2 | `routes/rooms.py` | guest-join 방당 게스트 상한(20) — 무한생성·member_count 부풀림 차단. 같은 이름 재가입은 기존 user 재사용(상한 무관) | 데모 게스트 3명 << 20 (6.6배) |

검증: py_compile · restart healthy · 모듈 import · 스모크 — budget(5/30 한도·TTL·fail-open) PASS, guest-count 쿼리 실DB PASS.

## 보류 (방어심화/시그니처)
- **#10 IP단위 rate-limit**(옵션2, `request: Request` 파라미터 추가): FastAPI 자동주입이라 non-breaking이나 시그니처 변경이라 방어심화로 전시 후. 방당 게스트 상한이 핵심 방어를 커버.

## ⚠️ 권장 — 전시 전 데모 회귀 1회 실행
이번 라운드는 **confirm/place/vote/guest-join 등 데모-크리티컬 경로의 권한**을 바꿨다. 코드·행위자 기준 검증은 통과했으나, 전시 전 `.gstack-demo.py` 1회 실행으로 ACT 0.5~5.5 GREEN을 최종 확인 권장(특히 ACT3 방장 확정 / ACT5 장소 확정 / 게스트 투표).

## 남은 product-decision (미적용 — 설계 결정 또는 K2 재측정 필요)
이들은 코드만으로 안전히 못 고침:
- **정책 결정 필요(동작 정의)**: #31 동점·번복(해결점 P) · #19 eligible_voters 재산정 · #58 1인 자동확정 · #11 호스트 leave 소유권 이전 · #20 호스트 퇴장 후 확정 트리거 · #30 confirm NX lock 의미 · #39 부분매듭 만료/리마인더 · #41 confirmed 방 재트리거 중복 pending
- **K2 회귀 위험(측정 동반)**: #21·#49 완곡거부/다중의도 정규식(해결점 O 인접) · #47 slot_filling 중 잡담 · #32 근무시간 밖 시각 · #29 rejected_places 같은지역 거부루프
- **defer-frontend**: #13/#15/#22/#46/#28/#37/#61/#56 (프론트+백 동반)

## 누적 (자유 사용 감사 전체)
- 라운드1(d1ddba0): 8건 / 라운드2(c9e0ef4): 9건 / 라운드3(3dd9b14+8207117): 7건 = **총 24건 적용**.
