"""Naver place_id → Kakao place_id 배치 매핑

전략:
  1차: place_name + address 검색 + 좌표 100m 이내 검증  (신뢰도 HIGH)
  2차: place_name 단독 검색 + 좌표 50m 이내 검증        (신뢰도 MED)
  미매핑: kakao_place_id = None

출력: output/kakao_map.csv
  naver_place_id, kakao_place_id, kakao_name, distance_m, confidence
"""

import math
import os
import time
import logging

import pandas as pd
import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

KAKAO_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

CHECKPOINT_PATH = "output/kakao_map_checkpoint.csv"
OUTPUT_PATH = "output/kakao_map.csv"

HIGH_DIST_M = 100   # 1차 매핑 허용 거리
MED_DIST_M  = 50    # 2차 매핑 허용 거리
REQUEST_DELAY = 0.05  # 초 (20 req/s)


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def name_match(our_name, kakao_name) -> bool:
    if not isinstance(our_name, str) or not isinstance(kakao_name, str):
        return False
    a = our_name.strip().lower().replace(" ", "")
    b = kakao_name.strip().lower().replace(" ", "")
    return bool(a) and (a == b or a in b or b in a)


def kakao_search(query: str, lat: float, lng: float, radius: int, size: int = 5) -> list[dict]:
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": query, "y": lat, "x": lng, "radius": radius, "size": size}
    try:
        r = requests.get(SEARCH_URL, headers=headers, params=params, timeout=5)
        r.raise_for_status()
        return r.json().get("documents", [])
    except Exception as e:
        logger.warning(f"API 오류: {e}")
        return []


def find_kakao_id(place_name, address: str, lat: float, lng: float) -> dict:
    """1차(address+name) → 2차(name only) 순서로 매핑 시도."""
    _null = {"kakao_place_id": None, "kakao_name": None, "distance_m": None, "confidence": None}
    if not isinstance(place_name, str) or not place_name.strip():
        return _null

    # ── 1차: place_name + address, 100m ──────────────────────
    docs = kakao_search(f"{place_name} {address}", lat, lng, radius=200)
    for doc in docs:
        klat, klng = float(doc["y"]), float(doc["x"])
        dist = haversine_m(lat, lng, klat, klng)
        if dist <= HIGH_DIST_M:
            return {
                "kakao_place_id": doc["id"],
                "kakao_name": doc["place_name"],
                "distance_m": round(dist, 1),
                "confidence": "HIGH",
            }

    time.sleep(REQUEST_DELAY)

    # ── 2차: place_name 단독, 50m ──────────────────────────────
    docs = kakao_search(place_name, lat, lng, radius=100)
    for doc in docs:
        klat, klng = float(doc["y"]), float(doc["x"])
        dist = haversine_m(lat, lng, klat, klng)
        if dist <= MED_DIST_M and name_match(place_name, doc["place_name"]):
            return {
                "kakao_place_id": doc["id"],
                "kakao_name": doc["place_name"],
                "distance_m": round(dist, 1),
                "confidence": "MED",
            }

    return {"kakao_place_id": None, "kakao_name": None, "distance_m": None, "confidence": None}


def build_kakao_map(
    places_path: str = "output/places.csv",
    output_path: str = OUTPUT_PATH,
    checkpoint_path: str = CHECKPOINT_PATH,
):
    if not KAKAO_API_KEY:
        raise EnvironmentError("KAKAO_REST_API_KEY 환경변수를 설정하세요.")

    os.makedirs("output", exist_ok=True)

    df = pd.read_csv(places_path, usecols=["naver_place_id", "place_name", "address", "lat", "lng"])
    logger.info(f"장소 로드: {len(df)}개")

    # 체크포인트 이어받기
    done_ids = set()
    rows = []
    if os.path.exists(checkpoint_path):
        ckpt = pd.read_csv(checkpoint_path, dtype={"naver_place_id": str})
        done_ids = set(ckpt["naver_place_id"].astype(str))
        rows = ckpt.to_dict("records")
        logger.info(f"체크포인트 재개: {len(done_ids)}개 완료")

    total = len(df)
    for i, row in df.iterrows():
        pid = str(row["naver_place_id"])
        if pid in done_ids:
            continue

        result = find_kakao_id(row["place_name"], row["address"], row["lat"], row["lng"])
        rows.append({"naver_place_id": pid, **result})
        done_ids.add(pid)

        time.sleep(REQUEST_DELAY)

        # 500개마다 체크포인트 저장
        if len(done_ids) % 500 == 0:
            pd.DataFrame(rows).to_csv(checkpoint_path, index=False)
            matched = sum(1 for r in rows if r["kakao_place_id"])
            logger.info(f"[{len(done_ids)}/{total}] 매핑: {matched} / 미매핑: {len(done_ids)-matched}")

    result_df = pd.DataFrame(rows)
    result_df.to_csv(output_path, index=False)

    # 체크포인트 정리
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    # 결과 요약
    matched_high = (result_df["confidence"] == "HIGH").sum()
    matched_med  = (result_df["confidence"] == "MED").sum()
    unmatched    = result_df["kakao_place_id"].isna().sum()

    logger.info("=" * 40)
    logger.info(f"총 장소:       {len(result_df):,}")
    logger.info(f"매핑 HIGH:     {matched_high:,}  ({matched_high/len(result_df)*100:.1f}%)")
    logger.info(f"매핑 MED:      {matched_med:,}   ({matched_med/len(result_df)*100:.1f}%)")
    logger.info(f"미매핑:        {unmatched:,}   ({unmatched/len(result_df)*100:.1f}%)")
    logger.info(f"저장: {output_path}")

    return result_df


if __name__ == "__main__":
    build_kakao_map()
