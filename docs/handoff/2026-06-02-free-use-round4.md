# 2026-06-02 — 자유 사용 감사 라운드 4 (정책 결정 5건 구현)

> 선행: `2026-06-02-free-use-round3.md`. 사용자가 8개 정책 항목 중 결정한 방향대로 구현.
> 결정: A=소유권이양 / B=동점안내 / C=1인 건너뛰기 / D=과반재계산 / E=현행유지 / F=재트리거억제 / G=측정후.
> 전시 D-2. 전부 데모 happy path 미접촉(적대적 검증).

## 적용 (5건, commit 72c3676)
| # | 결정 | 파일 | 핵심 |
|---|---|---|---|
| #11+#20 | A 소유권 이양 | `rooms.py` | 호스트 leave 시 활성 모임 cancel 대신 가장 오래된 남은 멤버에게 created_by+role=owner 이양. host_transferred WS |
| #31 | B 동점 안내 | `meetings.py` | 최다득표 옵션 ≥2면 자동 단일선택 금지 → vote_tie 안내(호스트 직접 선택). vote_update에 tie 필드 additive |
| #58 | C 1인 건너뛰기 | `vote_card.py`, `scheduling_round.py` | member<2면 vote_card skip+안내, is_majority_reached/majority_reached_for에 eligible<2 가드 |
| #19 | D 과반 재계산 | `scheduling_round.py`, `meetings.py` | host_confirm에 eligible_override(keyword, non-breaking) — 확정 시점 RoomMember 수로 재계산 |
| #41 | F 재트리거 억제 | `agent.py` | 활성 confirmed 모임 존재 시 자동 트리거(stalemate/all_members) 억제+안내. direct_request 미접촉 |

보류: **E #39**(현행 유지), **G #30**(측정 후 결정).
프론트 동반 보류분: 소유권 실시간 리렌더, 동점 UI·재투표 가드 완화, 재트리거 인터랙티브 다이얼로그.

## 검증
- py_compile 5/5 · restart healthy · 모듈 import OK
- 스모크: #31 동점감지(만장일치→tie=False) · #58/#19 과반(solo eligible<2 차단·override 재계산·데모 4인 케이스) PASS
- 타깃 테스트 격리 실행: **finalization 15 + scheduling_round 34 + availability_majority 9 = 모두 통과**

## ⚠️ 테스트 관련 중요 발견
1. **#07(라운드3 host-only)이 기존 테스트를 깸**: `test_confirm_succeeds_for_member`(비호스트 멤버 확정 성공 기대)가 403 host_only로 실패. 이는 "멤버 누구나 확정"이 **의도된 설계였음**을 확인 — 사용자 승인된 #07이 이를 뒤집음. host-only 동작 반영해 `test_confirm_rejects_non_host_member`로 갱신(commit 포함).
2. **refresh 4건은 사전존재 실패**: `test_refresh_*` 4건이 `422 toggle_disabled`(발화자 선호/공유동의 미설정)로 실패. **baseline(408fe0a, 모든 free-use 변경 이전)에서도 동일 실패** → 본 감사와 무관한 기존 red 테스트(픽스처가 선호/동의 데이터 미설정).
3. **전체 스위트 격리 이슈**: 전체 `pytest` 시 ~40 실패(개별 실행 시 통과하는 파일 포함) — 공유 Redis/DB 상태 오염. HEAD(round4 제외) 41 fail vs round4 적용 40 fail → **본 변경은 실패를 늘리지 않음**(오히려 #07 테스트 수정으로 −1).

## 누적 (자유 사용 감사 전체)
라운드1(d1ddba0) 8 + 라운드2(c9e0ef4) 9 + 라운드3(3dd9b14+8207117) 7 + 라운드4(72c3676) 5 = **총 29건 적용**.
미적용: E #39·G #30(보류), K2 회귀위험 정규식(#21/#49/#47/#32/#29), defer-frontend(#13/#15/#22/#46/#28/#37/#56/#61).

## 다음
- 라운드4는 아직 **미푸시**(rounds1~3는 origin/main push 완료, HEAD ddd08cb까지).
- 전시 전 `.gstack-demo.py` 데모 회귀 1회 강력 권장(권한·vote·confirm 경로 다수 변경).
