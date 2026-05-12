# 네이버 지도 장소 크롤러 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 네이버 지도 내부 API를 활용하여 서울 + 6대 광역시 약 6,000곳의 장소 데이터(평점, 리뷰수, 키워드태그, 메뉴, 영업시간)를 수집하는 크롤러 구축

**Architecture:** 네이버 지도 내부 GraphQL/REST API를 직접 호출하여 JSON 응답을 파싱. 거점 좌표 + 카테고리 기반 검색 → 장소 ID 수집 → 장소 상세 조회 → CSV/JSON 저장. httpx 비동기 클라이언트 사용.

**Tech Stack:** Python 3.12, httpx, pandas, tqdm, asyncio

---

## 파일 구조

```
madeup/data/
├── .venv/                    # Python 가상환경 (gitignore)
├── requirements.txt          # 의존성
├── config.py                 # 거점 좌표, 카테고리 매핑, 상수
├── crawler/
│   ├── __init__.py
│   ├── search.py             # 거점 기반 장소 목록 검색 (place_id 수집)
│   ├── detail.py             # 장소 상세 정보 조회 (GraphQL)
│   └── utils.py              # 헤더 생성, rate limit, 재시도 로직
├── run_search.py             # 1단계 실행: 장소 ID 수집
├── run_detail.py             # 2단계 실행: 장소 상세 수집
├── run_all.py                # 전체 파이프라인 실행
├── output/                   # 결과 저장 디렉토리
│   ├── place_ids/            # 거점별 place_id CSV
│   ├── raw/                  # 장소 상세 raw JSON
│   └── places.csv            # 최종 정제된 데이터
└── tests/
    ├── test_search.py
    ├── test_detail.py
    └── test_utils.py
```

---

### Task 1: 프로젝트 세팅 + config

**Files:**
- Create: `data/requirements.txt`
- Create: `data/config.py`
- Create: `data/crawler/__init__.py`

- [ ] **Step 1: requirements.txt 작성**

```txt
httpx==0.28.1
beautifulsoup4==4.14.3
pandas==3.0.2
tqdm==4.67.3
```

- [ ] **Step 2: config.py 작성 — 거점 좌표 + 카테고리 정의**

