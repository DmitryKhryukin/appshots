#!/usr/bin/env python3
"""Smoke test: render the bundled example and check the output structure.

Deliberately not a pixel-perfect golden test — font rasterization differs
across FreeType versions, so exact bytes are only stable on one machine.

    python tests/smoke.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent
EXAMPLE = ROOT / "example"


def load_example_config(tmp, **overrides):
    """Example config with its relative paths re-anchored to example/."""
    cfg = json.loads((EXAMPLE / "config.json").read_text())
    for spec in cfg["screenshots"]:
        spec["screenshot"] = str(EXAMPLE / spec["screenshot"])
        spec["background"] = str(EXAMPLE / spec["background"])
    p = cfg["font"]["path"]
    cfg["font"]["path"] = ({k: str(EXAMPLE / v) for k, v in p.items()}
                           if isinstance(p, dict) else str(EXAMPLE / p))
    cfg["output_dir"] = str(tmp / "output")
    cfg.update(overrides)
    return cfg


def run(tmp, cfg, name):
    cfg_path = tmp / f"{name}.json"
    cfg_path.write_text(json.dumps(cfg))
    return subprocess.run(
        [sys.executable, str(ROOT / "appshots.py"), "--config", str(cfg_path)],
        capture_output=True, text=True,
    )


def main():
    tmp = Path(tempfile.mkdtemp(prefix="appshots-smoke-"))
    try:
        # 1. Localized render: en + ru folders, portrait preset size
        proc = run(tmp, load_example_config(tmp), "base")
        assert proc.returncode == 0, f"base render failed:\n{proc.stdout}{proc.stderr}"
        expected = [f"{loc}/iphone-6.9-{sid}.png"
                    for loc in ("en", "ru") for sid in ("feed", "stats")]
        for rel in expected:
            path = tmp / "output" / rel
            assert path.exists(), f"missing {rel}"
            size = Image.open(path).size
            assert size == (1320, 2868), f"{rel} is {size}, want (1320, 2868)"

        # localized captions must actually differ between locales
        en = (tmp / "output/en/iphone-6.9-feed.png").read_bytes()
        ru = (tmp / "output/ru/iphone-6.9-feed.png").read_bytes()
        assert en != ru, "en and ru renders are identical — captions not localized?"

        # 2. Landscape preset swaps the dimensions
        cfg = load_example_config(tmp, devices=["iphone-6.9-landscape"],
                                  output_dir=str(tmp / "landscape"))
        proc = run(tmp, cfg, "landscape")
        assert proc.returncode == 0, f"landscape render failed:\n{proc.stdout}{proc.stderr}"
        size = Image.open(tmp / "landscape/en/iphone-6.9-landscape-feed.png").size
        assert size == (2868, 1320), f"landscape render is {size}, want (2868, 1320)"

        # 3. Missing glyphs fail loudly (Neucha has no CJK)
        cfg = load_example_config(tmp, output_dir=str(tmp / "glyphs"))
        cfg["screenshots"][0]["caption"] = {"en": "ok", "ja": "漢字"}
        proc = run(tmp, cfg, "glyphs")
        assert proc.returncode == 1, "render with missing glyphs should exit 1"
        assert "has no glyphs" in proc.stdout, f"expected glyph error, got:\n{proc.stdout}"

        # 4. '#index' selects a face inside a .ttc collection
        sys.path.insert(0, str(ROOT))
        import appshots as mod
        assert mod.split_font_ref("f.ttc#2") == ("f.ttc", 2)
        assert mod.split_font_ref("f.ttf") == ("f.ttf", 0)
        assert mod.split_font_ref("dir#1/f.ttf") == ("dir#1/f.ttf", 0)
        songti = "/System/Library/Fonts/Songti.ttc"
        if Path(songti).exists():
            # macOS-only render check: face 0 (Songti SC) lacks these Traditional
            # glyphs, so a successful render proves face 2 was actually loaded
            cfg = load_example_config(tmp, output_dir=str(tmp / "ttc"))
            cfg["font"]["path"] = f"{songti}#2"
            cfg["screenshots"] = [dict(cfg["screenshots"][0], caption="個時畫")]
            proc = run(tmp, cfg, "ttc")
            assert proc.returncode == 0, f"ttc-index render failed:\n{proc.stdout}{proc.stderr}"

        print("smoke OK — localized set, landscape preset, glyph check, ttc face index verified")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
