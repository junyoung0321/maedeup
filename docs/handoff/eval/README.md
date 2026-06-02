# 날짜추출 평가셋 (date-extraction eval)

free-use 환경에서 채팅 발화 → 가능/불가 날짜 추출 정확도를 측정하는 평가셋·하니스.

## 파일
- `date-extraction-evalset.json` — 103개 발화 + gold(unavailable/available/preferred). 기준일 **2026-06-02(화)**. 7카테고리(single/multi/complement/relative/preferred/mixed/edge). gold는 생성 후 독립 에이전트가 적대적 재도출·검증(corrected 1, dropped 1).
- `baseline-result.json` — 현재 entity.py 추출의 rejected_dates 측정 결과.
- `../../../backend/_eval_date_extraction.py` — 측정 하니스.

## 실행
```bash
docker cp docs/handoff/eval/date-extraction-evalset.json maedeup-api:/tmp/evalset.json
MSYS_NO_PATHCONV=1 docker exec maedeup-api python /app/_eval_date_extraction.py \
  | grep '^EVAL_RESULT=' | sed 's/^EVAL_RESULT=//' > docs/handoff/eval/<name>.json
```

## 베이스라인 (2026-06-02, 현재 entity.py)
| cat | n | P | R | F1 | exact |
|---|---|---|---|---|---|
| ALL | 103 | 0.449 | **0.148** | 0.222 | 0.340 |
| complement | 20 | 0.625 | 0.089 | 0.156 | 0.100 |

**문제**: 전체 recall 0.148 — 거부 날짜의 ~85% 누락. 여집합("X 빼고 다 바빠")·상대표현·혼합에서 특히 심각.
**원인**: LLM이 한 번에 의도이해+날짜계산+여집합생성을 하고, 결과를 검증 없이 필터. → enumerate+분류 구조로 전환(③).

## 통합 결과 (date_classify 적용, 2026-06-02)
| cat | n | P | R | F1 | exact |
|---|---|---|---|---|---|
| ALL | 103 | 0.61 | 0.63 | 0.62 | 0.61 |
| single | 14 | 0.52 | 0.79 | 0.63 | 0.71 |
| multi | 13 | 0.67 | 0.70 | 0.68 | 0.54 |
| complement | 20 | 0.81 | 0.75 | 0.78 | 0.70 |
| relative | 14 | 0.53 | 0.45 | 0.49 | 0.29 |
| preferred | 12 | 0.00 | 0.00 | 0.00 | 0.75 |
| mixed | 14 | 0.83 | 1.00 | 0.91 | 0.93 |
| edge | 16 | 0.30 | 0.25 | 0.27 | 0.38 |

**ALL F1 0.22→0.62, exact 0.34→0.62, complement exact 0.10→0.70.** 데모 회귀 GREEN(분류기 발동, 모임 생성 완료).