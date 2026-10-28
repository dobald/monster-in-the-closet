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


def store_has(c: TestClient, item_id: str) -> bool:
    return c.get(f"/api/wardrobe/{item_id}").status_code == 200


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

        # Gap finder (rules in fixture mode) and the thrift list.
        gaps = c.post("/api/gaps").json()
        assert gaps["source"] == "rules" and gaps["pieces"], gaps
        coat = gaps["pieces"][0]
        assert coat["category"] == "outerwear" and coat["outfits_unlocked"] == 1 and len(coat["pairs"]) == 2, coat
        # Example photos: fixture mode never generates; an existing one rides along with the piece.
        ex = c.post("/api/thrift/example", json={"name": coat["name"], "colors": coat["colors"], "category": coat["category"]}).json()
        assert ex["url"] is None and "live mode" in ex["reason"], ex
        examples = main.app.state.examples
        Image.new("RGB", (30, 20), "olive").save(examples.dir / f"{examples.key(coat)}.jpg")
        coat = c.post("/api/gaps").json()["pieces"][0]
        assert coat["example_url"] and c.get(coat["example_url"]).status_code == 200, coat
        assert c.get("/api/examples/..%2Fwardrobe.jpg").status_code == 404
        from server.examples import example_prompt
        prompt = example_prompt({"name": "Camel wool overcoat", "colors": ["camel"], "category": "outerwear"})
        assert "camel camel" not in prompt.lower() and "no logos" in prompt and "second-hand" in prompt, prompt

        tid = c.post("/api/thrift", json={"piece": coat}).json()["id"]
        assert c.post("/api/thrift", json={"piece": coat}).json()["id"] == tid, "re-adding updates, no duplicate"
        listed = c.get("/api/thrift").json()
        assert [t["name"] for t in listed] == [coat["name"]] and listed[0]["piece"]["pairs"], listed
        assert c.patch(f"/api/thrift/{tid}", json={"status": "found"}).status_code == 204
        assert c.get("/api/thrift").json()[0]["status"] == "found"
        assert c.patch(f"/api/thrift/{tid}", json={"status": "lost"}).status_code == 422
        c.post("/api/thrift", json={"piece": coat, "status": "dismissed"})
        assert c.get("/api/thrift").json() == [], "dismissed pieces are hidden from the list"
        again = c.post("/api/gaps").json()["pieces"]
        assert coat["name"] not in [p["name"] for p in again], "a dismissed piece is not suggested again"
        assert c.delete(f"/api/thrift/{tid}").status_code == 204

        # Try-on in fixture mode: setup rules, flat-lay fallback, cached renders, photo privacy.
        tryon = main.app.state.tryon
        assert c.get("/api/tryon/profile").json() == {"mode": "mannequin", "body": None, "ready": False, "photo": None}
        assert c.post("/api/tryon", json={"plan_id": plan["id"], "look": 0}).status_code == 409, "not set up yet"
        assert c.put("/api/tryon/profile", json={"mode": "mannequin"}).status_code == 422, "a mannequin needs details"
        assert c.put("/api/tryon/profile", json={"mode": "mannequin", "body": {"height_cm": 300}}).status_code == 422
        body = {"height_cm": 172, "build": "regular", "silhouette": "neutral", "skin_tone": 4}
        assert c.put("/api/tryon/profile", json={"mode": "mannequin", "body": body}).json()["ready"]
        job = c.post("/api/tryon", json={"plan_id": plan["id"], "look": 0}).json()
        assert job["status"] == "done" and job["render_url"] is None and "live mode" in job["note"], job
        assert c.get(job["flatlay_url"]).status_code == 200, "the flat-lay always exists"
        assert c.post("/api/tryon", json={"plan_id": plan["id"], "look": 7}).status_code == 422

        # A cached render (as live mode would record it) is served in fixture mode with its score.
        look_ids = [i for i in plan["looks"][0]["item_ids"] if store_has(c, i)]
        key = tryon._key(look_ids, tryon.profile())
        Image.new("RGB", (20, 40), "grey").save(tryon.render_dir / f"{key}.png")
        tryon.cache.put("renders", key, {"file": f"{key}.png", "photo_sha": None, "score": 5, "attempts": 1,
                                         "differences": [], "seconds": 40.0})
        job = c.post("/api/tryon", json={"plan_id": plan["id"], "look": 0}).json()
        assert job["cached"] and job["score"] == 5 and c.get(job["render_url"]).status_code == 200, job

        # The face version: consent first, and checking a photo needs live mode.
        jpg = photo_bytes(9)
        r = c.post("/api/tryon/photo", files={"photo": ("me.jpg", jpg, "image/jpeg")}, data={"consent": "false"})
        assert r.status_code == 422, r.text
        r = c.post("/api/tryon/photo", files={"photo": ("me.jpg", jpg, "image/jpeg")}, data={"consent": "true"})
        assert r.status_code == 409 and "live mode" in r.json()["detail"], r.text
        assert c.put("/api/tryon/profile", json={"mode": "photo"}).status_code == 422, "no photo on file"
        # Simulate a checked photo with one render made from it; deleting the photo deletes that render too.
        tryon.photo_path.write_bytes(jpg)
        prof = tryon.profile()
        prof["photo"] = {"sha": "abc123", "advice": "Looks good.", "checked_at": "2026-10-28T00:00:00+00:00"}
        tryon.store.put_setting("tryon", prof)
        (tryon.render_dir / "facerender.png").write_bytes(b"x")
        tryon.cache.put("renders", "facekey", {"file": "facerender.png", "photo_sha": "abc123", "score": 4,
                                               "attempts": 1, "differences": [], "seconds": 30.0})
        assert c.put("/api/tryon/profile", json={"mode": "photo"}).json()["mode"] == "photo"
        assert c.delete("/api/tryon/photo").json() == {"renders_deleted": 1}
        assert not tryon.photo_path.exists() and not (tryon.render_dir / "facerender.png").exists()
        p = c.get("/api/tryon/profile").json()
        assert p["mode"] == "mannequin" and p["photo"] is None, p
        assert c.get(f"/api/renders/{key}.png").status_code == 200, "mannequin renders are kept"

        # Layered try-on: fixture mode reports what exists and never generates.
        layers = main.app.state.layers
        ids = plan["looks"][0]["item_ids"]
        st = c.post("/api/tryon/layers", json={"item_ids": ids}).json()
        assert st["base"]["state"] == "missing" and not st["live"] and st["note"], st
        assert {l["state"] for l in st["layers"]} == {"missing"} and not layers._tasks, "fixture mode must not start renders"
        assert c.get("/api/tryon/flatlay", params={"plan_id": plan["id"], "look": 0}).json()["url"].startswith("/api/renders/flat-")
        # Simulate what live mode records: a base and a layer for the top.
        bk = st["base_key"]
        (layers.root / bk).mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (100, 200), "tan").save(layers.root / bk / "base.png")
        layers._put_meta(bk, "base", {"status": "ready", "size": [100, 200]})
        top_id = next(l["item_id"] for l in st["layers"] if l["category"] == "top")
        Image.new("RGBA", (40, 50), (90, 90, 90, 255)).save(layers.root / bk / f"{top_id}.png")
        layers._put_meta(bk, top_id, {"status": "ready", "box": [30, 40, 40, 50], "size": [100, 200]})
        st = c.post("/api/tryon/layers", json={"item_ids": ids, "prepare": False}).json()
        top = next(l for l in st["layers"] if l["item_id"] == top_id)
        assert st["base"]["state"] == "ready" and top["state"] == "ready" and top["box"] == [30, 40, 40, 50] and top["order"] == 2, st
        assert c.get(top["url"]).status_code == 200 and c.get(st["base"]["url"]).status_code == 200
        assert c.get(f"/api/layers/{bk}/..%2Fbase.png").status_code == 404
        # Changing the body makes a new base key: layers belong to one mannequin.
        c.put("/api/tryon/profile", json={"mode": "mannequin", "body": {**body, "skin_tone": 6}})
        assert c.post("/api/tryon/layers", json={"item_ids": ids}).json()["base_key"] != bk
        assert c.put("/api/tryon/profile", json={"mode": "flat"}).status_code == 200
        assert c.post("/api/tryon/layers", json={"item_ids": ids}).status_code == 409, "layers are mannequin-only"


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


