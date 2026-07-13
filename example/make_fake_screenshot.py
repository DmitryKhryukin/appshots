#!/usr/bin/env python3
"""Generate the example's fake app screenshots and gradient backgrounds.

Everything in example/input/ and example/backgrounds/ is produced by this
script — run it again if you want to tweak or regenerate the assets:

    python example/make_fake_screenshot.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
FONT = HERE / "fonts" / "Neucha-Regular.ttf"
W, H = 1320, 2868  # iPhone 6.9" portrait

LOREM = (
    "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua ut enim ad minim "
    "veniam quis nostrud exercitation ullamco laboris nisi ut aliquip"
).split()


def lorem(n, start=0):
    words = [LOREM[(start + i) % len(LOREM)] for i in range(n)]
    return " ".join(words).capitalize()


def font(size):
    return ImageFont.truetype(str(FONT), size)


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw_status_bar(draw):
    draw.text((110, 60), "9:41", font=font(56), fill="#2b2b2b")
    rounded(draw, (W - 190, 72, W - 110, 112), 12, "#2b2b2b")
    rounded(draw, (W - 184, 78, W - 132, 106), 8, "#7bc47f")


def screenshot_feed(path):
    img = Image.new("RGB", (W, H), "#f7f5f0")
    draw = ImageDraw.Draw(img)
    draw_status_bar(draw)

    draw.text((110, 220), "Lorem Ipsum", font=font(120), fill="#2b2b2b")
    draw.text((110, 370), lorem(4, 5), font=font(52), fill="#8a8578")

    palette = ["#e8b04b", "#7bc47f", "#6fa8dc", "#d5729a", "#a58fd4"]
    y = 520
    for i in range(5):
        rounded(draw, (90, y, W - 90, y + 360), 40, "#ffffff")
        draw.ellipse((140, y + 50, 260, y + 170), fill=palette[i])
        draw.text((300, y + 60), lorem(2, i * 3), font=font(64), fill="#2b2b2b")
        draw.text((300, y + 160), lorem(5, i * 7), font=font(44), fill="#8a8578")
        draw.text((300, y + 230), lorem(4, i * 11), font=font(44), fill="#b5b0a3")
        rounded(draw, (W - 350, y + 60, W - 140, y + 140), 40, "#f0ede4")
        draw.text((W - 320, y + 72), lorem(1, i), font=font(44), fill="#8a8578")
        y += 420

    draw.ellipse((W - 320, H - 340, W - 140, H - 160), fill="#e8734a")
    draw.text((W - 254, H - 310), "+", font=font(110), fill="#ffffff")
    img.save(path)


def screenshot_stats(path):
    img = Image.new("RGB", (W, H), "#f7f5f0")
    draw = ImageDraw.Draw(img)
    draw_status_bar(draw)

    draw.text((110, 220), "Ipsum stats", font=font(120), fill="#2b2b2b")
    draw.text((110, 370), lorem(3, 9), font=font(52), fill="#8a8578")

    rounded(draw, (90, 520, W - 90, 1500), 40, "#ffffff")
    bars = [0.45, 0.7, 0.35, 0.9, 0.6, 0.8, 0.5]
    bar_w, gap, base_y, max_h = 120, 40, 1380, 700
    x = 160
    for i, v in enumerate(bars):
        color = "#e8734a" if v == max(bars) else "#e8b04b"
        rounded(draw, (x, base_y - int(max_h * v), x + bar_w, base_y), 24, color)
        draw.text((x + 24, base_y + 20), lorem(1, i)[:3], font=font(40), fill="#8a8578")
        x += bar_w + gap

    y = 1620
    for i in range(3):
        rounded(draw, (90, y, W - 90, y + 300), 40, "#ffffff")
        draw.text((140, y + 50), lorem(2, i * 5), font=font(60), fill="#2b2b2b")
        draw.text((140, y + 150), lorem(6, i * 9), font=font(44), fill="#8a8578")
        draw.text((W - 330, y + 90), f"{87 - i * 13}%", font=font(90), fill="#7bc47f")
        y += 360
    img.save(path)


def gradient(path, top, bottom):
    img = Image.new("RGB", (W, H))
    (r1, g1, b1), (r2, g2, b2) = top, bottom
    for y in range(H):
        t = y / (H - 1)
        row = (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))
        img.paste(Image.new("RGB", (W, 1), row), (0, y))
    img.save(path)


def main():
    (HERE / "input").mkdir(exist_ok=True)
    (HERE / "backgrounds").mkdir(exist_ok=True)
    screenshot_feed(HERE / "input" / "feed.png")
    screenshot_stats(HERE / "input" / "stats.png")
    gradient(HERE / "backgrounds" / "feed.png", (46, 89, 132), (140, 82, 155))
    gradient(HERE / "backgrounds" / "stats.png", (196, 101, 63), (120, 56, 104))
    print("example assets regenerated")


if __name__ == "__main__":
    main()
