"""Install AIRuntime brand assets from provided PNG sources."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
BRAND = PUBLIC / "brand"
SOURCE = ROOT / "brand-source"

SRC_SYMBOL = SOURCE / "symbol.png"
SRC_WORDMARK = SOURCE / "wordmark.png"
SRC_FULL = SOURCE / "logo-full.png"


def remove_near_white_background(image: Image.Image, threshold: int = 246) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if r >= threshold and g >= threshold and b >= threshold:
                pixels[x, y] = (r, g, b, 0)
    return rgba


def trim_transparent(image: Image.Image, padding: int = 24) -> Image.Image:
    rgba = image.convert("RGBA")
    bbox = rgba.getbbox()
    if not bbox:
        return rgba
    cropped = rgba.crop(bbox)
    w, h = cropped.size
    side = max(w, h) + padding * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    offset = ((side - w) // 2, (side - h) // 2)
    canvas.paste(cropped, offset, cropped)
    return canvas


def save_png(image: Image.Image, path: Path, size: tuple[int, int] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = image
    if size:
        out = image.resize(size, Image.Resampling.LANCZOS)
    out.save(path, format="PNG", optimize=True)


def save_ico(image: Image.Image, path: Path) -> None:
    sizes = [(16, 16), (32, 32), (48, 48)]
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="ICO", sizes=sizes)


def main() -> None:
    symbol = Image.open(SRC_SYMBOL)
    wordmark = Image.open(SRC_WORDMARK)
    full = remove_near_white_background(Image.open(SRC_FULL))

    mark = trim_transparent(symbol, padding=28)
    save_png(mark, BRAND / "logo-mark.png", (512, 512))
    save_png(wordmark, BRAND / "logo-wordmark.png")
    save_png(full, BRAND / "logo-full.png", (1024, 1024))

    mark_512 = Image.open(BRAND / "logo-mark.png")
    save_ico(mark_512, PUBLIC / "favicon.ico")
    save_png(mark_512, PUBLIC / "apple-touch-icon.png", (180, 180))
    save_png(mark_512, PUBLIC / "icon-192.png", (192, 192))
    save_png(mark_512, PUBLIC / "icon-512.png", (512, 512))

    print("Installed brand assets:")
    for path in [
        BRAND / "logo-mark.png",
        BRAND / "logo-wordmark.png",
        BRAND / "logo-full.png",
        PUBLIC / "favicon.ico",
        PUBLIC / "apple-touch-icon.png",
        PUBLIC / "icon-192.png",
        PUBLIC / "icon-512.png",
    ]:
        print(" ", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
