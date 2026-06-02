"""매듭 PWA 아이콘 생성 (Pillow). 인디고 라운드스퀘어 + 흰색 매듭(연결고리) 마크.
실행: python frontend/scripts/gen_icons.py  → frontend/public/icons/*.png
"""
import math
import os
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "..", "public", "icons")
os.makedirs(OUT, exist_ok=True)

INDIGO = (79, 70, 229)      # #4f46e5
INDIGO_DK = (67, 56, 202)   # #4338ca
WHITE = (255, 255, 255)


def _grad_rounded(size, radius_ratio, c1, c2):
    """세로 그라데이션 라운드 스퀘어."""
    S = size * 4  # supersample
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    for y in range(S):
        t = y / S
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for x in range(0, S, S):  # row fill via paste below
            pass
        grad.paste((r, g, b, 255), (0, y, S, y + 1))
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    rad = int(S * radius_ratio)
    md.rounded_rectangle([0, 0, S - 1, S - 1], radius=rad, fill=255)
    img.paste(grad, (0, 0), mask)
    return img.resize((size, size), Image.LANCZOS)


def _ring(draw, cx, cy, r, w, color):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=w)


def _knot(size, glyph_ratio):
    """흰색 매듭 마크: 두 개의 인터로킹 링(연결고리)."""
    S = size * 4
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    g = S * glyph_ratio
    r = g * 0.30
    w = max(2, int(S * 0.062))
    off = r * 0.78
    cx, cy = S / 2, S / 2
    # 링 A (좌상) , 링 B (우하) — 살짝 대각 오프셋
    ax, ay = cx - off, cy - off
    bx, by = cx + off, cy + off
    _ring(d, ax, ay, r, w, WHITE)
    _ring(d, bx, by, r, w, WHITE)
    # 인터록 효과: B가 A 위로 지나가게, A의 우하 호를 B 색(흰색)으로 다시 덮은 뒤
    # B의 좌상 호를 한 번 더 그려 '겹쳐 지나가는' 느낌. (간단화: B를 한 번 더 위에 그림)
    _ring(d, ax, ay, r, w, WHITE)
    # 작은 indigo 갭으로 교차 표현
    gap = int(w * 1.7)
    # A의 우하단 교차점 부근에 indigo 갭
    ix, iy = (ax + bx) / 2, (ay + by) / 2
    d.ellipse([ix - gap, iy - gap, ix + gap, iy + gap], fill=(0, 0, 0, 0))
    _ring(d, bx, by, r, w, WHITE)
    return layer.resize((size, size), Image.LANCZOS)


def make(size, maskable=False, opaque=False):
    if maskable:
        # 마스커블: 라운딩 최소(거의 풀블리드), 글리프는 세이프존(중앙 ~56%)
        bg = _grad_rounded(size, 0.0, INDIGO, INDIGO_DK)
        glyph = _knot(size, 0.56)
    elif opaque:
        bg = _grad_rounded(size, 0.22, INDIGO, INDIGO_DK)
        glyph = _knot(size, 0.66)
    else:
        bg = _grad_rounded(size, 0.22, INDIGO, INDIGO_DK)
        glyph = _knot(size, 0.66)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(bg)
    out.alpha_composite(glyph)
    if opaque:
        flat = Image.new("RGB", (size, size), INDIGO)
        flat.paste(out, (0, 0), out)
        return flat
    return out


def save(img, name):
    img.save(os.path.join(OUT, name))
    print("  ✓", name, img.size)


print("아이콘 생성 →", os.path.abspath(OUT))
save(make(192), "icon-192.png")
save(make(512), "icon-512.png")
save(make(192, maskable=True), "icon-192-maskable.png")
save(make(512, maskable=True), "icon-512-maskable.png")
save(make(180, opaque=True), "apple-touch-icon.png")
save(make(32, opaque=True), "favicon-32.png")
save(make(1024), "icon-1024.png")  # TWA/Play Store용 고해상
print("완료.")
