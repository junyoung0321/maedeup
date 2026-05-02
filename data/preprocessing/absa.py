"""STEP 1-4. ABSA 속성 추출 (4축)

각 리뷰에서 4개 속성별 감성 점수를 추출:
- food_score: 음식·맛 ∈ [-1, +1]
- mood_score: 분위기 ∈ [-1, +1]
- svc_score: 서비스 ∈ [-1, +1]
- price_score: 가격·가성비 ∈ [-1, +1]

전략:
1. 속성 키워드로 리뷰 내 속성 언급 탐지
2. 속성 주변 감성어 + 부정 정보로 극성 결정
3. 장소 단위 평균, 리뷰 3건 미만 → 0 마스킹

입력: output/preprocessed/sarcasm_reviews.json
출력: output/preprocessed/absa_scores.json
"""

import json
import os
import logging
from preprocessing.io_utils import save_versioned

logger = logging.getLogger(__name__)

# ─── 속성별 키워드 (형태소 기준) ───

ASPECT_KEYWORDS = {
    "food": {
        "맛", "음식", "메뉴", "요리", "밥", "국", "반찬", "고기", "해물", "면",
        "빵", "디저트", "케이크", "커피", "음료", "차", "술", "맥주", "와인",
        "식사", "밑반찬", "소스", "양념", "재료", "신선", "맛있", "맛없",
        "짜", "싱겁", "달", "매콤", "담백", "고소", "쫄깃", "바삭",
        "질기", "딱딱", "부드럽", "촉촉", "퍽퍽", "밍밍",
    },
    "mood": {
        "분위기", "인테리어", "뷰", "야경", "조명", "음악", "소음",
        "조용", "시끄럽", "아늑", "따뜻", "깔끔", "깨끗", "더럽",
        "넓", "좁", "쾌적", "답답", "예쁘", "세련", "모던", "빈티지",
        "편하", "편안", "감성", "포토", "데이트", "분위기좋",
    },
    "svc": {
        "서비스", "직원", "사장", "알바", "응대", "친절", "불친절",
        "빠르", "느리", "대기", "웨이팅", "예약", "주차",
        "설명", "안내", "배려", "세심", "무뚝뚝", "무시",
    },
    "price": {
        "가격", "가성비", "비싸", "싸", "저렴", "합리", "양",
        "푸짐", "적", "많", "부족", "아깝", "값", "만원",
        "천원", "원", "비용", "돈", "가치",
    },
}

# ─── 감성어 사전 (극성 점수) ───

SENTIMENT_SCORES = {
    # 긍정 (+)
    "좋": 1.0, "맛있": 1.0, "훌륭": 1.0, "최고": 1.0, "추천": 0.8,
    "만족": 1.0, "깔끔": 0.8, "친절": 1.0, "신선": 0.8, "푸짐": 0.8,
    "넓": 0.6, "쾌적": 0.8, "예쁘": 0.8, "깨끗": 0.8, "빠르": 0.7,
    "편하": 0.7, "조용": 0.7, "아늑": 0.8, "따뜻": 0.7, "정갈": 0.7,
    "든든": 0.7, "괜찮": 0.5, "적당": 0.5, "합리": 0.7,
    "부드럽": 0.7, "촉촉": 0.7, "바삭": 0.7, "고소": 0.7,
    "담백": 0.6, "매콤": 0.5, "달": 0.4, "쫄깃": 0.7,
    "세련": 0.7, "감성": 0.7, "세심": 0.8, "배려": 0.8,
    "저렴": 0.7, "싸": 0.6, "대박": 0.9, "완전": 0.6,
    # 부정 (-)
    "별로": -0.8, "실망": -1.0, "최악": -1.0, "나쁘": -0.9,
    "불친절": -1.0, "더럽": -0.9, "맛없": -1.0, "비싸": -0.7,
    "짜": -0.5, "느리": -0.6, "좁": -0.5, "시끄럽": -0.6,
    "불쾌": -0.9, "아쉽": -0.5, "부족": -0.6, "밍밍": -0.6,
    "딱딱": -0.6, "질기": -0.7, "차갑": -0.4, "퍽퍽": -0.6,
    "답답": -0.6, "무뚝뚝": -0.7, "무시": -0.9,
    "아깝": -0.7, "적": -0.4, "후회": -0.9,
}

# 부정어에 의해 극성이 플립될 때의 감쇠 계수
NEGATION_FLIP_FACTOR = -0.7


def _score_aspect_in_review(morphemes: list[dict], aspect_keywords: set) -> float | None:
    """리뷰 형태소에서 특정 속성의 감성 점수 계산.
    속성 키워드가 없으면 None (언급 안 됨).
    """
    # 1) 속성 키워드 위치 찾기
    aspect_positions = []
    for i, m in enumerate(morphemes):
        if m["form"] in aspect_keywords:
            aspect_positions.append(i)

    if not aspect_positions:
        return None  # 이 리뷰에서 해당 속성 언급 없음

    # 2) 속성 키워드 주변 감성어 탐색 (앞뒤 3토큰)
    WINDOW = 3
    scores = []

    for pos in aspect_positions:
        start = max(0, pos - WINDOW)
        end = min(len(morphemes), pos + WINDOW + 1)

        for j in range(start, end):
            if j == pos:
                continue
            m = morphemes[j]
            form = m["form"]
            if form in SENTIMENT_SCORES:
                score = SENTIMENT_SCORES[form]
                # 부정어에 의해 부정된 감성어면 극성 플립
                if m.get("negated", False):
                    score *= NEGATION_FLIP_FACTOR
                scores.append(score)

    # 3) 점수 없으면 속성 키워드 자체의 감성 확인
    if not scores:
        for pos in aspect_positions:
            form = morphemes[pos]["form"]
            if form in SENTIMENT_SCORES:
                score = SENTIMENT_SCORES[form]
                if morphemes[pos].get("negated", False):
                    score *= NEGATION_FLIP_FACTOR
                scores.append(score)

    if not scores:
        return 0.0  # 속성은 언급했지만 감성어 없음 (중립)

    # 평균 점수, [-1, 1] 클리핑
    avg = sum(scores) / len(scores)
    return max(-1.0, min(1.0, avg))


