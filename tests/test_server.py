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

# No paid calls, ever: a dummy key and an unreachable address are set before closet.config reads
# .env (which never overrides what is already set), so a call a test forgot to stub fails at once.
for _k in ("MODEL_API_KEY", "BASETEN_API_KEY"):
    os.environ[_k] = "offline-tests"
for _k in ("MODEL_API_BASE_URL", "BASETEN_BASE_URL"):
    os.environ[_k] = "http://127.0.0.1:9/v1"

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

    def fake_tag(img, provider=None, hint="", notes=""):
        from closet.schema import Garment
        calls["tag"] += 1
        return Garment.model_validate(GARMENT)

    from server import pipeline, products as products_mod
    orig = (pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for, products_mod.models._edit)
    pipeline.scan.scan_image, pipeline.models.tag_garment = fake_scan_image, fake_tag
    pipeline.config.async_client_for = lambda provider="meta": None
    products_mod.models._edit = lambda images, prompt: (None, "stubbed: no paid calls in tests")  # the scan starts product shots
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
        pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for, products_mod.models._edit = orig


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
        assert plan["source"] == "rules" and len(plan["looks"]) == 1, "one top + one bottom is one look, not three copies"
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
        tryon = main.app.state.closets.get("main").tryon
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
        layers = main.app.state.closets.get("main").layers
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
        assert st["base"]["state"] == "ready" and top["state"] == "ready" and top["box"] == [30, 40, 40, 50] and top["order"] == 253, st  # a crewneck sweatshirt is a mid layer (closet/layering.py)
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
        assert main.app.state.closets.get("main").planning.location() == (34.69, 135.5)
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
        steps = c.post("/api/plan", json={}).json()["trace"]["steps"]
        kinds = [s["kind"] for s in steps]
        assert kinds[:5] == ["context", "tool", "tool", "rules", "check"] and kinds[-1] == "done", kinds
        assert any(s["label"] == "taste_model()" for s in steps), "the taste model shows in the trace"

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
        assert all("example_url" in t for t in r["touches"]), "every touch says whether it has an example picture"
        for t in r["touches"]:
            if t["example_url"]:
                assert c.get(t["example_url"]).headers["content-type"] == "image/jpeg"
        assert c.get("/api/touch-examples/nope.jpg").status_code == 404
        assert r["colour"]["summary"] and r["colour"]["plain"] and len(r["colour"]["palette"]) == len(plan["looks"][0]["item_ids"]), r["colour"]
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
    assert dark["plain"] == "All dark", dark["plain"]
    neutral = colour.read([item("n1", (225, 222, 215), "white"), item("n2", (60, 67, 78), "blue", "bottom")], var_dir)
    assert neutral["scheme"] == "all neutral" and neutral["contrast"] == "high" and neutral["idea_play"] == "accent_pop", neutral
    assert neutral["plain"].startswith("Easy neutrals, crisp light and dark"), neutral["plain"]
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
            store = main.app.state.closets.get("main").store
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


def test_device_closets(var_dir: Path, run_dir: Path) -> None:
    """MONSTER_CLOSETS=device: two browsers never see each other's clothes, and a link moves one across."""
    os.environ["MONSTER_CLOSETS"] = "device"
    os.environ["MONSTER_DEV"] = "1"  # dev seeding is off on shared servers unless asked for
    try:
        with client_for("fixture", var_dir) as a:
            b = TestClient(main.app)  # a second browser: its own cookie jar, the same running app
            ida, idb = a.get("/api/closet").json(), b.get("/api/closet").json()
            assert ida["per_device"] and ida["id"] != idb["id"], (ida, idb)
            ida, idb = ida["id"], idb["id"]
            assert a.get("/api/closet").json()["id"] == ida, "the cookie must stick"

            r = a.post("/api/dev/seed", json={"run": str(run_dir.relative_to(config.ROOT))})
            assert r.status_code == 200 and r.json()["imported"] == 2, r.text
            mine = a.get("/api/wardrobe").json()
            assert len(mine) == 2 and b.get("/api/wardrobe").json() == []
            assert b.get(f"/api/cutouts/{mine[0]['id']}.png").status_code == 404, "cutouts are per closet too"
            assert a.get("/api/profile").json()["onboarded"] is False and b.post("/api/scans", files=[
                ("photos", ("x.jpg", photo_bytes(3), "image/jpeg"))]).status_code == 409, "no replay of another closet"

            assert b.post("/api/closet/open", json={"id": "f" * 32}).status_code == 404
            assert b.post("/api/closet/open", json={"id": "main"}).status_code == 404, "the var/ root is never a closet"
            assert b.post("/api/closet/open", json={"id": ida}).status_code == 200
            assert len(b.get("/api/wardrobe").json()) == 2, "the link opens the same closet on the second device"
            assert b.post("/api/closet/new").status_code == 200 and b.get("/api/wardrobe").json() == []
            assert (var_dir / "closets" / ida / "wardrobe.sqlite3").exists()
            assert not (var_dir / "wardrobe.sqlite3").exists(), "device mode keeps nothing in the root closet"
    finally:
        os.environ.pop("MONSTER_CLOSETS", None)
        os.environ.pop("MONSTER_DEV", None)


def test_sample_closet_and_prebuild(var_dir: Path) -> None:
    """The sample closet plans straight away, a short closet says what's missing, and a wear builds tomorrow ahead."""
    with client_for("fixture", var_dir) as c:
        r = c.post("/api/plan")
        assert r.status_code == 409 and "sample closet" in r.json()["detail"], r.text

        assert c.post("/api/closet/sample").json()["imported"] == 9
        assert c.post("/api/closet/sample").json()["imported"] == 9 and len(c.get("/api/wardrobe").json()) == 9, "loading twice is harmless"
        items = c.get("/api/wardrobe").json()
        assert all(i["tags"] and i["worn_estimated"] for i in items) and c.get(f"/api/cutouts/{items[0]['id']}.png").status_code == 200
        assert c.get("/api/oni").json()["closet_alive_pct"] > 0, "the sample closet has recent wears to show"

        plan = c.post("/api/plan", json={"day": "2026-10-28"}).json()
        assert len(plan["looks"]) == 3 and len({frozenset(lk["item_ids"]) for lk in plan["looks"]}) == 3, plan["looks"]
        assert any(lk["rediscovered_id"] for lk in plan["looks"]), "something long forgotten gets rescued"

        assert c.get("/api/plan", params={"day": "2026-10-29"}).status_code == 404
        c.post(f"/api/plans/{plan['id']}/wear", json={"look": 0, "day": "2026-10-28"})
        ahead = c.get("/api/plan", params={"day": "2026-10-29"})
        assert ahead.status_code == 200 and ahead.json()["trace"]["prebuilt"], "a wear builds tomorrow's plan ahead"

        # Something changes after it was built (a piece's last-worn date), so it no longer counts.
        other = next(i for i in items if i["id"] not in plan["looks"][0]["item_ids"])
        assert c.post("/api/wardrobe/last-worn", json={"items": [{"id": other["id"], "days_ago": 2}]}).status_code == 200
        assert c.get("/api/plan", params={"day": "2026-10-29"}).status_code == 404, "a stale plan made ahead is dropped"


