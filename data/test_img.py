import sys, re, time, requests
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': 'https://map.naver.com/',
}
PLACE_RE = re.compile(r'PlaceDetailImages.*?"origin":"([^"]+)"')
MENU_RE  = re.compile(r'menuImages.*?"imageUrl":"([^"]+)"')

df = pd.read_csv('output/places.csv', encoding='utf-8')
ids   = df['naver_place_id'].head(5).tolist()
names = df['place_name'].head(5).tolist()

session = requests.Session()
for pid, name in zip(ids, names):
    time.sleep(0.8)
    res = session.get(f'https://m.place.naver.com/place/{pid}/home', headers=HEADERS, timeout=8)
    html = res.text
    m = PLACE_RE.search(html)
    if m:
        url = m.group(1).replace('\\u002F', '/')
        src = 'PlaceDetail'
    else:
        m2 = MENU_RE.search(html)
        url = m2.group(1).replace('\\u002F', '/') if m2 else None
        src = 'Menu' if m2 else 'None'
    print(f'[{pid}] {name[:15]} | {src}: {str(url)[:80]}')
