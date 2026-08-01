#!/usr/bin/env python3
"""Letterbox raw app screenshots into App Store Connect's legacy sizes.

Why this exists: the review-screenshot field on each in-app purchase in ASC
rejects modern device sizes (1320×2868 → "The dimensions of one or more
screenshots are wrong") while the app's own screenshot gallery accepts them.
Legacy sizes pass reliably. This tool downscales a raw capture without
distortion and pads the sides with a background color sampled from the image
itself, so the seam is invisible on solid-background apps.

Usage:
    python3 tools/letterbox.py store.png                 # → 1242x2208 + 640x920
    python3 tools/letterbox.py store.png --sizes 1242x2208
    python3 tools/letterbox.py store.png --bg "#F9F3E8"

Outputs land next to the input: store-1242x2208.png, store-640x920.png.
"""
import argparse
import re
from pathlib import Path

from PIL import Image

DEFAULT_SIZES = ["1242x2208", "640x920"]  # 5.5" legacy + documented minimum


def parse_size(s: str) -> tuple[int, int]:
    w, h = s.lower().split("x")
    return int(w), int(h)


def parse_color(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def letterbox(src: Image.Image, w: int, h: int, bg: tuple) -> Image.Image:
    canvas = Image.new("RGB", (w, h), bg)
    scale = min(w / src.width, h / src.height)
    sw, sh = round(src.width * scale), round(src.height * scale)
    resized = src.resize((sw, sh), Image.LANCZOS)
    canvas.paste(resized, ((w - sw) // 2, (h - sh) // 2))
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("images", nargs="+", type=Path, help="raw screenshot(s)")
    ap.add_argument("--sizes", nargs="+", default=DEFAULT_SIZES,
                    metavar="WxH", help=f"target sizes (default: {' '.join(DEFAULT_SIZES)})")
    ap.add_argument("--bg", type=parse_color, default=None, metavar="#RRGGBB",
                    help="padding color (default: sampled from the image edge)")
    args = ap.parse_args()

    for path in args.images:
        # Пропустить собственный вывод (глоб вроде *.png его захватывает) —
        # иначе повторный прогон плодит store-1242x2208-1242x2208.png.
        if re.search(r"-\d+x\d+$", path.stem):
            print(f"skip (already letterboxed): {path}")
            continue
        src = Image.open(path).convert("RGB")
        # Sample below any status bar / rounded corner — a plain background pixel.
        bg = args.bg or src.getpixel((min(20, src.width - 1), min(src.height // 6, src.height - 1)))
        for size in args.sizes:
            w, h = parse_size(size)
            out = path.with_name(f"{path.stem}-{w}x{h}{path.suffix}")
            letterbox(src, w, h, bg).save(out)
            print(out)


if __name__ == "__main__":
    main()
