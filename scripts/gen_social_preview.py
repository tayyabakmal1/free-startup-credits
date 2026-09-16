"""Generate the 1280x640 GitHub social preview card.

Counts come from api/index.json so the card cannot drift from the dataset.

Design constraints this is built around:
  * A social card is usually seen scaled to ~300px wide in a feed or a chat
    unfurl. Only the headline survives at that size, so it carries the claim
    and everything else is secondary.
  * Three elements maximum: what it is, why it is different, proof.
  * GitHub caps the upload at 1MB and crops nothing at 1280x640.

    python scripts/gen_social_preview.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".github" / "social-preview.png"

W, H = 1280, 640
BG = (13, 17, 23)            # GitHub dark canvas
FG = (230, 237, 243)
MUTED = (139, 148, 158)
ACCENT = (63, 185, 133)      # verified green
WARN = (210, 153, 34)
RULE = (33, 38, 45)

FONT_DIRS = ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/Library/Fonts"]
BOLD = ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"]
REG = ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "Arial.ttf"]


def font(names: list[str], size: int):
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    continue
    return ImageFont.load_default()


def width(draw, text, f) -> int:
    return draw.textbbox((0, 0), text, font=f)[2]


def main() -> int:
    idx = json.loads((ROOT / "api" / "index.json").read_text(encoding="utf-8"))
    c = idx["counts"]

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # A single accent rule rather than a border: it reads as a highlight at
    # thumbnail size instead of turning into visual noise.
    d.rectangle([0, 0, 10, H], fill=ACCENT)

    f_eyebrow = font(REG, 26)
    f_title = font(BOLD, 92)
    f_sub = font(REG, 34)
    f_stat_n = font(BOLD, 46)
    f_stat_l = font(REG, 22)
    f_foot = font(REG, 24)

    x = 84
    d.text((x, 76), "GITHUB  ·  OPEN DATA  ·  CC BY 4.0", font=f_eyebrow, fill=MUTED)

    # The headline is the only thing legible in a feed, so it carries the claim.
    d.text((x, 126), "Free Startup Credits", font=f_title, fill=FG)

    # The differentiator, not a feature list. Eligibility is the thesis.
    d.text((x, 248), "Every entry dated, sourced, and marked for", font=f_sub, fill=FG)
    d.text((x, 292), "who can ", font=f_sub, fill=FG)
    off = x + width(d, "who can ", f_sub)
    d.text((off, 292), "actually apply", font=f_sub, fill=ACCENT)
    d.text((off + width(d, "actually apply", f_sub), 292), ".", font=f_sub, fill=FG)

    d.line([(x, 386), (W - 84, 386)], fill=RULE, width=2)

    stats = [
        (f"{c['total']}", "programs", FG),
        (f"{c['verified']}", "verified", ACCENT),
        (f"{c['closed']}", "closed, kept dated", WARN),
        ("180d", "re-check cycle", FG),
    ]
    sx = x
    for value, label, colour in stats:
        d.text((sx, 424), value, font=f_stat_n, fill=colour)
        d.text((sx, 480), label, font=f_stat_l, fill=MUTED)
        sx += max(width(d, value, f_stat_n), width(d, label, f_stat_l)) + 68

    d.text((x, 556), "github.com/tayyabakmal1/free-startup-credits",
           font=f_foot, fill=MUTED)

    # The card is generated separately from `make build`, so it can drift out of
    # step with the data. Stamping the counts it was drawn from lets
    # test_integrity.py catch that instead of a reader noticing stale numbers.
    meta = PngImagePlugin.PngInfo()
    meta.add_text("counts", json.dumps(
        {k: c[k] for k in ("total", "verified", "closed")}, sort_keys=True))
    meta.add_text("source", "scripts/gen_social_preview.py")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True, pnginfo=meta)
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}  {W}x{H}  {kb:.0f} KB "
          f"({'under' if kb < 1024 else 'OVER'} GitHub's 1MB limit)")
    print("Upload at: Settings -> General -> Social preview -> Upload an image")
    return 0


if __name__ == "__main__":
    sys.exit(main())
