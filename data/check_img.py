import re, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('C:/Users/hong2/madeup/data/naver_test_1389858469.html', encoding='utf-8') as f:
    html = f.read()

m = re.search(r'PlaceDetailImages.{0,800}', html)
if m:
    print('PlaceDetailImages:')
    print(repr(m.group()[:600]))
print()

urls = re.findall(r'https:\\u002F\\u002F[a-zA-Z0-9._/\-]+\.jpg', html)
print(f'jpg URLs: {len(urls)}')
for u in urls[:5]:
    print(' ', u.replace('\\u002F', '/'))
