"""Build fixtures/style_boards/: the Pinterest-style boards for the style warm-up (closet/styles.py).

For every piece of every style board, Muse Image draws one product photo on a plain background,
then SAM 3.1 cuts it out exactly like a scanned garment (the union of every mask it finds, so a
pair of shoes stays a pair). The app lays the cutouts out as a collage. 12 styles x 6-7 pieces,
about a dollar in all. Already-made pieces are skipped.

    .venv/Scripts/python.exe scripts/make_style_boards.py                 # everything missing
    .venv/Scripts/python.exe scripts/make_style_boards.py gothic/shoes    # (re)make just these
    .venv/Scripts/python.exe scripts/make_style_boards.py --recut gothic/shoes   # cut the same drawing again
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from closet import config, models, products, styles  # noqa: E402

OUT = ROOT / "fixtures" / "style_boards"
SRC = ROOT / "var" / "style_src"  # the raw generations, kept out of git
EDGE = 420  # cutouts are shown at most ~200px wide; webp keeps the repo light

PROMPT = ("Studio product photo of {desc}, a single item, shown whole and centred on a plain light grey background, "
          "shot from the front in soft even light. No person, no mannequin, no hanger, no other objects, no text, "
          "no logos, no brand labels.")


async def make(client, gate, style: styles.Style, piece: styles.Piece) -> str:
    out = OUT / style.id / f"{piece.id}.webp"
    src = SRC / style.id / f"{piece.id}.jpg"
    async with gate:
        if src.exists():
            from PIL import Image
            photo = Image.open(src).convert("RGB")
        else:
            photo, status = await asyncio.to_thread(models.generate_image, PROMPT.format(desc=piece.desc))
            if photo is None:
                return f"{style.id}/{piece.id}: {status}"
            src.parent.mkdir(parents=True, exist_ok=True)
            photo.save(src, quality=90)
        img = None
        for attempt in range(3):  # SAM now and then times out; one bad piece shouldn't sink the batch
            try:
                img = await products.cut(client, photo, piece.noun, piece.category in ("jewelry", "bag"))
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    return f"{style.id}/{piece.id}: SAM failed ({type(e).__name__})"
        if img is None:
            return f"{style.id}/{piece.id}: SAM found no {piece.noun}"
        img.thumbnail((EDGE, EDGE))
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, format="WEBP", quality=82, method=6)
        return f"{style.id}/{piece.id}: ok ({out.stat().st_size // 1024} KB)"


async def main(only: list[str], recut: bool = False) -> None:
    client = config.async_client_for("meta")
    gate = asyncio.Semaphore(4)
    jobs = []
    for st in styles.STYLES:
        for pc in st.pieces:
            key = f"{st.id}/{pc.id}"
            path = OUT / st.id / f"{pc.id}.webp"
            if (only and key not in only) or (not only and path.exists()):
                continue
            if only and not recut:
                (SRC / st.id / f"{pc.id}.jpg").unlink(missing_ok=True)  # a remake draws it again; --recut only cuts again
            jobs.append(make(client, gate, st, pc))
    for line in await asyncio.gather(*jobs):
        print(line)
    manifest = {st.id: [{"id": pc.id, "category": pc.category, "name": pc.desc}
                        for pc in st.pieces if (OUT / st.id / f"{pc.id}.webp").exists()] for st in styles.STYLES}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "boards.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("pieces:", sum(len(v) for v in manifest.values()))


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(main([a for a in args if not a.startswith("--")], "--recut" in args))
