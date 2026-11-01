"""Product shots for scanned items (closet/products.py), made in the background after a scan.

Item ids hash their cutout, so a product shot is keyed by item id alone and every closet
shares one folder of them, like the model cache. Each item gets one try: a refusal, a SAM
miss or a redraw whose colour drifted is recorded next to it, and the app keeps showing
the scan. Fixture mode serves what exists and never generates.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from PIL import Image

from closet import config, media, models, products
from closet.schema import Garment

from .settings import Settings

PRODUCT_VERSION = "product1"
EDGE = 640  # shown at most ~300px wide on a phone
CONCURRENCY = 3
OPEN_SHAPES = {"accessory"}


class Products:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.dir = settings.cache_dir / "products" / PRODUCT_VERSION
        self.dir.mkdir(parents=True, exist_ok=True)
        self._gate = asyncio.Semaphore(CONCURRENCY)
        self._tasks: dict[str, asyncio.Task] = {}

    def url(self, item_id: str) -> str | None:
        return f"/api/products/{item_id}.webp" if (self.dir / f"{item_id}.webp").exists() else None

    def use_scan(self, item_id: str) -> None:
        """The owner prefers their own scan to the redraw (it lost a detail, say): never redraw it on its own again."""
        self.forget(item_id)
        self._note(item_id, ok=False, reason="the owner chose their scan")

    def forget(self, item_id: str) -> None:
        """Drop an item's product shot (its tags changed), so the next start() makes a new one."""
        for ext in ("webp", "json"):
            (self.dir / f"{item_id}.{ext}").unlink(missing_ok=True)

    def drift(self, item_id: str) -> float | None:
        """How far the product shot's measured colour is from the scan's (ΔE), if there is a shot."""
        meta = self.dir / f"{item_id}.json"
        if not (self.dir / f"{item_id}.webp").exists() or not meta.exists():
            return None
        return json.loads(meta.read_text()).get("drift")

    def _tried(self, item_id: str) -> bool:
        return (self.dir / f"{item_id}.webp").exists() or (self.dir / f"{item_id}.json").exists()

    def _wanted(self, items: list[dict]) -> list[dict]:
        return [i for i in items if i.get("tags") and i.get("is_garment", True) and not self._tried(i["id"])]

    def status(self, items: list[dict]) -> dict:
        ids = {i["id"] for i in items}
        return {"done": sum(1 for i in ids if (self.dir / f"{i}.webp").exists()),
                "running": sum(1 for k, t in self._tasks.items() if k in ids and not t.done()),
                "waiting": 0 if self.settings.live else len(self._wanted(items)),
                "live": self.settings.live}

    def start(self, items: list[dict], cutout_dir: Path) -> dict:
        """Start a product shot for every item that has none yet (live mode). Returns status()."""
        if self.settings.live:
            for it in self._wanted(items):
                if it["id"] not in self._tasks or self._tasks[it["id"]].done():
                    self._tasks[it["id"]] = asyncio.ensure_future(self._make(it, cutout_dir / f"{it['id']}.png"))
        return self.status(items)

    def _note(self, item_id: str, **meta) -> None:
        (self.dir / f"{item_id}.json").write_text(json.dumps({"version": PRODUCT_VERSION, **meta}))

    async def _make(self, item: dict, cutout_path: Path) -> None:
        item_id = item["id"]
        try:
            tags = Garment.model_validate(item["tags"])
            cutout = Image.open(cutout_path).convert("RGBA")
            prompt = products.prompt(tags, media.dominant_color(cutout))
            shot, check = None, None
            for attempt in range(2):  # a redraw that lost a detail gets one more go, told what it lost
                async with self._gate:
                    drawn, status = await asyncio.to_thread(models._edit, [media.on_white(cutout)], prompt)
                    if drawn is None:
                        return self._note(item_id, ok=False, reason=status)
                    client = config.async_client_for("meta")
                    shot = None
                    for noun in products.nouns(tags):
                        if shot := await products.cut(client, drawn, noun, tags.category in OPEN_SHAPES):
                            break
                if shot is None:
                    return self._note(item_id, ok=False, reason=f"SAM found no {tags.subtype}")
                drift = products.colour_drift(cutout, shot)
                if drift > products.MAX_DELTA_E:
                    return self._note(item_id, ok=False, reason=f"colour drifted (ΔE {drift:.1f})", drift=round(drift, 1))
                check = await asyncio.to_thread(products.check_details, cutout, shot, tags)
                if check.same_garment and not check.missing_details:
                    break
                prompt = (products.prompt(tags, media.dominant_color(cutout)) + " The last redraw lost these details of the "
                          "real item; they must be there this time: " + "; ".join(check.missing_details or [check.real_details]) + ".")
            if check and (not check.same_garment or check.missing_details):
                return self._note(item_id, ok=False, drift=round(drift, 1),
                                  reason="lost details: " + "; ".join(check.missing_details or ["not the same garment"])[:200])
            shot.thumbnail((EDGE, EDGE))
            shot.save(self.dir / f"{item_id}.webp", format="WEBP", quality=85, method=6)
            self._note(item_id, ok=True, drift=round(drift, 1), details=check.real_details[:300] if check else None)
        except (Exception, SystemExit) as e:  # noqa: BLE001  one bad item (or a missing API key) shouldn't stop the rest
            self._note(item_id, ok=False, reason=f"{type(e).__name__}: {e}"[:300])
