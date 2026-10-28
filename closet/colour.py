"""The colour read: what a look's colours are doing, from measured garment colours.

docs/STYLE_GUIDE.md section 1. Each garment's colour is measured from its cutout (the
median opaque pixel, closet/media.dominant_color), not guessed from its tag. The tag's
colour name only decides whether it counts as a fashion neutral: navy, denim, camel and
olive are neutrals in practice even though they have hue. The result names the scheme
(all neutral, neutral plus accent, tonal, analogous, complementary, contrasting), the
value contrast and the temperature, plus one idea for what would lift the look. The
touches agent reads this instead of judging colour itself.
"""

from __future__ import annotations

import colorsys
from functools import lru_cache
from pathlib import Path

from PIL import Image

from .media import dominant_color

NEUTRAL_WORDS = (
    "black", "white", "grey", "gray", "charcoal", "navy", "denim", "indigo", "cream", "ivory", "beige", "tan", "camel",
    "brown", "chocolate", "olive", "khaki", "taupe", "stone", "oatmeal", "ecru", "off-white", "bone", "silver", "heather",
)
WARM_WORDS = ("brown", "tan", "camel", "beige", "cream", "khaki", "rust", "red", "orange", "yellow", "mustard", "olive",
              "chocolate", "oatmeal", "ecru", "toffee", "burgundy", "pink", "coral")


@lru_cache(maxsize=1024)
def measured(path: str) -> str:
    """Measured #rrggbb of a cutout, on a thumbnail (cached per file)."""
    img = Image.open(path)
    img.thumbnail((256, 256))
    return dominant_color(img)


def _hls(hex_: str) -> tuple[float, float, float]:
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, l, s


def _hue_gap(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def read(items: list[dict], cutout_dir: Path) -> dict:
    """{palette, scheme, contrast, temperature, summary, idea} for one look."""
    palette = []
    for it in items:
        t = it["tags"]
        hex_ = measured(str(cutout_dir / f"{it['id']}.png"))
        h, l, s = _hls(hex_)
        name = t["primary_color"].lower()
        neutral = any(w in name for w in NEUTRAL_WORDS) or s < 0.15 or l < 0.12 or l > 0.92
        warm = any(w in name for w in WARM_WORDS) or (s >= 0.15 and (h < 70 or h > 330))
        palette.append({"item_id": it["id"], "name": t["primary_color"], "hex": hex_, "neutral": neutral, "warm": warm,
                        "light": round(l, 2), "hue": round(h), "sat": round(s, 2), "category": t["category"],
                        "printed": t["pattern"] in ("graphic", "print", "floral", "checked", "striped")})

    accents = [p for p in palette if not p["neutral"]]
    lights = [p["light"] for p in palette]
    spread = max(lights) - min(lights) if lights else 0
    contrast = "high" if spread >= 0.45 else "medium" if spread >= 0.2 else "low"
    warm_n = sum(p["warm"] for p in palette)
    temperature = "warm" if warm_n == len(palette) else "cool" if warm_n == 0 else "mixed"
    all_dark = all(l < 0.3 for l in lights)
    printed = any(p["printed"] for p in palette)

    if not accents:
        scheme = "tonal" if spread < 0.2 else "all neutral"
    elif len(accents) == 1:
        scheme = "neutral + accent"
    else:
        gaps = [_hue_gap(a["hue"], b["hue"]) for i, a in enumerate(accents) for b in accents[i + 1:]]
        scheme = "tonal" if max(gaps) < 20 else "analogous" if max(gaps) < 60 else "complementary" if min(gaps) > 150 else "contrasting"

    # One idea per situation, in the order a stylist would reach for them (docs/STYLE_GUIDE.md 1, 4).
    if all_dark:
        idea = ("light_break", "It's all dark: a light break (white tee hem, white socks or clean sneakers) would lift it.")
    elif scheme == "tonal":
        idea = ("texture_contrast", "Tonal looks need texture: mix a knit or rib with something smooth, or add leather.")
    elif scheme == "all neutral" and not printed:
        idea = ("accent_pop", "All neutrals: one small accent colour (cap, socks, scarf or bag) would give it a focal point.")
    elif printed:
        idea = ("colour_echo", "There's a print: repeat one of its colours once in an accessory.")
    elif scheme == "neutral + accent":
        idea = ("bookend", f"The {accents[0]['name']} is the accent: let it be the only colour, or bookend it with shoes or a cap.")
    elif scheme in ("complementary", "contrasting"):
        idea = ("accent_pop", "Two strong colours: let one lead (about 60%) and keep the other small.")
    else:
        idea = ("bookend", "Neighbouring colours: easy to wear; repeat the top's colour in your shoes to tie it together.")

    summary = f"{scheme} · {contrast} contrast · {temperature}"
    return {"palette": palette, "scheme": scheme, "contrast": contrast, "temperature": temperature,
            "summary": summary, "idea_play": idea[0], "idea": idea[1]}


def prompt_line(r: dict) -> str:
    cols = ", ".join(f"{p['name']} {p['category']} ({p['hex']}, {'neutral' if p['neutral'] else 'colour'})" for p in r["palette"])
    return f"Colour read (measured, trust it): {r['summary']}. Colours: {cols}. Stylist's idea: {r['idea']}"
