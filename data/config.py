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
REQUEST_DELAY_SEC: float = 1.0
MAX_RETRIES: int = 3
SEARCH_RESULT_LIMIT: int = 50

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
