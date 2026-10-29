"""Finding the same garment across different scan photos.

Item ids hash the cutout, so one hoodie photographed in two batches becomes two items.
Within one photo SAM's masks are compared directly (closet/sam.py); across photos the
cutouts differ in fold, crop and lighting, so this module:

1. shortlists pairs cheaply: compatible categories and a close measured colour
   (real duplicates in our test closet were within ΔE 7.4; we allow 20 for lighting);
2. asks Muse Spark 1.3 to compare the two cutouts and commit to a verdict.

The caller decides what to do with verdicts: merge, ask the user, or ignore.
"""

from __future__ import annotations

import itertools
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from . import config
from .media import dominant_color, on_white, to_data_url
from .schema import SameGarment

MAX_DELTA_E = 20.0
# Categories a tagger might mix up for one garment (a sweatshirt as top or outerwear).
CATEGORY_GROUP = {"top": "upper", "outerwear": "upper", "bottom": "bottom", "dress": "dress",
                  "shoes": "shoes", "accessory": "extra", "other": "extra"}

JUDGE_INSTRUCTIONS = (
    "You compare two cutouts from different photos of the same person's closet. Decide whether they show the "
    "SAME physical garment (one item photographed twice) or two different items. The photos differ in folding, "
    "crumpling, cropping, lighting and sometimes which side faces up (a print on the back may be hidden). "
    "Same item: distinctive details match (logo, print, stripes, buttons, wash, ribbing, cut) and nothing "
    "conflicts. Different items: any real conflict, e.g. a different logo, print, stripe count, collar, sleeve "
    "length or colour. Two plain items of the same kind and colour are only the same if their cut and small "
    "details match too; when it is truly impossible to tell, say same_item=false with low confidence."
)


@lru_cache(maxsize=512)
def _lab(path: str) -> tuple[float, float, float]:
    """Measured colour of a cutout in CIELAB, computed on a thumbnail."""
    img = Image.open(path)
    img.thumbnail((256, 256))
    hexc = dominant_color(img)
    rgb = np.array([int(hexc[i:i + 2], 16) for i in (1, 3, 5)]) / 255
    rgb = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = m @ rgb / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return (float(116 * f[1] - 16), float(500 * (f[0] - f[1])), float(200 * (f[1] - f[2])))


def delta_e(a: Path, b: Path) -> float:
    return float(np.linalg.norm(np.array(_lab(str(a))) - np.array(_lab(str(b)))))


def visible_area(path: Path) -> int:
    """Opaque pixels: the flatter, less-cropped shot of a garment shows more of it."""
    alpha = np.asarray(Image.open(path).convert("RGBA"))[..., 3]
    return int((alpha > 200).sum())


def candidate_pairs(items: list[dict], cutout_dir: Path, focus: set[str] | None = None,
                    skip: set[tuple[str, str]] | None = None) -> list[tuple[dict, dict, float]]:
    """Pairs worth a model look, closest colour first. With `focus`, only pairs touching those ids."""
    out = []
    for a, b in itertools.combinations(items, 2):
        if focus is not None and a["id"] not in focus and b["id"] not in focus:
            continue
        if skip and tuple(sorted((a["id"], b["id"]))) in skip:
            continue
        if a.get("source") and (a.get("source"), a.get("scan_id")) == (b.get("source"), b.get("scan_id")):
            continue  # two pieces SAM cut from the same photo are two garments
        ga, gb = (CATEGORY_GROUP.get(x["tags"]["category"]) for x in (a, b))
        if ga != gb:
            continue
        d = delta_e(cutout_dir / f"{a['id']}.png", cutout_dir / f"{b['id']}.png")
        if d <= MAX_DELTA_E:
            out.append((a, b, d))
    return sorted(out, key=lambda p: p[2])


def judge_same(a_img: Image.Image, b_img: Image.Image, a_tags: dict, b_tags: dict) -> SameGarment:
    """One Muse Spark 1.3 look at two cutouts."""
    def line(t: dict) -> str:
        return f"{t['primary_color']} {t['subtype']}; details: {t['distinctive_details']}"

    client = config.client_for("meta")
    resp = client.responses.parse(
        model=config.REASON_MODEL,
        instructions=JUDGE_INSTRUCTIONS,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": f"Image 1 was tagged: {line(a_tags)}"},
            {"type": "input_image", "image_url": to_data_url(_fit(on_white(a_img)))},
            {"type": "input_text", "text": f"Image 2 was tagged: {line(b_tags)}"},
            {"type": "input_image", "image_url": to_data_url(_fit(on_white(b_img)))},
            {"type": "input_text", "text": "Same physical garment?"},
        ]}],
        text_format=SameGarment,
        reasoning={"effort": "low"},
    )
    return resp.output_parsed


def _fit(img: Image.Image, edge: int = 1024) -> Image.Image:
    img = img.copy()
    img.thumbnail((edge, edge))
    return img
