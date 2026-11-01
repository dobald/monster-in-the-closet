"""The scan flow: flat-lay photo batches → garment cutouts.

The user lays up to 8 items flat (one is fine) and takes one photo per batch. Day-0 testing showed this
beats filming the rail by a wide margin (4/4 clean garments in ~15s for <1¢, versus
slivers and 27-39 minute waits for video), so photos are the primary capture path.

One SAM 3.1 request per photo with the single prompt "clothing" finds everything;
extra noun prompts only produced duplicates.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import meta_sam_parser as sp
from openai import AsyncOpenAI
from PIL import Image

from . import config, media, sam

PROMPT = "clothing"
MIN_CONFIDENCE = 0.6  # below this SAM is usually matching background clutter
MIN_AREA_FRACTION = 0.01  # cutouts smaller than 1% of the photo are specks, not garments
PHOTO_CONCURRENCY = 4
# SAM takes ~21-25s per photo at 2048px but ~7s at 1024px, with the same garments found on
# a neat flat-lay. Segment a small copy, then cut from the full-resolution photo.
SEGMENT_EDGE = 1024
SEGMENT_PREP = "clahe1"  # what SAM is sent: media.for_segmentation (in the scan cache key)
LOW_CONTRAST_DE = 14  # a piece this close in colour to its background is hard to cut out cleanly


def shape_notes(cutout: Image.Image, rel_size: float | None = None) -> str:
    """Measurements of a cutout's outline, as a note for the tagger.

    Colour and print mislead a vision model (a printed square of a folded tee reads as a bandana);
    construction doesn't. Sleeves, armholes and trouser legs cut notches into an outline, so the
    share of its convex hull it fills ("solidity") separates a tee (about 0.7-0.9) from a flat
    square or triangle of fabric (0.95+). Size next to the other pieces in the same photo separates
    a bandana from a shirt.
    """
    import cv2
    import numpy as np

    alpha = np.asarray(cutout.convert("RGBA"))[..., 3] > 127
    if alpha.sum() < 50:
        return ""
    ys, xs = np.nonzero(alpha)
    h, w = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
    contours, _ = cv2.findContours(alpha.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hull = cv2.contourArea(cv2.convexHull(np.vstack(contours)))
    solidity = float(alpha.sum()) / hull if hull else 1.0
    notes = [f"its outline is {h / w:.1f}x as tall as it is wide",
             f"it fills {min(solidity, 1):.0%} of its convex outline (sleeves, armholes and legs make notches: tops "
             f"and trousers usually fill 60-90%, a flat square or triangle of fabric like a bandana or scarf 95% or more)"]
    if rel_size is not None:
        notes.append(f"it is {rel_size:.0%} the size of the largest item in the same photo")
    return "Measured from the cutout: " + "; ".join(notes) + "."


@dataclass
class ScanItem:
    """One garment found in one photo."""

    source: str  # photo file name
    batch: int  # index of the photo in the batch
    object_id: str
    box: tuple[int, int, int, int]
    confidence: float | None
    cutout: Image.Image
    kept: bool = True
    reason: str = ""  # why it was dropped, if not kept

    @property
    def name(self) -> str:
        return f"p{self.batch}_{self.object_id}.png"


async def scan_photo(client: AsyncOpenAI, path: Path, batch: int) -> list[ScanItem]:
    return await scan_image(client, media.load_image(path), batch, path.name)


async def scan_image(client: AsyncOpenAI, photo: Image.Image, batch: int, source: str) -> list[ScanItem]:
    """Segment one upright, size-capped photo (see media.load_image) into garment cutouts."""
    small = photo.copy()
    small.thumbnail((SEGMENT_EDGE, SEGMENT_EDGE))
    run = await sam.segment(client, PROMPT, image_data_url=media.to_data_url(media.for_segmentation(small)))

    # SAM sometimes returns the same object under two ids; keep the more confident one.
    dupes = sam.cross_prompt_duplicates(run.tracks)
    dropped_as_dupe = set()
    for a, b, _ in dupes:
        ta = next(t for t in run.tracks if t.key == a)
        tb = next(t for t in run.tracks if t.key == b)
        weaker = ta if ta.confidence.get(0, 0) < tb.confidence.get(0, 0) else tb
        dropped_as_dupe.add(weaker.key)

    items = []
    for t in run.tracks:
        if 0 not in t.masks:
            continue
        rec = t.masks[0]
        b = rec.bounds
        small_mask, _ = media.place_mask(
            sp.decode_mask_to_raster(rec.mask), rec.mask.width, rec.mask.height,
            (b.left, b.top, b.right, b.bottom), small.width, small.height,
        )
        mask = media.upscale_mask(small_mask, photo.size)
        item = ScanItem(source, batch, t.object_id, t.boxes[0], t.confidence.get(0), media.cutout(photo, mask))
        if t.key in dropped_as_dupe:
            item.kept, item.reason = False, "duplicate"
        elif item.confidence is not None and item.confidence < MIN_CONFIDENCE:
            item.kept, item.reason = False, "low confidence"
        elif mask.sum() < MIN_AREA_FRACTION * photo.width * photo.height:
            item.kept, item.reason = False, "too small"
        items.append(item)
    return items


def contrast_warning(photo: Image.Image, items: list[ScanItem]) -> str | None:
    """A note for the user when the clothes and the background are too alike to cut out well.

    Compares each kept piece's measured colour with the background's, read from a ring around the
    photo's edges (in a flat-lay that's floor or bed). Nothing found in a flat, one-tone photo gets
    the same note."""
    import numpy as np

    from .dedupe import lab

    kept = [i for i in items if i.kept]
    if not kept:
        gray = np.asarray(photo.convert("L"), dtype=np.float32)
        if gray.std() < 28:
            return "I couldn't find clothes in a photo that's all one tone. Try laying them on a contrasting floor or cover."
        return None
    rgb = np.asarray(photo.convert("RGB"))
    h, w = rgb.shape[:2]
    m = max(4, int(0.05 * min(h, w)))
    ring = np.concatenate([rgb[:m].reshape(-1, 3), rgb[-m:].reshape(-1, 3), rgb[:, :m].reshape(-1, 3), rgb[:, -m:].reshape(-1, 3)])
    background = Image.fromarray(ring[:: max(1, len(ring) // 4096)].reshape(-1, 1, 3)).convert("RGBA")
    bg = np.array(lab(background))
    close = [i for i in kept if np.linalg.norm(np.array(lab(i.cutout)) - bg) < LOW_CONTRAST_DE]
    if close:
        return (f"{len(close)} piece{'s' if len(close) > 1 else ''} in {kept[0].source} {'are' if len(close) > 1 else 'is'} "
                "close in colour to the background, so the edges may be rough. Light clothes scan best on a darker floor, "
                "dark clothes on a lighter one.")
    return None


async def scan_photos(paths: list[Path]) -> list[ScanItem]:
    """Segment a batch of flat-lay photos concurrently; returns every item, kept or not."""
    client = config.async_client_for("meta")
    gate = asyncio.Semaphore(PHOTO_CONCURRENCY)

    async def one(i: int, p: Path) -> list[ScanItem]:
        async with gate:
            return await scan_photo(client, p, i)

    results = await asyncio.gather(*(one(i, p) for i, p in enumerate(paths)))
    return [item for batch in results for item in batch]


def estimate_cost(n_photos: int) -> float:
    return n_photos * sam.PRICE_PER_IMAGE
