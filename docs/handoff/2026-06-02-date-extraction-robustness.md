# 2026-06-02 — 날짜추출 견고성 (브랜치 feat/date-extraction-robustness)

> 문제 제기(사용자): "다음주 토요일 빼고 다 바빠"처럼 자유 채팅의 거부/선호 날짜가 제대로 추출되는가?
> 측정 결과 **NO** — 거부 날짜의 ~85%를 놓침. 프롬프트 땜질은 whack-a-mole이라 구조를 재설계.
> 전시용이므로 전시 후 미루지 않고 끝까지 완성. main 미병합(별도 브랜치, 자율 푸시).

## 진단 (Phase ①)
- eval set 103발화(single/multi/complement/relative/preferred/mixed/edge) + gold 적대 검증. 기준일 2026-06-02(화).
- 현재 entity.py rejected_dates 베이스라인: **ALL F1 0.22, recall 0.15, exact 0.34**. 여집합(complement) exact **0.10**.
- 원인: 단일 LLM이 의도이해+날짜계산+여집합생성을 한 번에 → brittle. 결과를 검증 없이 `_filter_out_rejected`로 필터.
- 파일: `docs/handoff/eval/` (evalset, baseline, integrated, README), 하니스 `backend/_eval_date_extraction.py`.

## 구조 재설계 (Phase ③) — `helpers/date_classify.py`
2단계: **LLM은 '가용성 제약' 구조만**(범위·요일·극성·예외), **날짜 enumerate/여집합 확장은 코드가 결정적으로**.
라벨 달력(ISO+요일+오늘/내일/이번주 태그) 제공 → LLM 날짜 산술 환각 제거. 'X 빼고 다 바빠'는 코드가 그 주에서 X만 빼고 채움.
- 프롬프트 반복 v1~v6: enumerate(v1) → 정밀도 규칙(v2) → 구조화(v3) → 여집합/직접거부 구분(v4) → 라벨달력(v5) → 'can-come' 멘탈모델+자기검증(v6).
- 통합: entity.py 두 경로(`_extract_entities_from_context` 래퍼 + `pre_extracted_signals` 분기) 모두에서 날짜 단서 있을 때 rejected_dates 덮어씀. latency 게이트(`_DATE_SIGNAL_RE`), 실패 시 기존값 유지.

### 결과 (통합 경로 재측정)
| cat | F1 (base→new) | exact (base→new) |
|---|---|---|
| **ALL** | **0.22 → 0.62** | **0.34 → 0.62** |
| complement(여집합) | 0.16 → 0.78 | **0.10 → 0.70** |
| mixed | 0.14 → 0.91 | 0.07 → 0.93 |
| multi | 0.28 → 0.68 | 0.23 → 0.54 |
| single | 0.48 → 0.63 | 0.43 → 0.71 |
| relative | 0.16 → 0.49 | 0.07 → 0.29 |
recall 0.15 → 0.63. 여집합 exact 0.10→0.70이 핵심.

## 안전망 (Phase ②) — reflect-back
거부 2개+(비자명 해석) 시 "📅 일정을 이렇게 이해했어요 — 어려운 날: 6/8(월)·… 제가 잘못 봤으면 알려주세요" narrator를 emit.
잔여 ~38% 오차가 조용히 반영되는 대신 가시화 → 예측 못한 입력도 사용자가 교정. 단일 거부는 생략(노이즈), 최근 메시지 dedupe.

## 검증
- eval 통합 경로: 위 표.
- 데모 회귀(`.gstack-demo.py --fast`) **3회 연속 GREEN**: 분류기 발동(rejected=6) + reflect-back 발동 + "모임 생성 완료". ACT2 18→22~25s(분류기 LLM 추가, 60s 폴링 내).
- 단위 테스트 40 passed(entity/date/pipeline), 전체 import OK.

## 잔여/후속
- relative/edge가 상대적 약점(F1 0.49/0.27). reflect-back이 보완하나 추가 개선 여지.
- 추출기 2개(conversation_analyzer + entity) 중 rejected_dates는 date_classify가 단일 진실이 됨(entity가 override). conversation_analyzer의 rejected_dates 로직은 이제 superseded — 후속 정리 가능.
- 분류기 LLM 호출 1회 추가(date 단서 메시지 한정). latency 민감 시 entity 메인 추출과 병합 검토.
- 커밋: 6813b59(①) · 2aff55e(③) · 76fa191(②). main 미병합 — 리뷰 후 머지.
