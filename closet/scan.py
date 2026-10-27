"""The scan flow: flat-lay photo batches → garment cutouts.

The user lays 4-8 items flat and takes one photo per batch. Day-0 testing showed this
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
    photo = media.load_image(path)
    small = photo.copy()
    small.thumbnail((SEGMENT_EDGE, SEGMENT_EDGE))
    run = await sam.segment(client, PROMPT, image_data_url=media.to_data_url(small))

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
        item = ScanItem(path.name, batch, t.object_id, t.boxes[0], t.confidence.get(0), media.cutout(photo, mask))
        if t.key in dropped_as_dupe:
            item.kept, item.reason = False, "duplicate"
        elif item.confidence is not None and item.confidence < MIN_CONFIDENCE:
            item.kept, item.reason = False, "low confidence"
        elif mask.sum() < MIN_AREA_FRACTION * photo.width * photo.height:
            item.kept, item.reason = False, "too small"
        items.append(item)
    return items


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
