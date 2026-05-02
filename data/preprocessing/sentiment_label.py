"""STEP 1-5. 긍부정 레이블링 (평점 × 리뷰 일치도 기반)

리뷰 텍스트 감성과 장소 전체 평점을 비교하여 일치도(confidence)를 계산.

일치도 규칙:
  평점 긍정(≥4.0) + 텍스트 긍정  →  strong    (confidence=1.0)  강하게 학습
  평점 부정(≤2.5) + 텍스트 부정  →  strong    (confidence=1.0)  강하게 학습
  평점·텍스트 상충               →  conflict  (confidence=0.4)  약하게 학습
  어느 한쪽이 중립               →  neutral   (confidence=0.6)  보통 학습
  평점 정보 없음(0)              →  unknown   (confidence=0.5)

출력: output/preprocessed/sentiment_labels.json
  {
    "pid": {
      "text_sentiment": 0.45,       # 리뷰 텍스트 평균 감성 [-1, +1]
      "rating_pol":  1,             # 평점 극성 (+1/0/-1)
      "text_pol":    1,             # 텍스트 극성 (+1/0/-1)
      "consistency": "strong",      # strong/conflict/neutral/unknown
      "confidence":  1.0,           # 학습 신뢰 가중치
      "label_score": 0.45,          # text_sentiment × confidence
    }
  }

입력:
  output/preprocessed/sarcasm_reviews.json  (형태소 + 반어법 플래그)
  output/places.csv                          (장소 전체 평점)
"""

import json
import os
import logging

import pandas as pd

from preprocessing.absa import SENTIMENT_SCORES, NEGATION_FLIP_FACTOR
from preprocessing.io_utils import save_versioned

logger = logging.getLogger(__name__)

# ── 임계값 ──────────────────────────────────────────────────────────────
# 평점: 고정 임계값 대신 percentile rank 기반 (항상 50/50 분포 보장)
# percentile >= 0.5 → positive, < 0.5 → negative
TEXT_POS_THRESHOLD = 0.15     # 텍스트 긍정 기준 (노이즈 필터링 강화)
TEXT_NEG_THRESHOLD = -0.15    # 텍스트 부정 기준

CONFIDENCE_STRONG  = 1.0      # 평점 + 텍스트 일치
CONFIDENCE_NEUTRAL = 0.6      # 한쪽 중립
CONFIDENCE_WEAK    = 0.4      # 평점 + 텍스트 상충
CONFIDENCE_UNKNOWN = 0.5      # 평점 정보 없음


def _review_text_sentiment(morphemes: list[dict]) -> float:
    """형태소 리스트 전체에서 종합 감성 점수 계산 (속성 무관).

    반어법·중립 형태소는 score 0 → 자동 제외.
    """
    scores = []
    for m in morphemes:
        form = m.get("form", "")
        if form in SENTIMENT_SCORES:
            score = SENTIMENT_SCORES[form]
            if m.get("negated", False):
                score *= NEGATION_FLIP_FACTOR
            scores.append(score)

    if not scores:
        return 0.0
    avg = sum(scores) / len(scores)
    return max(-1.0, min(1.0, avg))


def _polarity(score: float) -> int:
    """점수 → 극성 (1 / 0 / -1)."""
    if score >= TEXT_POS_THRESHOLD:
        return 1
    if score <= TEXT_NEG_THRESHOLD:
        return -1
    return 0


def _rating_polarity(rating_pct: float | None) -> int | None:
    """평점 백분위 → 극성.
    percentile >= 0.5 → +1 (상위 50%), < 0.5 → -1 (하위 50%), None → 평점 없음.
    """
    if rating_pct is None:
        return None
    return 1 if rating_pct >= 0.5 else -1