def test_yesterday_question(var_dir: Path) -> None:
    """The morning question: asked once about a plan that was shown, "no" just stops asking, "yes" logs the wear."""
    from datetime import timedelta
    from server.planning import today_local

    y = (today_local() - timedelta(days=1)).isoformat()
    with client_for("fixture", var_dir) as c:
        c.post("/api/closet/sample")
        assert c.get("/api/yesterday").json()["plan"] is None
        plan = c.post("/api/plan", json={"day": y}).json()
        assert c.get("/api/yesterday").json()["plan"] is None, "only a plan shown on its own day is asked about"

        store = main.app.state.closets.get("main").store
        store.put_setting("seen_plans", {y: plan["id"]})  # as if Today showed it yesterday
        c.post("/api/plan")  # this morning's plan is shown first...
        assert c.get("/api/yesterday").json()["plan"]["id"] == plan["id"], "...and yesterday's is still asked about"
        assert c.post("/api/yesterday", json={}).json()["worn"] is None
        assert c.get("/api/yesterday").json()["plan"] is None, "no means stop asking"
        assert c.post("/api/yesterday", json={"look": 0}).status_code == 404

        store.put_setting("asked_worn", {})
        assert c.post("/api/yesterday", json={"look": 9}).status_code == 422
        worn = c.post("/api/yesterday", json={"look": 0}).json()["worn"]
        assert worn["day"] == y and worn["rescued"], worn
        assert c.get("/api/yesterday").json()["plan"] is None, "a logged wear means nothing to ask"

        today_plan = c.get("/api/plan").json()
        assert c.get("/api/plan").json()["id"] == today_plan["id"], "yesterday's wear never swaps out today's plan"


def test_same_photo_pairs(var_dir: Path) -> None:
    """Two pieces cut from one photo are two garments: never shortlisted as duplicates."""
    from closet import dedupe as cdedupe
    var_dir.mkdir(parents=True, exist_ok=True)
    for n in ("x", "y"):
        cutout_png((30, 30, 30)).save(var_dir / f"{n}.png")
    same = [{"id": "x", "source": "p.jpg", "scan_id": "s1", "tags": GARMENT}, {"id": "y", "source": "p.jpg", "scan_id": "s1", "tags": GARMENT}]
    assert cdedupe.candidate_pairs(same, var_dir) == []
    assert len(cdedupe.candidate_pairs([same[0], {**same[1], "source": "q.jpg"}], var_dir)) == 1


def test_taste(var_dir: Path) -> None:
    """The taste model: a stretch look from day one, a warm-up that teaches it, corrections, evaluation, thrift fit."""
    from datetime import timedelta
    from server.planning import today_local

    with client_for("fixture", var_dir) as c:
        c.post("/api/closet/sample")
        dna = c.get("/api/taste").json()
        assert dna["signals"] == 0 and dna["traits"] == [] and "getting to know you" in dna["narrative"], dna

        plan = c.post("/api/plan").json()
        scores = plan["trace"]["scores"]
        assert len(scores) == len(plan["looks"]) and all({"rescue", "weather", "colour", "taste", "total"} <= set(x) for x in scores), scores
        assert any(st["label"] == "score()" for st in plan["trace"]["steps"]), "the score breakdown is in the trace"
        st = plan["trace"]["stretch"]
        assert plan["looks"][st["look"]]["name"] == "Stretch" and 0 <= st["pct"] <= 100, st
        assert len(plan["trace"]["taste"]["fit"]) == len(plan["looks"])
        assert {frozenset(lk["item_ids"]) for lk in plan["looks"]}.__len__() == len(plan["looks"]), "the stretch is a new outfit"
        again = c.post("/api/plan").json()
        assert again["looks"][st["look"]]["item_ids"] == plan["looks"][st["look"]]["item_ids"], "same day, same closet: same stretch"

        # The warm-up: always pick the outfit with knitwear in it.
        knit = lambda outfit: any(w in i["tags"]["subtype"] for i in outfit for w in ("sweater", "cardigan"))  # noqa: E731
        answered, seen = 0, set()
        for _ in range(3):
            pairs = c.get("/api/taste/quiz").json()["pairs"]
            assert pairs, "the quiz has pairs to ask"
            keys = {frozenset((frozenset(i["id"] for i in pr["a"]), frozenset(i["id"] for i in pr["b"]))) for pr in pairs}
            assert not keys & seen, "a pair already answered is never asked again"
            seen |= keys
            answers = []
            for pr in pairs:
                a, b = (pr["a"], pr["b"]) if knit(pr["a"]) or not knit(pr["b"]) else (pr["b"], pr["a"])
                answers.append({"picked": [i["id"] for i in a], "other": [i["id"] for i in b]})
            answered += c.post("/api/taste/quiz", json={"answers": answers}).json()["saved"]
        dna = c.get("/api/taste").json()
        assert dna["signals"] == answered and dna["counts"]["quiz"] == answered, dna
        knitwear = next(t for t in dna["traits"] if t["feature"] == "knit")
        assert knitwear["weight"] > 0 and "knitwear" in knitwear["sentence"], dna["traits"]
        taught = c.post("/api/plan").json()
        assert knit(taught["looks"][1]["items"]), "look B is the best match for what the warm-up taught, even from the rule picker"
        assert max(taught["trace"]["taste"]["fit"][:2]) >= 60, taught["trace"]["taste"]

        # "Not me" on the card moves the weight the other way.
        assert c.post("/api/taste/correct", json={"feature": "nope", "value": -1}).status_code == 404
        c.post("/api/taste/correct", json={"feature": "knit", "value": -1})
        after = next((t["weight"] for t in c.get("/api/taste").json()["traits"] if t["feature"] == "knit"), 0)
        assert after < knitwear["weight"], (after, knitwear)

        # Three worn choices on three days: the model is scored on predicting them, leave-one-out.
        for back in (3, 2, 1):
            day = (today_local() - timedelta(days=back)).isoformat()
            pl = c.post("/api/plan", json={"day": day}).json()
            c.post(f"/api/plans/{pl['id']}/wear", json={"look": 0, "day": day})
        dna = c.get("/api/taste").json()
        acc = dna["accuracy"]
        assert acc and acc["n"] == 3 and 0 <= acc["accuracy"] <= 1 and acc["chance"] > 0, acc
        assert dna["coverage"]["possible"] == 15 and dna["coverage"]["worn"] >= 1, dna["coverage"]

        gaps = c.post("/api/gaps").json()
        assert all(0 <= p["taste_fit"] <= 100 for p in gaps["pieces"]), gaps["pieces"]


def test_scoring() -> None:
    """The shared outfit score: capped rescue, whole-outfit weather, occasion, colour, and how A and B are picked."""
    from datetime import date, timedelta
    from closet import scoring

    today = date(2026, 10, 31)

    def item(iid, cat, warmth=2, form="casual", pattern="solid", days=None):
        worn = None if days is None else (today - timedelta(days=days)).isoformat()
        return {"id": iid, "last_worn": worn, "tags": {**GARMENT, "category": cat, "warmth": warmth, "formality": form,
                                                       "pattern": pattern, "subtype": cat}}

    def read(scheme="all neutral", lights=(0.5, 0.5)):
        return {"scheme": scheme, "contrast": "medium", "temperature": "mixed",
                "palette": [{"light": l, "category": "top"} for l in lights]}

    mild = scoring.day_context({"parts": {"afternoon": {"temp_c": [18, 22], "feels_like_low_c": 19, "rain_chance_pct": 0}}}, {"events": []})
    cold = scoring.day_context({"parts": {"morning": {"temp_c": [1, 4], "feels_like_low_c": 0, "rain_chance_pct": 0}}}, {"events": []})
    assert mild.target == 1 and not mild.cold and cold.target == 4 and cold.cold

    b = lambda outfit, day=mild, r=None: scoring.breakdown(outfit, r or read(), day, today)  # noqa: E731
    # Rescue is capped: 400 days idle is worth no more than 90, and a fresh wear is worth nothing.
    assert b([item("t", "top", days=400), item("b", "bottom", days=1)])["rescue"] == b([item("t", "top", days=90), item("b", "bottom")])["rescue"] == 3.0
    assert b([item("t", "top", days=3), item("b", "bottom", days=3)])["rescue"] == 0
    # The weather decides over a forgotten coat on a mild day.
    coat_day = b([item("t", "top", warmth=1), item("b", "bottom"), item("c", "outerwear", warmth=5, days=400)])
    tee_day = b([item("t", "top", warmth=1, days=60), item("b", "bottom")])
    assert tee_day["total"] > coat_day["total"] and coat_day["weather"] < -2, (coat_day, tee_day)
    # Cold day: a layer beats no layer.
    assert b([item("t", "top", 3), item("b", "bottom"), item("c", "outerwear", 4)], cold)["weather"] > b([item("t", "top", 3), item("b", "bottom")], cold)["weather"]
    # A dress code wants something smart.
    dressy = scoring.day_context({"parts": {}}, {"events": [{"start": "10:00", "title": "Crit", "dress_code": "smart casual"}]})
    assert b([item("t", "top", form="smart_casual"), item("b", "bottom")], dressy)["occasion"] > b([item("t", "top", form="athleisure"), item("b", "bottom")], dressy)["occasion"]
    # Colour: one pop beats a clash; two patterns and head-to-toe dark cost a little.
    assert b([item("t", "top"), item("b", "bottom")], r=read("neutral + accent"))["colour"] > b([item("t", "top"), item("b", "bottom")], r=read("contrasting"))["colour"]
    assert b([item("t", "top", pattern="striped"), item("b", "bottom", pattern="checked")])["colour"] < b([item("t", "top"), item("b", "bottom")])["colour"]
    assert b([item("t", "top"), item("b", "bottom")], r=read(lights=(0.1, 0.2)))["colour"] < b([item("t", "top"), item("b", "bottom")])["colour"]

    # A: the best look that rescues something. B: the best look sharing no piece with A.
    t1, t2, b1, b2 = item("t1", "top", days=200), item("t2", "top", days=2), item("b1", "bottom", days=2), item("b2", "bottom", days=2)
    scored = [([t, bb], b([t, bb])) for t in (t1, t2) for bb in (b1, b2)]
    a, second = scoring.pick_two(scored)
    assert any(i["id"] == "t1" for i in scored[a][0]), "A rescues the forgotten top"
    assert not {i["id"] for i in scored[a][0]} & {i["id"] for i in scored[second][0]}, "B shares nothing with A"
    assert "rescue +3.0" in scoring.summary("A", b([t1, b1])), scoring.summary("A", b([t1, b1]))


