"""Layered try-on experiment ("paper doll"): can separately rendered garments share one mannequin?

1. Render a bare base mannequin once (from the stored try-on body profile).
2. For each garment, ask Muse Image to put just that item on *that exact image*.
3. Cut the garment out of each dressed render with SAM 3.1.
4. Measure how far the mannequin drifted between renders (ECC alignment on everything that
   isn't the garment), warp each layer back onto the base, and stack layers into outfits.

If drift is small, every outfit can be composed instantly from per-garment layers: one render
per garment instead of one per outfit.

    python spike/layers.py --top 208284 --bottom 9632e7 --alt-top fecf90

Ids are prefixes of wardrobe item ids. Output: out/layers-<timestamp>/ (git-ignored).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import meta_sam_parser as sp  # noqa: E402

from closet import config, media, models, sam  # noqa: E402
from closet.schema import BodyProfile, Garment  # noqa: E402
from server import settings as settings_mod  # noqa: E402
from server.store import Store  # noqa: E402

BASE_BG = (232, 230, 226)


def base_prompt(profile: BodyProfile, detail: int) -> str:
    # No "unclothed"/"nothing on it" wording: next to body details it trips Muse Image's content filter.
    return (f"Full-body front view studio product photo of {profile.describe(detail)}, standing straight and facing "
            "the camera, arms hanging relaxed slightly away from the sides, feet slightly apart, centred in the frame "
            "with space above the head and below the feet. Plain light grey seamless studio background, soft even "
            "lighting. A retail display fixture ready to be dressed.")


def layer_prompt(tags: Garment, color_hex: str, other_area: str) -> str:
    return ("Image 1 is a store display mannequin. Image 2 is a real clothing item. Put exactly the item from image 2 "
            "on the mannequin in image 1, and nothing else. Keep everything else in image 1 identical: the same "
            "mannequin, the same pose, the same position and size in the frame, the same camera, background and "
            f"lighting. Leave the {other_area} exactly as it is in image 1. Item: {tags.render_line(color_hex)}. "
            + models.GARMENT_RULES.replace(" Full-body, neutral studio background.", ""))


def canvas(size=(1024, 2048)) -> Image.Image:
    return Image.new("RGB", size, BASE_BG)


async def garment_mask(img: Image.Image, prompts: list[str]) -> tuple[np.ndarray | None, str]:
    """Largest confident SAM mask for the first prompt that finds anything, at full image size."""
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
            return media.fill_holes(media.upscale_mask(best, img.size)), prompt
    return None, ""


def align(base: Image.Image, dressed: Image.Image, garment: np.ndarray) -> tuple[np.ndarray, dict]:
    """Affine warp mapping dressed -> base, fitted on pixels outside the (dilated) garment."""
    g0 = cv2.cvtColor(np.asarray(base), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    g1 = cv2.cvtColor(np.asarray(dressed), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    keep = (~cv2.dilate(garment.astype(np.uint8), np.ones((41, 41), np.uint8)).astype(bool)).astype(np.uint8)
    scale = 0.25  # fit on a quarter-size copy: faster and less sensitive to texture noise
    s0, s1 = (cv2.resize(x, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) for x in (g0, g1))
    km = cv2.resize(keep, (s0.shape[1], s0.shape[0]), interpolation=cv2.INTER_NEAREST)
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        cc, warp = cv2.findTransformECC(s0, s1, warp, cv2.MOTION_AFFINE,
                                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), km, 5)
    except cv2.error:
        cc = float("nan")
    warp[:, 2] /= scale  # translation back to full size
    sx, sy = float(np.hypot(*warp[:, 0])), float(np.hypot(*warp[:, 1]))
    before = float(np.abs(g0 - g1)[keep.astype(bool)].mean())
    aligned = cv2.warpAffine(g1, warp, (g0.shape[1], g0.shape[0]), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
    after = float(np.abs(g0 - aligned)[keep.astype(bool)].mean())
    return warp, {"shift_px": [round(float(warp[0, 2]), 1), round(float(warp[1, 2]), 1)],
                  "scale": [round(sx, 3), round(sy, 3)], "ecc": round(float(cc), 3),
                  "diff_before": round(before, 4), "diff_after": round(after, 4)}


def layer(dressed: Image.Image, garment: np.ndarray, warp: np.ndarray, size: tuple[int, int]) -> Image.Image:
    """The garment as an RGBA layer in base coordinates, with a soft edge."""
    alpha = cv2.GaussianBlur(garment.astype(np.float32), (0, 0), 1.5)
    rgba = np.dstack([np.asarray(dressed).astype(np.float32), alpha * 255])
    w = cv2.warpAffine(rgba, warp, size, flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=(0, 0, 0, 0))
    return Image.fromarray(np.clip(w, 0, 255).astype(np.uint8), "RGBA")


def compose(base: Image.Image, layers: list[Image.Image]) -> Image.Image:
    out = base.convert("RGBA")
    for lyr in layers:
        out.alpha_composite(lyr)
    return out.convert("RGB")


def ghost(a: Image.Image, b: Image.Image) -> Image.Image:
    """Base in red, dressed render in cyan: perfect alignment shows grey, drift shows colour fringes."""
    ga = np.asarray(a.convert("L"))
    gb = np.asarray(b.convert("L").resize(a.size))
    return Image.fromarray(np.dstack([ga, gb, gb]))


def sheet(cells: list[tuple[str, Image.Image]], h: int = 900) -> Image.Image:
    from PIL import ImageDraw
    thumbs = [(t, im.resize((round(im.width * h / im.height), h))) for t, im in cells]
    out = Image.new("RGB", (sum(im.width for _, im in thumbs) + 10 * len(thumbs), h + 34), "white")
    x, d = 0, ImageDraw.Draw(out)
    for t, im in thumbs:
        out.paste(im, (x, 34))
        d.text((x + 6, 8), t, fill="black")
        x += im.width + 10
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", required=True)
    ap.add_argument("--bottom", required=True)
    ap.add_argument("--alt-top", help="a second top, to compose a second outfit from the same bottom layer")
    args = ap.parse_args()

    s = settings_mod.load()
    store = Store(s.db_path)
    by_prefix = {i["id"]: i for i in store.list_items()}

    def item(prefix: str) -> dict:
        hits = [v for k, v in by_prefix.items() if k.startswith(prefix)]
        if len(hits) != 1:
            raise SystemExit(f"{prefix!r} matches {len(hits)} items")
        return hits[0]

    body = (store.get_setting("tryon") or {}).get("body") or {"height_cm": 170, "build": "regular",
                                                                "silhouette": "neutral", "skin_tone": 4}
    profile = BodyProfile.model_validate(body)
    out = config.ROOT / "out" / f"layers-{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True)
    report: dict = {"body": body, "steps": []}
    t0 = time.time()

    # 1. Base mannequin: an edit of a blank portrait canvas, so the output is portrait like our try-ons.
    base, status = None, ""
    for detail in (2, 1, 0):  # same idea as MANNEQUIN_LADDER: fewer body details on a refusal
        base, status = await asyncio.to_thread(models._edit, [canvas()],
                                               "Replace this blank canvas with: " + base_prompt(profile, detail))
        print(f"base detail={detail}: {status[:90]}")
        if base is not None or not status.startswith("refused"):
            break
    if base is None:
        raise SystemExit(f"base render failed: {status}")
    base.save(out / "base.png")
    report["steps"].append({"step": "base", "status": status, "size": base.size, "t": round(time.time() - t0, 1)})
    print(f"base {base.size} {status} ({time.time() - t0:.0f}s)")

    # 2-4. One layer per garment.
    pieces = [("bottom", item(args.bottom), "upper body and arms"), ("top", item(args.top), "legs and feet")]
    if args.alt_top:
        pieces.append(("alt_top", item(args.alt_top), "legs and feet"))

    async def one(role: str, it: dict, other: str) -> dict:
        t = time.time()
        g = Image.open(s.cutout_dir / f"{it['id']}.png").convert("RGBA")
        tags = Garment.model_validate(it["tags"])
        dressed, st = await asyncio.to_thread(models._edit, [base, media.on_white(g)],
                                              layer_prompt(tags, media.dominant_color(g), other))
        if dressed is None:
            return {"role": role, "status": st}
        resized = dressed.size != base.size
        if resized:
            dressed = dressed.resize(base.size)
        dressed.save(out / f"dressed_{role}.png")
        words = tags.subtype.split()
        mask, used = await garment_mask(dressed, [tags.subtype, words[-1], "clothing"])
        if mask is None:
            return {"role": role, "status": "SAM found no garment"}
        warp, stats = align(base, dressed, mask)
        lyr = layer(dressed, mask, warp, base.size)
        lyr.save(out / f"layer_{role}.png")
        ghost(base, dressed).save(out / f"ghost_{role}.png")
        print(f"{role}: {tags.subtype} {st} resized={resized} sam='{used}' {stats} ({time.time() - t:.0f}s)")
        return {"role": role, "item": tags.subtype, "status": st, "output_resized": resized, "sam_prompt": used,
                **stats, "seconds": round(time.time() - t, 1), "layer": lyr, "dressed": dressed}

    results = await asyncio.gather(*(one(*p) for p in pieces))
    layers = {r["role"]: r for r in results if "layer" in r}
    report["steps"] += [{k: v for k, v in r.items() if k not in ("layer", "dressed")} for r in results]

    cells = [("base", base)]
    cells += [(f"dressed {r}", layers[r]["dressed"]) for r in ("bottom", "top", "alt_top") if r in layers]
    if {"bottom", "top"} <= layers.keys():
        a = compose(base, [layers["bottom"]["layer"], layers["top"]["layer"]])
        a.save(out / "outfit_A.png")
        cells.append(("outfit A (composed)", a))
        # Score the composed outfit with the same judge as full renders.
        garments = [Image.open(s.cutout_dir / f"{item(x)['id']}.png").convert("RGBA") for x in (args.top, args.bottom)]
        tags = [Garment.model_validate(item(x)["tags"]) for x in (args.top, args.bottom)]
        review = await asyncio.to_thread(models.judge_render, garments, a, profile=profile,
                                         requested_view=models.outfit_brief(tags, garments)[1])
        report["judge_outfit_A"] = {"score": models.review_score(review, mannequin=True),
                                    "garments": [g.model_dump() for g in review.garments],
                                    "subject": review.subject.model_dump()}
        print("judge outfit A:", report["judge_outfit_A"]["score"], [g.differences[:90] for g in review.garments])
    if {"bottom", "alt_top"} <= layers.keys():
        b = compose(base, [layers["bottom"]["layer"], layers["alt_top"]["layer"]])
        b.save(out / "outfit_B.png")
        cells.append(("outfit B (same bottom layer)", b))
    sheet(cells).save(out / "sheet.jpg")
    for r in ("bottom", "top"):
        if r in layers:
            Image.open(out / f"ghost_{r}.png").save(out / f"ghost_{r}.png")
    report["seconds"] = round(time.time() - t0, 1)
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    print(f"done in {report['seconds']}s -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
