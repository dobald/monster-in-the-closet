"""Cent-level smoke test for the Meta Model API.

Checks: the key works (list models), Muse Spark 1.3 structured tags from an image,
and SAM 3.1 segmentation through the streaming parser. Uses a synthetic image only.

Run: python spike/smoke_meta.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from smoke_baseten import fake_shirt  # noqa: E402

from closet import config, media, models, sam  # noqa: E402


def main() -> None:
    client = config.client_for("meta")

    print("1) Key check: list models")
    ids = sorted(m.id for m in client.models.list().data)
    print("   " + ", ".join(ids) + "\n")

    print("2) Muse Spark 1.3 structured tags from an image")
    t = time.time()
    g = models.tag_garment(fake_shirt(), provider="meta")
    print("   " + json.dumps(g.model_dump(), ensure_ascii=False))
    print(f"   {time.time() - t:.1f}s\n")

    print("3) SAM 3.1 on the same image, prompt 'shirt'")
    t = time.time()
    url = media.to_data_url(fake_shirt())
    run = asyncio.run(sam.segment(config.async_client_for("meta"), "shirt", image_data_url=url))
    for tr in run.tracks:
        f = tr.frames[0]
        m = tr.masks.get(f)
        print(f"   object {tr.object_id}: box {tr.boxes[f]} conf {tr.confidence.get(f)} "
              f"mask {m.mask.width}x{m.mask.height} {m.mask.encoding}" if m else f"   object {tr.object_id}: box only")
    print(f"   outcome {run.outcome}, frame size {run.frame_size}, diagnostics {run.diagnostics[:3]}")
    print(f"   {time.time() - t:.1f}s  (~${sam.PRICE_PER_IMAGE:.4f})")


if __name__ == "__main__":
    main()
