"""Tagging bake-off: Muse Spark Open (Baseten) vs Muse Spark 1.3 (Meta) on the same cutouts.

Run: python spike/compare_tags.py out/<run>
Writes wardrobe_meta.json, wardrobe_baseten.json and tag_comparison.json in the run folder.
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from closet import models  # noqa: E402

FIELDS = ["is_garment", "category", "pattern", "formality"]


def tag_all(cutouts: list[Path], provider: str) -> tuple[list[dict], float]:
    def one(p: Path) -> dict:
        t = time.time()
        try:
            g = models.tag_garment(Image.open(p), provider)
            return {"file": p.name, "seconds": round(time.time() - t, 2), **g.model_dump()}
        except Exception as e:
            return {"file": p.name, "error": f"{type(e).__name__}: {e}"[:300]}

    start = time.time()
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(one, cutouts))
    return rows, time.time() - start


def main() -> None:
    run = Path(sys.argv[1])
    cutouts = sorted((run / "cutouts").glob("*.png"))
    results = {}
    for provider in ("baseten", "meta"):
        rows, wall = tag_all(cutouts, provider)
        (run / f"wardrobe_{provider}.json").write_text(json.dumps(rows, indent=2))
        ok = [r for r in rows if "error" not in r]
        results[provider] = {
            "items": len(rows),
            "errors": len(rows) - len(ok),
            "wall_seconds": round(wall, 1),
            "median_seconds": sorted(r["seconds"] for r in ok)[len(ok) // 2] if ok else None,
        }
        print(f"{provider}: {len(ok)}/{len(rows)} tagged in {wall:.1f}s")

    a = {r["file"]: r for r in json.loads((run / "wardrobe_baseten.json").read_text()) if "error" not in r}
    b = {r["file"]: r for r in json.loads((run / "wardrobe_meta.json").read_text()) if "error" not in r}
    both = sorted(set(a) & set(b))
    agree = {f: sum(a[k][f] == b[k][f] for k in both) for f in FIELDS}
    color = sum(a[k]["primary_color"].split()[-1].lower() == b[k]["primary_color"].split()[-1].lower() for k in both)
    disagreements = [
        {"file": k, **{f: [a[k][f], b[k][f]] for f in FIELDS + ["primary_color", "subtype"] if a[k][f] != b[k][f]}}
        for k in both
    ]
    summary = {
        "compared": len(both),
        "agreement": {f: f"{agree[f]}/{len(both)}" for f in FIELDS} | {"primary_color (base word)": f"{color}/{len(both)}"},
        "providers": results,
        "disagreements": [d for d in disagreements if len(d) > 1],
    }
    (run / "tag_comparison.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["agreement"], indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
