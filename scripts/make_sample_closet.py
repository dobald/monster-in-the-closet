"""Build fixtures/sample_closet/: a small made-up closet for testers and judges who'd rather not scan.

Nobody's real clothes: Muse Image draws two flat-lay photos, then the same scan path as the
app (SAM 3.1 cutouts, Muse Spark tags) turns them into wardrobe items. Costs about 5 cents.

    .venv/Scripts/python.exe scripts/make_sample_closet.py

The flat-lays are kept in var/sample_src/ (not committed); the cutouts and tags are committed.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from closet import config, models, scan  # noqa: E402

OUT = ROOT / "fixtures" / "sample_closet"
SRC = ROOT / "var" / "sample_src"
EDGE = 512  # cutouts are shown small in the app; this keeps the repo light

SCENE = ("Overhead flat-lay product photo, shot straight down, of {n} separate clothing items laid out flat with "
         "clear space between them on a plain pale grey floor, soft even daylight, no people, no hangers, nothing "
         "overlapping, nothing else in frame: {items}.")
PHOTOS = {
    "tops": ["a white cotton oxford button-down shirt", "a heather grey crewneck wool sweater",
             "a navy and white breton striped long-sleeve tee", "a plain black crew-neck t-shirt",
             "a cream chunky cable-knit cardigan"],
    "bottoms": ["dark indigo straight-leg jeans", "beige cotton chinos", "black wide-leg trousers",
                "an olive cotton field jacket", "a pair of white leather low-top sneakers"],
}
# Days since each piece was last worn, in scan order, so a fresh sample closet already has
# forgotten pieces for the oni to rescue and a closet-alive % with something behind it.
IDLE_DAYS = [3, 140, 12, 1, 260, 6, 45, 400, 90, 2, 30, 75]


def png_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    client = config.async_client_for("meta")
    rows = []
    for batch, (name, items) in enumerate(PHOTOS.items()):
        src = SRC / f"{name}.jpg"
        if src.exists():
            from PIL import Image
            photo = Image.open(src).convert("RGB")
        else:
            photo, status = models.generate_image(SCENE.format(n=len(items), items="; ".join(items)))
            if photo is None:
                raise SystemExit(f"Muse Image: {status}")
            photo.save(src, quality=92)
        found = await scan.scan_image(client, photo, batch, src.name)
        print(f"{name}: SAM found {len(found)}, kept {sum(i.kept for i in found)}")
        for it in found:
            if not it.kept:
                continue
            cut = it.cutout.copy()
            cut.thumbnail((EDGE, EDGE))
            png = png_bytes(cut)
            garment = await asyncio.to_thread(models.tag_garment, cut)
            if not garment.is_garment:
                print("  skipped a non-garment")
                continue
            item_id = hashlib.sha256(png).hexdigest()[:16]
            (OUT / f"{item_id}.png").write_bytes(png)
            rows.append({"id": item_id, "idle_days": IDLE_DAYS[len(rows) % len(IDLE_DAYS)], "tags": garment.model_dump()})
            print(f"  {garment.primary_color} {garment.subtype} ({garment.category})")
    (OUT / "closet.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"wrote {len(rows)} items to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
