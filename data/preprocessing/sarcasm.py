"""STEP 1-3b. 반어법 탐지

전략: 토큰 레벨 감성과 문장 레벨 감성의 모순 탐지
- 문장 감성: KoELECTRA 기반 분류 (긍정/부정)
- 토큰 감성: 형태소 중 긍정어/부정어 비율
- 모순 시 sarcasm_score 부여
- 임계값 0.7 이상 → 학습 데이터에서 제외

입력: output/preprocessed/morpheme_reviews.json
출력: output/preprocessed/sarcasm_reviews.json
"""

import json
import os
import logging
from preprocessing.io_utils import save_versioned

logger = logging.getLogger(__name__)

# 감성어 사전 (형태소 기준)
POSITIVE_WORDS = {
    "좋", "맛있", "훌륭", "최고", "추천", "만족", "깔끔", "친절",
    "맛나", "신선", "푸짐", "넓", "쾌적", "예쁘", "깨끗", "빠르",
    "편하", "조용", "아늑", "따뜻", "정갈", "알차", "든든",
    "괜찮", "적당", "나이스", "굿", "대박", "짱",
    # 부사
    "잘", "정말", "진짜", "너무", "매우", "완전",
}

NEGATIVE_WORDS = {
    "별로", "실망", "최악", "나쁘", "싫", "불친절", "더럽",
    "맛없", "비싸", "짜", "느리", "좁", "시끄럽", "불쾌",
    "아쉽", "부족", "밍밍", "딱딱", "질기", "차갑", "떨어지",
    "후회", "그냥", "그저그렇",
    # 부정 부사
    "안", "못", "없",
}

# 문장 감성 분류기 (lazy load)
_classifier = None
_MODEL_NAME = "jaehyeong/koelectra-base-v3-generalized-sentiment-analysis"


def _get_classifier():
    global _classifier
    if _classifier is None:
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        from transformers import pipeline
        _classifier = pipeline(
            "sentiment-analysis",
            model=_MODEL_NAME,
            device=-1,  # CPU
        )
    return _classifier


def _token_sentiment(morphemes: list[dict]) -> dict:
    """형태소 리스트에서 긍정/부정 토큰 비율 계산."""
    pos_count = 0
    neg_count = 0
    pos_words = []
    neg_words = []

    for m in morphemes:
        form = m["form"]
        if form in POSITIVE_WORDS:
            pos_count += 1
            pos_words.append(form)
        elif form in NEGATIVE_WORDS:
            neg_count += 1
            neg_words.append(form)

    total = pos_count + neg_count
    if total == 0:
        return {
            "token_sentiment": "neutral",
            "pos_ratio": 0.0,
            "neg_ratio": 0.0,
            "pos_words": [],
            "neg_words": [],
        }

    pos_ratio = pos_count / total
    neg_ratio = neg_count / total

    if pos_ratio > 0.6:
        token_sent = "positive"
    elif neg_ratio > 0.6:
        token_sent = "negative"
    else:
        token_sent = "mixed"

    return {
        "token_sentiment": token_sent,
        "pos_ratio": round(pos_ratio, 3),
        "neg_ratio": round(neg_ratio, 3),
        "pos_words": pos_words,
        "neg_words": neg_words,
    }


def detect_sarcasm(
    normalized_text: str,
    morphemes: list[dict],
) -> dict:
    """반어법 탐지.

    반환:
    {
        "sentence_label": "positive" or "negative",
        "sentence_confidence": 0.98,
        "token_sentiment": "positive" or "negative" or "mixed" or "neutral",
        "sarcasm_score": 0.0~1.0,
        "is_sarcastic": False,
    }
    """
    classifier = _get_classifier()

    # 1) 문장 레벨 감성
    try:
        result = classifier(normalized_text[:512])[0]
        sent_label = "positive" if result["label"] == "1" else "negative"
        sent_conf = result["score"]
    except Exception:
        return {
            "sentence_label": "unknown",
            "sentence_confidence": 0.0,
            "token_sentiment": "neutral",
            "sarcasm_score": 0.0,
            "is_sarcastic": False,
        }

    # 2) 토큰 레벨 감성
    token_info = _token_sentiment(morphemes)
    token_sent = token_info["token_sentiment"]

    # 3) 반어법 점수 계산
    # 모순: 토큰은 긍정인데 문장은 부정 (또는 반대)
    sarcasm_score = 0.0

    if token_sent == "positive" and sent_label == "negative":
        # 긍정 단어 많은데 전체는 부정 → 반어법 가능성
        sarcasm_score = sent_conf * token_info["pos_ratio"]
    elif token_sent == "negative" and sent_label == "positive":
        # 부정 단어 많은데 전체는 긍정 → 반어법 가능성
        sarcasm_score = sent_conf * token_info["neg_ratio"]
    elif token_sent == "mixed":
        # 혼합 감성 → 약한 반어법 신호
        sarcasm_score = 0.3 * (1 - abs(token_info["pos_ratio"] - token_info["neg_ratio"]))

    # 문장 confidence가 낮으면 (0.5~0.6) 모델이 헷갈린다는 의미
    # → 반어법 추가 신호
    if 0.5 <= sent_conf <= 0.65 and token_sent != "neutral":
        sarcasm_score = max(sarcasm_score, 0.5)

    sarcasm_score = min(round(sarcasm_score, 3), 1.0)

    return {
        "sentence_label": sent_label,
        "sentence_confidence": round(sent_conf, 3),
        "token_sentiment": token_sent,
        "sarcasm_score": sarcasm_score,
        "is_sarcastic": sarcasm_score >= 0.7,
        **token_info,
    }