def test_styles(var_dir: Path) -> None:
    """Style archetypes: the board quiz learns a style mix, reads the closet in the same terms, and finds room to grow."""
    from closet import styles, taste

    # The model: someone who always picks dark academia, and prefers minimalist over the rest.
    picks = [("dark_academia", s) for s in styles.IDS if s != "dark_academia"] + [("minimalist", s) for s in ("y2k", "gorpcore", "grunge")]
    m = styles.fit(picks)
    mix = m.mix()
    assert mix[0]["id"] == "dark_academia" and mix[0]["pct"] >= 75 and mix[-1]["pct"] < 50, mix[:3]
    assert styles.fit([]).mix()[0]["pct"] == 50, "no answers: no opinion"
    asked = {frozenset(p) for p in picks}
    nxt = styles.next_pairs(m, asked, 6)
    assert nxt and not any(frozenset(p) in asked for p in nxt), "never asks a pair twice"
    assert max(sum(st in p for p in nxt) for st in styles.IDS) <= 2, "no style more than twice a round"
    for st in styles.STYLES:  # every profile speaks the taste model's language
        assert set(st.profile) <= set(taste.INDEX) and st.signature and len(st.pieces) >= 6, st.id

    with client_for("fixture", var_dir) as c:
        c.post("/api/closet/sample")
        dna = c.get("/api/taste").json()["styles"]
        assert dna["answers"] == 0 and dna["liked"] == [] and dna["grow"] is None and dna["closet"], dna
        pairs = c.get("/api/styles/quiz").json()["pairs"]
        boards = (config.ROOT / "fixtures" / "style_boards" / "boards.json").exists()
        if boards:
            assert pairs and all(pr["a"]["style"] != pr["b"]["style"] and pr["a"]["pieces"] for pr in pairs), pairs[:1]
            piece = pairs[0]["a"]["pieces"][0]
            assert c.get(piece["cutout_url"]).headers["content-type"] == "image/webp"
        assert c.get("/api/style-boards/../x.webp").status_code == 404

        answers = [{"picked": "dark_academia", "other": o} for o in ("streetwear", "y2k", "gorpcore", "cyberpunk")]
        assert c.post("/api/styles/quiz", json={"answers": answers + [{"picked": "nope", "other": "y2k"}]}).json()["saved"] == 4
        dna = c.get("/api/taste").json()
        st = dna["styles"]
        assert st["answers"] == 4 and st["liked"][0]["id"] == "dark_academia", st["liked"]
        assert st["grow"] and st["grow"]["signature"], st["grow"]
        assert dna["counts"].get("style") == 4, "board picks teach the outfit model too"
        if boards:
            again = c.get("/api/styles/quiz").json()["pairs"]
            assert not {frozenset((pr["a"]["style"], pr["b"]["style"])) for pr in again} & {frozenset(("dark_academia", a["other"])) for a in answers}

        plan = c.post("/api/plan").json()
        assert plan["trace"]["stretch"]["towards"] == st["grow"]["name"], plan["trace"]["stretch"]