def test_gap_math() -> None:
    """The +N outfits number is counted, not trusted; model output is cleaned before it reaches the app."""
    from closet import gaps
    from closet.schema import GapPiece, GapReport
    items = _items_for_planner()  # aaa: top, bbb: bottom
    items += [{**items[0], "id": "ccc"}, {**items[1], "id": "ddd"}]  # 2 tops, 2 bottoms
    assert gaps.outfits_unlocked("outerwear", ["aaa", "bbb", "ccc", "ddd"], items) == 4
    assert gaps.outfits_unlocked("top", ["bbb", "ddd", "aaa"], items) == 2
    assert gaps.outfits_unlocked("bottom", ["aaa"], items) == 1

    def piece(**kw):
        base = dict(name="Wool coat", category="outerwear", colors=["camel"], pairs_with=["aaa", "bbb"], why="",
                    look_for="", price_range="$30-80", search_terms=["wool coat second hand"])
        return GapPiece(**{**base, **kw})
    report = GapReport(summary="", pieces=[
        piece(name="outerwear — mid-weight wool shacket in oatmeal or grey", pairs_with=["aaa", "bbb", "ccc", "ddd"]),
        piece(name="Invented", category="top", pairs_with=["zzz", "yyy"]),  # no real ids -> dropped
        piece(name="Oxford shirt", category="top", pairs_with=["bbb", "ddd"], price_range="2"),
    ])
    out = gaps.clean_report(report, items)
    assert [p["name"] for p in out] == ["Mid-weight wool shacket", "Oxford shirt"], out
    assert out[0]["outfits_unlocked"] == 4 and out[1]["outfits_unlocked"] == 2
    assert out[1]["price_range"] == "", "a price without a range is dropped, not shown"
    assert out[0]["search_terms"] == ["wool coat"]


