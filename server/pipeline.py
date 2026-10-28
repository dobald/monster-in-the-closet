"""Photo batch -> garment cutouts -> tags -> wardrobe, with caching and fixture replay.

Live mode calls SAM 3.1 (Meta) once per new photo and Muse Spark once per new cutout,
and records both in the content-addressed cache. Fixture mode never calls an API:
known photos and cutouts come from the cache, and an unseen photo replays one of the
recorded scans so the front end always has realistic data to render.
"""

from __future__ import annotations

import asyncio
import io
import time
import uuid
from dataclasses import dataclass, field

from PIL import Image

from closet import config, media, models, scan
from closet.schema import Garment

from .cache import Cache, scan_key, sha256, tag_key
from .dedupe import Dedupe
from .settings import Settings
from .store import Store, now

TAG_CONCURRENCY = 8


class FixtureMissing(RuntimeError):
    """Fixture mode was asked for something it has never recorded."""


@dataclass
class PhotoResult:
    source: str
    kept: list[dict] = field(default_factory=list)  # {item_id, confidence}
    dropped: list[dict] = field(default_factory=list)  # {source, reason}
    cached: bool = False
    replayed: bool = False


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class Pipeline:
    def __init__(self, settings: Settings, cache: Cache, store: Store):
        self.settings, self.cache, self.store = settings, cache, store
        self._photo_gate = asyncio.Semaphore(scan.PHOTO_CONCURRENCY)
        self._tag_gate = asyncio.Semaphore(TAG_CONCURRENCY)
        self.dedupe = Dedupe(settings, cache, store)

    # -- scanning

    async def _scan_photo(self, index: int, source: str, data: bytes) -> PhotoResult:
        key = scan_key(data)
        hit = self.cache.get("scans", key)
        if hit and all((self.settings.cutout_dir / f"{i['item_id']}.png").exists() for i in hit["kept"]):
            return PhotoResult(source, hit["kept"], [{"source": source, "reason": r} for r in hit["dropped"]], cached=True)

        if not self.settings.live:
            recorded = self.cache.keys("scans")
            if not recorded:
                raise FixtureMissing(
                    "Fixture mode has no recorded scans yet. Run one scan with MONSTER_MODE=live, "
                    "or POST /api/dev/seed with a spike run folder."
                )
            replay = self.cache.get("scans", recorded[int(key, 16) % len(recorded)])
            return PhotoResult(source, replay["kept"], [{"source": source, "reason": r} for r in replay["dropped"]],
                               cached=True, replayed=True)

        photo = media.load_image(io.BytesIO(data))
        async with self._photo_gate:
            items = await scan.scan_image(config.async_client_for("meta"), photo, index, source)
        kept, dropped = [], []
        for it in items:
            if not it.kept:
                dropped.append(it.reason)
                continue
            png = _png(it.cutout)
            item_id = sha256(png)[:16]
            (self.settings.cutout_dir / f"{item_id}.png").write_bytes(png)
            kept.append({"item_id": item_id, "confidence": it.confidence})
        self.cache.put("scans", key, {"source": source, "kept": kept, "dropped": dropped, "version": "scan"})
        return PhotoResult(source, kept, [{"source": source, "reason": r} for r in dropped])

    # -- tagging

    async def _tag(self, item_id: str) -> tuple[Garment | None, str | None]:
        png = (self.settings.cutout_dir / f"{item_id}.png").read_bytes()
        key = tag_key(png)
        hit = self.cache.get("tags", key)
        if hit:
            return Garment.model_validate(hit), None
        if not self.settings.live:
            return None, "no recorded tags for this cutout (fixture mode)"
        async with self._tag_gate:
            try:
                garment = await asyncio.to_thread(models.tag_garment, Image.open(io.BytesIO(png)))
            except Exception as e:  # one bad cutout shouldn't fail the whole scan
                return None, f"{type(e).__name__}: {e}"[:300]
        self.cache.put("tags", key, garment.model_dump())
        return garment, None

    # -- the whole scan

    async def run_scan(self, photos: list[tuple[str, bytes]]) -> dict:
        t0 = time.time()
        scan_id = uuid.uuid4().hex[:12]
        results = await asyncio.gather(*(self._scan_photo(i, name, data) for i, (name, data) in enumerate(photos)))

        kept = [(r.source, k) for r in results for k in r.kept]
        unique = list({k["item_id"]: (src, k) for src, k in kept}.values())  # same cutout twice -> once
        tags = await asyncio.gather(*(self._tag(k["item_id"]) for _, k in unique))
        item_ids, new_ids = [], []
        for (src, k), (garment, err) in zip(unique, tags):
            existed = self.store.get_item(k["item_id"]) is not None
            item_id = self.store.upsert_item(k["item_id"], scan_id, src, k.get("confidence"), garment, err)
            item_ids.append(item_id)
            if not existed:
                new_ids.append(item_id)

        # The same garment shot in two photos (this batch or an earlier one) becomes one item.
        dupes = await self.dedupe.check(new_ids) if new_ids else {"merged": [], "review": [], "checked": 0}
        merged_into = {m["dropped_id"]: m["kept_id"] for m in dupes["merged"]}
        item_ids = list(dict.fromkeys(merged_into.get(i, i) for i in item_ids))

        record = {
            "id": scan_id,
            "created_at": now(),
            "mode": self.settings.mode,
            "seconds": round(time.time() - t0, 1),
            "photos": len(photos),
            "cached_photos": sum(r.cached for r in results),
            "replayed": any(r.replayed for r in results),
            "item_ids": item_ids,
            "dropped": [d for r in results for d in r.dropped],
        }
        self.store.add_scan(record)
        return {**record, "duplicates": dupes}

    # -- dev: import a spike run as fixtures

    def seed_from_run(self, run_dir, scan_id: str | None = None) -> dict:
        """Import a spike `out/<run>` (cutouts + wardrobe.json) as wardrobe items and tag fixtures."""
        import json

        rows = {}
        wardrobe = run_dir / "wardrobe.json"
        if wardrobe.exists():
            rows = {r["file"]: r for r in json.loads(wardrobe.read_text())}
        scan_id = scan_id or f"seed-{uuid.uuid4().hex[:8]}"
        imported, untagged = [], 0
        for p in sorted((run_dir / "cutouts").glob("*.png")):
            png = p.read_bytes()
            item_id = sha256(png)[:16]
            (self.settings.cutout_dir / f"{item_id}.png").write_bytes(png)
            garment = None
            row = rows.get(p.name)
            if row:
                try:
                    garment = Garment.model_validate({k: v for k, v in row.items() if k in Garment.model_fields})
                    self.cache.put("tags", tag_key(png), garment.model_dump())
                except ValueError:
                    garment = None
            untagged += garment is None
            self.store.upsert_item(item_id, scan_id, p.name, None, garment,
                                   None if garment else "not tagged in the seeded run")
            imported.append(item_id)
        # Record the run as one replayable scan so fixture mode can answer new uploads.
        self.cache.put("scans", sha256(f"seed:{run_dir.name}".encode()),
                       {"source": run_dir.name, "kept": [{"item_id": i, "confidence": None} for i in imported],
                        "dropped": [], "version": "seed"})
        return {"scan_id": scan_id, "imported": len(imported), "untagged": untagged}