def extract_absa_scores(morphemes: list[dict]) -> dict:
    """단일 리뷰에서 4축 ABSA 점수 추출.
    반환: {"food": 0.8, "mood": None, "svc": -0.5, "price": None}
    None = 해당 속성 미언급
    """
    result = {}
    for aspect, keywords in ASPECT_KEYWORDS.items():
        result[aspect] = _score_aspect_in_review(morphemes, keywords)
    return result


def aggregate_place_scores(reviews_scores: list[dict]) -> dict:
    """장소 단위 ABSA 평균 점수 계산.
    리뷰 3건 미만 속성 → 0으로 마스킹.

    반환: {
        "food_score": 0.65,
        "mood_score": 0.0,  (마스킹)
        "svc_score": -0.3,
        "price_score": 0.4,
        "food_count": 12,
        "mood_count": 2,  (3건 미만 → 마스킹됨)
        "svc_count": 8,
        "price_count": 5,
    }
    """
    result = {}
    for aspect in ["food", "mood", "svc", "price"]:
        scores = [r[aspect] for r in reviews_scores if r[aspect] is not None]
        count = len(scores)
        result[f"{aspect}_count"] = count

        if count >= 3:
            avg = sum(scores) / count
            # 극단값 클리핑 (±0.9)
            avg = max(-0.9, min(0.9, avg))
            result[f"{aspect}_score"] = round(avg, 3)
        else:
            result[f"{aspect}_score"] = 0.0  # 마스킹

    return result


def process_all_absa(
    input_path: str = "output/preprocessed/sarcasm_reviews.json",
    output_path: str = "output/preprocessed/absa_scores.json",
    resume: bool = True,
):
    """전체 장소의 ABSA 점수 계산.

    출력:
    {
        "naver_place_id": {
            "place_name": "...",
            "food_score": 0.65,
            "mood_score": 0.42,
            "svc_score": -0.1,
            "price_score": 0.3,
            "food_count": 15,
            "mood_count": 8,
            "svc_count": 5,
            "price_count": 4,
            "review_count": 18,
            "sarcasm_excluded": 1,
        }
    }
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # resume: 기존 처리 결과 로드
    existing = {}
    if resume and os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        logger.info(f"기존 처리 결과 로드: {len(existing)}곳 (재개 모드)")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    todo = {pid: place for pid, place in data.items() if pid not in existing}
    logger.info(f"입력: {len(data)}곳 (처리 필요: {len(todo)}곳)")

    results = {}
    total_reviews = 0
    excluded_sarcasm = 0

    for i, (pid, place) in enumerate(todo.items()):
        reviews_scores = []

        for rev in place["reviews"]:
            # 반어법 리뷰 제외
            if rev["sarcasm"]["is_sarcastic"]:
                excluded_sarcasm += 1
                continue

            morphemes = rev["morphemes"]
            scores = extract_absa_scores(morphemes)
            reviews_scores.append(scores)
            total_reviews += 1

        if reviews_scores:
            agg = aggregate_place_scores(reviews_scores)
            results[pid] = {
                "place_name": place["place_name"],
                **agg,
                "review_count": len(reviews_scores),
                "sarcasm_excluded": place["review_count"] - len(reviews_scores),
            }

        if (i + 1) % 200 == 0:
            logger.info(f"  [{i+1}/{len(todo)}] 신규 처리 완료")

    # 기존 결과와 merge 후 저장
    existing.update(results)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    save_versioned(output_path)

    # 통계 (전체 기준)
    food_active = sum(1 for r in existing.values() if r["food_score"] != 0)
    mood_active = sum(1 for r in existing.values() if r["mood_score"] != 0)
    svc_active = sum(1 for r in existing.values() if r["svc_score"] != 0)
    price_active = sum(1 for r in existing.values() if r["price_score"] != 0)

    logger.info(
        f"ABSA 완료: 신규 {len(results)}곳 + 기존 {len(existing) - len(results)}곳 = 총 {len(existing)}곳, "
        f"신규 리뷰 {total_reviews}건 (반어법 제외 {excluded_sarcasm}건)\n"
        f"  전체 활성 장소: food={food_active}, mood={mood_active}, "
        f"svc={svc_active}, price={price_active}"
    )

    return {
        "places": len(existing),
        "reviews": total_reviews,
        "sarcasm_excluded": excluded_sarcasm,
        "active_food": food_active,
        "active_mood": mood_active,
        "active_svc": svc_active,
        "active_price": price_active,
        "output_path": output_path,
    }