def test_getting_started(var_dir: Path, run_dir: Path) -> None:
    """Fixture mode: the profile drives onboarding, location and the calendar the planner reads."""
    from datetime import date as d, timedelta
    with client_for("fixture", var_dir) as c:
        p = c.get("/api/profile").json()
        assert not p["onboarded"] and p["calendar"] == "sample" and not p["can_plan"] and p["wardrobe"] == {}, p
        c.post("/api/dev/seed", json={"run": str(run_dir.relative_to(config.ROOT))})
        assert c.get("/api/profile").json()["can_plan"], "a top and a bottom are enough to plan"

        loc = {"name": "Osaka, Japan", "lat": 34.69, "lon": 135.5}
        assert c.put("/api/profile", json={"location": loc}).json()["location"] == loc
        assert main.app.state.planning.location() == (34.69, 135.5)
        assert c.put("/api/profile", json={"calendar": "ics"}).status_code == 422, "no file uploaded yet"

        today = d.today().strftime("%Y%m%d")
        ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART:" + today + "T150000\r\nDTEND:" + today + "T160000\r\n"
               "SUMMARY:Portfolio review\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        r = c.post("/api/profile/calendar", files={"file": ("work.ics", ics.encode(), "text/calendar")})
        assert r.status_code == 200 and r.json()["events"] == 1 and r.json()["today"][0]["title"] == "Portfolio review", r.text
        assert c.post("/api/profile/calendar", files={"file": ("x.ics", b"not a calendar", "text/calendar")}).status_code == 422
        plan = c.post("/api/plan", json={}).json()
        assert [e["title"] for e in plan["calendar"]["events"]] == ["Portfolio review"], plan["calendar"]
        assert c.delete("/api/profile/calendar").json()["calendar"] == "none"
        assert c.post("/api/plan", json={}).json()["calendar"]["events"] == [], "no calendar -> no events"

        assert c.post("/api/preferences", json={"text": "Add a warmer layer; I run cold."}).json() == {"new": True}
        assert c.post("/api/preferences", json={"text": "x"}).status_code == 422
        assert c.get("/api/geocode", params={"q": "a"}).json() == [], "too short to search"
        assert c.put("/api/profile", json={"onboarded": True}).json()["onboarded"]
        assert c.get("/api/profile").json()["onboarded_at"]

        # Fixture-mode plans carry a rule-picker trace too.
        kinds = [s["kind"] for s in c.post("/api/plan", json={}).json()["trace"]["steps"]]
        assert kinds == ["context", "tool", "tool", "rules", "check", "done"], kinds

        # Wear-history backfill: estimates make forgotten clothes visible from day one.
        items = {i["tags"]["category"]: i for i in c.get("/api/wardrobe").json()}
        top, bottom = items["top"], items["bottom"]
        r = c.post("/api/wardrobe/last-worn", json={"items": [{"id": top["id"], "days_ago": 135}]}).json()
        assert r[0]["worn_estimated"] and r[0]["wear_count"] == top["wear_count"], "an estimate is not a wear"
        assert r[0]["last_worn"] == (d.today() - timedelta(days=135)).isoformat(), r
        assert c.get("/api/oni").json()["forgotten"] >= 1
        plan = c.post("/api/plan", json={}).json()
        look = next(n for n, lk in enumerate(plan["looks"]) if top["id"] in lk["item_ids"])
        worn = c.post(f"/api/plans/{plan['id']}/wear", json={"look": look}).json()
        assert [x["id"] for x in worn["rescued"]] == [top["id"]] and worn["rescued"][0]["days"] == 135, worn["rescued"]
        after = c.get(f"/api/wardrobe/{top['id']}").json()
        assert not after["worn_estimated"] and after["last_worn"] == d.today().isoformat(), "a real wear replaces the estimate"
        r = c.post("/api/wardrobe/last-worn", json={"items": [{"id": top["id"], "days_ago": 300}]}).json()
        assert r[0]["last_worn"] == d.today().isoformat() and not r[0]["worn_estimated"], "an older guess never hides a logged wear"
        c.post("/api/wardrobe/last-worn", json={"items": [{"id": bottom["id"], "days_ago": 15}]})
        r = c.post("/api/wardrobe/last-worn", json={"items": [{"id": bottom["id"], "days_ago": None}]}).json()
        assert r[0]["last_worn"] in (None, d.today().isoformat()), "clearing an estimate falls back to logged wears"
        assert c.post("/api/wardrobe/last-worn", json={"items": [{"id": top["id"], "days_ago": 5000}]}).status_code == 422
        assert c.post("/api/wardrobe/last-worn", json={"items": [{"id": "nope", "days_ago": 3}]}).status_code == 404


