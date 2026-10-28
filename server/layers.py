"""Layered try-on ("paper doll"): one mannequin render per body profile, one layer per garment.

The spike (spike/layers.py) showed Muse Image keeps a mannequin's pose and framing when
asked to dress an existing image, to within ~1% of pixels outside the garment, so layers
rendered separately line up without any alignment step. So:

- base: a plain white mannequin (body details next to a bare mannequin trip Muse Image's
  content filter), then an edit that recolours it to the user's finish and form. Once per
  body profile.
- layer: the base dressed in a single garment, cut out with SAM 3.1, cropped to its box.
  Once per garment per base.
- outfit: the app stacks layers on the base (bottoms, then tops, then outerwear). Free and
  instant, so swapping looks or taking a piece off costs nothing.

Everything is cached on disk under var/layers/<base key>/. Fixture mode serves what exists
and never generates. Only tops, bottoms, dresses and outerwear get layers.
"""

from __future__ import annotations

import asyncio
import json
import time

import cv2
import meta_sam_parser as sp
import numpy as np
from PIL import Image

from closet import config, media, models, sam
from closet.schema import SILHOUETTE_WORDS, SKIN_TONES, BodyProfile, Garment

from .cache import sha256
from .settings import Settings
from .store import Store

ORDER = {"bottom": 1, "dress": 1, "top": 2, "outerwear": 3}  # stacking order, bottom first
KEEP_AREA = {"bottom": "upper body and arms", "top": "legs and feet", "outerwear": "legs and feet",
             "dress": "arms and lower legs"}
CANVAS = (1024, 2048)
CANVAS_BG = (232, 230, 226)
EDIT_CONCURRENCY = 3

BASE_PROMPT = (
    "Replace this blank canvas with: Full-body front view studio product photo of a white store display mannequin "
    "with a smooth featureless head, standing straight and facing the camera, arms hanging relaxed slightly away from "
    "the sides, feet slightly apart, on a round chrome stand, centred in the frame with space above the head and "
    "below the feet. Plain light grey seamless studio background, soft even lighting. A retail display fixture ready "
    "to be dressed."
)
KEEP = ("Keep everything else identical: the same pose, position and size in the frame, the same stand, camera, "
        "background and lighting.")
LAYER_VERSION = "layers1-" + sha256((BASE_PROMPT + KEEP + config.IMAGE_MODEL + models.GARMENT_RULES).encode())[:8]


def recolour_prompts(body: BodyProfile) -> list[str]:
    """Most specific first; each step drops a detail if the content filter refuses."""
    hex_, tone = SKIN_TONES[body.skin_tone]
    form = SILHOUETTE_WORDS[body.silhouette]
    head = "Image 1 is a white store display mannequin. Change it to a "
    tail = f" in a {tone} matte finish ({hex_}), with the same smooth featureless head. " + KEEP
    return [head + f"{form} store display mannequin with a {body.build} build" + tail,
            head + f"{form} store display mannequin" + tail,
            f"Image 1 is a white store display mannequin. Change only its colour to a {tone} matte finish ({hex_}). " + KEEP]


def layer_prompt(tags: Garment, color_hex: str, category: str) -> str:
    return ("Image 1 is a store display mannequin. Image 2 is a real clothing item. Put exactly the item from image 2 "
            f"on the mannequin in image 1, and nothing else. {KEEP} Leave the {KEEP_AREA[category]} exactly as they "
            f"are in image 1. Item: {tags.render_line(color_hex)}. "
            + models.GARMENT_RULES.replace(" Full-body, neutral studio background.", ""))


async def garment_mask(img: Image.Image, prompts: list[str]) -> np.ndarray | None:
    """The largest SAM mask for the first prompt that finds anything, at full size, holes filled."""
    client = config.async_client_for("meta")
    small = img.copy()
    small.thumbnail((1024, 1024))
    for prompt in prompts:
        run = await sam.segment(client, prompt, image_data_url=media.to_data_url(small))
        best = None
        for t in run.tracks:
            if 0 not in t.masks:
                continue
            rec = t.masks[0]
            b = rec.bounds
            m, _ = media.place_mask(sp.decode_mask_to_raster(rec.mask), rec.mask.width, rec.mask.height,
                                    (b.left, b.top, b.right, b.bottom), small.width, small.height)
            if best is None or m.sum() > best.sum():
                best = m
        if best is not None:
            return media.fill_holes(media.upscale_mask(best, img.size))
    return None


def cut_layer(dressed: Image.Image, mask: np.ndarray) -> tuple[Image.Image, list[int]]:
    """The garment as a soft-edged RGBA crop, plus its box [x, y, w, h] on the base."""
    alpha = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 1.5)
    rgba = np.dstack([np.asarray(dressed.convert("RGB")), (alpha * 255).clip(0, 255).astype(np.uint8)])
    ys, xs = np.nonzero(alpha > 0.02)
    x0, y0, x1, y1 = max(xs.min() - 2, 0), max(ys.min() - 2, 0), min(xs.max() + 3, rgba.shape[1]), min(ys.max() + 3, rgba.shape[0])
    return Image.fromarray(rgba[y0:y1, x0:x1], "RGBA"), [int(x0), int(y0), int(x1 - x0), int(y1 - y0)]


