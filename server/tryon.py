"""Try-on: who wears the outfit, and render jobs.

Three modes, matching the privacy design:
- mannequin (default): a faceless stand-in built from height, build, form and a finish colour.
- photo (opt-in): the user's own full-body photo. It needs explicit consent and must pass
  Muse Spark's photo check (one person, head to feet, face visible). It is re-encoded on
  arrival, which strips EXIF metadata like GPS, and kept in var/private/. Deleting it also
  deletes every render made from it.
- flat: no body at all, just the real cutouts on a board. Always faithful, always free.

Renders take a minute or so (Muse Image, then the Muse Spark judge, maybe one corrected
retry), so they run as background jobs the app polls. Finished renders are cached under a
hash of the look's items and the wearer, so the same look is never paid for twice; fixture
mode serves cached renders and otherwise falls back to the flat-lay.
"""

from __future__ import annotations

import asyncio
import io
import json
import time
import uuid
from datetime import datetime, timezone

from PIL import Image

from closet import config, media, models
from closet.schema import BodyProfile, Garment

from .cache import Cache, sha256
from .settings import Settings
from .store import Store

RENDER_VERSION = "render1-" + sha256(f"{config.IMAGE_MODEL}:{config.REASON_MODEL}:{models.GARMENT_RULES}".encode())[:8]
PHOTO_EDGE = 1536
DEFAULT_PROFILE = {"mode": "mannequin", "body": None, "photo": None}
STEP_TEXT = {"render": "Dressing up", "judge": "Checking it matches your clothes"}


def review_summary(review, items: list[dict], mannequin: bool, score: int) -> dict:
    """What the app shows under a render: the score and the judge's notes, garments first.
    Wearer notes are included whenever they cost points, so a low score never comes unexplained."""
    diffs = [f"{items[g.garment - 1]['tags']['subtype'].capitalize()}: {g.differences}"
             for g in review.garments if g.score < 5 and g.differences.strip().lower() != "none"
             and 0 < g.garment <= len(items)]
    s = review.subject
    if s.matches_request < 4 or (mannequin and s.has_human_face):
        diffs.append(("Mannequin: " if mannequin else "You: ") + s.notes)
    return {"score": score, "differences": diffs[:4]}