def test_touches(var_dir: Path, run_dir: Path) -> None:
    """Finishing touches: playbook-only picks, a mix of kinds, owned basics from the user's checklist."""
    from closet import styling
    from closet.schema import TouchSet
    with client_for("fixture", var_dir) as c:
        c.post("/api/dev/seed", json={"run": str(run_dir.relative_to(config.ROOT))})
        plan = c.post("/api/plan", json={}).json()
        r = c.get(f"/api/plans/{plan['id']}/touches", params={"look": 0}).json()
        ts = r["touches"]
        assert r["source"] == "rules" and 1 <= len(ts) <= 3, r
        assert r["colour"]["summary"] and len(r["colour"]["palette"]) == len(plan["looks"][0]["item_ids"]), r["colour"]
        assert sum(t["kind"] == "colour" for t in ts) <= 1
        assert r["recall"] and "scan it in" in r["recall"]["text"].lower(), r["recall"]
        c.put("/api/style", json={"skip": [r["recall"]["id"]]})
        r2 = c.get(f"/api/plans/{plan['id']}/touches", params={"look": 0}).json()
        assert (r2["recall"] or {}).get("id") != r["recall"]["id"], "'I don't have one' stops that prompt"
        c.put("/api/style", json={"skip": []})
        assert all(t["play"] in styling.PLAYS for t in ts)
        kinds = [t["kind"] for t in ts]
        assert kinds.count("underlayer") <= 1 and kinds.count("technique") <= 1 and kinds.count("accessory") <= 2, kinds
        assert all(t["owned"] == (not t["needs"]) for t in ts), "nothing ticked yet: only techniques count as owned"
        assert c.get(f"/api/plans/{plan['id']}/touches", params={"look": 9}).status_code == 422
        assert c.get("/api/plans/nope/touches").status_code == 404

        st = c.put("/api/style", json={"basics": ["white_tee", "button_up", "silver_rings", "made_up"]}).json()
        assert st["basics"] == ["button_up", "silver_rings", "white_tee"] and st["catalog"][0]["group"] == "Underlayers", st
        ts = c.get(f"/api/plans/{plan['id']}/touches", params={"look": 0}).json()["touches"]
        # The demo calendar has a smart-casual crit, so the rules put a collar under the crewneck.
        layer = next(t for t in ts if t["kind"] == "underlayer")
        assert layer["owned"] and layer["owned_label"] in ("Button-up shirt", "Plain white tee"), ts
        first_play = ts[0]["play"]
        c.put("/api/style", json={"skip": [first_play, "not_a_play"]})
        assert c.get("/api/style").json()["skip"] == [first_play]
        assert first_play not in [t["play"] for t in c.get(f"/api/plans/{plan['id']}/touches", params={"look": 0}).json()["touches"]]

    # clean(): invented plays dropped, one underlayer at most, owned first once anything is ticked.
    picked = TouchSet(touches=[
        {"playbook_id": "made_up", "item": "", "suggestion": "x", "why": "y"},
        {"playbook_id": "watch", "item": "watch", "suggestion": "Add a watch.", "why": "Polished."},
        {"playbook_id": "hem_peek", "item": "white tee", "suggestion": "Tee peeks out.", "why": "Clean line."},
        {"playbook_id": "collar_peek", "item": "shirt", "suggestion": "Collar out.", "why": "Smart."},
        {"playbook_id": "rings", "item": "rings", "suggestion": "Silver rings.", "why": "Cool tones."},
    ])
    out = styling.clean(picked, owned={"silver_rings"}, skip=set())
    assert [t["play"] for t in out] == ["rings", "watch", "hem_peek"], out
    assert out[0]["owned"] and out[0]["owned_label"] == "Silver rings" and not out[1]["owned"]


