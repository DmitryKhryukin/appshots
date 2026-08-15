#!/usr/bin/env python3
"""
appshots — Compose App Store marketing screenshots from raw gameplay
captures, background images, and captions.

Usage:
    python appshots.py --config CONFIG.json
    python appshots.py --config CONFIG.json --filter archer
    python appshots.py --config CONFIG.json --device iphone-6.9
    python appshots.py --config CONFIG.json --locale ru
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont


RESAMPLE = {
    "nearest": Image.NEAREST,
    "lanczos": Image.LANCZOS,
    "bilinear": Image.BILINEAR,
    "bicubic": Image.BICUBIC,
}

# Portrait presets for the sizes App Store Connect currently requires;
# append "-landscape" to any id for the rotated variant.
DEVICE_PRESETS = {
    "iphone-6.9": (1320, 2868),
    "iphone-6.5": (1284, 2778),
    "ipad-13": (2064, 2752),
}

# The REQUIRED App Store Connect sizes (both orientations), including the
# alternate resolutions of each size class. ASC also accepts optional sizes
# (6.3", 6.1", …) not listed here, so mismatches warn instead of rejecting.
REQUIRED_APP_STORE_SIZES = {(w, h) for w, h in [
    (1320, 2868), (1290, 2796),   # iPhone 6.9"
    (1284, 2778), (1242, 2688),   # iPhone 6.5"
    (2064, 2752), (2048, 2732),   # iPad 13"
]}
REQUIRED_APP_STORE_SIZES |= {(h, w) for w, h in REQUIRED_APP_STORE_SIZES}


def normalize_device(entry):
    """A device is either a preset id string or a {id, width, height} dict."""
    if isinstance(entry, str):
        base = entry.removesuffix("-landscape")
        if base not in DEVICE_PRESETS:
            known = ", ".join(sorted(DEVICE_PRESETS))
            raise KeyError(f"Unknown device preset {entry!r} (known: {known}, "
                           f"each also accepts a '-landscape' suffix)")
        w, h = DEVICE_PRESETS[base]
        if entry.endswith("-landscape"):
            w, h = h, w
        return {"id": entry, "width": w, "height": h}
    absent = [k for k in ("id", "width", "height") if k not in entry]
    if absent:
        raise KeyError(f"Device entry {entry!r} is missing {', '.join(absent)}")
    if (entry["width"], entry["height"]) not in REQUIRED_APP_STORE_SIZES:
        print(f"  warning: {entry['id']} is {entry['width']}x{entry['height']} — "
              f"not one of the required App Store sizes", file=sys.stderr)
    return entry


def parse_hex_color(s):
    """Parse #RRGGBB or #RRGGBBAA into an (r, g, b, a) tuple."""
    s = s.lstrip("#")
    if len(s) == 6:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
    if len(s) == 8:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))
    raise ValueError(f"Invalid hex color: {s!r}")


def resolve(base, path):
    if path is None:
        return None
    p = Path(path)
    return p if p.is_absolute() else (base / p).resolve()


def cover(image, w, h, resample):
    """Resize image to cover (w, h), preserving aspect ratio, then center-crop."""
    sw, sh = image.size
    scale = max(w / sw, h / sh)
    new_w, new_h = int(round(sw * scale)), int(round(sh * scale))
    resized = image.resize((new_w, new_h), resample)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return resized.crop((left, top, left + w, top + h))


def apply_screenshot_overlays(image, overlays):
    """Paint colored rectangles over the screenshot (e.g. to hide the Dynamic Island)."""
    if not overlays:
        return image
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for ov in overlays:
        x1, y1, x2, y2 = ov["rect"]
        color = parse_hex_color(ov.get("color", "#000000"))
        radius = ov.get("radius", 0)
        if radius > 0:
            draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=color)
        else:
            draw.rectangle((x1, y1, x2, y2), fill=color)
    return Image.alpha_composite(image, layer)


