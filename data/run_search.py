"""1단계: 거점 기반 장소 ID 수집 실행"""

import json
import os
from crawler.search import search_all_hubs
from config import PLACE_IDS_DIR


def main():
    os.makedirs(PLACE_IDS_DIR, exist_ok=True)

    places = search_all_hubs()

    output_path = os.path.join(PLACE_IDS_DIR, "all_place_ids.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {output_path} ({len(places)}곳)")


if __name__ == "__main__":
    main()
