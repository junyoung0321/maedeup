# 2026-05-27 — Silent fail audit + bug-26-g/f fix + 시연 GREEN

## 결론
- origin/main 갱신: `703a692 → 8ceffdb` (5 commits push). 모두 PM 자율 fix 트랙.
- 시연 GREEN 도달 (iteration 2, room=224, meeting=237). bug-26-g NameError 회귀 완전 해소, 첫 추천 메시지/slot patch narrator/maedeup summary 3개 시각 100% 일관.
- silent-fail audit 결과 P0 4건 가시화 + P1 15건 backlog 분류.

## 진행 흐름

| 단계 | 작업 | 결과 |
|---|---|---|
| 진단 | code-analyst 위임 — silent fail 패턴 전수 감사 | P0 4건 / P1 ~15건 / P2 ~17건 식별 |
| fix #1 | `f717b06 fix(silent-fail)` — BUG-26-4 동형 패턴 P0 4건 가시화 | social.py / entity.py / vote_card.py / place.py 의 `debug→warning` 또는 `pass→exception` 승격 |
| 시연 1차 | qa-runtime 위임 iteration 1 (room=222, meeting=235) | **RED** — bug-26-g fix 자체가 NameError silent swallow 로 미작동 (msg 1720 "6:00" 미갱신) |
| fix #2 | `8ceffdb fix(bug-26-g/f)` — `meeting_obj.id → pending_ms.id` 1줄 fix | slot.py:379, 386 의 정의 안 된 변수 참조 수정 |
| restart | `docker restart maedeup-api` — 두 fix 모두 컨테이너 반영 | health ok |
| 시연 2차 | qa-runtime iteration 2 (room=224, meeting=237) | **GREEN** — msg 1742/1744/1747 시각 100% 일관 |
| push | 5 commits → origin/main (사용자 승인) | `703a692..8ceffdb` |

## bug-26-f 정체 확정

어제 (2026-05-26) commit 라벨이 `bug-26-a/b/c/d/e/g/h` 로 f 가 점프. 흔적 추적 결과 reflog/docs/code/memory 어디에도 없음. 2nd 시연 GREEN 직전 분석으로 **bug-26-f = bug-26-g 회귀 자체** 로 확정. 즉 어제 commit 작성 시 NameError 가 silent swallow 로 묻혀 GREEN 통과했으나 실제로 미작동 → bug-26-g/f 통합 fix (`8ceffdb`) 로 본래 의도 (Redis recommend_msg_id GET+DELETE → chat_messages UPDATE → WS broadcast) 복원.

## silent-fail audit 발견 요약

총 36건 (bare except 0건, broad `except Exception` 149건 중 silent fail 패턴):
- **P0: 4건** (이번 commit `f717b06` 으로 가시화 완료)
  - `social.py:758-760` `_detect_and_notify_intent` 외층 117줄 try (BUG-26-4 직계)
  - `entity.py:296-297` Gemini 분기 `except Exception: pass`
  - `vote_card.py:407-408` narrator emit `debug swallow`
  - `place.py:514-515` narrator emit `debug swallow`
- **P1: ~15건** (next-commit 후보 A/B/C 시리즈로 분류)
  - **A**: `slot.py:454` VOTE_OPTIONS_PATCH 외층 warning (try 범위 30줄+, exc_info 누락)
  - **B**: `helpers/slots.py:118-119, 161-162, 485-486` google_calendar busy_periods + Redis 분기
  - **C**: `agent.py:213-215, 264-362, 868-872` snapshot/greeting/trigger 5건
- **P2: ~17건** (cleanup pass, fail-open rate limit, 의도된 fallback 등 후순위)

## 2nd 시연 GREEN 검증 핵심

`chat_messages` (room_id=224) 3개 narrator 시각:
| msg_id | content (요약) | 검증 |
|---|---|---|
| 1742 | "캘린더 확인 결과, 2026-06-08 19:30~21:00을(를) 추천드려요" | 첫 narrator |
| 1744 | "⏰ 2026-06-08 19:30~21:00로 조정했어요" | slot patch (bug-26-e) |
| 1747 | "✨ 매듭 완성! 6월 8일 (월) 오후 7:30 진미평양냉면 별관에서 만나요" | maedeup summary (bug-26-b) |