class TryOn:
    def __init__(self, settings: Settings, cache: Cache, store: Store):
        self.settings, self.cache, self.store = settings, cache, store
        self.render_dir = settings.var_dir / "renders"
        self.private_dir = settings.var_dir / "private"
        for d in (self.render_dir, self.private_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, dict] = {}
        self._running: dict[str, str] = {}  # render key -> job id

    # ------------------------------------------------------------ profile

    @property
    def photo_path(self):
        return self.private_dir / "person.jpg"

    def profile(self) -> dict:
        return {**DEFAULT_PROFILE, **(self.store.get_setting("tryon") or {})}

    def public_profile(self) -> dict:
        p = self.profile()
        photo = p["photo"] if p["photo"] and self.photo_path.exists() else None
        ready = (p["mode"] == "flat" or (p["mode"] == "mannequin" and p["body"] is not None)
                 or (p["mode"] == "photo" and photo is not None))
        return {"mode": p["mode"], "body": p["body"], "ready": ready,
                "photo": {"checked_at": photo["checked_at"], "advice": photo["advice"]} if photo else None}

    def set_profile(self, mode: str, body: dict | None) -> dict:
        p = self.profile()
        if mode == "mannequin":
            if body is None and p["body"] is None:
                raise ValueError("The mannequin needs height, build, form and finish.")
            if body is not None:
                p["body"] = BodyProfile.model_validate(body).model_dump()
        if mode == "photo" and not (p["photo"] and self.photo_path.exists()):
            raise ValueError("Add a full-body photo first.")
        p["mode"] = mode
        self.store.put_setting("tryon", p)
        return self.public_profile()

    async def set_photo(self, data: bytes, consent: bool) -> dict:
        if not consent:
            raise ValueError("Please confirm you want to use your photo for try-on.")
        if not self.settings.live:
            raise ValueError("Checking a photo needs live mode (MONSTER_MODE=live).")
        img = media.load_image(io.BytesIO(data), max_edge=PHOTO_EDGE)
        check = await asyncio.to_thread(models.check_person_photo, img)
        result = {"ok": check.ok, "advice": check.advice, "one_person": check.one_person,
                  "full_body": check.full_body, "face_visible": check.face_visible}
        if not check.ok:
            return result  # a failed photo is never stored
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)  # re-encoding drops EXIF (location, device)
        self.delete_photo(keep_mode=True)
        self.photo_path.write_bytes(buf.getvalue())
        p = self.profile()
        p["photo"] = {"sha": sha256(buf.getvalue())[:16], "advice": check.advice,
                      "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        p["mode"] = "photo"
        self.store.put_setting("tryon", p)
        return result

    def delete_photo(self, keep_mode: bool = False) -> int:
        """Delete the photo and every render made from it. Returns how many renders went."""
        p = self.profile()
        sha = p["photo"]["sha"] if p["photo"] else None
        removed = 0
        if sha:
            for key in self.cache.keys("renders"):
                meta = self.cache.get("renders", key)
                if meta and meta.get("photo_sha") == sha:
                    (self.render_dir / meta["file"]).unlink(missing_ok=True)
                    (self.cache.root / "renders" / f"{key}.json").unlink(missing_ok=True)
                    removed += 1
        self.photo_path.unlink(missing_ok=True)
        p["photo"] = None
        if p["mode"] == "photo" and not keep_mode:
            p["mode"] = "mannequin" if p["body"] else "flat"
        self.store.put_setting("tryon", p)
        return removed

    # ------------------------------------------------------------ renders

    def _look(self, plan_id: str, look_index: int) -> tuple[dict, list[dict]]:
        plan = self.store.get_plan(plan_id=plan_id)
        if not plan:
            raise KeyError("No such plan.")
        looks = plan["plan"]["looks"]
        if not 0 <= look_index < len(looks):
            raise IndexError(f"look must be 0-{len(looks) - 1}")
        items = [i for i in (self.store.get_item(x) for x in looks[look_index]["item_ids"]) if i and i["tags"]]
        if not items:
            raise KeyError("That look's items are no longer in the closet.")
        return looks[look_index], items

    def _cutout(self, item_id: str) -> Image.Image:
        # Load fully now: lazily-loaded PIL images raced across threads in the Day-0 eval.
        return Image.open(self.settings.cutout_dir / f"{item_id}.png").convert("RGBA")

    def flatlay_url(self, item_ids: list[str]) -> str:
        name = f"flat-{sha256(':'.join(item_ids).encode())[:16]}.png"
        path = self.render_dir / name
        if not path.exists():
            media.flat_lay([self._cutout(i) for i in item_ids]).save(path)
        return f"/api/renders/{name}"

    def _key(self, item_ids: list[str], p: dict) -> str:
        wearer = p["body"] if p["mode"] == "mannequin" else (p["photo"] or {}).get("sha")
        return sha256(json.dumps([RENDER_VERSION, item_ids, p["mode"], wearer], sort_keys=True).encode())[:24]

    def start(self, plan_id: str, look_index: int) -> dict:
        look, items = self._look(plan_id, look_index)
        ids = [i["id"] for i in items]
        p = self.profile()
        base = {"id": uuid.uuid4().hex[:12], "plan_id": plan_id, "look": look_index, "look_name": look["name"],
                "mode": p["mode"], "flatlay_url": self.flatlay_url(ids), "render_url": None, "cached": False,
                "score": None, "attempts": 0, "differences": [], "seconds": None, "error": None, "note": None}
        if p["mode"] == "flat":
            return {**base, "status": "done"}
        if not self.public_profile()["ready"]:
            raise ValueError("Set up try-on first: a mannequin or your photo.")

        key = self._key(ids, p)
        meta = self.cache.get("renders", key)
        if meta and (self.render_dir / meta["file"]).exists():
            return {**base, **{k: meta[k] for k in ("score", "attempts", "differences", "seconds")},
                    "status": "done", "cached": True, "render_url": f"/api/renders/{meta['file']}"}
        if key in self._running and self._running[key] in self.jobs:
            return self.jobs[self._running[key]]
        if not self.settings.live:
            return {**base, "status": "done", "note": "Renders need live mode, so here's the flat-lay of your real pieces."}

        job = {**base, "status": "running", "step": STEP_TEXT["render"], "started": time.time()}
        self.jobs[job["id"]] = job
        self._running[key] = job["id"]
        asyncio.get_running_loop().create_task(self._run(job, key, items, p))
        return job

    async def _run(self, job: dict, key: str, items: list[dict], p: dict) -> None:
        def step(s: str) -> None:
            kind, n = s.split()
            job["step"] = STEP_TEXT[kind] + (" (fixing details)" if kind == "render" and n != "1" else "")
            job["attempts"] = int(n)

        try:
            garments = [self._cutout(i["id"]) for i in items]
            tags = [Garment.model_validate(i["tags"]) for i in items]
            person = Image.open(self.photo_path).convert("RGB") if p["mode"] == "photo" else None
            body = BodyProfile.model_validate(p["body"]) if p["mode"] == "mannequin" else None
            out = await asyncio.to_thread(models.render_best, garments, tags, person=person, profile=body, on_step=step)
            best = out["best"]
            if best["image"] is None:
                job.update(status="failed", error="Muse Image couldn't render this look: " + best["status"][:200])
                return
            file = f"{key}.png"
            best["image"].save(self.render_dir / file)
            summary = {**review_summary(best["review"], items, mannequin=person is None, score=best["score"]),
                       "attempts": len(out["attempts"]), "seconds": round(time.time() - job["started"], 1)}
            self.cache.put("renders", key, {"file": file, "photo_sha": (p["photo"] or {}).get("sha")
                                            if p["mode"] == "photo" else None, **summary})
            job.update(status="done", render_url=f"/api/renders/{file}", **summary)
        except Exception as e:
            job.update(status="failed", error=f"{type(e).__name__}: {e}"[:300])
        finally:
            self._running.pop(key, None)
