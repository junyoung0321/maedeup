"""STEP 1-1. 노이즈 정규화

순서: 이모티콘 정규화 → 반복 문자 압축 → 띄어쓰기 교정(Kiwi)
입력: raw review texts (output/raw/*.json → review_texts[])
출력: output/preprocessed/normalized_reviews.json
"""

import json
import os
import re
import logging

from soynlp.normalizer import emoticon_normalize, repeat_normalize
from preprocessing.io_utils import save_versioned

logger = logging.getLogger(__name__)

# kiwipiepy lazy load (싱글턴)
_kiwi = None


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


def normalize_text(text: str) -> str:
    """단일 리뷰 텍스트 노이즈 정규화.
    1) 이모티콘 정규화: ㅋㅋㅋㅋ → ㅋㅋ
    2) 반복 문자 압축: 맛있어어어어 → 맛있어어
    3) 줄바꿈 → 공백
    4) 다중 공백 → 단일 공백
    """
    if not text or not text.strip():
        return ""

    # 1) 이모티콘 정규화
    text = emoticon_normalize(text, num_repeats=2)

    # 2) 반복 문자 압축
    text = repeat_normalize(text, num_repeats=2)

    # 3) 줄바꿈 → 공백, 다중 공백 정리
    text = re.sub(r"\s+", " ", text).strip()

    return text


def apply_spacing(text: str) -> str:
    """띄어쓰기 교정 (kiwipiepy.space)."""
    if not text or len(text) < 5:
        return text
    try:
        kiwi = _get_kiwi()
        return kiwi.space(text)
    except Exception:
        return text


def normalize_review(text: str, use_spacing: bool = True) -> str:
    """전체 정규화 파이프라인."""
    text = normalize_text(text)
    if not text:
        return ""
    if use_spacing:
        text = apply_spacing(text)
    return text


def process_all_reviews(
    raw_dir: str = "output/raw",
    output_path: str = "output/preprocessed/normalized_reviews.json",
    min_length: int = 10,
    use_spacing: bool = True,
    resume: bool = True,
):
    """전체 장소의 리뷰를 정규화하여 저장.

    출력 형식:
    {
        "naver_place_id": {
            "place_name": "...",
            "reviews_raw": ["원본1", ...],
            "reviews_normalized": ["정규화1", ...],
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

    raw_files = [f for f in os.listdir(raw_dir) if f.endswith(".json")]
    # 이미 처리된 pid 스킵
    raw_files_todo = [f for f in raw_files if f.replace(".json", "") not in existing]
    logger.info(f"raw 파일 수: {len(raw_files)} (처리 필요: {len(raw_files_todo)})")

    results = {}
    total_raw = 0
    total_kept = 0
    total_filtered = 0

    for i, fname in enumerate(raw_files_todo):
        with open(os.path.join(raw_dir, fname), "r", encoding="utf-8") as f:
            data = json.load(f)

        pid = data.get("naver_place_id", fname.replace(".json", ""))
        raw_reviews = data.get("review_texts", [])

        if not raw_reviews:
            continue

        total_raw += len(raw_reviews)
        normalized = []

        for text in raw_reviews:
            norm = normalize_review(text, use_spacing=use_spacing)
            if len(norm) >= min_length:
                normalized.append(norm)
            else:
                total_filtered += 1

        if normalized:
            results[pid] = {
                "place_name": data.get("place_name", ""),
                "reviews_raw": raw_reviews,
                "reviews_normalized": normalized,
                "review_count": len(normalized),
            }
            total_kept += len(normalized)

        if (i + 1) % 200 == 0:
            logger.info(
                f"  [{i+1}/{len(raw_files_todo)}] "
                f"신규 {len(results)}곳, 리뷰 {total_kept}건"
            )

    # 기존 결과와 merge 후 저장
    existing.update(results)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    save_versioned(output_path)

    logger.info(
        f"정규화 완료: 신규 {len(results)}곳 + 기존 {len(existing) - len(results)}곳 = 총 {len(existing)}곳, "
        f"신규 리뷰: 원본 {total_raw} → 유지 {total_kept} (필터 {total_filtered})"
    )

    return {
        "places": len(existing),
        "raw_reviews": total_raw,
        "kept_reviews": total_kept,
        "filtered": total_filtered,
        "output_path": output_path,
    }
