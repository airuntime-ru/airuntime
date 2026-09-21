"""Backgrounds for the PowerPoint deck.

pptxgenjs has no gradient fills and no repeating background, so the cover's MAX->AIRuntime
split and the starfield on the dark slides ship as images. Regenerate with:

    python make-backgrounds.py
"""

import random

from PIL import Image, ImageDraw

W, H = 2560, 1440  # 2x of 1280x720 so it stays crisp on a 13.3in slide
MAX_BLUE, MAX_VIOLET = (0, 119, 255), (123, 44, 255)
SPACE, SPACE2 = (5, 7, 15), (10, 17, 35)


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def diagonal(img, c0, c1, x0=0, x1=None):
    x1 = x1 or img.width
    draw = ImageDraw.Draw(img)
    span = x1 - x0
    for x in range(x0, x1):
        draw.line([(x, 0), (x, img.height)], fill=lerp(c0, c1, (x - x0) / max(span - 1, 1)))


def stars(img, count, seed, x0=0, x1=None):
    x1 = x1 or img.width
    rnd = random.Random(seed)
    draw = ImageDraw.Draw(img, "RGBA")
    for _ in range(count):
        x, y = rnd.randrange(x0, x1), rnd.randrange(0, img.height)
        r = rnd.choice([1, 1, 2, 2, 3])
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.randint(70, 215)))


def cover():
    img = Image.new("RGB", (W, H))
    split = int(W * 0.58)
    diagonal(img, MAX_BLUE, MAX_VIOLET, 0, split)

    right = Image.new("RGB", (W - split, H))
    dr = ImageDraw.Draw(right)
    for y in range(H):
        dr.line([(0, y), (right.width, y)], fill=lerp(SPACE, SPACE2, y / H))
    glow = Image.new("RGBA", right.size, (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    for i in range(70, 0, -1):
        dg.ellipse(
            [right.width * 0.7 - i * 14, -220 - i * 9, right.width * 0.7 + i * 14, 340 + i * 9],
            fill=(35, 136, 255, 3),
        )
    img.paste(Image.alpha_composite(right.convert("RGBA"), glow).convert("RGB"), (split, 0))
    stars(img, 420, 11, split, W)

    # The staircase steps out of the bright half and across the seam into the dark one.
    dc = ImageDraw.Draw(img, "RGBA")
    step_w, step_h = 128, 180
    for i, (col, alpha) in enumerate(
        [(0, 26), (1, 34), (2, 30), (1, 20), (2, 32), (3, 26), (2, 18), (3, 28)]
    ):
        x = split - 300 + col * step_w
        dc.rectangle([x, i * step_h, x + step_w, (i + 1) * step_h], fill=(255, 255, 255, alpha))
    img.save("bg-cover.png", optimize=True)


def dark():
    img = Image.new("RGB", (W, H))
    dd = ImageDraw.Draw(img)
    for y in range(H):
        dd.line([(0, y), (W, y)], fill=lerp(SPACE, SPACE2, min(1.0, y / (H * 0.85))))
    bloom = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    db = ImageDraw.Draw(bloom)
    for i in range(90, 0, -1):
        db.ellipse(
            [W * 0.5 - i * 22, -420 - i * 10, W * 0.5 + i * 22, 300 + i * 10],
            fill=(35, 136, 255, 2),
        )
        db.ellipse(
            [W * 0.12 - i * 15, H * 0.2 - i * 9, W * 0.12 + i * 15, H * 0.2 + i * 9],
            fill=(124, 108, 255, 2),
        )
    img = Image.alpha_composite(img.convert("RGBA"), bloom).convert("RGB")
    stars(img, 520, 7)
    img.save("bg-dark.png", optimize=True)


if __name__ == "__main__":
    cover()
    dark()
    print("wrote bg-cover.png, bg-dark.png")
