"""FastAPI app. Run from the repo root:

    uvicorn server.main:app --reload                      # fixture mode (default): no API calls
    MONSTER_MODE=live uvicorn server.main:app --reload    # live: SAM 3.1 + Muse Spark, cached

Interactive docs at http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ValidationError

from closet import config
from closet.schema import Garment

from . import settings as settings_mod
from .cache import Cache
from .pipeline import FixtureMissing, Pipeline
from .planning import Planning, today_local
from .store import Store

MAX_PHOTOS = 10
MAX_PHOTO_BYTES = 25 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


class ItemOut(BaseModel):
    id: str
    cutout_url: str
    source: str
    scan_id: str
    created_at: str
    confidence: float | None
    is_garment: bool
    user_edited: bool
    wear_count: int
    last_worn: str | None
    tags: Garment | None
    tag_error: str | None


class ScanOut(BaseModel):
    id: str
    created_at: str
    mode: str
    seconds: float
    photos: int
    cached_photos: int
    replayed: bool
    dropped: list[dict[str, Any]]
    items: list[ItemOut]


class SeedIn(BaseModel):
    run: str  # a spike output folder under out/, e.g. "out/20261027-162912"


class PlanIn(BaseModel):
    day: date | None = None  # default: today
    notes: str = ""  # e.g. "nothing black, dinner moved inside"
    lat: float | None = None
    lon: float | None = None
    fresh: bool = False  # ignore the cached plan for identical inputs


class WearIn(BaseModel):
    look: int = 0
    day: date | None = None


class CheckinIn(BaseModel):
    day: date | None = None
    plan_id: str | None = None
    temperature: Literal["cold", "just_right", "warm"]
    feeling: Literal["meh", "fine", "good", "iconic"]
    tags: list[str] = []  # e.g. ["compliments", "rained on"]
    note: str = ""  # free text, e.g. a voice transcript


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = settings_mod.load()
    cache = Cache(s.cache_dir)
    store = Store(s.db_path)
    app.state.settings, app.state.store = s, store
    app.state.pipeline = Pipeline(s, cache, store)
    app.state.planning = Planning(s, cache, store)
    yield


app = FastAPI(title="Monster in the Closet API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _item_out(d: dict) -> ItemOut:
    return ItemOut(**{k: v for k, v in d.items() if k in ItemOut.model_fields and k != "cutout_url"},
                   cutout_url=f"/api/cutouts/{d['id']}.png")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """No front end yet: send the browser to the interactive API docs."""
    return RedirectResponse("/docs")


@app.get("/api/health")
def health() -> dict:
    s = app.state.settings
    return {"ok": True, "mode": s.mode, "tag_model": config.TAG_MODEL[config.TAG_PROVIDER], **app.state.store.counts()}


@app.post("/api/scans", response_model=ScanOut)
async def create_scan(photos: list[UploadFile] = File(..., description="1-10 flat-lay photos, 4-8 items each")) -> ScanOut:
    if not 1 <= len(photos) <= MAX_PHOTOS:
        raise HTTPException(422, f"Send 1-{MAX_PHOTOS} photos per scan.")
    batch = []
    for f in photos:
        data = await f.read()
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(413, f"{f.filename} is over {MAX_PHOTO_BYTES // 2**20} MB.")
        if f.content_type not in PHOTO_TYPES and not (f.filename or "").lower().endswith((".heic", ".heif")):
            raise HTTPException(415, f"{f.filename}: send JPEG, PNG, WebP or HEIC photos.")
        batch.append((f.filename or f"photo{len(batch)}", data))
    try:
        record = await app.state.pipeline.run_scan(batch)
    except FixtureMissing as e:
        raise HTTPException(409, str(e))
    store = app.state.store
    items = [store.get_item(i) for i in record["item_ids"]]
    return ScanOut(**{k: v for k, v in record.items() if k != "item_ids"}, items=[_item_out(i) for i in items if i])


@app.get("/api/scans/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: str) -> ScanOut:
    store = app.state.store
    record = store.get_scan(scan_id)
    if not record:
        raise HTTPException(404, "No such scan.")
    items = [store.get_item(i) for i in record["item_ids"]]
    return ScanOut(**{k: v for k, v in record.items() if k != "item_ids"}, items=[_item_out(i) for i in items if i])


@app.get("/api/wardrobe", response_model=list[ItemOut])
def list_wardrobe(category: str | None = None, include_hidden: bool = False) -> list[ItemOut]:
    """Garments in the wardrobe. Cutouts tagged as not-a-garment are hidden unless include_hidden."""
    return [_item_out(i) for i in app.state.store.list_items(include_hidden, category)]


@app.get("/api/wardrobe/{item_id}", response_model=ItemOut)
def get_item(item_id: str) -> ItemOut:
    item = app.state.store.get_item(item_id)
    if not item:
        raise HTTPException(404, "No such item.")
    return _item_out(item)


@app.patch("/api/wardrobe/{item_id}", response_model=ItemOut)
def fix_tags(item_id: str, changes: dict[str, Any]) -> ItemOut:
    """The 'Fix tags' button: merge the user's corrections into the item's tags."""
    store = app.state.store
    item = store.get_item(item_id)
    if not item:
        raise HTTPException(404, "No such item.")
    unknown = set(changes) - set(Garment.model_fields)
    if unknown:
        raise HTTPException(422, f"Unknown tag fields: {sorted(unknown)}")
    if not item["tags"] and set(changes) != set(Garment.model_fields):
        raise HTTPException(422, "This item has no tags yet; send every Garment field.")
    try:
        merged = Garment.model_validate({**(item["tags"] or {}), **changes})
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False))
    store.update_tags(item_id, merged)
    return _item_out(store.get_item(item_id))


@app.delete("/api/wardrobe/{item_id}", status_code=204)
def delete_item(item_id: str) -> None:
    if not app.state.store.delete_item(item_id):
        raise HTTPException(404, "No such item.")
    (app.state.settings.cutout_dir / f"{item_id}.png").unlink(missing_ok=True)


@app.get("/api/cutouts/{item_id}.png")
def cutout(item_id: str) -> FileResponse:
    if not item_id.isalnum():
        raise HTTPException(404, "No such cutout.")
    path = app.state.settings.cutout_dir / f"{item_id}.png"
    if not path.exists():
        raise HTTPException(404, "No such cutout.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=31536000, immutable"})


def _plan_out(record: dict) -> dict:
    """A stored plan with each look's items expanded, ready for the Today screen."""
    store = app.state.store
    out = {k: record[k] for k in ("id", "day", "created_at", "source", "notes", "weather", "calendar")}
    out["trace"] = {k: v for k, v in record["trace"].items() if k in
                    ("provider", "model", "tool_calls", "repairs", "seconds", "tokens_in", "tokens_out", "cached", "failures")}
    plan = record["plan"]
    out["weather_summary"], out["plans_summary"] = plan["weather_summary"], plan["plans_summary"]
    out["looks"] = []
    for look in plan["looks"]:
        items = [store.get_item(i) for i in look["item_ids"]]
        out["looks"].append({**look, "items": [_item_out(i).model_dump() for i in items if i]})
    return out


