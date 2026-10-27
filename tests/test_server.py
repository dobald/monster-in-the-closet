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


BOTTOM = {**GARMENT, "category": "bottom", "subtype": "wide-leg jeans", "primary_color": "indigo",
          "fit": "wide-leg, loose", "print_side": "unknown", "distinctive_details": "none"}


def test_plan_wear_checkin(var_dir: Path, run_dir: Path) -> None:
    """Fixture mode: rules planner, wearing a look, a check-in that learns, the oni's mood."""
    # Make the seeded wardrobe a real outfit: one top, one bottom.
    rows = json.loads((run_dir / "wardrobe.json").read_text())
    rows[1] = {"file": rows[1]["file"], **BOTTOM}
    (run_dir / "wardrobe.json").write_text(json.dumps(rows))
    with client_for("fixture", var_dir) as c:
        assert c.post("/api/plan", json={}).status_code == 409, "empty wardrobe -> clear error"
        c.post("/api/dev/seed", json={"run": str(run_dir.relative_to(config.ROOT))})

        plan = c.post("/api/plan", json={"day": "2026-10-28", "notes": "nothing too warm"}).json()
        assert plan["source"] == "rules" and len(plan["looks"]) == 3, plan
        assert all(len(l["items"]) >= 2 for l in plan["looks"]), plan["looks"]
        assert {i["tags"]["category"] for i in plan["looks"][0]["items"]} >= {"top", "bottom"}
        assert c.get("/api/plan", params={"day": "2026-10-28"}).json()["id"] == plan["id"]

        worn = c.post(f"/api/plans/{plan['id']}/wear", json={"look": 0, "day": "2026-10-28"}).json()
        assert worn["closet_alive_after"] == 100 and worn["streak_days"] == 1, worn
        assert worn["rescued"] == [], "items added today can't be rescued"
        assert c.post(f"/api/plans/{plan['id']}/wear", json={"look": 9}).status_code == 422
        item = c.get(f"/api/wardrobe/{worn['look']['item_ids'][0]}").json()
        assert item["wear_count"] == 1 and item["last_worn"] == "2026-10-28", item

        ci = c.post("/api/checkins", json={"day": "2026-10-28", "temperature": "cold", "feeling": "good",
                                           "tags": ["compliments"]}).json()
        assert ci["oni_reply"] and ci["new_preference"] and set(ci["worn_item_ids"]) == set(worn["look"]["item_ids"]), ci
        again = c.post("/api/checkins", json={"day": "2026-10-28", "temperature": "cold", "feeling": "good"}).json()
        assert not again["new_preference"], "the same preference must not be stored twice"
        prefs = c.get("/api/preferences").json()
        assert len(prefs) == 1 and "cold" in prefs[0]["text"], prefs
        assert c.post("/api/checkins", json={"temperature": "freezing", "feeling": "good"}).status_code == 422

        oni = c.get("/api/oni", params={"day": "2026-10-28"}).json()
        assert oni["closet_alive_pct"] == 100 and oni["garments"] == 2, oni
        assert c.delete(f"/api/preferences/{prefs[0]['id']}").status_code == 204


def _items_for_planner() -> list[dict]:
    from closet.schema import Garment
    top = Garment.model_validate(GARMENT).model_dump()
    bottom = Garment.model_validate(BOTTOM).model_dump()
    return [{"id": "aaa", "tags": top, "last_worn": None, "wear_count": 0},
            {"id": "bbb", "tags": bottom, "last_worn": "2026-08-01", "wear_count": 3}]


def test_validate_plan() -> None:
    from closet import planner
    from closet.schema import Look, OutfitPlan
    items = _items_for_planner()
    good = OutfitPlan(weather_summary="", plans_summary="", looks=[Look(name="a", item_ids=["aaa", "bbb"], why="", rediscovered_id="bbb")])
    assert planner.validate_plan(good, items) == []
    invented = OutfitPlan(weather_summary="", plans_summary="", looks=[Look(name="a", item_ids=["aaa", "zzz"], why="", rediscovered_id=None)])
    assert "not in the wardrobe" in planner.validate_plan(invented, items)[0]
    no_bottom = OutfitPlan(weather_summary="", plans_summary="", looks=[Look(name="a", item_ids=["aaa"], why="", rediscovered_id=None)])
    assert "needs a top and a bottom" in planner.validate_plan(no_bottom, items)[0]
    samey = OutfitPlan(weather_summary="", plans_summary="", looks=[Look(name="a", item_ids=["aaa", "bbb"], why="", rediscovered_id=None)] * 3)
    assert planner.variety_problems(samey, items) == []  # only one top and one bottom owned: repeating is fine
    second_top = {**items[0], "id": "ccc"}
    assert "same top" in planner.variety_problems(samey, items + [second_top])[0]


def test_agent_loop_and_repair() -> None:
    """plan_with_agent with a scripted client: it must call tools, then repair an invented id."""
    from types import SimpleNamespace as NS
    from datetime import date as d
    from closet import planner
    from closet.schema import Look, OutfitPlan

    usage = NS(prompt_tokens=100, completion_tokens=50)
    tool_round = NS(choices=[NS(message=NS(content="", tool_calls=[
        NS(id="t1", function=NS(name="get_weather", arguments="{}")),
        NS(id="t2", function=NS(name="get_calendar", arguments="{}"))]))], usage=usage)
    done_round = NS(choices=[NS(message=NS(content="ready", tool_calls=None))], usage=usage)
    bad = OutfitPlan(weather_summary="w", plans_summary="p", looks=[Look(name="x", item_ids=["aaa", "nope"], why="", rediscovered_id=None)])
    good = OutfitPlan(weather_summary="w", plans_summary="p", looks=[Look(name="x", item_ids=["aaa", "bbb"], why="ok", rediscovered_id="bbb")] * 3)
    creates, parses = iter([tool_round, done_round]), iter([bad, good])
    seen = {"tools": 0}

    class FakeCompletions:
        def create(self, **kw):
            assert kw["tools"] and kw["reasoning_effort"] == "medium"
            return next(creates)

        def parse(self, **kw):
            return NS(choices=[NS(message=NS(parsed=next(parses)))], usage=usage)

    fake = NS(chat=NS(completions=FakeCompletions()))
    orig = planner.config.client_for
    planner.config.client_for = lambda provider="meta": fake
    try:
        def tool(name):
            def fn():
                seen["tools"] += 1
                return {"tool": name}
            return fn
        plan, trace = planner.plan_with_agent(_items_for_planner(), [], d(2026, 10, 28), "",
                                              {"get_weather": tool("w"), "get_calendar": tool("c")}, "baseten")
    finally:
        planner.config.client_for = orig
    assert seen["tools"] == 2 and trace["tool_calls"] == ["get_weather", "get_calendar"], trace
    assert trace["repairs"] == 1 and plan.looks[0].item_ids == ["aaa", "bbb"], (trace, plan)
    assert trace["tokens_in"] == 400 and trace["tokens_out"] == 200, trace


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
        test_plan_wear_checkin(tmp / "plan", run_dir)
        test_validate_plan()
        test_agent_loop_and_repair()
        print("OK: fixture mode, seeding, tag fixes, caching, dedupe, planning, wear, check-ins and the agent loop all behave.")
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main_()
