"""STEP 1-2. 형태소 분석

- Kiwi (kiwipiepy) 기반 형태소 분석
- POS 필터링: NNG, VA, VV, MAG, XR 유지 (감성어 포함)
- 도메인 불용어 제거 (감성어는 보존)
- 입력: output/preprocessed/normalized_reviews.json
- 출력: output/preprocessed/morpheme_reviews.json
"""

import json
import os
import logging
from kiwipiepy import Kiwi
from preprocessing.io_utils import save_versioned

logger = logging.getLogger(__name__)

# 유지할 POS 태그
# NNG: 일반명사 (분위기, 가성비, 카페)
# VA: 형용사 (맛있다, 좋다, 별로)
# VV: 동사 (먹다, 가다, 추천하다)
# MAG: 부사 (너무, 정말, 진짜, 매우)
# XR: 어근 (조용, 깔끔, 친절 — 감성 핵심)
KEEP_TAGS = {"NNG", "VA", "VV", "MAG", "XR"}

# 도메인 불용어: 의미 없는 고빈도 명사/동사
# 감성어(맛있, 맛없, 좋, 나쁘, 별로 등)는 절대 제거하지 않음
STOPWORDS = {
    # 범용 불용어
    "것", "수", "때", "등", "더", "좀", "정도", "이번",
    "거", "게", "데", "듯", "만큼", "뿐", "쪽",
    # 행위 동사 (감성 없음)
    "가다", "오다", "하다", "되다", "있다", "없다",
    "먹다", "마시다", "시키다", "주문",
    # 시간/장소 일반어
    "오늘", "어제", "다음", "여기", "저기",
    "번", "개", "명", "곳",
}

# Kiwi에서 VV/VA 원형이 "~다" 형태로 나오지 않으므로
# 어간 형태로도 불용어 등록
_STOPWORD_STEMS = set()
for w in STOPWORDS:
    if w.endswith("다"):
        _STOPWORD_STEMS.add(w[:-1])  # 가다 → 가, 오다 → 오
    _STOPWORD_STEMS.add(w)

_kiwi = None


def _get_kiwi() -> Kiwi:
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


def extract_morphemes(text: str) -> list[dict]:
    """텍스트에서 감성 분석용 형태소를 추출.
    반환: [{"form": "맛있", "tag": "VA", "start": 0, "end": 2}, ...]
    """
    kiwi = _get_kiwi()
    tokens = kiwi.tokenize(text)

    result = []
    for t in tokens:
        if t.tag not in KEEP_TAGS:
            continue
        form = t.form.strip()
        if not form or len(form) < 1:
            continue
        if form in _STOPWORD_STEMS:
            continue
        result.append({
            "form": form,
            "tag": t.tag,
        })

    return result


def extract_morpheme_text(text: str) -> str:
    """형태소 추출 후 공백으로 연결한 문자열 반환.
    ABSA 모델 입력용."""
    morphemes = extract_morphemes(text)
    return " ".join(m["form"] for m in morphemes)


def process_all_morphemes(
    input_path: str = "output/preprocessed/normalized_reviews.json",
    output_path: str = "output/preprocessed/morpheme_reviews.json",
    resume: bool = True,
):
    """정규화된 리뷰에 형태소 분석을 적용.

    출력 형식:
    {
        "naver_place_id": {
            "place_name": "...",
            "reviews": [
                {
                    "normalized": "원본 정규화 텍스트",
                    "morphemes": [{"form": "맛있", "tag": "VA"}, ...],
                    "morpheme_text": "맛있 카페 분위기 좋"
                },
                ...
            ],
            "review_count": 15
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
    total_morphemes = 0

    for i, (pid, place) in enumerate(todo.items()):
        reviews = []
        for text in place["reviews_normalized"]:
            morphemes = extract_morphemes(text)
            morph_text = " ".join(m["form"] for m in morphemes)

            if morphemes:  # 형태소가 1개 이상 추출된 경우만
                reviews.append({
                    "normalized": text,
                    "morphemes": morphemes,
                    "morpheme_text": morph_text,
                })
                total_morphemes += len(morphemes)

        if reviews:
            results[pid] = {
                "place_name": place["place_name"],
                "reviews": reviews,
                "review_count": len(reviews),
            }
            total_reviews += len(reviews)

        if (i + 1) % 200 == 0:
            logger.info(
                f"  [{i+1}/{len(todo)}] "
                f"신규 {len(results)}곳, 리뷰 {total_reviews}건"
            )

    # 기존 결과와 merge 후 저장
    existing.update(results)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    save_versioned(output_path)

    avg_morph = total_morphemes / total_reviews if total_reviews else 0
    logger.info(
        f"형태소 분석 완료: 신규 {len(results)}곳 + 기존 {len(existing) - len(results)}곳 = 총 {len(existing)}곳, "
        f"신규 리뷰 {total_reviews}건, 형태소 {total_morphemes}개 (리뷰당 평균 {avg_morph:.1f}개)"
    )

    return {
        "places": len(existing),
        "reviews": total_reviews,
        "morphemes": total_morphemes,
        "avg_per_review": round(avg_morph, 1),
        "output_path": output_path,
    }
