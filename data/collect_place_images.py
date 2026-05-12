"""장소 대표 사진 URL 수집
PlaceDetailImages[0] → menuImages[0] 순으로 폴백
결과: output/features/place_images.csv (naver_place_id, image_url)
"""

import re
import time
import random
import logging
import requests
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Referer": "https://map.naver.com/",
}

PLACE_IMAGE_RE = re.compile(
    r'"PlaceDetailImages","images":\[(\{"__typename":"Image","origin":"([^"]+)")'
)
MENU_IMAGE_RE = re.compile(
    r'"menuImages":\[.*?"imageUrl":"([^"]+)"'
)

# 429 시 backoff 설정
BACKOFF_BASE = 90      # 첫 번째 429: 90초 대기
BACKOFF_MAX = 300      # 최대 5분 대기
MAX_RETRIES = 3


def unescape_url(url: str) -> str:
    return url.replace("\\u002F", "/")


def get_image_url(pid: int, session: requests.Session) -> str | None:
    url = f"https://m.place.naver.com/place/{pid}/home"
    backoff = BACKOFF_BASE

    for attempt in range(MAX_RETRIES):
        try:
            res = session.get(url, headers=HEADERS, timeout=10, allow_redirects=True)

            if res.status_code == 429:
                wait = backoff + random.uniform(0, 30)
                logger.warning(f"[{pid}] 429 Too Many Requests — {wait:.0f}초 대기 후 재시도 ({attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
                backoff = min(backoff * 2, BACKOFF_MAX)
                # 세션 재생성으로 쿠키/연결 초기화
                session.cookies.clear()
                continue

            if res.status_code != 200:
                logger.debug(f"[{pid}] HTTP {res.status_code}")
                return None

            html = res.text

            m = PLACE_IMAGE_RE.search(html)
            if m:
                return unescape_url(m.group(2))

            m = MENU_IMAGE_RE.search(html)
            if m:
                return unescape_url(m.group(1))

            return None

        except Exception as e:
            logger.warning(f"[{pid}] 요청 실패: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(5)

    return None


def collect(
    places_path: str = "output/places.csv",
    output_path: str = "output/features/place_images.csv",
    delay_min: float = 1.5,
    delay_max: float = 3.0,
    checkpoint_every: int = 200,
):
    df = pd.read_csv(places_path, encoding="utf-8")
    ids = df["naver_place_id"].tolist()
    logger.info(f"총 {len(ids)}개 장소 수집 시작")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 체크포인트 재개 (URL 있는 항목만 완료로 처리 — 빈 URL은 재시도)
    done: dict[int, str] = {}
    checkpoint = Path(str(output_path).replace(".csv", "_checkpoint.csv"))
    if checkpoint.exists():
        cp = pd.read_csv(checkpoint)
        done = {
            int(row["naver_place_id"]): row["image_url"]
            for _, row in cp.iterrows()
            if pd.notna(row["image_url"]) and str(row["image_url"]).strip() != ""
        }
        skipped = len(cp) - len(done)
        logger.info(f"체크포인트 재개: {len(done)}개 확보 완료, {skipped}개 빈 URL 재시도 대상")

    session = requests.Session()
    results: list[tuple] = list(done.items())

    pending = [pid for pid in ids if pid not in done]
    logger.info(f"수집 대상: {len(pending)}개")

    for i, pid in enumerate(pending):
        img_url = get_image_url(pid, session)
        results.append((pid, img_url))

        if (i + 1) % checkpoint_every == 0:
            cp_df = pd.DataFrame(results, columns=["naver_place_id", "image_url"])
            cp_df.to_csv(checkpoint, index=False, encoding="utf-8-sig")
            found = sum(1 for _, u in results if u)
            logger.info(f"[{i+1}/{len(pending)}] 체크포인트 저장 — 사진 확보율: {found}/{len(results)} ({found/len(results)*100:.1f}%)")

        time.sleep(random.uniform(delay_min, delay_max))

    final = pd.DataFrame(results, columns=["naver_place_id", "image_url"])
    final.to_csv(output_path, index=False, encoding="utf-8-sig")

    found = final["image_url"].notna().sum()
    logger.info(f"완료: {found}/{len(final)} 장소 사진 확보 ({found/len(final)*100:.1f}%)")
    logger.info(f"저장: {output_path}")

    if checkpoint.exists():
        checkpoint.unlink()

    return final


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent)
    collect()
