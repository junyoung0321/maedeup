"""2단계: 장소 ID 기반 상세 정보 수집 (Playwright GraphQL)"""

import json
import os
import pandas as pd
from crawler.detail import enrich_with_ratings, save_raw
from config import PLACE_IDS_DIR, RAW_DIR, FINAL_CSV, OUTPUT_DIR


def main():
    ids_path = os.path.join(PLACE_IDS_DIR, "all_place_ids.json")
    if not os.path.exists(ids_path):
        print(f"Error: {ids_path} 없음. run_search.py를 먼저 실행하세요.")
        return

    with open(ids_path, "r", encoding="utf-8") as f:
        places = json.load(f)

    print(f"총 {len(places)}개 장소 상세 수집 시작")

    # 이미 수집된 ID 스킵 (이어하기 지원)
    existing_ids = set()
    if os.path.exists(RAW_DIR):
        existing_ids = {f.replace(".json", "") for f in os.listdir(RAW_DIR) if f.endswith(".json")}

    remaining = []
    for p in places:
        pid = p.get("naver_place_id", p.get("id", ""))
        if pid and pid not in existing_ids:
            remaining.append(p)

    print(f"이미 수집: {len(existing_ids)}곳, 남은: {len(remaining)}곳")

    if remaining:
        enriched = enrich_with_ratings(remaining)
        # rating > 0인 것만 저장 (방문자 별점 있는 장소만)
        rated = [p for p in enriched if p["rating"] > 0]
        print(f"별점 있는 장소: {len(rated)}/{len(enriched)}곳 → 저장")
        save_raw(rated)

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

    df = df.drop_duplicates(subset="naver_place_id")
    before = len(df)
    df = df[(df["review_count"] > 0) & (df["rating"] > 0)]
    print(f"평점/리뷰 없는 장소 제거: {before} → {len(df)}곳 (방문자 리뷰+평점 보유)")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df.to_csv(FINAL_CSV, index=False, encoding="utf-8-sig")
    print(f"최종 저장: {FINAL_CSV} ({len(df)}곳)")


if __name__ == "__main__":
    main()