def test_products(var_dir: Path) -> None:
    """Scans get a clean product shot in the background; a redraw whose colour drifted is thrown away."""
    import time

    from server import pipeline, products as products_mod

    async def fake_scan_image(client, photo, batch, source):
        return [scan.ScanItem(source, batch, "0", (0, 0, 1, 1), 0.9, cutout_png((30, 40, 90))),
                scan.ScanItem(source, batch, "1", (0, 0, 1, 1), 0.9, cutout_png((200, 30, 30)))]

    def fake_tag(img, provider=None, hint="", notes=""):
        from closet.schema import Garment
        return Garment.model_validate(GARMENT)

    async def fake_cut(client, photo, noun, open_shape=False):
        r, g, b = photo.getpixel((photo.width // 2, photo.height // 2))
        return cutout_png((20, 200, 20) if r > 150 else (r, g, b))  # the red one comes back green: drifted

    calls = {"edit": 0}

    def fake_edit(images, prompt):
        calls["edit"] += 1
        assert "Keep it faithful" in prompt and "crewneck sweatshirt" in prompt, prompt
        return images[0], "ok"

    orig = (pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for,
            products_mod.models._edit, products_mod.products.cut)
    pipeline.scan.scan_image, pipeline.models.tag_garment = fake_scan_image, fake_tag
    pipeline.config.async_client_for = lambda provider="meta": None
    products_mod.models._edit, products_mod.products.cut = fake_edit, fake_cut
    from closet.schema import DetailCheck
    orig_check = products_mod.products.check_details
    products_mod.products.check_details = lambda cut, shot, tags: DetailCheck(
        real_details="plain", missing_details=[], added_details=[], same_garment=True)
    try:
        with client_for("live", var_dir) as c:
            items = c.post("/api/scans", files=[("photos", ("bed.jpg", photo_bytes(3), "image/jpeg"))]).json()["items"]
            assert all(i["photo_url"] == i["cutout_url"] for i in items), "the scan shows straight away"
            for _ in range(100):
                st = c.get("/api/products").json()
                if not st["running"] and calls["edit"] == 2:
                    break
                time.sleep(0.05)
            assert st == {"done": 1, "running": 0, "waiting": 0, "live": True}, st
            by_colour = {i["tags"]["primary_color"] + str(n): i for n, i in enumerate(c.get("/api/wardrobe").json())}
            shown = [i for i in by_colour.values() if i["photo_url"] != i["cutout_url"]]
            assert len(shown) == 1 and shown[0]["photo_url"].endswith(".webp"), by_colour
            assert shown[0]["photo_drift"] == 0.0 and all(i["photo_drift"] is None for i in by_colour.values() if i is not shown[0])
            assert c.get(shown[0]["photo_url"]).headers["content-type"] == "image/webp"
            drifted = next(i for i in by_colour.values() if i["photo_url"] == i["cutout_url"])
            note = json.loads((main.app.state.products.dir / f"{drifted['id']}.json").read_text())
            assert not note["ok"] and "colour drifted" in note["reason"], note
            c.post("/api/products")
            assert calls["edit"] == 2, "one try per item"
    finally:
        (pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for,
         products_mod.models._edit, products_mod.products.cut) = orig
        products_mod.products.check_details = orig_check



def test_occasions(var_dir: Path) -> None:
    """Events read as occasions, scored on their own, planned apart from the day; linked calendars stay private."""
    import asyncio
    from datetime import date as d, timedelta

    from closet import occasions, scoring, tools
    from server import calfeed, planning as planning_mod

    r = occasions.read({"start": "14:00", "title": "Job interview at Shopify"})
    assert (r.kind, r.formality, r.evening) == ("interview", 3, False), r
    r = occasions.read({"start": "19:00", "end": "21:30", "title": "Dinner outside with friends", "location": "Patio restaurant"})
    assert (r.kind, r.formality, r.evening, r.outdoors) == ("evening_out", 2, True, True), r
    assert occasions.read({"start": "07:00", "title": "Morning workout"}).kind == "active", "workout isn't work"
    assert occasions.read({"start": "10:00", "title": "Studio crit", "dress_code": "black tie"}).formality == 4, "a dress code wins"

    # Only the event's hours count: a warm afternoon doesn't help a cold evening dinner.
    weather = {"parts": {"afternoon": {"temp_c": [18, 22], "feels_like_low_c": 19, "rain_chance_pct": 0},
                         "evening": {"temp_c": [4, 6], "feels_like_low_c": 1, "rain_chance_pct": 70}}}
    dinner = scoring.day_context(weather, {"events": []}, {"start": "19:00", "title": "Dinner", "location": "patio"})
    assert dinner.cold and dinner.rainy and dinner.target == 4 and dinner.formality == 2, dinner

    def piece(cat, form, sub="x"):
        return {"id": sub, "last_worn": None, "tags": {**GARMENT, "category": cat, "formality": form, "subtype": sub, "warmth": 2}}
    read = {"palette": [{"light": 0.4, "category": "top"}], "scheme": "all neutral"}
    interview = scoring.day_context({"parts": {}}, {"events": []}, {"start": "14:00", "title": "Interview"})
    smart = scoring.breakdown([piece("top", "business", "shirt"), piece("bottom", "smart_casual", "chinos")], read, interview, d.today())
    sporty = scoring.breakdown([piece("top", "athleisure", "tee"), piece("bottom", "athleisure", "joggers")], read, interview, d.today())
    assert smart["occasion"] > 0 > sporty["occasion"], (smart, sporty)

    # A weekly class from a real feed: UTC times, an RRULE and a cancelled week.
    first = d.today() - timedelta(days=7)
    utc = lambda day, h: day.strftime("%Y%m%d") + f"T{h:02d}0000Z"  # noqa: E731
    ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:a\r\nDTSTART:" + utc(first, 15) + "\r\nDTEND:" + utc(first, 16)
           + "\r\nRRULE:FREQ=WEEKLY;COUNT=4\r\nEXDATE:" + utc(first + timedelta(days=14), 15)
           + "\r\nSUMMARY:Design studio\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n").encode()
    assert tools.ics_count(ics) == 1 and tools.ics_count(b"nope") == 0
    today = tools.ics_events(ics, d.today())
    assert [e["title"] for e in today] == ["Design studio"], today
    from datetime import datetime, timezone
    # Today's occurrence in local time (not the first one's: clocks may have changed in between).
    local = datetime(d.today().year, d.today().month, d.today().day, 15, tzinfo=timezone.utc).astimezone().strftime("%H:%M")
    assert today[0]["start"] == local, (today, local)
    assert tools.ics_events(ics, d.today() + timedelta(days=7)) == [], "the cancelled week is gone"
    assert [e["title"] for e in tools.ics_events(ics, d.today() + timedelta(days=14))] == ["Design studio"]

    # Calendar links: https only, never a private address, and the link itself never comes back.
    assert calfeed.normalise("webcal://p01-caldav.icloud.com/published/2/abc") == "https://p01-caldav.icloud.com/published/2/abc"
    for bad in ("http://calendar.google.com/x.ics", "file:///etc/passwd", "https://localhost/x.ics", "https://127.0.0.1/x.ics"):
        try:
            asyncio.run(calfeed.fetch(bad))
            raise AssertionError(f"fetched {bad}")
        except calfeed.FeedError:
            pass

    async def fake_fetch(url):
        assert url.startswith("https://calendar.google.com/"), url
        return ics
    orig = planning_mod.calfeed.fetch
    planning_mod.calfeed.fetch = fake_fetch
    try:
        with client_for("fixture", var_dir) as c:
            c.post("/api/closet/sample")
            up = c.get("/api/occasions").json()
            assert up["calendar"] == "sample" and [e["title"] for e in up["events"]][:2] == ["Studio crit", "Dinner outside with friends"], up
            assert len(up["events"]) == 4 and up["events"][1]["read"]["label"] == "smart casual · evening · outdoors", up["events"][1]

            day_plan = c.post("/api/plan").json()
            ev = {k: up["events"][1][k] for k in ("title", "start", "end", "location")}
            occ = c.post("/api/occasions/plan", json={"event": ev}).json()
            assert occ["occasion"]["read"]["kind"] == "evening_out" and occ["calendar"]["events"] == [ev], occ["occasion"]
            assert "Dress me for one occasion" in occ["notes"] and len(occ["looks"]) >= 2, occ["notes"]
            assert c.get("/api/plan").json()["id"] == day_plan["id"], "an event plan never replaces the day's plan"
            assert c.get("/api/occasions").json()["events"][1]["plan_id"] == occ["id"]
            assert c.get(f"/api/plans/{occ['id']}").json()["occasion"]["event"]["title"] == ev["title"]

            typed = c.post("/api/occasions/plan", json={"day": (d.today() + timedelta(days=3)).isoformat(),
                                                         "event": {"title": "Job interview", "start": "10:00"}}).json()
            assert typed["day"] == (d.today() + timedelta(days=3)).isoformat() and typed["occasion"]["read"]["formality"] == 3
            listed = [e for e in c.get("/api/occasions").json()["events"] if e.get("typed")]
            assert [(e["title"], e["plan_id"]) for e in listed] == [("Job interview", typed["id"])], "typed occasions stay listed"
            far = c.post("/api/occasions/plan", json={"day": (d.today() + timedelta(days=30)).isoformat(), "event": {"title": "Gala"}})
            assert far.status_code == 422, far.text

            secret = "https://calendar.google.com/calendar/ical/me%40gmail.com/private-0123456789abcdef/basic.ics"
            r = c.post("/api/profile/calendar-link", json={"url": secret})
            assert r.status_code == 200 and r.json()["profile"]["calendar"] == "link", r.text
            assert r.json()["profile"]["calendar_name"] == "calendar.google.com" and "private-" not in r.text + c.get("/api/profile").text
            assert [e["title"] for e in c.get("/api/occasions").json()["events"] if not e.get("typed")] == ["Design studio"], "the linked calendar is read"
            assert c.delete("/api/profile/calendar").json()["calendar"] == "none"
            assert not main.app.state.closets.get("main").planning.calendar_link_path.exists(), "disconnecting deletes the link"
    finally:
        planning_mod.calfeed.fetch = orig



def test_deploy(var_dir: Path) -> None:
    """A public deploy: the spend cap turns a live server into demo mode for the day, and the API serves the app."""
    dist = var_dir / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>app</title>")
    (dist / "assets" / "app-1.js").write_text("console.log(1)")
    os.environ.update({"MONSTER_CLOSET_DAILY_CALLS": "1", "MONSTER_CLOSETS": "device"})
    main.WEB_DIST = dist.resolve()
    try:
        with client_for("live", var_dir) as c:
            h = c.get("/api/health").json()
            assert h["mode"] == "live" and h["budget_left"] == 1, h
            assert c.post("/api/products").json()["live"] and c.get("/api/health").json()["budget_left"] == 1, "browsing is free"
            assert c.post("/api/plan").status_code == 409, "a paid request (an empty closet can't plan, but it counts)"
            h = c.get("/api/health").json()
            assert h["mode"] == "fixture" and h["budget_left"] == 0, h
            assert c.post("/api/closet/new").status_code == 200
            assert c.get("/api/health").json()["budget_left"] == 1, "the cap is per closet"
            assert c.post("/api/plans/nope/wear", json={"look": 0}).status_code in (404, 422)

            before = main.app.state.closets.count()
            assert all(c.get("/api/ping", cookies={}).json() == {"ok": True} for _ in range(3))
            assert main.app.state.closets.count() == before, "health probes never create closets"
            assert "<title>app</title>" in c.get("/").text and "<title>app</title>" in c.get("/closet/anything").text
            r = c.get("/assets/app-1.js")
            assert r.text == "console.log(1)" and "immutable" in r.headers["cache-control"], r.headers
            assert c.get("/api/nope").status_code == 404
            for probe in ("/.env", "/.git/config", "/server/main.py", "/var/wardrobe.sqlite3"):
                assert c.get(probe).status_code == 404, f"{probe} must be a plain 404, not the app"
            assert "MODEL_API_KEY" not in c.get("/../.env").text
    finally:
        for k in ("MONSTER_CLOSET_DAILY_CALLS", "MONSTER_CLOSETS"):
            os.environ.pop(k, None)
        main.WEB_DIST = (config.ROOT / "web" / "dist").resolve()



def test_layering(var_dir: Path) -> None:
    """Layers stack by what they are, and an inner layer never pokes out from under an outer one."""
    import numpy as np

    from closet import layering
    from closet.schema import Garment

    t = lambda cat, sub, fit="regular": {"category": cat, "subtype": sub, "fit": fit, "warmth": 2}  # noqa: E731
    tee, crew = t("top", "graphic t-shirt", "loose, oversized"), t("top", "crewneck sweatshirt", "regular, long sleeve")
    hoodie, jeans = t("outerwear", "zip-up hoodie", "relaxed"), t("bottom", "wide-leg jeans")
    assert layering.rank(jeans) < layering.rank(tee) < layering.rank(crew) < layering.rank(hoodie)
    assert layering.rank(t("top", "corduroy overshirt")) == layering.rank(t("top", "bomber jacket")), "an overshirt is an outer layer"
    assert [layering.sleeves(x) for x in (tee, crew, hoodie, t("outerwear", "puffer vest"))] == ["short", "long", "long", "none"]

    # A hoodie (torso + long sleeves) over an oversized tee whose sleeves stick out sideways,
    # whose hem hangs below the hoodie's, and whose collar shows at the neck.
    outer = np.zeros((100, 100), np.uint8)
    outer[20:80, 30:70] = 255
    outer[25:75, 22:30] = 255
    outer[25:75, 70:78] = 255
    inner = np.zeros((100, 100), np.uint8)
    inner[22:90, 32:68] = 255   # torso, longer than the hoodie
    inner[25:45, 12:32] = 255   # left sleeve, wider than the hoodie sleeve
    inner[25:45, 68:88] = 255   # right sleeve
    inner[14:22, 44:56] = 255   # collar above the hoodie's neckline
    cut = layering.occlude(inner, outer, outer_long_sleeves=True)
    assert not cut[25:45, 12:22].any() and not cut[25:45, 78:88].any(), "sleeves beside a long sleeve are hidden"
    assert cut[82:90, 35:65].all(), "a longer hem still peeks out below"
    assert cut[14:20, 46:54].all(), "the collar shows at the neck"
    assert cut[30:40, 40:60].all(), "under the outer is left alone (it's drawn over anyway)"
    short = layering.occlude(inner, outer, outer_long_sleeves=False)
    assert short[25:45, 12:22].all(), "under a short-sleeved or sleeveless outer, the inner sleeves show"

    # The server cuts back layers for exactly the pieces being worn, and caches each combination.
    with client_for("fixture", var_dir) as c:
        closet = main.app.state.closets.get("main")
        body = {"height_cm": 170}
        key = closet.layers.base_key(body)
        (closet.layers.root / key).mkdir(parents=True, exist_ok=True)
        from PIL import Image
        for item_id, tags, mask in (("teeitem", tee, inner), ("hoodieitem", hoodie, outer)):
            closet.store.upsert_item(item_id, "s", "x", None, Garment.model_validate({**GARMENT, **tags}), None)
            Image.fromarray(np.dstack([np.full((100, 100, 3), 90, np.uint8), mask]), "RGBA").save(closet.layers.root / key / f"{item_id}.png")
            (closet.layers.root / key / f"{item_id}.json").write_text(json.dumps({"status": "ready", "box": [0, 0, 100, 100], "size": [100, 100]}))
        st = closet.layers.stack(body, ["hoodieitem", "teeitem"])
        assert [(l["item_id"], l["order"]) for l in st["layers"]] == [("teeitem", 1), ("hoodieitem", 2)], st
        tee_url = st["layers"][0]["url"]
        assert tee_url != f"/api/layers/{key}/teeitem.png" and st["layers"][1]["url"].endswith("hoodieitem.png"), st
        png = closet.layers.root / key / (tee_url.rsplit("/", 1)[1])
        a = np.asarray(Image.open(png))[..., 3]
        assert not a[25:45, 12:22].any() and a[82:90, 35:65].all(), "the served tee is cut back"
        alone = closet.layers.stack(body, ["teeitem"])["layers"][0]["url"]
        assert alone == f"/api/layers/{key}/teeitem.png", "take the hoodie off and the tee is whole again"
        assert closet.layers.stack(body, ["teeitem", "hoodieitem"])["layers"][0]["url"] == tee_url, "cached per combination"
        assert c.get(tee_url).status_code == 200



def test_inside_labels() -> None:
    """Inside labels the tagger noticed in a flat-lay never reach a render prompt; logos and prints do."""
    from closet import models
    from closet.schema import Garment, outside_details

    assert outside_details("medium-wash faded denim, brand tag visible at waistband") == "medium-wash faded denim"
    assert outside_details("front zip closure, drawstrings, white interior neck tag") == "front zip closure, drawstrings"
    assert outside_details("small white CK monogram logo on left chest") == "small white CK monogram logo on left chest"
    g = Garment.model_validate({**GARMENT, "distinctive_details": "two-button placket; small Uniqlo tag at back neck"})
    line = g.render_line("#202020")
    assert "two-button placket" in line and "tag" not in line.lower(), line
    assert "never show them on the outside" in models.GARMENT_RULES



def test_corrections(var_dir: Path) -> None:
    """When the AI gets a piece wrong: fix it by hand, ask again with a hint, or rescan it with a new photo."""
    from closet.schema import Garment
    from server import pipeline, products as products_mod

    with client_for("fixture", var_dir / "demo") as c:
        c.post("/api/closet/sample")
        item = c.get("/api/wardrobe").json()[0]
        assert c.post(f"/api/wardrobe/{item['id']}/retag", json={"hint": "a hoodie"}).status_code == 409, "asking again needs live mode"
        r = c.post(f"/api/wardrobe/{item['id']}/rescan", files={"photo": ("p.jpg", photo_bytes(5), "image/jpeg")})
        assert r.status_code == 409 and "demo mode" in r.json()["detail"], "a demo replay must never replace a real piece"
        fixed = c.patch(f"/api/wardrobe/{item['id']}", json={"subtype": "zip-up hoodie", "category": "outerwear"}).json()
        assert fixed["user_edited"] and fixed["tags"]["subtype"] == "zip-up hoodie" and fixed["photo_url"] == item["photo_url"], fixed
        assert c.patch(f"/api/wardrobe/{item['id']}", json={"is_garment": False}).status_code == 200
        assert item["id"] not in {i["id"] for i in c.get("/api/wardrobe").json()}, "'not clothing' hides it"

    seen = {}

    def fake_tag(img, provider=None, hint="", notes=""):
        seen["hint"] = hint
        return Garment.model_validate({**GARMENT, "subtype": "zip-up hoodie" if hint else "dress", "category": "outerwear" if hint else "dress"})

    async def fake_scan_image(client, photo, batch, source):
        tone = photo.getpixel((10, 10))[0]
        return [scan.ScanItem(source, batch, "0", (0, 0, 1, 1), 0.9, cutout_png((tone, 60, 60))),
                scan.ScanItem(source, batch, "1", (0, 0, 1, 1), 0.5, cutout_png((tone, 200, 60), size=(40, 40)))]

    orig = (pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for, products_mod.models._edit)
    pipeline.scan.scan_image, pipeline.models.tag_garment = fake_scan_image, fake_tag
    pipeline.config.async_client_for = lambda provider="meta": None
    products_mod.models._edit = lambda images, prompt: (None, "stubbed")
    try:
        with client_for("live", var_dir / "live") as c:
            first = c.post("/api/scans", files=[("photos", ("a.jpg", photo_bytes(1), "image/jpeg"))]).json()["items"]
            old = next(i for i in first if i["confidence"] == 0.9)
            assert old["tags"]["subtype"] == "dress", "the AI got it wrong"
            assert c.post("/api/plans/x/wear", json={"look": 0}).status_code in (404, 422)
            c.post("/api/wardrobe/last-worn", json={"items": [{"id": old["id"], "days_ago": 3}]})

            again = c.post(f"/api/wardrobe/{old['id']}/retag", json={"hint": "it's a zip-up hoodie, not a dress"}).json()
            assert seen["hint"].startswith("it's a zip-up hoodie") and again["tags"]["category"] == "outerwear" and again["user_edited"], again

            n_before = len(c.get("/api/wardrobe").json())
            new = c.post(f"/api/wardrobe/{old['id']}/rescan", files={"photo": ("b.jpg", photo_bytes(30), "image/jpeg")}).json()
            assert new["id"] != old["id"] and new["last_worn"] is not None, "the new photo takes over, wear history and all"
            ids = {i["id"] for i in c.get("/api/wardrobe").json()}
            assert old["id"] not in ids and new["id"] in ids and len(ids) == n_before, "one piece in, one out: the smaller find isn't added"
            assert c.get(f"/api/wardrobe/{old['id']}").status_code in (200, 404)
    finally:
        pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for, products_mod.models._edit = orig



def test_hardening(var_dir: Path) -> None:
    """A public deploy shrugs off stray traffic, bad uploads and hostile calendars, and keeps photos private."""
    import time
    from datetime import date as d

    from closet import tools
    from server import budget

    # Bots without a cookie can't fill the closet cap: unused closets make room once they're stale.
    os.environ.update({"MONSTER_CLOSETS": "device", "MONSTER_MAX_CLOSETS": "3"})
    try:
        with client_for("fixture", var_dir / "public") as c:
            closets = main.app.state.closets
            assert c.post("/api/closet/sample").json()["imported"] == 9  # a real visitor, really using it
            for _ in range(2):
                assert TestClient(main.app).get("/api/health").status_code == 200  # a fresh client: no cookie
            assert closets.count() == 3
            assert TestClient(main.app).get("/api/health").status_code == 503, "full, and nothing is stale yet"
            old = time.time() - 3600
            for dir_ in closets.root.iterdir():
                os.utime(dir_, (old, old))
            assert TestClient(main.app).get("/api/health").status_code == 200, "stale unused closets made room"
            assert len(c.get("/api/wardrobe").json()) == 9, "the closet with clothes in it was kept"

            # Product shots live in one shared folder: only the owning closet can fetch one.
            item = c.get("/api/wardrobe").json()[0]
            shot = main.app.state.products.dir / f"{item['id']}.webp"
            shot.write_bytes(b"RIFF0000WEBP")
            assert c.get(f"/api/products/{item['id']}.webp").status_code == 200
            assert TestClient(main.app).get(f"/api/products/{item['id']}.webp").status_code == 404, "another closet can't"
            assert "private" in c.get(f"/api/cutouts/{item['id']}.png").headers["cache-control"]
            assert c.get("/api/cutouts/%E2%91%A0.png").status_code == 404, "only ASCII names (isalnum() takes '①')"

            assert c.post("/api/dev/seed", json={"run": "out/x"}).status_code == 404, "no dev seeding on a shared server"
            assert "access-control-allow-origin" not in c.get("/api/ping", headers={"Origin": "https://evil.example"}).headers
    finally:
        for k in ("MONSTER_CLOSETS", "MONSTER_MAX_CLOSETS"):
            os.environ.pop(k, None)

    # Uploads that aren't photos are a clear 422, not a crash (live mode decodes them; demo mode replays).
    with client_for("live", var_dir / "live") as c:
        r = c.post("/api/scans", files=[("photos", ("x.jpg", b"not an image at all", "image/jpeg"))])
        assert r.status_code == 422 and "isn't a photo" in r.json()["detail"], r.text

    # The spend cap counts what can spend, and not browsing.
    paid = lambda m, path: any(rx.match(f"{m} {path}") for rx in budget.PAID)  # noqa: E731
    assert paid("POST", "/api/scans") and paid("POST", "/api/wardrobe/abc/rescan") and paid("POST", "/api/plans/x/wear")
    assert not paid("POST", "/api/tryon/layers/stack") and not paid("GET", "/api/taste") and not paid("POST", "/api/products")
    assert not paid("POST", "/api/plans") and paid("POST", "/api/plan")

    # A calendar event repeating every minute is read once, not expanded 1,440 times.
    stamp = d.today().strftime("%Y%m%d")
    ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:spam\r\nDTSTART:" + stamp + "T090000\r\n"
           "RRULE:FREQ=MINUTELY\r\nSUMMARY:Spam\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n").encode()
    t0 = time.time()
    events = tools.ics_events(ics, d.today())
    assert len(events) == 1 and time.time() - t0 < 2, (len(events), time.time() - t0)