```python
"""크롤링 설정: 거점 좌표, 카테고리, 상수"""

# 거점 좌표 (이름, 위도, 경도, 검색 반경m)
HUBS: list[dict] = [
    # 서울 (7거점)
    {"name": "서울_강남", "lat": 37.4979, "lng": 127.0276, "radius": 1500},
    {"name": "서울_홍대", "lat": 37.5563, "lng": 126.9236, "radius": 1500},
    {"name": "서울_건대", "lat": 37.5407, "lng": 127.0700, "radius": 1500},
    {"name": "서울_종로", "lat": 37.5704, "lng": 126.9922, "radius": 1500},
    {"name": "서울_여의도", "lat": 37.5216, "lng": 126.9243, "radius": 1500},
    {"name": "서울_성수", "lat": 37.5445, "lng": 127.0560, "radius": 1500},
    {"name": "서울_잠실", "lat": 37.5133, "lng": 127.1001, "radius": 1500},
    # 부산 (3거점)
    {"name": "부산_서면", "lat": 35.1578, "lng": 129.0599, "radius": 2000},
    {"name": "부산_해운대", "lat": 35.1631, "lng": 129.1635, "radius": 2000},
    {"name": "부산_남포동", "lat": 35.0977, "lng": 129.0324, "radius": 2000},
    # 대구 (3거점)
    {"name": "대구_동성로", "lat": 35.8691, "lng": 128.5946, "radius": 2000},
    {"name": "대구_수성구", "lat": 35.8580, "lng": 128.6320, "radius": 2000},
    {"name": "대구_범어", "lat": 35.8594, "lng": 128.6235, "radius": 2000},
    # 인천 (2거점)
    {"name": "인천_부평", "lat": 37.5074, "lng": 126.7219, "radius": 2000},
    {"name": "인천_구월", "lat": 37.4492, "lng": 126.7042, "radius": 2000},
    # 광주 (2거점)
    {"name": "광주_충장로", "lat": 35.1492, "lng": 126.9158, "radius": 2000},
    {"name": "광주_상무", "lat": 35.1533, "lng": 126.8514, "radius": 2000},
    # 대전 (3거점) — 시연 대상, 밀도 높게
    {"name": "대전_둔산", "lat": 36.3551, "lng": 127.3830, "radius": 2000},
    {"name": "대전_은행동", "lat": 36.3275, "lng": 127.4271, "radius": 2000},
    {"name": "대전_유성", "lat": 36.3620, "lng": 127.3562, "radius": 2000},
    # 울산 (2거점)
    {"name": "울산_삼산", "lat": 35.5383, "lng": 129.3368, "radius": 2000},
    {"name": "울산_성남", "lat": 35.5567, "lng": 129.3149, "radius": 2000},
]

# 검색 카테고리 (네이버 지도 검색 키워드)
CATEGORIES: list[dict] = [
    {"name": "음식점", "keywords": ["맛집", "한식", "양식", "중식", "일식", "분식"]},
    {"name": "카페", "keywords": ["카페", "디저트카페", "브런치카페"]},
    {"name": "술집", "keywords": ["호프", "이자카야", "와인바", "포차"]},
    {"name": "스터디", "keywords": ["스터디카페", "회의실", "공유오피스"]},
]

# 요청 설정
REQUEST_DELAY_SEC: float = 1.0  # 요청 간 딜레이
MAX_RETRIES: int = 3
SEARCH_RESULT_LIMIT: int = 50  # 검색당 최대 결과 수

# User-Agent 로테이션 풀
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

# 출력 경로
OUTPUT_DIR = "output"
PLACE_IDS_DIR = f"{OUTPUT_DIR}/place_ids"
RAW_DIR = f"{OUTPUT_DIR}/raw"
FINAL_CSV = f"{OUTPUT_DIR}/places.csv"
```

- [ ] **Step 3: crawler/__init__.py 생성**

```python
```

- [ ] **Step 4: output 디렉토리 생성 + .gitignore 업데이트**

```bash
cd /c/Users/hong2/madeup/data
mkdir -p output/place_ids output/raw
```

`madeup/.gitignore`에 추가:
```
# Data crawler
data/.venv/
data/output/
```

- [ ] **Step 5: 커밋**

```bash
git add data/requirements.txt data/config.py data/crawler/__init__.py .gitignore
git commit -m "feat(data): 네이버 크롤러 프로젝트 세팅 — 거점 22곳, 카테고리 4종"
```

---

### Task 2: utils — 헤더, 딜레이, 재시도

**Files:**
- Create: `data/crawler/utils.py`
- Create: `data/tests/test_utils.py`

- [ ] **Step 1: 테스트 작성**

```python
# data/tests/test_utils.py
import time
from crawler.utils import get_headers, rate_limit_sleep

def test_get_headers_has_required_fields():
    headers = get_headers()
    assert "User-Agent" in headers
    assert "Referer" in headers
    assert "pcmap.place.naver.com" in headers["Referer"]

def test_get_headers_rotates_user_agent():
    agents = {get_headers()["User-Agent"] for _ in range(20)}
    assert len(agents) > 1  # 최소 2종 이상 나와야 함

def test_rate_limit_sleep_delays():
    start = time.time()
    rate_limit_sleep(0.1)
    elapsed = time.time() - start
    assert elapsed >= 0.1
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
cd /c/Users/hong2/madeup/data
source .venv/Scripts/activate
pip install pytest
python -m pytest tests/test_utils.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'crawler.utils'`

- [ ] **Step 3: utils.py 구현**