def apply_screen_frame(image, frame):
    """Round corners and add a bezel with optional inner highlight."""
    radius = frame.get("corner_radius", 60)
    border_width = frame.get("border_width", 0)
    border_color = parse_hex_color(frame.get("border_color", "#000000"))

    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    rounded = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rounded.paste(image, (0, 0), mask)

    if border_width <= 0:
        return rounded

    bw = border_width
    out_w, out_h = w + bw * 2, h + bw * 2
    bezel_mask = Image.new("L", (out_w, out_h), 0)
    ImageDraw.Draw(bezel_mask).rounded_rectangle(
        (0, 0, out_w, out_h), radius=radius + bw, fill=255
    )
    bezel = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    bezel.paste(Image.new("RGBA", (out_w, out_h), border_color), (0, 0), bezel_mask)
    bezel.alpha_composite(rounded, (bw, bw))

    # Inner highlight — thin lighter ring at the bezel/screen boundary
    hl_color = frame.get("inner_highlight_color")
    if hl_color:
        hl_width = frame.get("inner_highlight_width", 2)
        hl_layer = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        ImageDraw.Draw(hl_layer).rounded_rectangle(
            (bw - 1, bw - 1, bw + w + 1, bw + h + 1),
            radius=radius + 1,
            outline=parse_hex_color(hl_color),
            width=hl_width,
        )
        bezel.alpha_composite(hl_layer)

    return bezel


def apply_vignette(canvas, vignette):
    """Darken the canvas toward the edges with a soft radial gradient."""
    color = parse_hex_color(vignette.get("color", "#000000"))
    intensity = vignette.get("intensity", 0.6)
    falloff = vignette.get("falloff", 1.3)

    w, h = canvas.size
    max_alpha = int(255 * intensity)

    mask = Image.new("L", (w, h), max_alpha)
    draw = ImageDraw.Draw(mask)

    steps = 60
    for i in range(steps, 0, -1):
        f = i / steps
        rx = int(w * f / 2 * falloff)
        ry = int(h * f / 2 * falloff)
        alpha = int(max_alpha * f * f)  # quadratic falloff = smoother gradient
        draw.ellipse([w // 2 - rx, h // 2 - ry, w // 2 + rx, h // 2 + ry], fill=alpha)

    overlay = Image.new("RGBA", (w, h), color)
    overlay.putalpha(mask)
    canvas.alpha_composite(overlay)
    return canvas


def apply_image_shadow(image, shadow):
    """Composite a soft drop shadow behind the given RGBA image."""
    color = parse_hex_color(shadow["color"])
    offset = shadow.get("offset", [0, 0])
    blur = shadow.get("blur", 0)

    w, h = image.size
    pad = max(int(blur * 3), abs(offset[0]), abs(offset[1]), 8)
    canvas = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))

    alpha = image.split()[-1]
    tint = Image.new("RGBA", (w, h), color)
    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_layer.paste(tint, (pad + offset[0], pad + offset[1]), alpha)
    if blur > 0:
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))

    canvas = Image.alpha_composite(canvas, shadow_layer)
    canvas.paste(image, (pad, pad), image)
    return canvas


def draw_caption(canvas, text, font, cx, cy, fill, shadow, stroke):
    """Draw centered text with optional drop shadow and stroke outline."""
    if shadow:
        sx = cx + shadow["offset"][0]
        sy = cy + shadow["offset"][1]
        sc = parse_hex_color(shadow["color"])
        blur = shadow.get("blur", 0)
        if blur > 0:
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((sx, sy), text, font=font, fill=sc, anchor="mm")
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
            canvas.alpha_composite(layer)
        else:
            ImageDraw.Draw(canvas).text((sx, sy), text, font=font, fill=sc, anchor="mm")

    stroke_width = stroke.get("width", 0) if stroke else 0
    stroke_fill = parse_hex_color(stroke["color"]) if stroke else None
    ImageDraw.Draw(canvas).text(
        (cx, cy), text, font=font, fill=fill, anchor="mm",
        stroke_width=stroke_width, stroke_fill=stroke_fill,
    )


def screenshot_path_for_device(spec, device_id):
    """The 'screenshot' field can be a path (shared) or a dict keyed by device id."""
    s = spec["screenshot"]
    if isinstance(s, dict):
        if device_id not in s:
            raise KeyError(f"No screenshot for device {device_id!r} in spec {spec['id']!r}")
        return s[device_id]
    return s


def caption_for_locale(spec, locale):
    """The 'caption' field can be a string (all locales) or a dict keyed by locale."""
    c = spec.get("caption", "")
    if isinstance(c, dict):
        if locale not in c:
            raise KeyError(f"No caption for locale {locale!r} in spec {spec['id']!r}")
        return c[locale]
    return c


