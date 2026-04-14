"""STEP 3. Feature 가공 — 장소 고정 feature 12개 + 감성 feature 4개

장소별 1회 계산 후 저장. 시나리오 의존 feature 8개는 STEP 4에서 계산.

입력:
- output/places.csv (기본 장소 데이터)
- output/preprocessed/absa_scores.json (감성 점수)

출력:
- output/features/place_features.csv (장소당 16개 feature)
"""

import json
import math
import os
import re
import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 프랜차이즈 패턴
CHAIN_PATTERNS = [
    r"스타벅스", r"투썸", r"이디야", r"메가커피", r"빽다방", r"컴포즈",
    r"맥도날드", r"버거킹", r"롯데리아", r"KFC", r"서브웨이",
    r"bbq|BBQ|비비큐", r"교촌|굽네|BHC|bhc",
    r"CU|GS25|세븐일레븐|이마트24",
    r"올리브영", r"다이소",
    r"본죽", r"죽이야기", r"한솥",
    r"파리바게뜨|뚜레쥬르|성심당",
    r"공차|타이거슈가|밀크티",
]
_CHAIN_RE = re.compile("|".join(CHAIN_PATTERNS), re.IGNORECASE)


def compute_place_features(
    csv_path: str = "output/places.csv",
    absa_path: str = "output/preprocessed/absa_scores.json",
    sentiment_label_path: str = "output/preprocessed/sentiment_labels.json",
    output_path: str = "output/features/place_features.csv",
) -> pd.DataFrame:
    """장소 고정 feature 12개 + 감성 feature 4개 계산."""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # ── 데이터 로드 ──
    df = pd.read_csv(csv_path)
    logger.info(f"CSV 로드: {len(df)}곳")

    with open(absa_path, "r", encoding="utf-8") as f:
        absa = json.load(f)
    logger.info(f"ABSA 로드: {len(absa)}곳")

    sentiment_labels = {}
    if os.path.exists(sentiment_label_path):
        with open(sentiment_label_path, "r", encoding="utf-8") as f:
            sentiment_labels = json.load(f)
        logger.info(f"sentiment_labels 로드: {len(sentiment_labels)}곳")
    else:
        logger.warning(f"sentiment_labels 없음 (run_sentiment_label.py 미실행): {sentiment_label_path}")

    # keyword_tags 파싱
    def parse_tags(x):
        if pd.isna(x):
            return []
        try:
            return json.loads(x)
        except (json.JSONDecodeError, TypeError):
            return []

    df["_tags"] = df["keyword_tags"].apply(parse_tags)

    # menu_prices 파싱 → 평균가
    def parse_avg_price(x):
        if pd.isna(x):
            return 0
        try:
            menus = json.loads(x)
            prices = [int(m["price"]) for m in menus if m.get("price") and str(m["price"]).isdigit()]
            return sum(prices) / len(prices) if prices else 0
        except (json.JSONDecodeError, TypeError, ValueError):
            return 0

    df["_avg_price"] = df["menu_prices"].apply(parse_avg_price)

    # ── Feature 1~3: 정량 지표 정규화 ──
    df["rating_norm"] = df["rating"] / 5.0

    max_review_log = math.log(df["review_count"].max() + 1) if df["review_count"].max() > 0 else 1
    df["review_count_log"] = df["review_count"].apply(lambda x: math.log(x + 1) / max_review_log)

    max_blog_log = math.log(df["blog_review_count"].max() + 1) if df["blog_review_count"].max() > 0 else 1
    df["blog_count_log"] = df["blog_review_count"].apply(lambda x: math.log(x + 1) / max_blog_log)

    # ── Feature 4: price_level (1~4 구간화) ──
    def price_level(avg_price):
        if avg_price <= 0:
            return 2  # 정보 없으면 중간값
        if avg_price < 8000:
            return 1
        if avg_price < 15000:
            return 2
        if avg_price < 30000:
            return 3
        return 4

    df["price_level"] = df["_avg_price"].apply(price_level)

    # ── Feature 5~9: mood 키워드 기반 ──
    # 네이버 themes는 대분류이므로, 원래 keyword_tags에서 세부 키워드 매칭
    # 현재 keyword_tags가 대분류(맛/분위기/서비스 등)이므로 부분 매칭
    mood_keywords = {
        "mood_quiet": ["조용", "아늑", "편안"],
        "mood_group": ["단체", "모임", "회식", "넓"],
        "mood_vibe": ["분위기", "감성", "인테리어", "예쁜"],
        "mood_budget": ["가성비", "저렴", "합리"],
        "mood_private": ["룸", "개인", "프라이빗", "독립"],
    }

    for feature_name, keywords in mood_keywords.items():
        df[feature_name] = df["_tags"].apply(
            lambda tags: 1 if any(kw in " ".join(tags) for kw in keywords) else 0
        )

    # ── Feature 10: is_chain ──
    df["is_chain"] = df["place_name"].apply(
        lambda x: 1 if _CHAIN_RE.search(str(x)) else 0
    )

    # ── Feature 11~12: category encoding ──
    # category_depth1: 대분류
    cat_map_depth1 = {"음식점": 0, "카페": 1, "술집": 2, "스터디": 3}
    df["category_depth1"] = df["category_group"].map(cat_map_depth1).fillna(0).astype(int)

    # category_depth2: 중분류 (category 컬럼에서 추출)
    def extract_depth2(cat_str):
        if pd.isna(cat_str):
            return "기타"
        parts = str(cat_str).split(">")
        if len(parts) >= 2:
            return parts[1].strip()
        return parts[0].strip()

    df["_depth2"] = df["category"].apply(extract_depth2)
    # 상위 빈도 20개만 유지, 나머지는 "기타"
    top_cats = df["_depth2"].value_counts().head(20).index.tolist()
    df["_depth2_clean"] = df["_depth2"].apply(lambda x: x if x in top_cats else "기타")
    depth2_map = {cat: i for i, cat in enumerate(sorted(df["_depth2_clean"].unique()))}
    df["category_depth2"] = df["_depth2_clean"].map(depth2_map)

    # ── Feature 21~24: 감성 feature (ABSA 4축 × percentile 정규화) ──
    # raw ABSA 점수는 긍정 편향으로 avg 0.7~0.8에 집중 → 변별력 낮음
    # 활성 장소(score != 0)만 대상으로 percentile rank (0~1) 변환
    # 마스킹된 장소(0.0)는 0.0 유지
    for axis, col in [("food_score", "food_sentiment"), ("mood_score", "mood_sentiment"),
                      ("svc_score", "svc_sentiment"), ("price_score", "price_sentiment")]:
        df[col] = df["naver_place_id"].apply(
            lambda pid: absa.get(str(pid), {}).get(axis, 0.0)
        )
        active_mask = df[col] != 0.0
        if active_mask.sum() > 0:
            df.loc[active_mask, col] = df.loc[active_mask, col].rank(pct=True)

    # ── Feature 25~26: 긍부정 레이블 (평점 × 텍스트 일치도) ──
    df["sentiment_confidence"] = df["naver_place_id"].apply(
        lambda pid: sentiment_labels.get(str(pid), {}).get("confidence", 0.5)
    )
    df["label_score"] = df["naver_place_id"].apply(
        lambda pid: sentiment_labels.get(str(pid), {}).get("label_score", 0.0)
    )

    # ── 결과 DataFrame 구성 ──
    feature_cols = [
        "naver_place_id", "place_name", "lat", "lng", "hub", "category_group",
        # 12 고정 feature
        "rating_norm", "review_count_log", "blog_count_log", "price_level",
        "mood_quiet", "mood_group", "mood_vibe", "mood_budget", "mood_private",
        "is_chain", "category_depth1", "category_depth2",
        # 4 감성 feature (ABSA 4축)
        "food_sentiment", "mood_sentiment", "svc_sentiment", "price_sentiment",
        # 2 긍부정 레이블 feature
        "sentiment_confidence", "label_score",
    ]

    result = df[feature_cols].copy()
    result.to_csv(output_path, index=False, encoding="utf-8-sig")

    logger.info(f"Feature 저장: {output_path} ({len(result)}곳, {len(feature_cols)-6}개 feature: 고정12 + 감성4 + 긍부정2)")

    # 통계
    sentiment_active = (result[["food_sentiment", "mood_sentiment", "svc_sentiment", "price_sentiment"]] != 0).any(axis=1).sum()
    chain_count = result["is_chain"].sum()

    return {
        "places": len(result),
        "features": len(feature_cols) - 6,
        "sentiment_active": int(sentiment_active),
        "chain_count": int(chain_count),
        "output_path": output_path,
    }