def compute_place_sentiment_label(
    reviews: list[dict],
    rating_percentile: float | None,
) -> dict:
    """장소 단위 긍부정 레이블 계산.

    Parameters
    ----------
    reviews           : sarcasm_reviews.json 의 place["reviews"] 리스트
    rating_percentile : places.csv 전체 대비 평점 백분위 (0~1), 없으면 None
    """
    # ── 텍스트 감성: 반어법 제외 리뷰만 집계 ──────────────────────────
    text_scores = []
    for rev in reviews:
        if rev.get("sarcasm", {}).get("is_sarcastic", False):
            continue
        morphemes = rev.get("morphemes", [])
        if morphemes:
            text_scores.append(_review_text_sentiment(morphemes))

    # 감성어가 있는 리뷰만 평균
    nonzero = [s for s in text_scores if s != 0.0]
    text_sentiment = (sum(nonzero) / len(nonzero)) if nonzero else 0.0
    text_sentiment = round(max(-1.0, min(1.0, text_sentiment)), 3)

    text_pol   = _polarity(text_sentiment)
    rating_pol = _rating_polarity(rating_percentile)

    # ── 일치도 → confidence ────────────────────────────────────────────
    if rating_pol is None:
        consistency = "unknown"
        confidence  = CONFIDENCE_UNKNOWN
    elif rating_pol == 0 or text_pol == 0:
        consistency = "neutral"
        confidence  = CONFIDENCE_NEUTRAL
    elif rating_pol == text_pol:
        consistency = "strong"
        confidence  = CONFIDENCE_STRONG
    else:
        consistency = "conflict"
        confidence  = CONFIDENCE_WEAK

    label_score = round(text_sentiment * confidence, 3)

    return {
        "text_sentiment": text_sentiment,
        "rating_pol":     rating_pol if rating_pol is not None else 0,
        "text_pol":       text_pol,
        "consistency":    consistency,
        "confidence":     confidence,
        "label_score":    label_score,
    }


def process_all_sentiment_labels(
    sarcasm_path: str = "output/preprocessed/sarcasm_reviews.json",
    places_csv:   str = "output/places.csv",
    output_path:  str = "output/preprocessed/sentiment_labels.json",
    resume:       bool = True,
) -> dict:
    """전체 장소 긍부정 레이블 계산."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # resume: 기존 결과 로드
    existing = {}
    if resume and os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        logger.info(f"기존 처리 결과 로드: {len(existing)}곳 (재개 모드)")

    # 입력 로드
    with open(sarcasm_path, "r", encoding="utf-8") as f:
        sarcasm_data = json.load(f)
    logger.info(f"sarcasm_reviews 로드: {len(sarcasm_data)}곳")

    places_df = pd.read_csv(places_csv)
    # 평점 백분위 rank (rating > 0인 장소만 대상, pct=True → 0~1)
    rated = places_df[places_df["rating"] > 0].copy()
    rated["rating_pct"] = rated["rating"].rank(pct=True)
    rating_pct_map = dict(zip(rated["naver_place_id"].astype(str), rated["rating_pct"]))
    logger.info(f"places.csv 로드: {len(places_df)}곳 (평점 백분위 매핑, median≈{rated.rating.median():.2f})")

    todo = {pid: v for pid, v in sarcasm_data.items() if pid not in existing}
    logger.info(f"처리 필요: {len(todo)}곳")

    results = {}
    stats = {"strong": 0, "conflict": 0, "neutral": 0, "unknown": 0}

    for i, (pid, place) in enumerate(todo.items()):
        pct = rating_pct_map.get(str(pid), None)
        label = compute_place_sentiment_label(place.get("reviews", []), pct)
        results[pid] = {
            "place_name": place.get("place_name", ""),
            **label,
        }
        stats[label["consistency"]] = stats.get(label["consistency"], 0) + 1

        if (i + 1) % 500 == 0:
            logger.info(f"  [{i+1}/{len(todo)}] 처리 완료")

    # 저장
    existing.update(results)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    save_versioned(output_path)

    # 전체 통계
    all_stats = {"strong": 0, "conflict": 0, "neutral": 0, "unknown": 0}
    for v in existing.values():
        all_stats[v["consistency"]] = all_stats.get(v["consistency"], 0) + 1

    strong_pct  = 100 * all_stats["strong"]  / len(existing) if existing else 0
    conflict_pct = 100 * all_stats["conflict"] / len(existing) if existing else 0

    logger.info(
        f"긍부정 레이블 완료: {len(existing)}곳\n"
        f"  strong  (일치): {all_stats['strong']}곳 ({strong_pct:.1f}%)\n"
        f"  conflict(상충): {all_stats['conflict']}곳 ({conflict_pct:.1f}%)\n"
        f"  neutral (중립): {all_stats['neutral']}곳\n"
        f"  unknown (평점없음): {all_stats['unknown']}곳"
    )

    return {
        "places": len(existing),
        "strong": all_stats["strong"],
        "conflict": all_stats["conflict"],
        "neutral": all_stats["neutral"],
        "unknown": all_stats["unknown"],
        "output_path": output_path,
    }
