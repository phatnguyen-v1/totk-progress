"""Draws the app icon (this project's own artwork): a folded map with a dotted trail ending at a pin.
Writes web/app-icon.png (256 px, window / browser tab) and app.ico (16-256 px, the exe).
Run: python tools/make_app_icon.py"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
S = 1024  # drawn large, then scaled down for smooth edges

BG, BORDER = (26, 32, 38), (111, 211, 194)
PAPER = [(236, 222, 180), (214, 196, 148), (236, 222, 180), (214, 196, 148)]
INK, TRAIL = (120, 86, 48), (176, 70, 52)
GOLD, GOLD_DARK = (238, 192, 84), (120, 82, 20)


def draw():
    img = Image.new('RGBA', (S, S))
    d = ImageDraw.Draw(img)
    # badge
    d.rounded_rectangle((24, 24, S - 24, S - 24), radius=210, fill=BG, outline=BORDER, width=36)

    # folded map: four panels, alternately tilted (zig-zag top and bottom edges)
    left, right, top, bottom, fold = 170, 854, 250, 800, 46
    xs = [left + (right - left) * i / 4 for i in range(5)]
    for i in range(4):
        dy0 = 0 if i % 2 == 0 else fold
        dy1 = fold if i % 2 == 0 else 0
        d.polygon([(xs[i], top + dy0), (xs[i + 1], top + dy1), (xs[i + 1], bottom + dy1), (xs[i], bottom + dy0)],
                  fill=PAPER[i])
    outline = [(xs[i], top + (0 if i % 2 == 0 else fold)) for i in range(5)] + \
              [(xs[i], bottom + (0 if i % 2 == 0 else fold)) for i in range(4, -1, -1)]
    d.line(outline + [outline[0]], fill=INK, width=14, joint='curve')

    # contour hints
    d.arc((230, 330, 470, 520), 200, 340, fill=(190, 168, 120), width=12)
    d.arc((560, 560, 800, 740), 190, 350, fill=(190, 168, 120), width=12)

    # dotted trail from bottom-left to the pin
    pts = [(250, 700), (330, 640), (400, 650), (470, 600), (520, 520), (600, 480), (660, 440)]
    for x, y in pts:
        d.ellipse((x - 20, y - 20, x + 20, y + 20), fill=TRAIL)

    # pin
    cx, cy, r = 700, 330, 110
    tip = (cx, cy + 250)
    d.polygon([(cx - r * 0.86, cy + r * 0.5), (cx + r * 0.86, cy + r * 0.5), tip], fill=GOLD_DARK)
    d.ellipse((cx - r - 16, cy - r - 16, cx + r + 16, cy + r + 16), fill=GOLD_DARK)
    d.polygon([(cx - r * 0.74, cy + r * 0.48), (cx + r * 0.74, cy + r * 0.48), (cx, tip[1] - 26)], fill=GOLD)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GOLD)
    d.ellipse((cx - 42, cy - 42, cx + 42, cy + 42), fill=BG)
    return img


def main():
    big = draw()
    png = big.resize((256, 256), Image.LANCZOS)
    png.save(ROOT / 'web' / 'app-icon.png', optimize=True)
    sizes = [(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
    big.resize((256, 256), Image.LANCZOS).save(ROOT / 'app.ico', sizes=sizes)
    print('web/app-icon.png, app.ico')


if __name__ == '__main__':
    main()
