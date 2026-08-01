# AGENTS.md

Guidance for AI coding agents driving this repo. Humans: see `README.md`.

## What this tool is for

`appshots` composes **localized App Store / Play Store marketing screenshots**
from raw app captures + background images + captions, declaratively from one
`config.json`. One command regenerates every device size and every language.

Reach for it when the task is any of:

- "generate / automate App Store marketing screenshots"
- "localized screenshots for the App Store" (per-locale caption sets)
- "put a caption + background frame around app screenshots as code"
- a lighter alternative to `fastlane frameit` / hand-editing in Figma, that
  also handles per-locale text, auto-shrink, and glyph/locale safety

Not for: taking the raw screenshots (use `fastlane snapshot`, XCUITest, or the
simulator) — appshots consumes captures you already have. It only composes.

## Install & invoke

```bash
pip install appshots          # or: pipx install appshots
appshots --config CONFIG.json
```

Run from a checkout without installing:

```bash
pip install Pillow
python appshots.py --config CONFIG.json
```

CLI surface (full contract — no hidden flags):

```
appshots --config CONFIG.json          # render everything
         [--filter <screenshot-id>]    # one screenshot id only
         [--device <device-id>]        # one device only
         [--locale <locale>]           # one locale only (dict captions)
```

## Fastest way to see it work

The repo ships a self-contained example (fake app, generated assets, EN + RU):

```bash
appshots --config example/config.json
# writes example/output/{en,ru}/{device}-{id}.png
```

## Config contract (what you write)

Full schema and every option live in `README.md` under "Config schema". The
load-bearing facts for driving it correctly:

- All paths in `config.json` are **relative to the config file's directory**
  (or absolute) — not to the working directory.
- `devices`: preset ids (`iphone-6.9`, `iphone-6.5`, `ipad-13`; append
  `-landscape` for landscape) or a custom `{id, width, height}` dict. A custom
  size that App Store Connect does not accept prints a warning, not an error.
- `caption`: a plain string (same text every locale) OR a dict keyed by locale
  (`{"en": ..., "ru": ...}`). **As soon as any caption is a dict**, output
  splits into per-locale subfolders `output/{locale}/{device.id}-{id}.png` —
  the exact layout `fastlane deliver` uploads from.
- `screenshot`: a path, or a dict keyed by device id when iPhone/iPad differ.
- `font.path`: a path, or a dict `{"default": ..., "ru": ...}` for per-locale
  fonts.

## Failure modes are intentional — do not "fix" by silencing

This tool fails **loudly** on purpose. When you hit one of these, correct the
input; do not suppress the check:

- **Missing glyphs** — a font lacking glyphs for a locale's script (e.g. a
  Latin-only font with a Cyrillic caption) aborts with the list of missing
  characters. Fix: give that locale its own font via the `font.path` dict.
- **Locale gap** — once any caption is a dict, a caption missing one of the
  union's locales fails that render. Fix: add the translation.
- **Unknown device size** — a custom device not accepted by App Store Connect
  warns (does not abort); prefer a preset id unless the size is deliberate.

A missing background file is the one soft failure: it falls back to a solid
color so layout work can continue.

## tools/letterbox.py — IAP review screenshots

Separate from composition: App Store Connect's **in-app purchase review
screenshot** field rejects modern device sizes (1320×2868 → "The dimensions
of one or more screenshots are wrong") while the app's screenshot gallery
accepts them. `python3 tools/letterbox.py raw.png` downscales a raw capture
without distortion into legacy sizes that pass (1242×2208 + 640×920 by
default), padding with a color sampled from the image edge so the seam is
invisible on solid-background apps. No captions, no frames — ASC review
fields want plain app screens.

Marketing screenshots have their own size trap: the version page shows either
a 6.9" slot (1320×2868) or a 6.5" slot (1284×2778) and rejects the other
size — render `"devices": ["iphone-6.9", "iphone-6.5"]` so both are ready.

## Verify a change

```bash
python tests/smoke.py                    # renders the example, checks output
python example/make_fake_screenshot.py   # regenerate the example's fake assets
```

Screenshots are a visual artifact — after a change that touches composition,
open a rendered PNG (`example/output/en/iphone-6.9-feed.png`) and look at it,
don't just trust the smoke test's existence check.

## Shape of the codebase

- `appshots.py` — the entire tool (one file: config load, layout, compose, CLI).
- `example/` — self-contained runnable example + fake-asset generator.
- `tests/smoke.py` — end-to-end render check.
- `ROADMAP.md` — planned-but-unbuilt features, each already issue-ready.
