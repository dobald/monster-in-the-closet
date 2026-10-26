"""Go/no-go spike: does the closet pipeline survive real, messy footage?

Answers three questions, written to out/<run>/SUMMARY.md:
  1. Does SAM 3.1 segmentation hold up on a cluttered closet?
  2. Does it double-count garments (across frames, or across prompts)?
  3. Does a Muse Image try-on stay faithful to a real garment, or get refused?

Usage (from the repo root, venv active):
  python spike/spike.py segment data/closet.mp4 --expected 25
  python spike/spike.py tag out/<run>
  python spike/spike.py render out/<run> --person data/me.jpg
  python spike/spike.py all data/closet.mp4 --person data/me.jpg --expected 25
Add --dry-run to `segment` or `all` to see the cost estimate without calling the API.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import meta_sam_parser as sp  # noqa: E402
from PIL import Image  # noqa: E402

from closet import config, media, models, sam  # noqa: E402

DEFAULT_PROMPTS = [
    "clothing",  # generic probe: if this alone works, we need far fewer requests
    "shirt",
    "sweater",
    "jacket",
    "pants",
    "jeans",
    "dress",
    "skirt",
    "shoes",
]
MIN_TRACK_FRAMES = 3  # video tracks shorter than this are probably flicker


# ---------------------------------------------------------------- segment


async def _segment_all(path: Path, prompts: list[str]) -> tuple[list[sam.SegmentationRun], Image.Image | None]:
    client = config.async_client_for("meta")
    if media.is_video(path):
        print(f"Uploading {path.name} ...")
        file_id = await sam.upload_video(client, path)
        jobs = [sam.segment(client, p, video_file_id=file_id) for p in prompts]
        still = None
    else:
        still = media.load_image(path)
        url = media.to_data_url(still)
        jobs = [sam.segment(client, p, image_data_url=url) for p in prompts]
    print(f"Running SAM 3.1 for {len(prompts)} prompts in parallel ...")
    runs = await asyncio.gather(*jobs, return_exceptions=True)
    ok = []
    for p, r in zip(prompts, runs):
        if isinstance(r, Exception):
            print(f"  ! '{p}' failed: {r}")
        else:
            ok.append(r)
    return ok, still


def _merge_groups(tracks: list[sam.Track], dupes: list[tuple[str, str, float]]) -> list[list[str]]:
    parent = {t.key: t.key for t in tracks}

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for a, b, _ in dupes:
        parent[find(a)] = find(b)
    groups: dict[str, list[str]] = {}
    for t in tracks:
        groups.setdefault(find(t.key), []).append(t.key)
    return list(groups.values())


def cmd_segment(args: argparse.Namespace) -> Path:
    path = Path(args.media)
    if not path.exists():
        raise SystemExit(f"Not found: {path}")
    prompts = args.prompts or DEFAULT_PROMPTS
    info = media.video_info(path) if media.is_video(path) else None
    cost = sam.estimate_cost(len(prompts), info["frames"] if info else None)
    print(f"Media: {path.name} {info or '(photo)'}")
    print(f"Prompts ({len(prompts)}): {', '.join(prompts)}")
    print(f"Estimated SAM cost: ${cost:.2f}")
    if args.dry_run:
        return Path()

    run_dir = ROOT / "out" / time.strftime("%Y%m%d-%H%M%S")
    cut_dir = run_dir / "cutouts"
    cut_dir.mkdir(parents=True)

    runs, still = asyncio.run(_segment_all(path, prompts))
    tracks = [t for r in runs for t in r.tracks]

    frame_cache: dict[int, Image.Image] = {}
    sam_size = next((r.frame_size for r in runs if r.frame_size), None)

    def frame_at(i: int) -> Image.Image:
        if still is not None:
            return still
        if i not in frame_cache:
            img = media.read_frame(path, i)
            if sam_size and img.size != sam_size:
                img = img.resize(sam_size)  # SAM coordinates win if decode size differs
            frame_cache[i] = img
        return frame_cache[i]

    track_rows, sheet_items, mask_modes = [], [], set()
    for t in tracks:
        row = {
            "key": t.key,
            "frames_seen": len(t.frames),
            "first_frame": t.frames[0],
            "last_frame": t.frames[-1],
            "mean_confidence": round(sum(t.confidence.values()) / len(t.confidence), 3) if t.confidence else None,
            "flicker": bool(info) and len(t.frames) < MIN_TRACK_FRAMES,
            "cutout": None,
        }
        mask_frames = [f for f in t.masks if f in t.boxes]
        if mask_frames:
            f = max(mask_frames, key=lambda fr: t.area(fr) * t.confidence.get(fr, 1.0))
            rec = t.masks[f]
            frame = frame_at(f)
            try:
                raster = sp.decode_mask_to_raster(rec.mask)
                b = rec.bounds
                mask, mode = media.place_mask(
                    raster, rec.mask.width, rec.mask.height,
                    (b.left, b.top, b.right, b.bottom), frame.width, frame.height,
                )
                mask_modes.add(mode)
                img = media.cutout(frame, mask)
                name = f"{t.prompt.replace(' ', '_')}_{t.object_id}_f{f}.png"
                img.save(cut_dir / name)
                row.update(cutout=name, best_frame=f, mask_mode=mode)
                sheet_items.append((t.key, img))
            except sp.InvalidSegmentationMaskError as e:
                row["mask_error"] = str(e)
        track_rows.append(row)

    dupes = sam.cross_prompt_duplicates(tracks)
    groups = _merge_groups(tracks, dupes)
    real = [g for g in groups if not all(next(r for r in track_rows if r["key"] == k)["flicker"] for k in g)]

    report = {
        "media": str(path),
        "video_info": info,
        "sam_frame_size": sam_size,
        "local_frame_size": [info["width"], info["height"]] if info else list(still.size),
        "mask_modes_seen": sorted(mask_modes),
        "estimated_cost_usd": round(cost, 2),
        "prompts": [
            {
                "prompt": r.prompt,
                "tracks": len(r.tracks),
                "max_objects_in_a_frame": r.max_objects_in_a_frame,
                "hit_16_object_cap": r.max_objects_in_a_frame >= sam.MAX_OBJECTS_PER_FRAME,
                "outcome": r.outcome,
                "diagnostics": r.diagnostics[:10],
            }
            for r in runs
        ],
        "tracks": track_rows,
        "cross_prompt_duplicates": dupes,
        "unique_garments_estimate": len(real),
        "expected_garments": args.expected,
    }
    (run_dir / "segment_report.json").write_text(json.dumps(report, indent=2))
    if sheet_items:
        media.contact_sheet(sheet_items).save(run_dir / "contact_sheet.png")
    write_summary(run_dir)
    print(f"\nSegmented -> {run_dir}")
    print(f"  tracks: {len(tracks)}  unique estimate: {len(real)}  expected: {args.expected or '?'}")
    print(f"  cross-prompt duplicates: {len(dupes)}  mask modes: {sorted(mask_modes)}")
    return run_dir


# ---------------------------------------------------------------- tag


def cmd_tag(args: argparse.Namespace) -> None:
    run_dir = Path(args.run)
    cutouts = sorted((run_dir / "cutouts").glob("*.png"))
    if not cutouts:
        raise SystemExit(f"No cutouts in {run_dir}/cutouts. Run `segment` first.")
    provider = args.provider or config.TAG_PROVIDER
    print(f"Tagging {len(cutouts)} cutouts with {config.TAG_MODEL[provider]} ({provider}) ...")

    def one(p: Path) -> dict:
        try:
            g = models.tag_garment(Image.open(p), provider)
            return {"file": p.name, **g.model_dump()}
        except Exception as e:  # keep going; the spike wants to see failure rates
            return {"file": p.name, "error": f"{type(e).__name__}: {e}"}

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(one, cutouts))
    (run_dir / "wardrobe.json").write_text(json.dumps(rows, indent=2))
    write_summary(run_dir)
    good = [r for r in rows if r.get("is_garment")]
    print(f"  garments: {len(good)}/{len(rows)}  errors: {sum('error' in r for r in rows)}")


# ---------------------------------------------------------------- render


def _pick_test_garment(run_dir: Path) -> Path:
    """Prefer a patterned or logo'd item: that's what generative try-on usually breaks."""
    wardrobe = run_dir / "wardrobe.json"
    if wardrobe.exists():
        rows = [r for r in json.loads(wardrobe.read_text()) if r.get("is_garment")]
        rows.sort(key=lambda r: (
            r.get("pattern") == "solid" and r.get("distinctive_details", "none") == "none",
            -r.get("confidence", 0),
        ))
        if rows:
            return run_dir / "cutouts" / rows[0]["file"]
    first = next(iter(sorted((run_dir / "cutouts").glob("*.png"))), None)
    if not first:
        raise SystemExit("No cutouts to render.")
    return first


def cmd_render(args: argparse.Namespace) -> None:
    run_dir = Path(args.run)
    person = media.load_image(Path(args.person), max_edge=1536)
    garment_paths = [Path(g) for g in args.garment] if args.garment else [_pick_test_garment(run_dir)]
    garments = [Image.open(p) for p in garment_paths]
    print(f"Rendering with: {', '.join(p.name for p in garment_paths)}")

    models.save(media.flat_lay(garments), run_dir / "flatlay.png")
    img, status = models.render_outfit(person, garments)
    result = {"garments": [p.name for p in garment_paths], "status": status, "fidelity": []}
    if img is not None:
        models.save(img, run_dir / "render.png")
        for p, g in zip(garment_paths, garments):
            check = models.judge_fidelity(g, img, person)
            result["fidelity"].append({"garment": p.name, **check.model_dump()})
    (run_dir / "render_report.json").write_text(json.dumps(result, indent=2))
    write_summary(run_dir)
    print(f"  render: {status}")


# ---------------------------------------------------------------- summary


def _verdict(ok: bool | None) -> str:
    return {True: "PASS", False: "FAIL", None: "NOT RUN"}[ok]


def write_summary(run_dir: Path) -> None:
    seg = run_dir / "segment_report.json"
    tag = run_dir / "wardrobe.json"
    ren = run_dir / "render_report.json"
    lines = [f"# Spike results: {run_dir.name}", ""]

    q1 = q2 = q3 = None
    if seg.exists():
        s = json.loads(seg.read_text())
        found, expected = s["unique_garments_estimate"], s["expected_garments"]
        capped = [p["prompt"] for p in s["prompts"] if p["hit_16_object_cap"]]
        flicker = sum(t["flicker"] for t in s["tracks"])
        lines += [
            "## 1. Does segmentation hold up?",
            f"- Unique garments found: **{found}**" + (f" (you said there are {expected})" if expected else ""),
            f"- Tracks per prompt: " + ", ".join(f"{p['prompt']}={p['tracks']}" for p in s["prompts"]),
            f"- Prompts that hit SAM's 16-objects-per-frame cap: {capped or 'none'}",
            f"- Mask placement mode(s): {s['mask_modes_seen']}  (check contact_sheet.png looks right)",
            f"- SAM frame size {s['sam_frame_size']} vs local {s['local_frame_size']}",
        ]
        if expected:
            q1 = found >= 0.7 * expected and not capped
        lines += ["", "## 2. Does it double-count?",
                  f"- Same garment matched by two prompts: **{len(s['cross_prompt_duplicates'])}** pairs (merged in the estimate)",
                  f"- Flicker tracks (< {MIN_TRACK_FRAMES} frames): {flicker}"]
        if expected:
            q2 = found <= 1.2 * expected
        lines.append("")

    if tag.exists():
        rows = json.loads(tag.read_text())
        good = [r for r in rows if r.get("is_garment")]
        lines += ["## Tagging",
                  f"- {len(good)}/{len(rows)} cutouts tagged as real garments; "
                  f"{sum('error' in r for r in rows)} errors",
                  f"- Not-a-garment cutouts are segmentation noise: {len(rows) - len(good)}", ""]

    if ren.exists():
        r = json.loads(ren.read_text())
        lines += ["## 3. Does the try-on stay faithful?", f"- Muse Image status: **{r['status']}**"]
        for f in r["fidelity"]:
            lines.append(
                f"- {f['garment']}: color {f['color_preserved']}/5, pattern {f['pattern_preserved']}/5, "
                f"details {f['details_preserved']}/5, cut {f['cut_and_fit_preserved']}/5, "
                f"identity {f['person_identity_preserved']}/5. {f['differences']}"
            )
        if r["status"] != "ok":
            q3 = False
        elif r["fidelity"]:
            q3 = all(min(f["color_preserved"], f["pattern_preserved"], f["details_preserved"]) >= 4 for f in r["fidelity"])
        lines += ["- Compare render.png with flatlay.png (the always-faithful fallback).", ""]

    lines += [
        "## Verdict",
        f"- Segmentation holds up: **{_verdict(q1)}**" + ("" if q1 is not None or not seg.exists() else " (pass --expected N to grade)"),
        f"- No serious double-counting: **{_verdict(q2)}**",
        f"- Try-on is faithful: **{_verdict(q3)}** (if FAIL, ship the flat-lay as default and keep try-on optional)",
        "",
        "Kill rule: if segmentation fails on your real closet, rethink the capture flow before Day 2.",
    ]
    (run_dir / "SUMMARY.md").write_text("\n".join(lines))


# ---------------------------------------------------------------- cli


def cmd_all(args: argparse.Namespace) -> None:
    run_dir = cmd_segment(args)
    if args.dry_run:
        return
    args.run = str(run_dir)
    args.provider = None
    cmd_tag(args)
    if args.person:
        args.garment = None
        cmd_render(args)
    print(f"\nRead {run_dir / 'SUMMARY.md'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def seg_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("media", help="closet video (.mp4/.mov) or photo")
        p.add_argument("--prompts", nargs="+", help=f"noun phrases (default: {' '.join(DEFAULT_PROMPTS)})")
        p.add_argument("--expected", type=int, help="how many garments are really in the shot")
        p.add_argument("--dry-run", action="store_true", help="estimate cost only")

    p = sub.add_parser("segment", help="SAM 3.1 -> cutouts + duplicate report")
    seg_args(p)
    p.set_defaults(fn=cmd_segment)

    p = sub.add_parser("tag", help="Muse Spark structured tags for each cutout")
    p.add_argument("run", help="out/<run> folder from `segment`")
    p.add_argument("--provider", choices=["meta", "baseten"])
    p.set_defaults(fn=cmd_tag)

    p = sub.add_parser("render", help="Muse Image try-on + fidelity check + flat-lay")
    p.add_argument("run", help="out/<run> folder")
    p.add_argument("--person", required=True, help="plain front-facing photo of you")
    p.add_argument("--garment", nargs="+", help="cutout PNGs (default: most patterned one)")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("all", help="segment -> tag -> render")
    seg_args(p)
    p.add_argument("--person", help="photo of you, to run the render test")
    p.set_defaults(fn=cmd_all)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