def test_colour_and_recall(var_dir: Path) -> None:
    """The colour read classifies measured colours; "Got one?" asks for core pieces the closet has none of."""
    from closet import colour, styling
    var_dir.mkdir(parents=True, exist_ok=True)

    def item(iid: str, rgb: tuple[int, int, int], name: str, cat: str = "top", pattern: str = "solid", subtype: str = "tee") -> dict:
        cutout_png(rgb).save(var_dir / f"{iid}.png")
        return {"id": iid, "tags": {**GARMENT, "primary_color": name, "category": cat, "pattern": pattern, "subtype": subtype}}

    dark = colour.read([item("d1", (20, 20, 22), "black"), item("d2", (40, 30, 32), "dark brown", "bottom")], var_dir)
    assert dark["idea_play"] == "light_break" and dark["contrast"] == "low", dark
    neutral = colour.read([item("n1", (225, 222, 215), "white"), item("n2", (60, 67, 78), "blue", "bottom")], var_dir)
    assert neutral["scheme"] == "all neutral" and neutral["contrast"] == "high" and neutral["idea_play"] == "accent_pop", neutral
    printed = colour.read([item("p1", (200, 200, 195), "white", pattern="graphic"), item("p2", (70, 70, 67), "charcoal", "bottom")], var_dir)
    assert printed["idea_play"] == "colour_echo", printed
    clash = colour.read([item("c1", (200, 40, 40), "red"), item("c2", (40, 160, 170), "teal", "bottom")], var_dir)
    assert clash["scheme"] == "complementary" and not any(p["neutral"] for p in clash["palette"]), clash
    accent = colour.read([item("a1", (200, 60, 40), "rust"), item("a2", (30, 30, 30), "black", "bottom")], var_dir)
    assert accent["scheme"] == "neutral + accent" and accent["idea_play"] == "bookend", accent

    closet = [{"id": "x", "tags": {**GARMENT, "category": "top", "subtype": "henley t-shirt"}},
              {"id": "y", "tags": {**GARMENT, "category": "bottom", "subtype": "wide-leg jeans"}}]
    assert styling.recall_for(closet, cold=True, smart=False, skip=set()).id == "rec_jacket"
    assert styling.recall_for(closet, cold=False, smart=False, skip=set()).id == "rec_knit", "no jacket prompt on a warm day"
    assert styling.recall_for(closet, cold=True, smart=False, skip={"rec_jacket"}).id == "rec_knit"
    assert styling.recall_for(closet, cold=True, smart=True, skip=set(), look_index=1).id != "rec_jacket", "looks rotate"
    assert all(r.id != "rec_jeans" for r in [styling.recall_for(closet, True, True, set(), n) for n in range(6)]), "owns jeans"


