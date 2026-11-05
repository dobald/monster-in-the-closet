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
from closet import dedupe as dedupe_mod
from closet.schema import Garment

from .cache import Cache, scan_key, sha256, tag_key
from .dedupe import Dedupe
from .settings import Settings
from .store import Store, now

TAG_CONCURRENCY = 8
SAMPLE_DIR = config.ROOT / "fixtures" / "sample_closet"


class FixtureMissing(RuntimeError):
    """Fixture mode was asked for something it has never recorded."""


@dataclass
class PhotoResult:
    source: str
    kept: list[dict] = field(default_factory=list)  # {item_id, confidence}
    dropped: list[dict] = field(default_factory=list)  # {source, reason}
    cached: bool = False
    replayed: bool = False
    warning: str | None = None  # e.g. white clothes on a white sheet


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
            return PhotoResult(source, hit["kept"], [{"source": source, "reason": r} for r in hit["dropped"]], cached=True,
                               warning=hit.get("warning"))

        if not self.settings.live:
            recorded = self.cache.keys("scans")
            if not recorded:
                raise FixtureMissing(
                    "Fixture mode has no recorded scans yet. Run one scan with MONSTER_MODE=live, "
                    "or POST /api/dev/seed with a spike run folder."
                )
            # Only replay scans whose cutouts this closet holds: another device's clothes never leak in.
            mine = [r for r in (self.cache.get("scans", k) for k in recorded) if r and r["kept"] and all(
                (self.settings.cutout_dir / f"{i['item_id']}.png").exists() for i in r["kept"])]
            if not mine:
                raise FixtureMissing("Fixture mode has nothing recorded for this closet. Load the sample closet, "
                                     "or run with MONSTER_MODE=live.")
            replay = mine[int(key, 16) % len(mine)]
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
        warning = scan.contrast_warning(photo, items)
        self.cache.put("scans", key, {"source": source, "kept": kept, "dropped": dropped, "version": "scan", "warning": warning})
        return PhotoResult(source, kept, [{"source": source, "reason": r} for r in dropped], warning=warning)

    # -- tagging

    async def _tag(self, item_id: str, notes: str = "") -> tuple[Garment | None, str | None]:
        png = (self.settings.cutout_dir / f"{item_id}.png").read_bytes()
        key = tag_key(png)
        hit = self.cache.get("tags", key)
        if hit:
            return Garment.model_validate(hit), None
        if not self.settings.live:
            return None, "no recorded tags for this cutout (fixture mode)"
        async with self._tag_gate:
            try:
                garment = await asyncio.to_thread(models.tag_garment, Image.open(io.BytesIO(png)), None, "", notes)
            except Exception as e:  # one bad cutout shouldn't fail the whole scan
                return None, config.redact(f"{type(e).__name__}: {e}")[:300]
        self.cache.put("tags", key, garment.model_dump())
        return garment, None

    # -- correcting one item: ask the tagger again, or replace its photo

    async def retag(self, item_id: str, hint: str = "") -> None:
        """Tag the item's cutout again, with the owner's hint if any. Kept as a user fix (later rescans keep it)."""
        if not self.settings.live:
            raise FixtureMissing("Asking again needs live mode (it calls Muse Spark). You can still fix the tags by hand.")
        img = Image.open(self.settings.cutout_dir / f"{item_id}.png")
        async with self._tag_gate:
            garment = await asyncio.to_thread(models.tag_garment, img, None, hint)
        self.store.update_tags(item_id, garment)

    async def rescan(self, old_id: str, name: str, data: bytes) -> str:
        """A new photo of one piece replaces its old cutout. The best garment SAM finds in the photo becomes
        the item; the old item's wear history moves onto it. Returns the new item id."""
        if not self.settings.live:
            raise FixtureMissing("Rescanning needs live mode: in demo mode a photo replays a recorded scan.")
        before = {i["id"] for i in self.store.list_items(include_hidden=True)}
        res = await self._scan_photo(0, name, data)
        if not res.kept:
            raise ValueError("I couldn't find a garment in that photo. Lay just this piece flat on a plain floor and try again.")
        cut = self.settings.cutout_dir
        best = max(res.kept, key=lambda k: (k.get("confidence") or 0.5) * dedupe_mod.visible_area(cut / f"{k['item_id']}.png"))
        for k in res.kept:  # other things in the photo aren't part of this fix
            if k["item_id"] != best["item_id"] and k["item_id"] not in before:
                (cut / f"{k['item_id']}.png").unlink(missing_ok=True)
        garment, err = await self._tag(best["item_id"])
        scan_id = uuid.uuid4().hex[:12]
        # The store maps a cutout it has merged before onto the item it went into.
        new_id = self.store.upsert_item(best["item_id"], scan_id, name, best.get("confidence"), garment, err)
        if new_id == old_id:
            return old_id
        self.store.merge_items(new_id, old_id)
        self.store.add_scan({"id": scan_id, "created_at": now(), "mode": self.settings.mode, "seconds": 0, "photos": 1,
                             "cached_photos": int(res.cached), "replayed": False, "item_ids": [new_id], "dropped": []})
        return new_id

    # -- the whole scan

    async def run_scan(self, photos: list[tuple[str, bytes]]) -> dict:
        t0 = time.time()
        scan_id = uuid.uuid4().hex[:12]
        results = await asyncio.gather(*(self._scan_photo(i, name, data) for i, (name, data) in enumerate(photos)))

        kept = [(r.source, k) for r in results for k in r.kept]
        unique = list({k["item_id"]: (src, k) for src, k in kept}.values())  # same cutout twice -> once
        notes = self._shape_notes(results)
        tags = await asyncio.gather(*(self._tag(k["item_id"], notes.get(k["item_id"], "")) for _, k in unique))
        item_ids, new_ids = [], []
        for (src, k), (garment, err) in zip(unique, tags, strict=True):
            existed = self.store.get_item(k["item_id"]) is not None
            item_id = self.store.upsert_item(k["item_id"], scan_id, src, k.get("confidence"), garment, err)
            item_ids.append(item_id)
            if not existed:
                new_ids.append(item_id)

        # The same garment shot in two photos (this batch or an earlier one) becomes one item.
        dupes = await self.dedupe.check(new_ids) if new_ids else {"merged": [], "review": [], "checked": 0}
        merged_into = {m["dropped_id"]: m["kept_id"] for m in dupes["merged"]}
        item_ids = list(dict.fromkeys(merged_into.get(i, i) for i in item_ids))

        # Real clothes replace the sample closet: its made-up pieces would otherwise mix into their plans.
        sample_removed = 0
        if any(not r.replayed for r in results):
            sample_removed = self.remove_sample()

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
            "warnings": [r.warning for r in results if r.warning],
        }
        self.store.add_scan(record)
        return {**record, "duplicates": dupes, "sample_removed": sample_removed}

    def _shape_notes(self, results: list[PhotoResult]) -> dict[str, str]:
        """Outline measurements per new cutout, with its size next to the largest piece in the same photo."""
        out = {}
        for r in results:
            if r.cached or r.replayed:
                continue  # tags for these come from the cache
            sizes = {k["item_id"]: dedupe_mod.visible_area(self.settings.cutout_dir / f"{k['item_id']}.png") for k in r.kept}
            biggest = max(sizes.values(), default=0) or 1
            for item_id, area in sizes.items():
                img = Image.open(self.settings.cutout_dir / f"{item_id}.png")
                out[item_id] = scan.shape_notes(img, area / biggest if len(sizes) > 1 else None)
        return out

    def sample_ids(self) -> set[str]:
        import json
        return {r["id"] for r in json.loads((SAMPLE_DIR / "closet.json").read_text(encoding="utf-8"))}

    def remove_sample(self) -> int:
        """Take the sample closet's pieces out (they're made up). Returns how many were removed."""
        ids = self.sample_ids() & {i["id"] for i in self.store.list_items(include_hidden=True)}
        for item_id in ids:
            self.store.delete_item(item_id)
        return len(ids)

    # -- the sample closet (fixtures/sample_closet, made by scripts/make_sample_closet.py)

    def load_sample(self, today) -> dict:
        """Fill this closet with the made-up sample closet, so someone can try the app without scanning.

        Each piece gets an estimated last-worn date, so there are forgotten pieces to rescue straight away.
        Loading twice is harmless: items are keyed by their cutout.
        """
        import json
        from datetime import timedelta

        rows = json.loads((SAMPLE_DIR / "closet.json").read_text(encoding="utf-8"))
        ids = []
        for r in rows:
            png = (SAMPLE_DIR / f"{r['id']}.png").read_bytes()
            (self.settings.cutout_dir / f"{r['id']}.png").write_bytes(png)
            garment = Garment.model_validate(r["tags"])
            self.cache.put("tags", tag_key(png), garment.model_dump())
            self.store.upsert_item(r["id"], "sample", "sample closet", None, garment, None)
            self.store.set_last_worn_estimate(r["id"], (today - timedelta(days=r["idle_days"])).isoformat())
            ids.append(r["id"])
        # Replayable in fixture mode, like any recorded scan.
        self.cache.put("scans", sha256(b"sample-closet"), {"source": "sample closet", "dropped": [], "version": "sample",
                                                         "kept": [{"item_id": i, "confidence": None} for i in ids]})
        self.store.add_scan({"id": f"sample-{uuid.uuid4().hex[:6]}", "created_at": now(), "mode": "sample", "seconds": 0,
                             "photos": 0, "cached_photos": 0, "replayed": False, "item_ids": ids, "dropped": []})
        return {"imported": len(ids)}

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
