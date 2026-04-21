"""nan hub 매핑 수정: 주소 + 좌표 기반으로 hub 필드 채우기

대상: output/raw/*.json 중 hub가 비어있는 파일
전략:
  1. lat/lng 있으면 → HUBS_ALL + HUBS 전체에서 최근접 거점 할당
  2. lat/lng 없으면 → address 첫 키워드로 도시명 → 대표 거점 할당
"""

import json
import math
import os

from config import HUBS, HUBS_ALL, HUBS_METRO

RAW_DIR = "output/raw"
SUPPLEMENT_IDS_PATH = "output/place_ids/supplement_place_ids.json"


def haversine(lat1, lng1, lat2, lng2) -> float:
    """두 좌표 간 거리 (km)"""
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_hub(lat: float, lng: float, all_hubs: list[dict]) -> str:
    best = min(all_hubs, key=lambda h: haversine(lat, lng, h["lat"], h["lng"]))
    return best["name"]


# 도시 키워드 → 대표 거점 (lat/lng 없는 경우 폴백)
CITY_FALLBACK = {
    "서울": "서울_강남",
    "부산": "부산_서면",
    "대구": "대구_동성로",
    "인천": "인천_부평",
    "광주": "광주_충장로",
    "대전": "대전_둔산",
    "울산": "울산_삼산",
    "세종": "세종_어진동",
    "경기": "수원_인계동",
    "수원": "수원_인계동",
    "성남": "성남_분당",
    "용인": "용인_기흥",
    "고양": "고양_일산",
    "부천": "부천_중동",
    "안산": "안산_중앙",
    "화성": "화성_동탄",
    "안양": "안양_범계",
    "평택": "평택_중앙",
    "의정부": "의정부_중앙",
    "파주": "파주_운정",
    "충남": "천안_신부동",
    "천안": "천안_신부동",
    "아산": "아산_온양",
    "충북": "청주_성안길",
    "청주": "청주_성안길",
    "전북": "전주_객사",
    "전주": "전주_객사",
    "익산": "익산_중앙",
    "전남": "순천_중앙",
    "순천": "순천_중앙",
    "목포": "목포_중앙",
    "여수": "여수_중앙",
    "경남": "창원_상남",
    "창원": "창원_상남",
    "진주": "진주_중앙",
    "김해": "김해_내외",
    "경북": "구미_송정",
    "구미": "구미_송정",
    "포항": "포항_중앙",
    "경주": "경주_중앙",
    "안동": "안동_중앙",
    "강원": "춘천_중앙",
    "춘천": "춘천_중앙",
    "강릉": "강릉_중앙",
    "원주": "원주_중앙",
    "속초": "속초_중앙",
    "제주": "제주_연동",
}


def addr_to_hub(address: str) -> str | None:
    for key, hub in CITY_FALLBACK.items():
        if key in address:
            return hub
    return None


def main():
    all_hubs = HUBS_ALL + HUBS + HUBS_METRO
    # deduplicate by name
    seen_names: set[str] = set()
    unique_hubs: list[dict] = []
    for h in all_hubs:
        if h["name"] not in seen_names:
            unique_hubs.append(h)
            seen_names.add(h["name"])

    raw_files = [f for f in os.listdir(RAW_DIR) if f.endswith(".json")]
    print(f"raw 파일 총 {len(raw_files):,}개 스캔 중...")

    fixed = 0
    skipped = 0

    for fname in raw_files:
        fpath = os.path.join(RAW_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue

        hub = str(d.get("hub", "")).strip()
        if hub and hub != "nan":
            skipped += 1
            continue

        # hub가 비어 있거나 nan인 경우
        lat = float(d.get("lat", 0) or 0)
        lng = float(d.get("lng", 0) or 0)
        addr = str(d.get("address", "") or "")

        if lat != 0 and lng != 0:
            new_hub = nearest_hub(lat, lng, unique_hubs)
        elif addr:
            new_hub = addr_to_hub(addr) or "미분류_원본"
        else:
            new_hub = "미분류_원본"

        d["hub"] = new_hub
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        fixed += 1

    print(f"hub 수정 완료: {fixed:,}개 | 기존 hub 있음: {skipped:,}개")

    # supplement_place_ids.json도 동기화
    if os.path.exists(SUPPLEMENT_IDS_PATH):
        with open(SUPPLEMENT_IDS_PATH, "r", encoding="utf-8") as f:
            places = json.load(f)

        sup_fixed = 0
        for p in places:
            hub = str(p.get("hub", "")).strip()
            if hub and hub != "nan":
                continue
            pid = str(p.get("naver_place_id", ""))
            raw_path = os.path.join(RAW_DIR, f"{pid}.json")
            if os.path.exists(raw_path):
                try:
                    with open(raw_path, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    p["hub"] = raw.get("hub", "미분류_원본")
                    sup_fixed += 1
                except Exception:
                    pass

        with open(SUPPLEMENT_IDS_PATH, "w", encoding="utf-8") as f:
            json.dump(places, f, ensure_ascii=False, indent=2)
        print(f"supplement_place_ids.json 동기화: {sup_fixed:,}개 hub 수정")


if __name__ == "__main__":
    main()
