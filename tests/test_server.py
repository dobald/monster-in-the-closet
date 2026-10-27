"""Offline API tests: fixture mode, seeding, caching, tag fixes. No paid API calls.

Run: python tests/test_server.py
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from closet import config, scan  # noqa: E402
from server import main  # noqa: E402

GARMENT = {
    "is_garment": True, "category": "top", "subtype": "crewneck sweatshirt", "primary_color": "black",
    "secondary_colors": [], "pattern": "solid", "material_guess": "cotton fleece", "warmth": 3,
    "formality": "casual", "seasons": ["fall", "winter"], "fit": "relaxed cropped",
    "distinctive_details": "small chest logo", "visible_side": "front", "print_side": "front", "confidence": 0.95,
}


def cutout_png(color: tuple[int, int, int], size=(120, 140)) -> Image.Image:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle([10, 10, size[0] - 10, size[1] - 10], fill=(*color, 255))
    return img


def photo_bytes(seed: int) -> bytes:
    img = Image.new("RGB", (400, 300), (200 + seed % 50, 190, 180))
    ImageDraw.Draw(img).rectangle([50, 50, 150, 200], fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def client_for(mode: str, var_dir: Path) -> TestClient:
    os.environ["MONSTER_MODE"] = mode
    os.environ["MONSTER_VAR_DIR"] = str(var_dir)
    return TestClient(main.app)


def test_fixture_mode(var_dir: Path, run_dir: Path) -> None:
    with client_for("fixture", var_dir) as c:
        h = c.get("/api/health").json()
        assert h["mode"] == "fixture" and h["garments"] == 0, h

        r = c.post("/api/scans", files=[("photos", ("a.jpg", photo_bytes(1), "image/jpeg"))])
        assert r.status_code == 409, r.text  # nothing recorded yet: clear error, no API call

        r = c.post("/api/dev/seed", json={"run": str(run_dir.relative_to(config.ROOT))})
        assert r.status_code == 200 and r.json()["imported"] == 2 and r.json()["untagged"] == 0, r.text

        items = c.get("/api/wardrobe").json()
        assert len(items) == 2 and all(i["tags"]["subtype"] == "crewneck sweatshirt" for i in items), items

        r = c.post("/api/scans", files=[("photos", ("new.jpg", photo_bytes(2), "image/jpeg"))]).json()
        assert r["replayed"] and r["cached_photos"] == 1 and len(r["items"]) == 2, r
        assert all(i["tags"] for i in r["items"]), "tags should come from the tag fixtures"
        assert len(c.get("/api/wardrobe").json()) == 2, "replaying the same cutouts must not duplicate them"

        item_id = items[0]["id"]
        assert c.get(f"/api/cutouts/{item_id}.png").status_code == 200
        r = c.patch(f"/api/wardrobe/{item_id}", json={"primary_color": "charcoal", "fit": "boxy"})
        assert r.status_code == 200 and r.json()["user_edited"] and r.json()["tags"]["primary_color"] == "charcoal", r.text
        assert c.patch(f"/api/wardrobe/{item_id}", json={"colour": "x"}).status_code == 422
        assert c.patch(f"/api/wardrobe/{item_id}", json={"warmth": "hot"}).status_code == 422

        c.post("/api/dev/seed", json={"run": str(run_dir.relative_to(config.ROOT))})
        assert c.get(f"/api/wardrobe/{item_id}").json()["tags"]["primary_color"] == "charcoal", "re-seed kept the user's fix"

        assert c.delete(f"/api/wardrobe/{item_id}").status_code == 204
        assert c.get(f"/api/cutouts/{item_id}.png").status_code == 404
        assert c.post("/api/dev/seed", json={"run": "data"}).status_code == 422, "seed only reads under out/"


def test_live_mode_caches(var_dir: Path) -> None:
    """Live mode with the model calls stubbed: a repeated photo must not be paid for twice."""
    calls = {"scan": 0, "tag": 0}

    async def fake_scan_image(client, photo, batch, source):
        calls["scan"] += 1
        return [
            scan.ScanItem(source, batch, "0", (0, 0, 1, 1), 0.9, cutout_png((30, 40, 90))),
            scan.ScanItem(source, batch, "1", (0, 0, 1, 1), 0.92, cutout_png((200, 30, 30))),
            scan.ScanItem(source, batch, "2", (0, 0, 1, 1), 0.3, cutout_png((5, 5, 5)), kept=False, reason="low confidence"),
        ]

    def fake_tag(img, provider=None):
        from closet.schema import Garment
        calls["tag"] += 1
        return Garment.model_validate(GARMENT)

    from server import pipeline
    orig = (pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for)
    pipeline.scan.scan_image, pipeline.models.tag_garment = fake_scan_image, fake_tag
    pipeline.config.async_client_for = lambda provider="meta": None
    try:
        with client_for("live", var_dir) as c:
            files = [("photos", ("bed.jpg", photo_bytes(7), "image/jpeg")), ("photos", ("bed2.jpg", photo_bytes(8), "image/jpeg"))]
            first = c.post("/api/scans", files=files).json()
            assert first["cached_photos"] == 0 and len(first["items"]) == 2, first  # same 2 cutouts in both photos -> deduped
            assert [d["reason"] for d in first["dropped"]] == ["low confidence", "low confidence"], first["dropped"]
            assert calls == {"scan": 2, "tag": 2}, calls

            again = c.post("/api/scans", files=files[:1]).json()
            assert again["cached_photos"] == 1 and not again["replayed"], again
            assert calls == {"scan": 2, "tag": 2}, f"cache miss on a repeated photo: {calls}"
    finally:
        pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for = orig


def main_() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="monster-test-"))
    run_dir = config.ROOT / "out" / f"_test_seed_{tmp.name}"
    try:
        (run_dir / "cutouts").mkdir(parents=True)
        rows = []
        for i, color in enumerate([(20, 20, 20), (40, 60, 120)]):
            name = f"clothing_{i}_f0.png"
            cutout_png(color).save(run_dir / "cutouts" / name)
            rows.append({"file": name, **GARMENT})
        (run_dir / "wardrobe.json").write_text(json.dumps(rows))

        test_fixture_mode(tmp / "fixture", run_dir)
        test_live_mode_caches(tmp / "live")
        print("OK: fixture mode, seeding, tag fixes, caching and dedupe all behave.")
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main_()
