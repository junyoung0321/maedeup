"""HTTP 요청 유틸: 헤더, rate limit, 재시도"""

import random
import time
import httpx
from config import USER_AGENTS, REQUEST_DELAY_SEC, MAX_RETRIES


def get_headers() -> dict[str, str]:
    """랜덤 User-Agent + 필수 Referer 헤더 반환"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "https://pcmap.place.naver.com/",
        "Accept": "application/json",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }


def rate_limit_sleep(delay: float | None = None) -> None:
    """요청 간 딜레이. 기본값은 config.REQUEST_DELAY_SEC"""
    time.sleep(delay if delay is not None else REQUEST_DELAY_SEC)


def fetch_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    max_retries: int = MAX_RETRIES,
    **kwargs,
) -> httpx.Response | None:
    """재시도 로직이 포함된 HTTP 요청. 실패 시 None 반환."""
    for attempt in range(max_retries):
        try:
            kwargs["headers"] = get_headers()
            resp = client.request(method, url, **kwargs)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 403:
                wait = (attempt + 1) * 5
                print(f"  [403] rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  [{resp.status_code}] {url[:80]}...")
        except httpx.RequestError as e:
            print(f"  [error] {e}")
            time.sleep(2)
    return None