```python
# data/crawler/utils.py
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
                # rate limit — 백오프
                wait = (attempt + 1) * 5
                print(f"  [403] rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  [{resp.status_code}] {url[:80]}...")
        except httpx.RequestError as e:
            print(f"  [error] {e}")
            time.sleep(2)
    return None
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
python -m pytest tests/test_utils.py -v
```

Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add data/crawler/utils.py data/tests/test_utils.py
git commit -m "feat(data): HTTP 유틸 — 헤더 로테이션, rate limit, 재시도"
```

---

### Task 3: search — 거점 기반 장소 ID 수집

**Files:**
- Create: `data/crawler/search.py`
- Create: `data/tests/test_search.py`

- [ ] **Step 1: 테스트 작성**

```python
# data/tests/test_search.py
from crawler.search import build_search_url, parse_search_results


def test_build_search_url_contains_query():
    url = build_search_url("맛집", lat=37.4979, lng=127.0276)
    assert "맛집" in url or "%EB%A7%9B%EC%A7%91" in url
    assert "127.0276" in url
    assert "37.4979" in url


def test_parse_search_results_extracts_place_ids():
    # 네이버 검색 API 응답 형태 모킹
    mock_response = {
        "result": {
            "place": {
                "list": [
                    {"id": "1234567890", "name": "테스트식당", "x": "127.0276", "y": "37.4979", "category": ["음식점"]},
                    {"id": "9876543210", "name": "테스트카페", "x": "127.0280", "y": "37.4980", "category": ["카페"]},
                ]
            }
        }
    }
    places = parse_search_results(mock_response)
    assert len(places) == 2
    assert places[0]["id"] == "1234567890"
    assert places[0]["name"] == "테스트식당"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
python -m pytest tests/test_search.py -v
```

Expected: FAIL

- [ ] **Step 3: search.py 구현**

```python
# data/crawler/search.py
"""네이버 지도 검색으로 장소 ID 목록 수집"""

import json
import urllib.parse
import httpx
from tqdm import tqdm

from config import HUBS, CATEGORIES, SEARCH_RESULT_LIMIT, PLACE_IDS_DIR
from crawler.utils import get_headers, rate_limit_sleep, fetch_with_retry


SEARCH_URL = "https://map.naver.com/v5/api/search"


def build_search_url(query: str, lat: float, lng: float) -> str:
    """네이버 지도 검색 URL 생성"""
    params = {
        "caller": "pcweb",
        "query": query,
        "type": "all",
        "searchCoord": f"{lng};{lat}",
        "page": "1",
        "displayCount": str(SEARCH_RESULT_LIMIT),
    }
    return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"


def parse_search_results(data: dict) -> list[dict]:
    """검색 응답에서 장소 ID/이름/좌표/카테고리 추출"""
    places = []
    try:
        place_list = data.get("result", {}).get("place", {}).get("list", [])
        for item in place_list:
            places.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "x": item.get("x", ""),
                "y": item.get("y", ""),
                "category": item.get("category", []),
            })
    except (KeyError, TypeError):
        pass
    return places


def search_hub_category(
    client: httpx.Client,
    hub: dict,
    keyword: str,
) -> list[dict]:
    """하나의 거점 + 키워드 조합으로 장소 검색"""
    url = build_search_url(keyword, hub["lat"], hub["lng"])
    resp = fetch_with_retry(client, "GET", url)
    if resp is None:
        return []
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return []
    places = parse_search_results(data)
    # 거점 정보 태깅
    for p in places:
        p["hub"] = hub["name"]
        p["keyword"] = keyword
    return places