`[BUG-26-G] recommend msg id=1742 content updated` 로그 정상 출력 → Redis GET+UPDATE+broadcast 흐름 NameError 없이 통과.

silent-fail fix 부작용: ERROR 0, Traceback 0, 신규 hidden bug 0건.

## 미해결 backlog (오늘 발견, 다음 트랙)

### P1-1: vote_options 부분 patch
`meeting_schedules.id=237` 의 vote_options 5개 슬롯 중 slot-37 (선택된 슬롯) 만 새 라벨 (`2026-06-08 19:30~21:00`), 나머지 4개 (slot-36/38/49/50) 는 옛 라벨 (`6월 8일 (월) 오후 6:00`) 그대로. bug-26-e 의 의도 (선택된 슬롯만 patch) 일 가능성 큼 — spec 결정 필요. vote_card 미리 닫힌 상태로 회귀 시 6:00 슬롯 다시 보이면 P0 격상 가능.

### P1-2: vote_options TZ aware/naive 혼재
- slot-37: `"2026-06-08T19:30:00"` (naive, KST 직접 저장)
- 나머지 4개: `"2026-06-08T11:00:00+00:00"` (aware UTC)

CLAUDE.md 컨벤션 (`datetime 은 naive UTC`) 위반 후보. root cause scope 분석 중 (code-analyst 위임). 옵션 A (좁음, slot patch 만 aware UTC 통일) vs B (깊음, 빌더 전체 naive UTC 회복) 선택 예정.

### silent-fail P1 backlog (다음 commit 트랙)
A → B → C 시리즈 순차 진행. 각 commit 후 시연 검증.

## 학습

### Silent fail 함정의 본질
BUG-26-4 (cfg/timeout NameError) + bug-26-g (meeting_obj NameError) 모두 동일 패턴 — try 범위 30줄+ 에 `except Exception: debug/warning` 로 NameError 같은 코드 버그가 무음 swallow. 시연 자동화 stdout 만 보면 영원히 안 잡힘. fix 자체에도 같은 함정 (slot.py:454 의 외층 warning) 이 있어 fix 후에도 silent fail 가능성 존재 — silent-fail audit P1 트랙으로 후속 정리.

### root cause vs surface fix
1줄 변수명 fix (`meeting_obj → pending_ms`) 가 본 case 의 root cause. silent-fail 가시화 (`debug → warning`) 도 패턴 자체 fix 라 root cause. 동일 패턴 다른 영역 재발 방지 효과. 사용자 룰 (2026-05-27 추가): **근본 해결 우선 + 자율 진행 강화** — feedback memory 저장.

### Remote Control 알림 트리거
2026-05-27 사용자 명시: rc 중에는 일반 텍스트 답변이 폰 알림 안 옴. AskUserQuestion 만 알림 트리거. turn 종료 시 후속 자동 활동 (백그라운드 에이전트 결과 알림 등) 없으면 무조건 AskUserQuestion 으로 폰 알림 트리거. feedback memory 저장.

## 산출물
- `commit f717b06` — silent-fail P0 4건 가시화
- `commit 8ceffdb` — bug-26-g/f NameError 회귀 fix
- `~/.claude/projects/-mnt-c-Users-cyun0-git-maedeup/memory/feedback_askuserquestion_for_rc_notification.md` — rc 알림 룰
- `~/.claude/projects/-mnt-c-Users-cyun0-git-maedeup/memory/feedback_root_cause_over_surface_fix.md` — 근본 해결 우선 룰

## 다음 task (D-8 = 2026-06-04 전시)
1. P1-2 TZ root cause fix (code-analyst 분석 결과 받고 결정)
2. silent-fail P1 A 트랙 — `slot.py:454` 외층 try 범위 축소 (회귀 방지 강화)
3. silent-fail P1 B 트랙 — `helpers/slots.py` google_calendar busy_periods + Redis
4. silent-fail P1 C 트랙 — `agent.py` snapshot/greeting/trigger
5. P1-1 spec 결정 — vote_options 전체 슬롯 라벨 정규화 여부
6. 전시 환경 한계 brainstorm 재개 (보류 상태, 사용자 합의 후 design doc → writing-plans)
7. 시연 영상 촬영 (날짜 TBD — handoff 2026-05-26 = 5/18 권고, qa-runtime 보고 = 5/30 권고. 사용자 확정 필요)