def collect_locales(config):
    """Union of locale keys across dict captions, in first-seen order.

    Returns [None] when every caption is a plain string — single-locale mode,
    output goes directly to output_dir with no per-locale subfolder.
    """
    locales = []
    for spec in config["screenshots"]:
        c = spec.get("caption", "")
        if isinstance(c, dict):
            for k in c:
                if k not in locales:
                    locales.append(k)
    return locales or [None]


def font_path_for_locale(font_cfg, locale):
    """The font 'path' can be a path (all locales) or a dict keyed by locale,
    with an optional 'default' fallback for the locales not listed."""
    p = font_cfg["path"]
    if isinstance(p, dict):
        key = locale if locale in p else "default"
        if key not in p:
            raise KeyError(f"No font for locale {locale!r} (add it or a 'default' entry)")
        return p[key]
    return p


def split_font_ref(ref):
    """A font reference may name a face inside a .ttc collection: 'Songti.ttc#2'.

    Collections put a different face at index 0 than the name suggests (e.g.
    macOS Songti.ttc opens as Songti SC while the Traditional faces sit deeper),
    so without an index the glyph-coverage check rejects a font that actually
    has the glyphs — just not in face 0.
    """
    s = str(ref)
    stem, sep, idx = s.rpartition("#")
    if sep and idx.isdigit():
        return stem, int(idx)
    return s, 0


def check_glyph_coverage(font, text, path):
    """Fail loudly when the font lacks glyphs for the caption.

    Pillow renders missing glyphs as blanks (often with a normal advance), so a
    Latin-only font with a Cyrillic caption silently produces an empty title.
    A glyph counts as missing when rendering it leaves no ink at all.
    """
    missing = sorted({
        ch for ch in text
        if not ch.isspace() and font.getmask(ch).getbbox() is None
    })
    if missing:
        raise ValueError(
            f"Font {Path(path).name!r} has no glyphs for {''.join(missing)!r} — "
            f"use a per-locale font ('path' as a locale dict)"
        )


def fit_caption_font(font_cfg, base, text, max_width, locale=None):
    """Load the caption font, shrinking the size until the text fits max_width.

    Localized strings vary a lot in length (German/Russian run ~30% longer than
    English); shrinking beats silently overflowing the canvas.
    """
    if "\n" in text:
        raise ValueError(f"Captions must be single-line (Pillow can't center "
                         f"multiline text): {text!r}")
    ref, face_index = split_font_ref(font_path_for_locale(font_cfg, locale))
    path = str(resolve(base, ref))
    size = font_cfg["size"]
    stroke_pad = (font_cfg.get("stroke") or {}).get("width", 0) * 2
    font = ImageFont.truetype(path, size, index=face_index)
    check_glyph_coverage(font, text, path)
    while size > 12 and font.getlength(text) + stroke_pad > max_width:
        size = max(12, int(size * 0.95))
        font = ImageFont.truetype(path, size, index=face_index)
    return font