def search_all_hubs() -> list[dict]:
    """전체 거점 × 카테고리 검색 실행. 중복 제거 후 반환."""
    all_places = []
    seen_ids: set[str] = set()

    total = sum(len(cat["keywords"]) for cat in CATEGORIES) * len(HUBS)

    with httpx.Client(timeout=30) as client:
        with tqdm(total=total, desc="검색 진행") as pbar:
            for hub in HUBS:
                for cat in CATEGORIES:
                    for keyword in cat["keywords"]:
                        places = search_hub_category(client, hub, keyword)
                        for p in places:
                            if p["id"] not in seen_ids:
                                p["category_group"] = cat["name"]
                                all_places.append(p)
                                seen_ids.add(p["id"])
                        rate_limit_sleep()
                        pbar.update(1)

    print(f"\n총 {len(all_places)}개 장소 수집 (중복 제거 후)")
    return all_places
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
python -m pytest tests/test_search.py -v
```

Expected: 2 passed

- [ ] **Step 5: run_search.py 작성**

```python
# data/run_search.py
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
```

- [ ] **Step 6: 커밋**

```bash
git add data/crawler/search.py data/tests/test_search.py data/run_search.py
git commit -m "feat(data): 네이버 지도 검색 — 거점×카테고리 장소 ID 수집"
```

---

### Task 4: detail — 장소 상세 정보 조회

**Files:**
- Create: `data/crawler/detail.py`
- Create: `data/tests/test_detail.py`

- [ ] **Step 1: 테스트 작성**

```python
# data/tests/test_detail.py
from crawler.detail import build_detail_url, parse_detail_response


def test_build_detail_url_contains_place_id():
    url = build_detail_url("1234567890")
    assert "1234567890" in url


def test_parse_detail_response_extracts_fields():
    # GraphQL 응답 모킹 (실제 구조 기반)
    mock_data = {
        "id": "1234567890",
        "name": "테스트식당",
        "category": "음식점 > 한식 > 국밥",
        "roadAddress": "서울 강남구 테헤란로 1",
        "x": "127.0276",
        "y": "37.4979",
        "reviewCount": 150,
        "blogReviewCount": 45,
        "visitorReviewScore": 4.3,
        "keywords": ["분위기좋은", "단체모임"],
        "menuInfo": [
            {"name": "된장찌개", "price": "8000"},
            {"name": "김치찌개", "price": "9000"},
        ],
        "businessHours": "매일 11:00 - 22:00",
    }
    result = parse_detail_response(mock_data)
    assert result["naver_place_id"] == "1234567890"
    assert result["place_name"] == "테스트식당"
    assert result["rating"] == 4.3
    assert result["review_count"] == 150
    assert result["blog_review_count"] == 45
    assert "분위기좋은" in result["keyword_tags"]
    assert result["menu_prices"][0]["name"] == "된장찌개"
    assert result["business_hours"] == "매일 11:00 - 22:00"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
python -m pytest tests/test_detail.py -v
```

Expected: FAIL

- [ ] **Step 3: detail.py 구현**

```python
# data/crawler/detail.py
"""네이버 장소 상세 정보 조회 (내부 API)"""

import json
import os
import httpx
from tqdm import tqdm

from config import RAW_DIR, FINAL_CSV
from crawler.utils import get_headers, rate_limit_sleep, fetch_with_retry


# 네이버 플레이스 상세 API (장소 ID로 조회)
DETAIL_URL_TEMPLATE = "https://map.naver.com/v5/api/sites/summary/{place_id}?lang=ko"

# 대안: pcmap GraphQL endpoint
GRAPHQL_URL = "https://pcmap-api.place.naver.com/graphql"


def build_detail_url(place_id: str) -> str:
    """장소 상세 API URL 생성"""
    return DETAIL_URL_TEMPLATE.format(place_id=place_id)


def parse_detail_response(data: dict) -> dict:
    """API 응답에서 필요한 필드만 추출하여 정규화된 dict 반환"""
    keywords = data.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]

    menu_info = data.get("menuInfo", [])
    menu_prices = []
    for item in menu_info:
        if isinstance(item, dict):
            menu_prices.append({
                "name": item.get("name", ""),
                "price": item.get("price", ""),
            })

    return {
        "naver_place_id": str(data.get("id", "")),
        "place_name": data.get("name", ""),
        "category": data.get("category", ""),
        "address": data.get("roadAddress", "") or data.get("address", ""),
        "lat": float(data.get("y", 0)),
        "lng": float(data.get("x", 0)),
        "rating": float(data.get("visitorReviewScore", 0) or 0),
        "review_count": int(data.get("reviewCount", 0) or 0),
        "blog_review_count": int(data.get("blogReviewCount", 0) or 0),
        "keyword_tags": keywords,
        "menu_prices": menu_prices,
        "business_hours": data.get("businessHours", "") or "",
    }


