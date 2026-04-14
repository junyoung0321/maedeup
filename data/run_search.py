"""1단계: 거점 기반 장소 ID 수집 실행 (Playwright)"""

import json
import os
from crawler.search import search_all_hubs
from config import PLACE_IDS_DIR


def main():
    os.makedirs(PLACE_IDS_DIR, exist_ok=True)

    new_places = search_all_hubs()
    for p in new_places:
        if "id" not in p:
            p["id"] = p.get("naver_place_id", "")

    output_path = os.path.join(PLACE_IDS_DIR, "all_place_ids.json")

    # 기존 데이터와 머지 (중복 제거)
    existing = []
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    existing_ids = {p.get("naver_place_id", p.get("id", "")) for p in existing}
    added = [p for p in new_places if p.get("naver_place_id", "") not in existing_ids]
    merged = existing + added

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"신규: {len(added)}곳 추가 / 누적: {len(merged)}곳 → {output_path}")


if __name__ == "__main__":
    main()
