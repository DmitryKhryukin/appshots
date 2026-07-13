# Roadmap

Planned feature ideas — not commitments. Build on demand: when one of these
causes real pain (in dogfooding or from user feedback), pick it up. Each entry
is written so it can become a GitHub issue verbatim when the time comes.

## Read captions from Xcode `.xcstrings` / `.strings` files

Translations are currently duplicated by hand in `config.json`
(`"caption": { "en": ..., "ru": ... }`). iOS projects already keep their
translations in `.xcstrings` (or legacy `.strings`) files. Reading captions
from there removes the duplication and keeps a screenshot set in sync with the
app's real localization.

- A caption could reference a key: `"caption": { "key": "screenshot_feed_title" }`.
- A config-level source points at the `.xcstrings`/`.strings` file(s).
- Locales come from the strings file; a missing translation for a declared
  locale fails loudly (consistent with the current glyph/locale checks).

This is the feature that turns appshots from a standalone tool into something
that drops into an existing iOS localization pipeline.

## Multi-line captions

Captions are forced to a single line — a `\n` is rejected, because Pillow's
`anchor="mm"` centering doesn't support multiline text. Marketing screenshots
often want a two-line title.

- Replace the single `draw.text(..., anchor="mm")` call with multiline-aware
  drawing (measure each line, stack them, keep the block centered).
- Keep auto-shrink; decide how wrapping and shrinking interact (probably wrap
  first, then shrink if still too tall).
- Preserve stroke + shadow per line.

## More device presets (6.1", 6.3", iPad 11") — good first issue

`DEVICE_PRESETS` covers iPhone 6.9"/6.5" and iPad 13". App Store Connect also
accepts other sizes.

- Add presets for iPhone 6.1", 6.3", and iPad 11" (verify exact pixel sizes
  against Apple's current App Store Connect specs).
- Add each to `DEVICE_PRESETS` and `REQUIRED_APP_STORE_SIZES` where applicable.
- Update the device table in `README.md`.

## Built-in gradient/solid backgrounds — good first issue

Backgrounds are PNG files today. `example/make_fake_screenshot.py` already
generates simple vertical gradients — that logic could become a built-in
background type, so a config can define a gradient (or solid color) without
shipping an image.

- Allow `"background"` to be an object: `{ "gradient": ["#2e5984", "#8c529b"] }`
  or `{ "solid": "#1a1a1a" }`, alongside the existing string path form.
- Render it in `compose_one` before the screenshot layer.
- Document the new form in `README.md`.