def fetch_place_detail(client: httpx.Client, place_id: str) -> dict | None:
    """장소 ID로 상세 정보 조회"""
    url = build_detail_url(place_id)
    resp = fetch_with_retry(client, "GET", url)
    if resp is None:
        return None
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return None
    return parse_detail_response(data)


def fetch_all_details(place_ids: list[str]) -> list[dict]:
    """전체 장소 ID에 대해 상세 정보 수집"""
    results = []
    failed = []

    with httpx.Client(timeout=30) as client:
        for pid in tqdm(place_ids, desc="상세 수집"):
            detail = fetch_place_detail(client, pid)
            if detail:
                results.append(detail)
                # raw JSON 개별 저장 (복구용)
                raw_path = os.path.join(RAW_DIR, f"{pid}.json")
                os.makedirs(RAW_DIR, exist_ok=True)
                with open(raw_path, "w", encoding="utf-8") as f:
                    json.dump(detail, f, ensure_ascii=False, indent=2)
            else:
                failed.append(pid)
            rate_limit_sleep()

    print(f"\n수집 완료: {len(results)}곳 성공, {len(failed)}곳 실패")
    if failed:
        print(f"실패 ID: {failed[:10]}{'...' if len(failed) > 10 else ''}")
    return results
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
python -m pytest tests/test_detail.py -v
```

Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add data/crawler/detail.py data/tests/test_detail.py
git commit -m "feat(data): 장소 상세 조회 — 평점/리뷰/태그/메뉴/영업시간 파싱"
```

---

### Task 5: run_detail + run_all + CSV 저장

**Files:**
- Create: `data/run_detail.py`
- Create: `data/run_all.py`

- [ ] **Step 1: run_detail.py 작성**

```python
# data/run_detail.py
"""2단계: 장소 ID 기반 상세 정보 수집"""

import json
import os
import pandas as pd
from crawler.detail import fetch_all_details
from config import PLACE_IDS_DIR, RAW_DIR, FINAL_CSV, OUTPUT_DIR


def main():
    # 1단계 결과 로드
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

    # 상세 수집
    results = fetch_all_details(remaining)

    # 기존 + 신규 합쳐서 CSV 생성
    all_results = []
    for fname in os.listdir(RAW_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(RAW_DIR, fname), "r", encoding="utf-8") as f:
                all_results.append(json.load(f))

    # DataFrame 변환 시 list/dict 컬럼은 JSON 문자열로
    df = pd.DataFrame(all_results)
    for col in ["keyword_tags", "menu_prices"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x)

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
```

- [ ] **Step 2: run_all.py 작성**

```python
# data/run_all.py
"""전체 파이프라인: 검색 → 상세 → CSV"""

from run_search import main as search_main
from run_detail import main as detail_main


def main():
    print("=" * 60)
    print("[1/2] 장소 ID 수집")
    print("=" * 60)
    search_main()

    print("\n" + "=" * 60)
    print("[2/2] 장소 상세 수집")
    print("=" * 60)
    detail_main()

    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 커밋**

```bash
git add data/run_detail.py data/run_all.py
git commit -m "feat(data): 실행 스크립트 — 이어하기 지원, CSV 저장, 전체 파이프라인"
```

---

### Task 6: 실제 API 탐색 + 엔드포인트 검증

**실제 네이버 API를 1~2건 호출하여 응답 구조 확인 후 파서를 보정하는 단계.**

- [ ] **Step 1: 검색 API 1건 테스트**

```bash
cd /c/Users/hong2/madeup/data
source .venv/Scripts/activate
python -c "
import httpx
from crawler.search import build_search_url, parse_search_results
from crawler.utils import get_headers

url = build_search_url('맛집', lat=37.4979, lng=127.0276)
print('URL:', url[:100])
resp = httpx.get(url, headers=get_headers(), timeout=30)
print('Status:', resp.status_code)
print('Keys:', list(resp.json().keys())[:10] if resp.status_code == 200 else resp.text[:200])

