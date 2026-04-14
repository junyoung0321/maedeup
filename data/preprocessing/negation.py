"""STEP 1-3a. 부정 탐지 (규칙 기반)

- 부정어: 안, 못, 없, 아니, 별로, 안되, 못하
- scope: 부정어 기준 앞 1어절 + 뒤 2어절 범위 내 감성어 극성 플립
- 출력: 각 형태소에 negated=True/False 부여
"""

import re

# 부정어 패턴
NEGATION_WORDS = {"안", "못", "없", "아니", "별로"}

# 부정 접두 패턴 (형태소 분석 후에도 남는 부정 표현)
NEGATION_PREFIXES = {"안", "못", "불", "비", "무"}

# 부정 scope: 부정어 앞 1토큰, 뒤 2토큰
SCOPE_BEFORE = 1
SCOPE_AFTER = 2


def detect_negation(morphemes: list[dict]) -> list[dict]:
    """형태소 리스트에 negated 플래그 추가.

    입력: [{"form": "맛있", "tag": "VA"}, ...]
    출력: [{"form": "맛있", "tag": "VA", "negated": True}, ...]

    규칙:
    - 부정어(안/못/없/아니/별로) 발견 시
    - 앞 1토큰 + 뒤 2토큰 범위의 감성어(VA, XR, MAG)에 negated=True
    """
    result = []
    neg_positions = set()

    # 1단계: 부정어 위치 찾기
    for i, m in enumerate(morphemes):
        form = m["form"]
        if form in NEGATION_WORDS:
            neg_positions.add(i)

    # 2단계: 부정 scope 내 감성어에 negated 표시
    negated_indices = set()
    sentiment_tags = {"VA", "XR", "MAG"}

    for neg_idx in neg_positions:
        start = max(0, neg_idx - SCOPE_BEFORE)
        end = min(len(morphemes), neg_idx + SCOPE_AFTER + 1)
        for j in range(start, end):
            if j == neg_idx:
                continue
            if morphemes[j]["tag"] in sentiment_tags:
                negated_indices.add(j)

    # 3단계: 결과 생성
    for i, m in enumerate(morphemes):
        result.append({
            **m,
            "negated": i in negated_indices,
        })

    return result


def has_negation(morphemes: list[dict]) -> bool:
    """리뷰에 부정 표현이 있는지 여부."""
    return any(m["form"] in NEGATION_WORDS for m in morphemes)


def get_negation_summary(morphemes_with_neg: list[dict]) -> dict:
    """부정 탐지 요약 통계."""
    total = len(morphemes_with_neg)
    negated = sum(1 for m in morphemes_with_neg if m.get("negated", False))
    neg_words = [m["form"] for m in morphemes_with_neg if m["form"] in NEGATION_WORDS]
    negated_targets = [
        m["form"] for m in morphemes_with_neg if m.get("negated", False)
    ]
    return {
        "has_negation": bool(neg_words),
        "negation_words": neg_words,
        "negated_targets": negated_targets,
        "negated_ratio": negated / total if total > 0 else 0,
    }
