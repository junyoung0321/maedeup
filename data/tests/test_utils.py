import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.utils import get_headers, rate_limit_sleep


def test_get_headers_has_required_fields():
    headers = get_headers()
    assert "User-Agent" in headers
    assert "Referer" in headers
    assert "pcmap.place.naver.com" in headers["Referer"]


def test_get_headers_rotates_user_agent():
    agents = {get_headers()["User-Agent"] for _ in range(20)}
    assert len(agents) > 1


def test_rate_limit_sleep_delays():
    start = time.time()
    rate_limit_sleep(0.1)
    elapsed = time.time() - start
    assert elapsed >= 0.1
