"""Cross-photo duplicate handling for the wardrobe.

After a scan (or on demand from the Closet screen), new items are compared with the
rest of the wardrobe. Confident "same garment" verdicts are merged automatically,
keeping the cutout that shows the most of the garment; unsure ones are returned for
the user to decide. Verdicts are cached per cutout pair, so fixture mode replays them
and a pair is never paid for twice. Pairs the user called different are never re-asked.
"""

from __future__ import annotations

import asyncio
import json

from PIL import Image

from closet import config, dedupe
from closet.schema import SameGarment

from .cache import Cache, sha256
from .settings import Settings
from .store import Store

AUTO_MERGE = 0.85  # live test: true pairs 0.88-0.96, different pairs judged different at 0.96+
JUDGE_CONCURRENCY = 6
DEDUPE_VERSION = "dupe1-" + sha256(
    (dedupe.JUDGE_INSTRUCTIONS + config.REASON_MODEL + json.dumps(SameGarment.model_json_schema(), sort_keys=True)).encode()
)[:8]


class Dedupe:
    def __init__(self, settings: Settings, cache: Cache, store: Store):
        self.settings, self.cache, self.store = settings, cache, store
        self._gate = asyncio.Semaphore(JUDGE_CONCURRENCY)

    def _key(self, a: str, b: str) -> str:
        return sha256(f"{DEDUPE_VERSION}:{':'.join(sorted((a, b)))}".encode())

    async def _judge(self, a: dict, b: dict) -> SameGarment | None:
        key = self._key(a["id"], b["id"])
        hit = self.cache.get("dupes", key)
        if hit:
            return SameGarment.model_validate(hit)
        if not self.settings.live:
            return None  # fixture mode: no verdict recorded, the user decides
        cut = self.settings.cutout_dir
        async with self._gate:
            try:
                verdict = await asyncio.to_thread(
                    dedupe.judge_same, Image.open(cut / f"{a['id']}.png"), Image.open(cut / f"{b['id']}.png"),
                    a["tags"], b["tags"])
            except Exception:
                return None  # a failed check shouldn't fail the scan; the pair goes to review
        self.cache.put("dupes", key, verdict.model_dump())
        return verdict

    def keep_drop(self, a: dict, b: dict) -> tuple[dict, dict]:
        """Keep a user-edited item, else the cutout that shows the most garment."""
        if a["user_edited"] != b["user_edited"]:
            return (a, b) if a["user_edited"] else (b, a)
        cut = self.settings.cutout_dir
        area = {x["id"]: dedupe.visible_area(cut / f"{x['id']}.png") for x in (a, b)}
        return (a, b) if area[a["id"]] >= area[b["id"]] else (b, a)

    async def check(self, focus: list[str] | None = None) -> dict:
        """Compare `focus` items (default: all) with the wardrobe. Returns {merged, review, checked}."""
        items = [i for i in self.store.list_items() if i["tags"]]
        pairs = dedupe.candidate_pairs(items, self.settings.cutout_dir, set(focus) if focus is not None else None,
                                       self.store.distinct_pairs())
        verdicts = await asyncio.gather(*(self._judge(a, b) for a, b, _ in pairs))

        merged, review, gone = [], [], {}
        def canon(x: str) -> str:
            while x in gone:
                x = gone[x]
            return x

        ranked = sorted(zip(pairs, verdicts), key=lambda pv: -(pv[1].confidence if pv[1] and pv[1].same_item else 0))
        for (a, b, _), v in ranked:
            ia, ib = canon(a["id"]), canon(b["id"])
            if ia == ib:
                continue  # already merged through another pair
            a, b = self.store.get_item(ia), self.store.get_item(ib)
            if v is not None and not v.same_item:
                continue
            if v is not None and v.confidence >= AUTO_MERGE:
                keep, drop = self.keep_drop(a, b)
                self.store.merge_items(keep["id"], drop["id"])
                gone[drop["id"]] = keep["id"]
                merged.append({"kept_id": keep["id"], "dropped_id": drop["id"], "confidence": v.confidence,
                               "reason": v.matching_details})
            else:
                review.append({"a_id": a["id"], "b_id": b["id"], "checked": v is not None,
                               "confidence": v.confidence if v else None,
                               "reason": v.matching_details if v else "Not checked yet: looks alike in kind and colour."})
        # A pair queued for review may involve an item merged away later in the loop.
        review = [r for r in review if r["a_id"] not in gone and r["b_id"] not in gone]
        return {"merged": merged, "review": review, "checked": len(pairs)}