def process_all_sarcasm(
    input_path: str = "output/preprocessed/morpheme_reviews.json",
    output_path: str = "output/preprocessed/sarcasm_reviews.json",
    resume: bool = True,
    batch_size: int = 64,
):
    """전체 리뷰에 부정 탐지 + 반어법 탐지 적용.

    배치 처리(batch_size=64)로 문장 감성 추론 속도 개선.
    출력에 추가되는 필드:
    - negation: {has_negation, negated_targets, ...}
    - sarcasm: {sarcasm_score, is_sarcastic, sentence_label, ...}
    """
    from preprocessing.negation import detect_negation, get_negation_summary

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

    # 모델 미리 로드
    classifier = _get_classifier()

    # 전체 리뷰 플랫 리스트로 수집 (배치 추론용)
    all_pids = []
    all_rev_indices = []
    all_texts = []
    all_morpheme_data = []

    for pid, place in todo.items():
        for j, rev in enumerate(place["reviews"]):
            all_pids.append(pid)
            all_rev_indices.append(j)
            all_texts.append(rev["normalized"][:512])
            all_morpheme_data.append(rev)

    total_texts = len(all_texts)
    logger.info(f"배치 추론 시작: {total_texts}건 (batch_size={batch_size})")

    # 배치 추론
    sentence_results = []
    for start in range(0, total_texts, batch_size):
        batch = all_texts[start: start + batch_size]
        try:
            batch_out = classifier(batch, truncation=True, max_length=512)
        except Exception as e:
            logger.warning(f"배치 추론 오류 (idx={start}): {e}")
            batch_out = [{"label": "1", "score": 0.5}] * len(batch)
        sentence_results.extend(batch_out)
        if (start // batch_size + 1) % 50 == 0:
            logger.info(f"  추론 진행: {start + len(batch)}/{total_texts}")

    logger.info("배치 추론 완료. 결과 조합 중...")

    # pid별로 결과 조합
    from collections import defaultdict
    pid_reviews: dict = defaultdict(list)
    pid_place_name: dict = {}

    total_reviews = 0
    sarcastic_count = 0
    negated_count = 0

    for idx, (pid, rev, sent_out) in enumerate(zip(all_pids, all_morpheme_data, sentence_results)):
        morphemes = rev["morphemes"]
        normalized = rev["normalized"]

        # 부정 탐지 (규칙 기반)
        morphemes_neg = detect_negation(morphemes)
        neg_summary = get_negation_summary(morphemes_neg)

        # 문장 감성 결과 파싱
        sent_label = "positive" if sent_out["label"] == "1" else "negative"
        sent_conf = round(sent_out["score"], 3)

        # 토큰 감성
        token_info = _token_sentiment(morphemes)
        token_sent = token_info["token_sentiment"]

        # 반어법 점수
        sarcasm_score = 0.0
        if token_sent == "positive" and sent_label == "negative":
            sarcasm_score = sent_conf * token_info["pos_ratio"]
        elif token_sent == "negative" and sent_label == "positive":
            sarcasm_score = sent_conf * token_info["neg_ratio"]
        elif token_sent == "mixed":
            sarcasm_score = 0.3 * (1 - abs(token_info["pos_ratio"] - token_info["neg_ratio"]))
        if 0.5 <= sent_conf <= 0.65 and token_sent != "neutral":
            sarcasm_score = max(sarcasm_score, 0.5)
        sarcasm_score = min(round(sarcasm_score, 3), 1.0)

        pid_reviews[pid].append({
            "normalized": normalized,
            "morphemes": morphemes_neg,
            "morpheme_text": rev["morpheme_text"],
            "negation": neg_summary,
            "sarcasm": {
                "sentence_label": sent_label,
                "sentence_confidence": sent_conf,
                "token_sentiment": token_sent,
                "sarcasm_score": sarcasm_score,
                "is_sarcastic": sarcasm_score >= 0.7,
            },
        })

        total_reviews += 1
        if sarcasm_score >= 0.7:
            sarcastic_count += 1
        if neg_summary["has_negation"]:
            negated_count += 1

    # place_name 매핑
    for pid, place in todo.items():
        pid_place_name[pid] = place["place_name"]

    results = {
        pid: {
            "place_name": pid_place_name[pid],
            "reviews": reviews,
            "review_count": len(reviews),
        }
        for pid, reviews in pid_reviews.items()
    }

    # 기존 결과와 merge 후 저장
    existing.update(results)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    save_versioned(output_path)

    logger.info(
        f"완료: 신규 {len(results)}곳 + 기존 {len(existing) - len(results)}곳 = 총 {len(existing)}곳, "
        f"신규 리뷰 {total_reviews}건, "
        f"반어법 {sarcastic_count}건, 부정 {negated_count}건"
    )

    return {
        "places": len(existing),
        "reviews": total_reviews,
        "sarcastic": sarcastic_count,
        "sarcastic_pct": round(sarcastic_count / total_reviews * 100, 1) if total_reviews else 0,
        "negated": negated_count,
        "negated_pct": round(negated_count / total_reviews * 100, 1) if total_reviews else 0,
        "output_path": output_path,
    }
