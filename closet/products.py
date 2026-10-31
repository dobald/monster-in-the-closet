"""Product shots: a scanned garment redrawn as a clean, flat product photo.

A scan cutout is the real garment, but crumpled, folded and lit by a bedroom lamp. For
showing the closet, Muse Image redraws the same garment from its cutout as a studio
product photo (laid flat, smoothed, plain background), and SAM 3.1 cuts it out exactly
like a scan, so it sits on a card the same way.

The cutout stays the source of truth: tags, colour reads, duplicates and try-on all use it.
A product shot is only shown when its measured colour stays within MAX_DELTA_E of the
cutout's; a redraw that drifted is thrown away and the scan is shown instead.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

import meta_sam_parser as sp

from . import media, sam
from .dedupe import lab
from .schema import Garment

SAM_EDGE = 1024
MAX_DELTA_E = 20.0  # as for duplicates (closet/dedupe.py): a redraw also drops the room's colour cast, so a
                    # white tee shot under a warm lamp measures ~13 from its own clean product shot
POSE = {
    "top": "laid perfectly flat, sleeves straightened out to the sides",
    "outerwear": "laid perfectly flat and closed, sleeves straightened out to the sides",
    "bottom": "laid perfectly flat with both legs straight and the full length visible",
    "dress": "laid perfectly flat with the full length visible",
    "shoes": "as a pair, side by side, seen from a three-quarter angle",
}


NOUN = {"top": "shirt", "bottom": "pants", "dress": "dress", "outerwear": "jacket", "shoes": "shoes", "accessory": "accessory"}


def nouns(tags: Garment) -> list[str]:
    """What to ask SAM for, most specific first: it finds nothing for some long names ("side-stripe track pants")."""
    last = tags.subtype.split()[-1] if tags.subtype else ""
    return list(dict.fromkeys(n for n in (tags.subtype, last, NOUN.get(tags.category), "clothing") if n))


def prompt(tags: Garment, color_hex: str) -> str:
    side = "back" if tags.visible_side == "back" else "front"
    return ("Image 1 is a phone photo of one real clothing item, cut out from a messy photo: it may be crumpled, "
            "folded or partly tucked under itself. Redraw exactly this item as a clean studio product photo: "
            f"{POSE.get(tags.category, 'laid out neatly')}, smoothed with no wrinkles, whole and centred, with its "
            f"{side} facing the camera, on a plain light grey background, shot from directly above in soft even light. "
            "Keep it faithful: the same colour, wash and fabric, the same cut, length and fit, and every print, "
            "graphic, text, stripe, pocket, button and seam that is on it. Add nothing that is not on the item and "
            "remove nothing that is. No person, no hanger, no mannequin, no props, no shadows on the background. "
            f"Item: {tags.render_line(color_hex)}.")


async def cut(client, photo: Image.Image, noun: str, open_shape: bool = False) -> Image.Image | None:
    """SAM 3.1 cutout of a product photo: the union of every mask it finds, so a pair of shoes stays a pair.

    `open_shape` keeps holes (a necklace, a bag handle); garments get theirs filled like a scan.
    """
    small = photo.copy()
    small.thumbnail((SAM_EDGE, SAM_EDGE))
    run = await sam.segment(client, noun, image_data_url=media.to_data_url(small))
    masks = []
    for t in run.tracks:
        if 0 not in t.masks or (t.confidence.get(0) or 0) < 0.3:
            continue
        rec = t.masks[0]
        b = rec.bounds
        small_mask, _ = media.place_mask(sp.decode_mask_to_raster(rec.mask), rec.mask.width, rec.mask.height,
                                         (b.left, b.top, b.right, b.bottom), small.width, small.height)
        masks.append(media.upscale_mask(small_mask, photo.size))
    if not masks:
        return None
    mask = np.logical_or.reduce(masks)
    if not open_shape:
        return media.cutout(photo, mask)
    rgba = photo.convert("RGBA")
    rgba.putalpha(Image.fromarray((mask * 255).astype(np.uint8)))
    ys, xs = np.nonzero(mask)
    return rgba.crop((max(xs.min() - 8, 0), max(ys.min() - 8, 0), min(xs.max() + 8, photo.width), min(ys.max() + 8, photo.height)))


def colour_drift(cutout: Image.Image, product: Image.Image) -> float:
    """ΔE between the measured colours of the scan and its product shot."""
    return float(np.linalg.norm(np.array(lab(cutout)) - np.array(lab(product))))