def compose_one(config, device, spec, base, locale=None):
    w, h = device["width"], device["height"]
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 255))

    layout = config.get("layout", {})
    bg_resample = RESAMPLE[layout.get("background_resample", "nearest")]
    shot_resample = RESAMPLE[layout.get("screenshot_resample", "nearest")]

    # Background — cover the full canvas (falls back to solid color if missing)
    bg_path = resolve(base, spec.get("background"))
    if bg_path and bg_path.exists():
        bg = Image.open(bg_path).convert("RGBA")
        canvas.paste(cover(bg, w, h, bg_resample), (0, 0))
    else:
        fallback = parse_hex_color(config.get("missing_background_color", "#1a1a1a"))
        canvas.paste(Image.new("RGBA", (w, h), fallback), (0, 0))

    # Vignette — darken edges of background to focus eye on the phone
    vignette_cfg = layout.get("vignette")
    if vignette_cfg:
        apply_vignette(canvas, vignette_cfg)

    # Screenshot — overlays, crop sim chrome, scale, optional frame + drop-shadow
    shot_path = resolve(base, screenshot_path_for_device(spec, device["id"]))
    shot = Image.open(shot_path).convert("RGBA")

    overlays = layout.get("screenshot_overlays")
    if overlays:
        shot = apply_screenshot_overlays(shot, overlays)

    crop = layout.get("screenshot_crop")
    if crop:
        sw, sh = shot.size
        shot = shot.crop((
            crop.get("left", 0),
            crop.get("top", 0),
            sw - crop.get("right", 0),
            sh - crop.get("bottom", 0),
        ))

    scale = layout.get("screenshot_scale", 0.78)
    target_w = int(round(w * scale))
    aspect = shot.size[1] / shot.size[0]
    target_h = int(round(target_w * aspect))
    max_h = int(h * layout.get("screenshot_max_height", 0.78))
    if target_h > max_h:
        target_h = max_h
        target_w = int(round(target_h / aspect))

    shot = shot.resize((target_w, target_h), shot_resample)

    frame_cfg = layout.get("screenshot_frame")
    if frame_cfg:
        shot = apply_screen_frame(shot, frame_cfg)

    shadow_cfg = layout.get("screenshot_shadow")
    if shadow_cfg:
        shot = apply_image_shadow(shot, shadow_cfg)

    sw, sh = shot.size
    y_offset = int(h * layout.get("screenshot_offset_y", 0.04))
    x = (w - sw) // 2
    y = (h - sh) // 2 + y_offset
    canvas.alpha_composite(shot, (x, y))

    # Caption
    caption = caption_for_locale(spec, locale)
    if caption:
        font_cfg = config["font"]
        max_width = int(w * layout.get("caption_max_width", 0.92))
        font = fit_caption_font(font_cfg, base, caption, max_width, locale)
        cy = int(h * layout.get("caption_position_y", 0.10))
        cx = w // 2
        draw_caption(
            canvas, caption, font, cx, cy,
            fill=parse_hex_color(font_cfg["color"]),
            shadow=font_cfg.get("shadow"),
            stroke=font_cfg.get("stroke"),
        )

    return canvas.convert("RGB")


def main():
    parser = argparse.ArgumentParser(description="Compose App Store marketing screenshots.")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--filter", help="Render only this screenshot id")
    parser.add_argument("--device", help="Render only this device id")
    parser.add_argument("--locale", help="Render only this locale (for dict captions)")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)
    base = config_path.parent
    try:
        config["devices"] = [normalize_device(d) for d in config["devices"]]
    except KeyError as e:
        print(e.args[0], file=sys.stderr)
        sys.exit(1)

    output_dir = resolve(base, config.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    locales = collect_locales(config)
    if args.locale:
        if args.locale not in locales:
            print(f"Locale {args.locale!r} not found in any caption "
                  f"(available: {', '.join(l for l in locales if l) or 'none'})",
                  file=sys.stderr)
            sys.exit(1)
        locales = [args.locale]
    if args.device and args.device not in {d["id"] for d in config["devices"]}:
        print(f"Device {args.device!r} not in config "
              f"(available: {', '.join(d['id'] for d in config['devices'])})",
              file=sys.stderr)
        sys.exit(1)
    if args.filter and args.filter not in {s["id"] for s in config["screenshots"]}:
        print(f"Screenshot {args.filter!r} not in config "
              f"(available: {', '.join(s['id'] for s in config['screenshots'])})",
              file=sys.stderr)
        sys.exit(1)

    rendered = 0
    failed = 0
    for locale in locales:
        # Per-locale subfolders match the layout fastlane deliver uploads from.
        locale_dir = output_dir / locale if locale else output_dir
        locale_dir.mkdir(parents=True, exist_ok=True)
        for device in config["devices"]:
            if args.device and device["id"] != args.device:
                continue
            for spec in config["screenshots"]:
                if args.filter and spec["id"] != args.filter:
                    continue
                label = f"{locale} / " if locale else ""
                print(f"  {label}{device['id']} / {spec['id']} …", end="", flush=True)
                try:
                    out = compose_one(config, device, spec, base, locale)
                    out_path = locale_dir / f"{device['id']}-{spec['id']}.png"
                    out.save(out_path, "PNG")
                    print(f" → {out_path.relative_to(output_dir)}")
                    rendered += 1
                except Exception as e:
                    print(f" FAILED: {e}")
                    failed += 1

    print(f"\n{rendered} rendered, {failed} failed → {output_dir}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