def test_scan_fixes(var_dir: Path) -> None:
    """Real scans replace the sample closet; the tagger gets outline measurements; removing a piece forgets it."""
    from PIL import Image, ImageDraw

    from closet.schema import Garment
    from server import pipeline, products as products_mod

    # A T-shape (a tee with sleeves) fills much less of its outline's hull than a flat square (a bandana).
    tee = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(tee)
    d.rectangle([60, 40, 140, 190], fill=(20, 20, 90, 255))
    d.rectangle([10, 40, 190, 80], fill=(20, 20, 90, 255))
    square = cutout_png((200, 30, 30), size=(150, 150))
    note_tee, note_sq = scan.shape_notes(tee, 1.0), scan.shape_notes(square, 0.3)
    fill = lambda n: int(n.split("fills ")[1].split("%")[0])  # noqa: E731
    assert fill(note_tee) < 85 <= 95 <= fill(note_sq), (note_tee, note_sq)
    assert "30% the size of the largest item" in note_sq

    seen = []

    def fake_tag(img, provider=None, hint="", notes=""):
        seen.append(notes)
        return Garment.model_validate(GARMENT)

    async def fake_scan_image(client, photo, batch, source):
        return [scan.ScanItem(source, batch, "0", (0, 0, 1, 1), 0.9, tee),
                scan.ScanItem(source, batch, "1", (0, 0, 1, 1), 0.9, square)]

    orig = (pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for, products_mod.models._edit)
    pipeline.scan.scan_image, pipeline.models.tag_garment = fake_scan_image, fake_tag
    pipeline.config.async_client_for = lambda provider="meta": None
    products_mod.models._edit = lambda images, prompt: (None, "stubbed")
    try:
        with client_for("live", var_dir) as c:
            assert c.post("/api/closet/sample").json()["imported"] == 9
            r = c.post("/api/scans", files=[("photos", ("mine.jpg", photo_bytes(11), "image/jpeg"))]).json()
            assert r["sample_removed"] == 9, r.get("sample_removed")
            items = c.get("/api/wardrobe").json()
            assert len(items) == 2 and all(i["source"] == "mine.jpg" for i in items), "only their own clothes are left"
            assert len(seen) == 2 and all("Measured from the cutout" in n for n in seen), seen
            assert any("the size of the largest item in the same photo" in n for n in seen)

            # Removing is undoable for two days, then the piece and its wear history are deleted for good.
            gone = items[0]["id"]
            c.post("/api/wardrobe/last-worn", json={"items": [{"id": gone, "days_ago": 1}]})
            c.post("/api/plans/x/wear", json={"look": 0})
            assert c.delete(f"/api/wardrobe/{gone}").status_code == 204
            assert gone not in {i["id"] for i in c.get("/api/wardrobe").json()} and c.get(f"/api/wardrobe/{gone}").status_code == 404
            back = c.post(f"/api/wardrobe/{gone}/restore").json()
            assert back["id"] == gone and back["last_worn"] is not None, "Undo brings it back as it was"
            assert c.post(f"/api/wardrobe/{gone}/restore").status_code == 404, "nothing left to undo"
            closet = main.app.state.closets.get("main")
            c.delete(f"/api/wardrobe/{gone}")
            closet.store._db.execute("UPDATE items SET removed_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (gone,))
            closet.store._db.commit()
            closet.store._purge_removed()
            assert closet.store.get_item(gone, include_removed=True) is None
            assert not (closet.settings.cutout_dir / f"{gone}.png").exists(), "the purge deletes the cutout too"
            c.post("/api/closet/sample")
            assert c.delete("/api/closet/sample").json()["removed"] == 9 and len(c.get("/api/wardrobe").json()) == 1
            assert c.get("/api/scan-guide/good.jpg").status_code == 200 and c.get("/api/scan-guide/x.jpg").status_code == 404
    finally:
        pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for, products_mod.models._edit = orig



def test_round_two(var_dir: Path) -> None:
    """Light-on-light photos get a warning, a redraw that lost a detail is retried then refused, and the owner
    can keep their own scan instead."""
    from PIL import Image, ImageDraw

    from closet.schema import DetailCheck, Garment
    from server import pipeline, products as products_mod

    def flat(bg, fg):
        im = Image.new("RGB", (600, 400), bg)
        ImageDraw.Draw(im).rectangle([200, 100, 400, 300], fill=fg)
        return im

    piece = lambda fg: scan.ScanItem("p.jpg", 0, "0", (0, 0, 1, 1), 0.9, Image.new("RGBA", (200, 200), (*fg, 255)))  # noqa: E731
    assert "close in colour" in scan.contrast_warning(flat((240, 238, 235), (250, 250, 248)), [piece((250, 250, 248))])
    assert scan.contrast_warning(flat((70, 55, 45), (250, 250, 248)), [piece((250, 250, 248))]) is None
    from closet import media
    assert media.for_segmentation(flat((240, 238, 235), (250, 250, 248))).size == (600, 400)

    edits, checks = [], []

    def fake_edit(images, prompt):
        edits.append(prompt)
        return images[0], "ok"

    async def fake_cut(client, photo, noun, open_shape=False):
        return cutout_png((90, 90, 120))

    def fake_check(cut, shot, tags):
        checks.append(1)
        return DetailCheck(real_details="ruffled skirt attached at the waist", missing_details=["ruffled skirt"],
                           added_details=[], same_garment=False)

    async def fake_scan_image(client, photo, batch, source):
        return [scan.ScanItem(source, batch, "0", (0, 0, 1, 1), 0.9, cutout_png((90, 90, 120)))]

    def fake_tag(img, provider=None, hint="", notes=""):
        return Garment.model_validate({**GARMENT, "subtype": "ruffle-hem tank top", "distinctive_details": "ruffled skirt"})

    orig = (pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for,
            products_mod.models._edit, products_mod.products.cut, products_mod.products.check_details)
    pipeline.scan.scan_image, pipeline.models.tag_garment = fake_scan_image, fake_tag
    pipeline.config.async_client_for = lambda provider="meta": None
    products_mod.models._edit, products_mod.products.cut, products_mod.products.check_details = fake_edit, fake_cut, fake_check
    try:
        import time
        with client_for("live", var_dir) as c:
            item = c.post("/api/scans", files=[("photos", ("frill.jpg", photo_bytes(21), "image/jpeg"))]).json()["items"][0]
            for _ in range(100):
                if not c.get("/api/products").json()["running"] and len(checks) >= 2:
                    break
                time.sleep(0.05)
            assert len(edits) == 2 and "ruffled skirt" in edits[1] and "must be there this time" in edits[1], edits
            note = json.loads((main.app.state.products.dir / f"{item['id']}.json").read_text())
            assert not note["ok"] and "lost details" in note["reason"], note
            assert c.get(f"/api/wardrobe/{item['id']}").json()["photo_url"].endswith(".png"), "the scan is shown instead"

            # "Use my scan" sticks; "Redraw" tries again.
            assert c.post(f"/api/wardrobe/{item['id']}/photo", json={"use": "scan"}).status_code == 200
            assert "chose their scan" in json.loads((main.app.state.products.dir / f"{item['id']}.json").read_text())["reason"]
            c.post("/api/products")
            assert len(edits) == 2, "a scan the owner chose is never redrawn on its own"
            assert c.post(f"/api/wardrobe/{item['id']}/photo", json={"use": "redraw"}).status_code == 200
            for _ in range(100):
                if len(edits) >= 4 and not c.get("/api/products").json()["running"]:
                    break
                time.sleep(0.05)
            assert len(edits) == 4, edits
    finally:
        (pipeline.scan.scan_image, pipeline.models.tag_garment, pipeline.config.async_client_for,
         products_mod.models._edit, products_mod.products.cut, products_mod.products.check_details) = orig



def test_materials(var_dir: Path) -> None:
    """Fabric preferences: the tagger's free-text material sorts into families, a fabric they won't wear stays
    out of the picks (and the Stretch), and a loved one is nudged up."""
    from closet import materials

    assert materials.families("cotton-blend fleece") == {"cotton", "fleece"}
    assert materials.families("suiting twill, likely polyester-viscose blend") == {"synthetic"}
    assert materials.families("faux leather") == {"synthetic"} and materials.families("suede") == {"leather"}
    assert materials.clean({"love": ["wool", "cotton", "nope"], "avoid": ["wool"]}) == {"love": ["cotton"], "avoid": ["wool"]}
    wool, tee = {"tags": {"material_guess": "merino knit"}}, {"tags": {"material_guess": "cotton jersey"}}
    assert materials.score([wool, tee], {"avoid": ["wool"]}) < 0 < materials.score([tee], {"love": ["cotton"]})
    assert materials.score([wool, tee], None) == 0

    with client_for("fixture", var_dir) as c:
        c.post("/api/closet/sample")
        prof = c.get("/api/profile").json()
        assert prof["materials"] == {"love": [], "avoid": []} and prof["materials_owned"]["wool"] == 3, prof["materials_owned"]
        assert c.put("/api/profile", json={"materials": {"avoid": ["velvet"]}}).status_code == 422
        prof = c.put("/api/profile", json={"materials": {"love": ["cotton", "wool"], "avoid": ["wool"]}}).json()
        assert prof["materials"] == {"love": ["cotton"], "avoid": ["wool"]}, "a fabric can't be loved and avoided"

        # Most of the sample closet is cotton: without a preference look A is cotton, avoiding it moves A to wool.
        by_id = {i["id"]: i for i in c.get("/api/wardrobe").json()}
        core = lambda look: [by_id[i]["tags"] for i in look["item_ids"] if by_id[i]["tags"]["category"] != "outerwear"]  # noqa: E731
        c.put("/api/profile", json={"materials": {"love": [], "avoid": []}})
        plain = c.post("/api/plan", json={"fresh": True}).json()
        assert any("cotton" in t["material_guess"] for t in core(plain["looks"][0])), core(plain["looks"][0])
        c.put("/api/profile", json={"materials": {"avoid": ["cotton"]}})
        plan = c.post("/api/plan", json={"fresh": True}).json()
        assert not any("cotton" in t["material_guess"] for t in core(plan["looks"][0])), core(plan["looks"][0])
        assert plan["trace"]["scores"][0]["material"] < 0, "the cotton field jacket is the only layer: it costs, but stays"

        # The preference is part of the plan's basis, so a plan made ahead before it changed isn't reused.
        from server.main import C, today_local
        before = C().planning.basis(today_local())
        c.put("/api/profile", json={"materials": {"love": [], "avoid": []}})
        assert C().planning.basis(today_local()) != before


def test_final_checks(var_dir: Path) -> None:
    """Found by the pre-deploy stress run: visitors writing the same cache entry at once, calendar files with
    unreadable times, oversized input, and picture redraws the spend cap didn't count."""
    import threading
    from datetime import date as d

    from closet import tools
    from server.cache import Cache

    # Many visitors loading the sample closet at once all write the same cache keys.
    cache, errors = Cache(var_dir / "race"), []

    def put(n: int) -> None:
        try:
            for _ in range(20):
                cache.put("tags", "same", {"n": n, "pad": "x" * 2000})
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    threads = [threading.Thread(target=put, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and cache.get("tags", "same")["pad"] == "x" * 2000, errors[:1]
    assert not list((var_dir / "race" / "tags").glob("*.tmp")), "no temp files left behind"

    # An event with an unreadable time is skipped; the rest of the calendar still works.
    stamp = d.today().strftime("%Y%m%d")
    ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART:" + stamp + "T999999\r\nSUMMARY:Broken\r\nEND:VEVENT\r\n"
           "BEGIN:VEVENT\r\nDTSTART:" + stamp + "\r\nRRULE:FREQ=WEEKLY;UNTIL=garbage\r\nSUMMARY:Bad rule\r\nEND:VEVENT\r\n"
           "BEGIN:VEVENT\r\nDTSTART:" + stamp + "T190000\r\nSUMMARY:Dinner\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n").encode()
    assert {e["title"] for e in tools.ics_events(ics, d.today())} == {"Bad rule", "Dinner"}
    only_bad = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART:" + stamp + "T999999\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n").encode()
    assert tools.ics_count(only_bad) == 0

    # A provider error that echoes a key never reaches the app; plain text about "LLMs" is left alone.
    os.environ["MODEL_API_KEY"] = "LLM|1234567890|abcdefghijklmnop"
    try:
        msg = config.redact("401: bad key LLM|1234567890|abcdefghijklmnop, also b10_abcdefghijklmnop")
        assert "abcdefghijklmnop" not in msg and msg.count("[REDACTED]") == 2, msg
        assert config.redact("LLMs are hard") == "LLMs are hard"
    finally:
        os.environ["MODEL_API_KEY"] = "offline-tests"

    with client_for("fixture", var_dir / "limits") as c:
        h = c.get("/api/ping").headers
        assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY", dict(h)
        assert "frame-ancestors 'none'" in h["content-security-policy"] and h["referrer-policy"] == "same-origin"
        c.post("/api/closet/sample")
        r = c.post("/api/profile/calendar", files={"file": ("c.ics", ics, "text/calendar")})
        assert r.status_code == 200 and r.json()["events"] == 2, r.text
        c.put("/api/profile", json={"calendar": "ics"})
        assert c.get("/api/occasions").status_code == 200 and c.post("/api/plan", json={"fresh": True}).status_code == 200
        assert c.post("/api/profile/calendar", files={"file": ("c.ics", only_bad, "text/calendar")}).status_code == 422

        # Oversized or out-of-range input is a 4xx before it reaches a prompt or the database.
        plan = c.post("/api/plan", json={}).json()
        item = c.get("/api/wardrobe").json()[0]
        assert c.post("/api/plan", content=b" " * (2 * 2**20), headers={"content-type": "application/json"}).status_code == 413
        for path, body in [("/api/plan", {"notes": "x" * 501}), ("/api/plan", {"lat": 400, "lon": 0}),
                           (f"/api/plans/{plan['id']}/wear", {"look": -1}),
                           ("/api/checkins", {"temperature": "cold", "feeling": "good", "tags": ["x"] * 21}),
                           ("/api/thrift", {"piece": {"name": "n" * 200}}), ("/api/thrift/example", {"name": "n" * 200}),
                           ("/api/preferences", {"text": "fine", "applies_when": "w" * 500})]:
            assert c.post(path, json=body).status_code == 422, (path, str(body)[:40])
        assert c.get(f"/api/plans/{plan['id']}/touches?look=-1").status_code == 422
        assert c.patch(f"/api/wardrobe/{item['id']}", json={"warmth": 9}).status_code == 422
        assert c.patch(f"/api/wardrobe/{item['id']}", json={"fit": "f" * 300}).status_code == 422
        assert c.patch(f"/api/wardrobe/{item['id']}", json={"warmth": 2}).status_code == 200

        # Thrift never suggests buying a fabric they won't wear (the rule finder used to offer a wool overcoat).
        assert "Wool overcoat" in [p["name"] for p in c.post("/api/gaps", json={"fresh": True}).json()["pieces"]]
        c.put("/api/profile", json={"materials": {"avoid": ["wool"]}})
        names = [p["name"] for p in c.post("/api/gaps", json={"fresh": True}).json()["pieces"]]
        assert names and not any("wool" in n.lower() or "merino" in n.lower() for n in names), names

        # Planning for an interview suits the interview first: the 400-day jeans used to win look A on rescue alone.
        p = c.post("/api/occasions/plan", json={"event": {"title": "Job interview at a bank", "start": "10:00"}, "fresh": True}).json()
        core = [i["tags"] for i in p["looks"][0]["items"] if i["tags"]["category"] in ("top", "bottom")]
        assert all(t["formality"] != "casual" for t in core), [t["subtype"] for t in core]

    # A redraw after a tag edit, or on request, counts against the cap like any paid call.
    os.environ.update({"MONSTER_CLOSET_DAILY_CALLS": "1", "MONSTER_CLOSETS": "device"})
    try:
        with client_for("live", var_dir / "redraw") as c:
            c.post("/api/closet/sample")
            a, b = c.get("/api/wardrobe").json()[:2]
            assert c.patch(f"/api/wardrobe/{a['id']}", json={"primary_color": "navy"}).status_code == 200
            assert c.get("/api/health").json()["budget_left"] == 0, "the first redraw was counted"
            assert c.patch(f"/api/wardrobe/{b['id']}", json={"primary_color": "navy"}).status_code == 200, "the edit still saves"
            note = json.loads((main.app.state.products.dir / f"{b['id']}.json").read_text())
            assert "limit" in note["reason"], note
            c.post("/api/products")
            assert b["id"] not in main.app.state.products._tasks, "and POST /api/products can't redraw it for free"
            assert c.post(f"/api/wardrobe/{b['id']}/photo", json={"use": "redraw"}).status_code == 429
    finally:
        for k in ("MONSTER_CLOSET_DAILY_CALLS", "MONSTER_CLOSETS"):
            os.environ.pop(k, None)


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
        test_device_closets(tmp / "devices", run_dir)
        test_sample_closet_and_prebuild(tmp / "sample")
        test_yesterday_question(tmp / "yesterday")
        test_same_photo_pairs(tmp / "pairs")
        test_taste(tmp / "taste")
        test_scoring()
        test_styles(tmp / "styles")
        test_products(tmp / "products")
        test_occasions(tmp / "occasions")
        test_deploy(tmp / "deploy")
        test_layering(tmp / "layering")
        test_inside_labels()
        test_corrections(tmp / "corrections")
        test_hardening(tmp / "hardening")
        test_scan_fixes(tmp / "scanfix")
        test_round_two(tmp / "round2")
        test_materials(tmp / "materials")
        test_final_checks(tmp / "final")
        print("OK: fixture mode, seeding, tag fixes, caching, dedupe, planning, wear, check-ins, the agent loop, gap finder, try-on, layered try-on, getting started, finishing touches, colour reads, "
              "cross-photo duplicates, per-device closets, the sample closet, plans made ahead, the morning wear question, the taste model, outfit scoring, style archetypes, product shots, occasions, calendar links, the spend cap, app serving, layer occlusion, item corrections, the public-deploy hardening, the scan fixes and the pre-deploy stress fixes all behave.")
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main_()