@app.post("/api/plan")
async def make_plan(body: PlanIn | None = None) -> dict:
    """The morning pick: three looks from the user's own clothes, for today's weather and plans."""
    body = body or PlanIn()
    try:
        record = await app.state.planning.make_plan(body.day or today_local(), body.notes, body.lat, body.lon, body.fresh)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return _plan_out(record)


@app.get("/api/plan")
def latest_plan(day: date | None = None) -> dict:
    record = app.state.store.get_plan(day=(day or today_local()).isoformat())
    if not record:
        raise HTTPException(404, "No plan for that day yet; POST /api/plan.")
    return _plan_out(record)


@app.post("/api/plans/{plan_id}/wear")
def wear(plan_id: str, body: WearIn | None = None) -> dict:
    """'Wear this': log the look, report rescued pieces, closet-alive change and the oni's mood."""
    body = body or WearIn()
    try:
        return app.state.planning.wear(plan_id, body.look, body.day or today_local())
    except KeyError as e:
        raise HTTPException(404, str(e))
    except IndexError as e:
        raise HTTPException(422, str(e))


@app.post("/api/checkins")
async def checkin(body: CheckinIn) -> dict:
    """Evening check-in: how the outfit went. The oni replies and may learn a preference."""
    answers = body.model_dump(include={"temperature", "feeling", "tags", "note"})
    return await app.state.planning.checkin(body.day or today_local(), answers, body.plan_id)


@app.get("/api/preferences")
def preferences() -> list[dict]:
    return app.state.store.list_preferences()


@app.delete("/api/preferences/{pref_id}", status_code=204)
def forget_preference(pref_id: int) -> None:
    if not app.state.store.delete_preference(pref_id):
        raise HTTPException(404, "No such preference.")


@app.get("/api/oni")
def oni(day: date | None = None) -> dict:
    """The oni's mood and the closet-alive meter, for the Today header."""
    return app.state.planning.oni(day or today_local())


@app.post("/api/dev/seed")
def seed(body: SeedIn) -> dict:
    """Import a spike run (out/<run>) as wardrobe items and fixtures. Local development only."""
    out_root = (config.ROOT / "out").resolve()
    run_dir = (config.ROOT / body.run).resolve()
    if out_root not in run_dir.parents or not (run_dir / "cutouts").is_dir():
        raise HTTPException(422, "run must be a spike output folder under out/ with a cutouts/ folder.")
    return app.state.pipeline.seed_from_run(Path(run_dir))