def test_cut_layer() -> None:
    """A layer is cropped to its garment, and its box says where it sits on the base."""
    import numpy as np
    from server.layers import cut_layer
    dressed = Image.new("RGB", (200, 400), "white")
    mask = np.zeros((400, 200), dtype=bool)
    mask[100:250, 50:150] = True
    layer, (x, y, w, h) = cut_layer(dressed, mask)
    assert layer.mode == "RGBA" and layer.size == (w, h)
    assert 45 <= x <= 50 and 95 <= y <= 100 and 100 <= w <= 110 and 150 <= h <= 160, (x, y, w, h)
    assert layer.getpixel((w // 2, h // 2))[3] == 255 and layer.getpixel((0, 0))[3] < 40, "soft edge, solid middle"


def test_agent_loop_and_repair() -> None:
    """plan_with_agent with a scripted client: it must call tools, then repair an invented id."""
    from types import SimpleNamespace as NS
    from datetime import date as d, timedelta
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
    # The trace the app shows, in order: both tool calls, the failed check, the repair, the passing check.
    kinds = [s["kind"] for s in trace["steps"]]
    assert kinds == ["context", "model", "tool", "tool", "model", "model", "check", "repair", "model", "check", "done"], kinds
    checks = [s for s in trace["steps"] if s["kind"] == "check"]
    assert checks[0]["ok"] is False and "not in the wardrobe" in checks[0]["detail"] and checks[1]["ok"] is True, checks
    assert [s["label"] for s in trace["steps"] if s["kind"] == "tool"] == ["get_weather()", "get_calendar()"]
    assert all(s.get("thought") is None for s in trace["steps"]), "the fake client returns no reasoning"
    from closet.planner import tool_summary
    assert tool_summary("get_calendar", {"events": []}) == "No events today"
    assert "feels like -2°" in tool_summary("get_weather", {"parts": {"morning": {"temp_c": [2, 8], "feels_like_low_c": -2,
                                                                                    "rain_chance_pct": 5, "sky": "clear"}}})


def test_duplicates(var_dir: Path) -> None:
    """Cross-photo duplicates with a scripted judge: confident pairs merge (wear history and aliases
    follow), unsure pairs go to review, and a pair the user calls different is never re-asked."""
    from closet import dedupe as cdedupe
    from closet.schema import Garment, SameGarment

    run_dir = config.ROOT / "out" / f"_test_dupes_{var_dir.name}"
    (run_dir / "cutouts").mkdir(parents=True)
    rows = []
    # a_big and a_small: one black sweatshirt shot twice (the bigger shot should win); b: a charcoal one, close enough in colour to be shortlisted.
    for name, color, size in [("a_big.png", (20, 20, 20), (200, 220)), ("a_small.png", (24, 23, 22), (90, 100)),
                              ("b.png", (34, 34, 40), (150, 160))]:
        cutout_png(color, size).save(run_dir / "cutouts" / name)
        rows.append({"file": name, **GARMENT})
    (run_dir / "wardrobe.json").write_text(json.dumps(rows))

    calls = []
    verdicts = {}  # frozenset of ids -> SameGarment

    def fake_judge(a_img, b_img, a_tags, b_tags):
        key = frozenset((a_img.size, b_img.size))
        calls.append(key)
        return verdicts.get(key, SameGarment(matching_details="none", conflicting_details="colour", same_item=False, confidence=0.97))

    orig = cdedupe.judge_same
    cdedupe.judge_same = fake_judge
    try:
        with client_for("live", var_dir) as c:
            c.post("/api/dev/seed", json={"run": str(run_dir.relative_to(config.ROOT))})
            items = {i["source"]: i for i in c.get("/api/wardrobe").json()}
            big, small, b = items["a_big.png"], items["a_small.png"], items["b.png"]
            store = main.app.state.store
            store.record_wear("2026-10-20", [small["id"]], None, None)

            verdicts[frozenset(((200, 220), (90, 100)))] = SameGarment(
                matching_details="same chest logo", conflicting_details="none", same_item=True, confidence=0.93)
            verdicts[frozenset(((200, 220), (150, 160)))] = SameGarment(
                matching_details="same cut", conflicting_details="maybe colour", same_item=True, confidence=0.6)
            r = c.post("/api/wardrobe/duplicates/check").json()
            assert [m["kept"]["id"] for m in r["merged"]] == [big["id"]] and r["merged"][0]["dropped_id"] == small["id"], r
            kept = c.get(f"/api/wardrobe/{big['id']}").json()
            assert kept["wear_count"] == 1 and kept["last_worn"] == "2026-10-20", "wear history follows the merge"
            assert c.get(f"/api/wardrobe/{small['id']}").json()["id"] == big["id"], "old ids resolve to the kept item"
            assert len(c.get("/api/wardrobe").json()) == 2
            assert store.upsert_item(small["id"], "rescan", "x", None, Garment.model_validate(GARMENT), None) == big["id"]
            assert len(c.get("/api/wardrobe").json()) == 2, "rescanning a merged cutout must not bring it back"

            assert len(r["review"]) == 1 and {r["review"][0]["a"]["id"], r["review"][0]["b"]["id"]} == {big["id"], b["id"]}, r
            n = len(calls)
            assert c.post("/api/wardrobe/duplicates/check").json()["review"], "unsure pair stays in review"
            assert len(calls) == n, "verdicts are cached per pair"
            assert c.post("/api/wardrobe/duplicates/distinct", json={"a": b["id"], "b": big["id"]}).status_code == 204
            r = c.post("/api/wardrobe/duplicates/check").json()
            assert r["review"] == [] and r["checked"] == 0, r

            r = c.post("/api/wardrobe/duplicates/merge", json={"a": b["id"], "b": big["id"]})
            assert r.status_code == 200 and len(c.get("/api/wardrobe").json()) == 1, r.text
    finally:
        cdedupe.judge_same = orig
        shutil.rmtree(run_dir, ignore_errors=True)


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
        test_getting_started(tmp / "start", run_dir)
        test_touches(tmp / "touches", run_dir)
        test_colour_and_recall(tmp / "colour")
        test_validate_plan()
        test_gap_math()
        test_cut_layer()
        test_agent_loop_and_repair()
        test_duplicates(tmp / "dupes")
        print("OK: fixture mode, seeding, tag fixes, caching, dedupe, planning, wear, check-ins, the agent loop, gap finder, try-on, layered try-on, getting started, finishing touches, colour reads "
              "and cross-photo duplicates all behave.")
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main_()