class Layers:
    def __init__(self, settings: Settings, store: Store):
        self.settings, self.store = settings, store
        self.root = settings.var_dir / "layers"
        self.root.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, asyncio.Task] = {}
        self._gate = asyncio.Semaphore(EDIT_CONCURRENCY)

    # ------------------------------------------------------------ paths and state

    @staticmethod
    def base_key(body: dict) -> str:
        return sha256(json.dumps([LAYER_VERSION, body], sort_keys=True).encode())[:16]

    def _meta(self, key: str, name: str) -> dict | None:
        p = self.root / key / f"{name}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def _put_meta(self, key: str, name: str, meta: dict) -> None:
        (self.root / key).mkdir(parents=True, exist_ok=True)
        (self.root / key / f"{name}.json").write_text(json.dumps(meta))

    def _state(self, key: str, name: str) -> dict:
        """ready | pending | failed | missing (nothing made yet, nothing running)."""
        meta = self._meta(key, name)
        if meta and meta.get("status") == "ready" and (self.root / key / f"{name}.png").exists():
            return {"state": "ready", "url": f"/api/layers/{key}/{name}.png", **{k: meta[k] for k in ("box", "size") if k in meta}}
        task = self._tasks.get(f"{key}/{name}")
        if task and not task.done():
            return {"state": "pending"}
        if meta and meta.get("status") == "failed":
            return {"state": "failed", "error": meta.get("error")}
        return {"state": "missing"}

    def status(self, body: dict, item_ids: list[str], prepare: bool = False) -> dict:
        """Base and per-item layer states for these items; with prepare, start whatever is missing (live only)."""
        key = self.base_key(body)
        items = [i for i in (self.store.get_item(x) for x in item_ids) if i and i["tags"]]
        if prepare and self.settings.live:
            if self._state(key, "base")["state"] in ("missing", "failed"):
                self._start(f"{key}/base", self._make_base(key, body))
            for it in items:
                if it["tags"]["category"] in ORDER and self._state(key, it["id"])["state"] in ("missing", "failed"):
                    self._start(f"{key}/{it['id']}", self._make_layer(key, body, it))
        base = self._state(key, "base")
        layers = []
        for it in items:
            cat = it["tags"]["category"]
            if cat not in ORDER:
                layers.append({"item_id": it["id"], "category": cat, "order": 0, "state": "unsupported"})
                continue
            layers.append({"item_id": it["id"], "category": cat, "order": ORDER[cat], **self._state(key, it["id"])})
        note = None if self.settings.live else "Layers are made in live mode; showing the ones already made."
        return {"base_key": key, "base": base, "layers": layers, "live": self.settings.live, "note": note}

    def _start(self, name: str, coro) -> None:
        task = self._tasks.get(name)
        if task and not task.done():
            coro.close()
            return
        self._tasks[name] = asyncio.get_running_loop().create_task(coro)

    # ------------------------------------------------------------ generation

    async def _base(self, key: str, body: dict) -> Image.Image:
        """The base image, waiting for (or starting) its generation."""
        task = self._tasks.get(f"{key}/base")
        if self._state(key, "base")["state"] != "ready":
            if not task or task.done():
                self._start(f"{key}/base", self._make_base(key, body))
            await self._tasks[f"{key}/base"]
        if self._state(key, "base")["state"] != "ready":
            raise RuntimeError("the base mannequin couldn't be made")
        return Image.open(self.root / key / "base.png").convert("RGB")

    async def _make_base(self, key: str, body: dict) -> None:
        t0 = time.time()
        try:
            async with self._gate:
                plain, status = await asyncio.to_thread(models._edit, [Image.new("RGB", CANVAS, CANVAS_BG)], BASE_PROMPT)
            if plain is None:
                raise RuntimeError(status)
            final, applied = plain, "plain"
            for i, prompt in enumerate(recolour_prompts(BodyProfile.model_validate(body))):
                async with self._gate:
                    img, status = await asyncio.to_thread(models._edit, [plain], prompt)
                if img is not None:
                    final, applied = (img.resize(plain.size) if img.size != plain.size else img), ["full", "form", "finish"][i]
                    break
                if not status.startswith("refused"):
                    break
            (self.root / key).mkdir(parents=True, exist_ok=True)
            final.save(self.root / key / "base.png")
            self._put_meta(key, "base", {"status": "ready", "size": list(final.size), "applied": applied,
                                         "seconds": round(time.time() - t0, 1)})
        except Exception as e:
            self._put_meta(key, "base", {"status": "failed", "error": f"{type(e).__name__}: {e}"[:300]})

    async def _make_layer(self, key: str, body: dict, item: dict) -> None:
        t0 = time.time()
        try:
            base = await self._base(key, body)
            cutout = Image.open(self.settings.cutout_dir / f"{item['id']}.png").convert("RGBA")
            tags = Garment.model_validate(item["tags"])
            async with self._gate:
                dressed, status = await asyncio.to_thread(
                    models._edit, [base, media.on_white(cutout)], layer_prompt(tags, media.dominant_color(cutout), tags.category))
            if dressed is None:
                raise RuntimeError(status)
            if dressed.size != base.size:
                dressed = dressed.resize(base.size)
            words = tags.subtype.split()
            mask = await garment_mask(dressed, list(dict.fromkeys([tags.subtype, words[-1], "clothing"])))
            if mask is None or mask.sum() < 0.002 * mask.size:
                raise RuntimeError("SAM couldn't find the garment on the mannequin")
            layer, box = cut_layer(dressed, mask)
            layer.save(self.root / key / f"{item['id']}.png")
            self._put_meta(key, item["id"], {"status": "ready", "box": box, "size": list(base.size),
                                             "seconds": round(time.time() - t0, 1)})
        except Exception as e:
            self._put_meta(key, item["id"], {"status": "failed", "error": f"{type(e).__name__}: {e}"[:300]})