if resp.status_code == 200:
    data = resp.json()
    places = parse_search_results(data)
    print(f'파싱 결과: {len(places)}곳')
    if places:
        print('첫 번째:', places[0])
"
```

- [ ] **Step 2: 검색 응답 구조에 맞게 parse_search_results 보정**

실제 응답 JSON 키 구조가 `result.place.list`가 아닐 수 있음.
응답 확인 후 `search.py`의 파서를 실제 구조에 맞게 수정.

- [ ] **Step 3: 상세 API 1건 테스트**

```bash
python -c "
import httpx
from crawler.detail import build_detail_url
from crawler.utils import get_headers

# Step 1에서 얻은 place_id 사용
place_id = 'PLACE_ID_FROM_STEP1'
url = build_detail_url(place_id)
print('URL:', url)
resp = httpx.get(url, headers=get_headers(), timeout=30)
print('Status:', resp.status_code)
if resp.status_code == 200:
    import json
    print(json.dumps(resp.json(), ensure_ascii=False, indent=2)[:2000])
else:
    print(resp.text[:500])
"
```

- [ ] **Step 4: 상세 응답 구조에 맞게 parse_detail_response 보정**

실제 응답의 키 이름이 다를 수 있음 (예: `visitorReviewScore` vs `scoreInfo`).
응답 확인 후 `detail.py`의 파서를 실제 구조에 맞게 수정.

- [ ] **Step 5: 커밋**

```bash
git add data/crawler/search.py data/crawler/detail.py
git commit -m "fix(data): 실제 네이버 API 응답 구조에 맞게 파서 보정"
```

---

### Task 7: 소규모 테스트 실행 (대전 1거점)

- [ ] **Step 1: config.py에서 대전 둔산 1거점만 활성화**

임시로 `HUBS`를 대전 둔산 1개만 남기고, `CATEGORIES`에서 `keywords`를 카테고리당 1개만 남겨서 테스트.

- [ ] **Step 2: 검색 실행**

```bash
cd /c/Users/hong2/madeup/data
source .venv/Scripts/activate
python run_search.py
```

Expected: 수십~200곳 정도의 place_id 수집

- [ ] **Step 3: 상세 수집 실행**

```bash
python run_detail.py
```

Expected: `output/places.csv`에 수십 곳의 전체 데이터

- [ ] **Step 4: CSV 확인**

```bash
python -c "
import pandas as pd
df = pd.read_csv('output/places.csv')
print(f'행: {len(df)}')
print(f'컬럼: {list(df.columns)}')
print(df[['place_name','rating','review_count','keyword_tags']].head(10))
print(f'\nrating 분포:\n{df[\"rating\"].describe()}')
print(f'\nkeyword_tags 예시:\n{df[\"keyword_tags\"].head(5)}')
"
```

- [ ] **Step 5: 문제 없으면 config.py 원복 (전체 거점) + 커밋**

```bash
git add data/config.py
git commit -m "test(data): 대전 1거점 테스트 완료, 전체 거점으로 원복"
```

---

### Task 8: 전체 크롤링 실행

- [ ] **Step 1: 전체 실행**

```bash
cd /c/Users/hong2/madeup/data
source .venv/Scripts/activate
python run_all.py
```

예상 소요: 3~5시간 (6,000곳 × 1초 딜레이 기준)

- [ ] **Step 2: 결과 검증**

```bash
python -c "
import pandas as pd
df = pd.read_csv('output/places.csv')
print(f'총 장소: {len(df)}')
print(f'\n도시별 분포:')
# address에서 도시 추출
df['city'] = df['address'].str.split(' ').str[0]
print(df['city'].value_counts())
print(f'\n카테고리 분포:')
print(df['category'].str.split(' > ').str[0].value_counts().head(10))
print(f'\nrating 분포:')
print(df['rating'].describe())
print(f'\nreview_count 분포:')
print(df['review_count'].describe())
"
```

- [ ] **Step 3: 최종 커밋**

```bash
git add data/
git commit -m "feat(data): 네이버 크롤러 완성 — 전체 파이프라인 실행 완료"
```
