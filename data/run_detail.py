"""2단계: 장소 ID 기반 상세 정보 수집"""

import json
import os
import pandas as pd
from crawler.detail import fetch_all_details
from config import PLACE_IDS_DIR, RAW_DIR, FINAL_CSV, OUTPUT_DIR


def main():
    ids_path = os.path.join(PLACE_IDS_DIR, "all_place_ids.json")
    if not os.path.exists(ids_path):
        print(f"Error: {ids_path} 없음. run_search.py를 먼저 실행하세요.")
        return

    with open(ids_path, "r", encoding="utf-8") as f:
        places = json.load(f)

    place_ids = [p["id"] for p in places]
    print(f"총 {len(place_ids)}개 장소 상세 수집 시작")

    # 이미 수집된 ID 스킵 (이어하기 지원)
    existing = set()
    if os.path.exists(RAW_DIR):
        existing = {f.replace(".json", "") for f in os.listdir(RAW_DIR) if f.endswith(".json")}
    remaining = [pid for pid in place_ids if pid not in existing]
    print(f"이미 수집: {len(existing)}곳, 남은: {len(remaining)}곳")

    if remaining:
        fetch_all_details(remaining)

    # 기존 + 신규 합쳐서 CSV 생성
    all_results = []
    for fname in os.listdir(RAW_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(RAW_DIR, fname), "r", encoding="utf-8") as f:
                all_results.append(json.load(f))

    df = pd.DataFrame(all_results)
    for col in ["keyword_tags", "menu_prices"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x
            )

    # 중복 제거 + 리뷰 0개 제거
    df = df.drop_duplicates(subset="naver_place_id")
    before = len(df)
    df = df[df["review_count"] > 0]
    print(f"리뷰 0개 제거: {before} → {len(df)}곳")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df.to_csv(FINAL_CSV, index=False, encoding="utf-8-sig")
    print(f"최종 저장: {FINAL_CSV} ({len(df)}곳)")


if __name__ == "__main__":
    main()
