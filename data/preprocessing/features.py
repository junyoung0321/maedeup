"""STEP 3. Feature 가공 — 장소 고정 feature 12개 + 감성 feature 4개

장소별 1회 계산 후 저장. 시나리오 의존 feature 8개는 STEP 4에서 계산.

입력:
- output/places.csv (기본 장소 데이터)
- output/preprocessed/absa_scores.json (감성 점수)

출력:
- output/features/place_features.csv (장소당 16개 feature)
"""

import ast
import json
import math
import os
import re
import logging

import pandas as pd
import numpy as np
from preprocessing.io_utils import save_versioned

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

    # keyword_tags 파싱 (CSV에 Python repr ['a','b'] 형식으로 저장됨)
    def parse_tags(x):
        if pd.isna(x):
            return []
        try:
            return json.loads(x)
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            return ast.literal_eval(x)
        except Exception:
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
    # rating: percentile rank (rating>0 장소만 대상, 0은 정보 없음으로 0.0 유지)
    # /5.0 대비 실제 분포 반영 — mean=4.443이 0.5로, 4.0(하위10%)이 0.1로 매핑
    active_rating = df["rating"] > 0
    df["rating_norm"] = 0.0
    df.loc[active_rating, "rating_norm"] = df.loc[active_rating, "rating"].rank(pct=True)

    max_review_log = math.log(df["review_count"].max() + 1) if df["review_count"].max() > 0 else 1
    df["review_count_log"] = df["review_count"].apply(lambda x: math.log(x + 1) / max_review_log)

    max_blog_log = math.log(df["blog_review_count"].max() + 1) if df["blog_review_count"].max() > 0 else 1
    df["blog_count_log"] = df["blog_review_count"].apply(lambda x: math.log(x + 1) / max_blog_log)

    # price_level 제거: menu_prices 미노출 장소가 대부분이라 전체가 default=2로 고정됨 (std=0.0)
    # → 상수 피쳐는 모델에 정보 기여 없음 (2026-04-25 제거)

    # ── Feature 5~9: mood 피쳐 — keyword_tags 대분류 기반 ──
    # keyword_tags는 네이버 키워드 리뷰 카테고리명 (맛/분위기/가격/목적 등 대분류)
    # 해당 카테고리에 리뷰가 있다 = 그 속성이 두드러지는 장소
    mood_tag_map = {
        "mood_quiet": ["전망"],          # 전망 리뷰 = 뷰/분위기 특화 (조용한 공간)
        "mood_group": ["목적"],          # 목적 리뷰 = 단체/모임 목적 언급
        "mood_vibe": ["분위기"],         # 분위기 리뷰 = 감성/인테리어 특화
        "mood_budget": ["가격"],         # 가격 리뷰 = 가성비 의식 장소
        "mood_private": ["예약"],        # 예약 리뷰 = 프라이빗/예약제 공간
    }

    for feature_name, tag_list in mood_tag_map.items():
        df[feature_name] = df["_tags"].apply(
            lambda tags: 1 if any(t in tags for t in tag_list) else 0
        )

    # ── Feature 10: is_chain ──
    df["is_chain"] = df["place_name"].apply(
        lambda x: 1 if _CHAIN_RE.search(str(x)) else 0
    )

    # ── Feature 11~12: category encoding ──
    # category_depth1: category 컬럼 depth1에서 추출 (category_group 결측 2,955개 커버)
    # category_group은 12.5% 결측 → fillna(0)으로 모두 음식점으로 처리되는 버그 수정
    # category 컬럼 예: "음식점 > 한식 > 한정식", "카페,디저트 > 카페" — 첫 토큰이 대분류
    _CAT_DEPTH1_KEYWORDS = {
        "카페": 1, "디저트": 1,          # "카페,디저트" 포함
        "술집": 2, "bar": 2, "바": 2,
        "스터디": 3,
        "음식점": 0,
    }

    def extract_depth1(cat_str):
        if pd.isna(cat_str):
            return 0  # 실제 정보 없음 → 음식점(0)으로 기본값
        token = str(cat_str).split(">")[0].strip().lower()
        for kw, code in _CAT_DEPTH1_KEYWORDS.items():
            if kw in token:
                return code
        return 0  # 매핑 안 되면 음식점(0)

    df["category_depth1"] = df["category"].apply(extract_depth1)

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

    # ── Feature 25: 긍부정 신뢰도 ──
    df["sentiment_confidence"] = df["naver_place_id"].apply(
        lambda pid: sentiment_labels.get(str(pid), {}).get("confidence", 0.5)
    )
    # label_score 제거: sentiment_confidence(r=0.832), food_sentiment(r=0.721)과 고상관
    # → 동일 정보를 중복 반영. sentiment_confidence가 더 직접적인 지표 (2026-04-25 제거)

    # ── 결과 DataFrame 구성 ──
    # sentiment_confidence 제거: v2 gain=39 (rating_norm=496의 8% 수준)
    # → rating_norm과 r=0.554 상관, 독립 정보 기여 미미 (2026-04-25 제거)
    feature_cols = [
        "naver_place_id", "place_name", "lat", "lng", "hub", "category_group",
        # 서빙/시뮬레이션 메타데이터 (학습 feature 제외): compute_scenario_features에 필요
        "category_depth1",
        # 9 고정 feature (price_level 제거: std=0 상수)
        # mood_group/vibe/budget은 시뮬레이션 mood_match_count 계산에 필요 → CSV에는 유지, 학습 feature 제외
        "rating_norm", "review_count_log", "blog_count_log",
        "mood_quiet", "mood_group", "mood_vibe", "mood_budget", "mood_private",
        # is_chain 제거: 장소명 키워드 기반이라 커버리지 3.1% → 사실상 상수, v2 gain=6 (2026-04-26)
        "category_depth2",
        # 4 감성 feature (ABSA 4축)
        "food_sentiment", "mood_sentiment", "svc_sentiment", "price_sentiment",
    ]

    result = df[feature_cols].copy()
    result.to_csv(output_path, index=False, encoding="utf-8-sig")
    save_versioned(output_path)

    logger.info(f"Feature 저장: {output_path} ({len(result)}곳, {len(feature_cols)-7}개 feature: 고정9 + 감성4)")

    # 통계
    sentiment_active = (result[["food_sentiment", "mood_sentiment", "svc_sentiment", "price_sentiment"]] != 0).any(axis=1).sum()
    chain_count = df["is_chain"].sum()  # is_chain은 feature_cols 제외, df에서 직접 참조

    return {
        "places": len(result),
        "features": len(feature_cols) - 7,
        "sentiment_active": int(sentiment_active),
        "chain_count": int(chain_count),
        "output_path": output_path,
    }
