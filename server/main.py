"""FastAPI app. Run from the repo root:

    uvicorn server.main:app --reload                      # fixture mode (default): no API calls
    MONSTER_MODE=live uvicorn server.main:app --reload    # live: SAM 3.1 + Muse Spark, cached

Interactive docs at http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ValidationError

from closet import config
from closet.schema import Garment

from . import settings as settings_mod
from .cache import Cache
from .closets import MAIN, SCOPE_KEY, Closet, ClosetMiddleware, Closets, ClosetsFull, current_id
from .pipeline import FixtureMissing
from .planning import today_local
from .examples import Examples

MAX_PHOTOS = 10
MAX_PHOTO_BYTES = 25 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def now_iso() -> str:
    from .store import now
    return now()


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
    worn_estimated: bool = False  # last_worn is the user's estimate, not a logged wear
    tags: Garment | None
    tag_error: str | None


class MergedOut(BaseModel):
    kept: ItemOut
    dropped_id: str
    confidence: float
    reason: str


class ReviewOut(BaseModel):
    a: ItemOut
    b: ItemOut
    checked: bool  # False: no model verdict (fixture mode or a failed call)
    confidence: float | None
    reason: str


class DuplicatesOut(BaseModel):
    merged: list[MergedOut]
    review: list[ReviewOut]
    checked: int


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
    duplicates: DuplicatesOut | None = None  # only on the response to the scan itself


class PairIn(BaseModel):
    a: str
    b: str


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
    app.state.settings, app.state.cache = s, cache
    app.state.closets = Closets(s, cache, int(os.environ.get("MONSTER_MAX_CLOSETS", "200")))
    app.state.examples = Examples(s)  # thrift example photos are generic, so every closet shares them
    yield


app = FastAPI(title="Monster in the Closet API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(ClosetMiddleware)  # added last, so it runs first


def C() -> Closet:
    """The closet this request belongs to (see server/closets.py)."""
    try:
        return app.state.closets.get(current_id())
    except ClosetsFull as e:
        raise HTTPException(503, str(e))


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
    return {"ok": True, "mode": s.mode, "tag_model": config.TAG_MODEL[config.TAG_PROVIDER], **C().store.counts()}


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
        record = await C().pipeline.run_scan(batch)
    except FixtureMissing as e:
        raise HTTPException(409, str(e))
    store = C().store
    items = [store.get_item(i) for i in record["item_ids"]]
    return ScanOut(**{k: v for k, v in record.items() if k not in ("item_ids", "duplicates")},
                   items=[_item_out(i) for i in items if i], duplicates=_dupes_out(record["duplicates"]))


def _dupes_out(d: dict) -> DuplicatesOut:
    store = C().store
    merged = [MergedOut(kept=_item_out(k), dropped_id=m["dropped_id"], confidence=m["confidence"], reason=m["reason"])
              for m in d["merged"] if (k := store.get_item(m["kept_id"]))]
    review = []
    for r in d["review"]:
        a, b = store.get_item(r["a_id"]), store.get_item(r["b_id"])
        if a and b and a["id"] != b["id"]:
            review.append(ReviewOut(a=_item_out(a), b=_item_out(b), checked=r["checked"],
                                    confidence=r["confidence"], reason=r["reason"]))
    return DuplicatesOut(merged=merged, review=review, checked=d["checked"])


@app.post("/api/wardrobe/duplicates/check", response_model=DuplicatesOut)
async def check_duplicates() -> DuplicatesOut:
    """Look for the same garment scanned more than once. Confident matches merge; unsure ones come back for review."""
    return _dupes_out(await C().pipeline.dedupe.check())


@app.post("/api/wardrobe/duplicates/merge", response_model=ItemOut)
def merge_duplicates(body: PairIn) -> ItemOut:
    """The user confirmed two items are one garment: keep the better cutout, fold in the other's wear history."""
    store = C().store
    a, b = store.get_item(body.a), store.get_item(body.b)
    if not a or not b:
        raise HTTPException(404, "No such item.")
    if a["id"] == b["id"]:
        return _item_out(a)
    keep, drop = C().pipeline.dedupe.keep_drop(a, b)
    store.merge_items(keep["id"], drop["id"])
    return _item_out(store.get_item(keep["id"]))


@app.post("/api/wardrobe/duplicates/distinct", status_code=204)
def not_duplicates(body: PairIn) -> None:
    """The user says these are two different items: never suggest the pair again."""
    C().store.mark_distinct(body.a, body.b)


@app.get("/api/scans/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: str) -> ScanOut:
    store = C().store
    record = store.get_scan(scan_id)
    if not record:
        raise HTTPException(404, "No such scan.")
    items = [store.get_item(i) for i in record["item_ids"]]
    return ScanOut(**{k: v for k, v in record.items() if k != "item_ids"}, items=[_item_out(i) for i in items if i])


@app.get("/api/wardrobe", response_model=list[ItemOut])
def list_wardrobe(category: str | None = None, include_hidden: bool = False) -> list[ItemOut]:
    """Garments in the wardrobe. Cutouts tagged as not-a-garment are hidden unless include_hidden."""
    return [_item_out(i) for i in C().store.list_items(include_hidden, category)]


class LastWornIn(BaseModel):
    id: str
    days_ago: int | None  # None clears the estimate


class LastWornBatchIn(BaseModel):
    items: list[LastWornIn]


@app.post("/api/wardrobe/last-worn", response_model=list[ItemOut])
def set_last_worn(body: LastWornBatchIn) -> list[ItemOut]:
    """Backfill wear history: "when did you last wear this?" for one or many items. Without it a new
    closet looks freshly worn, so nothing can be rescued and the closet-alive % means nothing."""
    store, today = C().store, today_local()
    out = []
    for e in body.items[:200]:
        if e.days_ago is not None and not 0 <= e.days_ago <= 3650:
            raise HTTPException(422, "days_ago must be 0-3650")
        day = None if e.days_ago is None else (today - timedelta(days=e.days_ago)).isoformat()
        if not store.set_last_worn_estimate(e.id, day):
            raise HTTPException(404, f"No such item: {e.id}")
        out.append(_item_out(store.get_item(e.id)))
    return out


@app.get("/api/wardrobe/{item_id}", response_model=ItemOut)
def get_item(item_id: str) -> ItemOut:
    item = C().store.get_item(item_id)
    if not item:
        raise HTTPException(404, "No such item.")
    return _item_out(item)


@app.patch("/api/wardrobe/{item_id}", response_model=ItemOut)
def fix_tags(item_id: str, changes: dict[str, Any]) -> ItemOut:
    """The 'Fix tags' button: merge the user's corrections into the item's tags."""
    store = C().store
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
    if not C().store.delete_item(item_id):
        raise HTTPException(404, "No such item.")
    (C().settings.cutout_dir / f"{item_id}.png").unlink(missing_ok=True)


@app.get("/api/cutouts/{item_id}.png")
def cutout(item_id: str) -> FileResponse:
    if not item_id.isalnum():
        raise HTTPException(404, "No such cutout.")
    path = C().settings.cutout_dir / f"{item_id}.png"
    if not path.exists():
        raise HTTPException(404, "No such cutout.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=31536000, immutable"})


def _plan_out(record: dict) -> dict:
    """A stored plan with each look's items expanded, ready for the Today screen."""
    store = C().store
    out = {k: record[k] for k in ("id", "day", "created_at", "source", "notes", "weather", "calendar")}
    out["trace"] = {k: v for k, v in record["trace"].items() if k in
                    ("provider", "model", "tool_calls", "repairs", "seconds", "tokens_in", "tokens_out", "cached", "failures", "steps", "prebuilt")}
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
        record = await C().planning.make_plan(body.day or today_local(), body.notes, body.lat, body.lon, body.fresh)
    except ValueError as e:
        raise HTTPException(409, str(e))
    C().planning.mark_seen(record)
    return _plan_out(record)


@app.get("/api/plan")
def latest_plan(day: date | None = None) -> dict:
    record = C().planning.current_plan(day or today_local())
    if not record:
        raise HTTPException(404, "No plan for that day yet; POST /api/plan.")
    C().planning.mark_seen(record)
    return _plan_out(record)


class YesterdayIn(BaseModel):
    look: int | None = None  # the look they wore, or None for "no, something else"


@app.get("/api/yesterday")
def yesterday() -> dict:
    """The morning question: did yesterday's pick make it out? `plan` is null when there's nothing to ask
    (no plan was shown yesterday, a wear was already logged, or it was answered)."""
    record = C().planning.yesterday(today_local())
    return {"plan": _plan_out(record) if record else None}


@app.post("/api/yesterday")
def answer_yesterday(body: YesterdayIn, background: BackgroundTasks) -> dict:
    """One tap instead of logging: wear yesterday's look (with rescues counted), or just stop asking."""
    try:
        worn = C().planning.answer_yesterday(today_local(), body.look)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except IndexError as e:
        raise HTTPException(422, str(e))
    if worn:
        background.add_task(C().planning.prebuild, today_local() + timedelta(days=1))
    return {"worn": worn}


@app.post("/api/plans/{plan_id}/wear")
def wear(plan_id: str, background: BackgroundTasks, body: WearIn | None = None) -> dict:
    """'Wear this': log the look, report rescued pieces, closet-alive change and the oni's mood.
    Tomorrow's plan starts building right away, so tomorrow morning opens on it."""
    body = body or WearIn()
    day = body.day or today_local()
    try:
        out = C().planning.wear(plan_id, body.look, day)
        background.add_task(C().planning.prebuild, day + timedelta(days=1))
        return out
    except KeyError as e:
        raise HTTPException(404, str(e))
    except IndexError as e:
        raise HTTPException(422, str(e))


@app.post("/api/checkins")
async def checkin(body: CheckinIn, background: BackgroundTasks) -> dict:
    """Evening check-in: how the outfit went. The oni replies and may learn a preference, and
    tomorrow's plan is rebuilt with what it learned."""
    answers = body.model_dump(include={"temperature", "feeling", "tags", "note"})
    day = body.day or today_local()
    out = await C().planning.checkin(day, answers, body.plan_id)
    background.add_task(C().planning.prebuild, day + timedelta(days=1))
    return out


@app.get("/api/preferences")
def preferences() -> list[dict]:
    return C().store.list_preferences()


@app.delete("/api/preferences/{pref_id}", status_code=204)
def forget_preference(pref_id: int) -> None:
    if not C().store.delete_preference(pref_id):
        raise HTTPException(404, "No such preference.")


class GapsIn(BaseModel):
    fresh: bool = False


class ThriftIn(BaseModel):
    piece: dict[str, Any]  # a piece from POST /api/gaps
    status: Literal["watching", "dismissed"] = "watching"


class ThriftStatusIn(BaseModel):
    status: Literal["watching", "found", "dismissed"]


def _with_pairs(piece: dict) -> dict:
    """A gap piece with the closet items it pairs with expanded (for the 'goes with' row),
    plus its example photo if one has been made."""
    store = C().store
    items = [store.get_item(i) for i in piece.get("pairs_with", [])]
    return {**piece, "pairs": [_item_out(i).model_dump() for i in items if i],
            "example_url": app.state.examples.url(piece) if piece.get("name") else None}


class ExampleIn(BaseModel):
    name: str
    colors: list[str] = []
    category: str = ""


@app.post("/api/thrift/example")
async def thrift_example(body: ExampleIn) -> dict:
    """An AI example photo of a gap piece (Muse Image, ~25s the first time, then cached)."""
    return await app.state.examples.ensure(body.model_dump())


@app.get("/api/examples/{name}.jpg")
def example_file(name: str) -> FileResponse:
    path = app.state.examples.dir / f"{name}.jpg"
    if not name.isalnum() or not path.exists():
        raise HTTPException(404, "No such example.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.post("/api/gaps")
async def find_gaps(body: GapsIn | None = None) -> dict:
    """The few pieces that would unlock the most outfits with what you own, with second-hand tips."""
    try:
        record = await C().planning.gaps(today_local(), (body or GapsIn()).fresh)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {**record, "pieces": [_with_pairs(p) for p in record["pieces"]]}


@app.get("/api/thrift")
def thrift_list() -> list[dict]:
    """Pieces the user is watching for or has found (dismissed ones are hidden)."""
    return [{**t, "piece": _with_pairs(t["piece"])} for t in C().store.list_thrift() if t["status"] != "dismissed"]


@app.post("/api/thrift")
def add_thrift(body: ThriftIn) -> dict:
    if not body.piece.get("name"):
        raise HTTPException(422, "piece needs a name")
    piece = {k: v for k, v in body.piece.items() if k != "pairs"}
    return {"id": C().store.add_thrift(piece, body.status)}


@app.patch("/api/thrift/{thrift_id}", status_code=204)
def update_thrift(thrift_id: int, body: ThriftStatusIn) -> None:
    if not C().store.set_thrift_status(thrift_id, body.status):
        raise HTTPException(404, "Not on the thrift list.")


@app.delete("/api/thrift/{thrift_id}", status_code=204)
def remove_thrift(thrift_id: int) -> None:
    if not C().store.delete_thrift(thrift_id):
        raise HTTPException(404, "Not on the thrift list.")


class TryOnProfileIn(BaseModel):
    mode: Literal["mannequin", "photo", "flat"]
    body: dict[str, Any] | None = None  # BodyProfile fields, for the mannequin


class TryOnIn(BaseModel):
    plan_id: str
    look: int = 0


@app.get("/api/tryon/profile")
def tryon_profile() -> dict:
    """Who wears the try-on: mannequin details, whether a checked photo is on file, and if it's ready."""
    return C().tryon.public_profile()


@app.put("/api/tryon/profile")
def set_tryon_profile(body: TryOnProfileIn) -> dict:
    try:
        return C().tryon.set_profile(body.mode, body.body)
    except (ValueError, ValidationError) as e:
        raise HTTPException(422, str(e))


@app.post("/api/tryon/photo")
async def upload_person_photo(photo: UploadFile = File(...), consent: bool = Form(False)) -> dict:
    """The opt-in face version. Needs consent; the photo is checked and only stored if it passes."""
    data = await photo.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "That photo is too large.")
    try:
        return await C().tryon.set_photo(data, consent)
    except ValueError as e:
        raise HTTPException(422 if "confirm" in str(e) else 409, str(e))


@app.delete("/api/tryon/photo")
def delete_person_photo() -> dict:
    """One tap: the photo and every render made from it are deleted."""
    return {"renders_deleted": C().tryon.delete_photo()}


@app.post("/api/tryon")
async def start_tryon(body: TryOnIn) -> dict:  # async: the render job is scheduled on this event loop
    """Start (or reuse) a render of one look. Poll GET /api/tryon/jobs/{id} until status is done."""
    try:
        return C().tryon.start(body.plan_id, body.look)
    except KeyError as e:
        raise HTTPException(404, str(e).strip("'\""))
    except IndexError as e:
        raise HTTPException(422, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


class LayersIn(BaseModel):
    item_ids: list[str]
    prepare: bool = True  # start making missing layers (live mode only)


@app.post("/api/tryon/layers")
async def tryon_layers(body: LayersIn) -> dict:
    """Layered try-on for the mannequin: the base image and one layer per garment, with their states.
    The app stacks ready layers itself, so swapping outfits needs no new render. Poll until ready."""
    p = C().tryon.profile()
    if p["mode"] != "mannequin" or not p["body"]:
        raise HTTPException(409, "Layered try-on needs the mannequin set up.")
    return C().layers.status(p["body"], body.item_ids[:60], prepare=body.prepare)


@app.get("/api/layers/{base_key}/{name}.png")
def layer_file(base_key: str, name: str) -> FileResponse:
    path = C().layers.root / base_key / f"{name}.png"
    if not (base_key.isalnum() and name.isalnum()) or not path.exists():
        raise HTTPException(404, "No such layer.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.get("/api/tryon/flatlay")
def tryon_flatlay(plan_id: str, look: int = 0) -> dict:
    """The always-exact flat-lay of a look, without starting a render."""
    try:
        _, items = C().tryon._look(plan_id, look)
    except KeyError as e:
        raise HTTPException(404, str(e).strip("'\""))
    except IndexError as e:
        raise HTTPException(422, str(e))
    return {"url": C().tryon.flatlay_url([i["id"] for i in items])}


@app.get("/api/tryon/jobs/{job_id}")
def tryon_job(job_id: str) -> dict:
    job = C().tryon.jobs.get(job_id)
    if not job:
        raise HTTPException(404, "No such try-on job (the server may have restarted).")
    return job


@app.get("/api/touch-examples/{play}.jpg")
def touch_example(play: str) -> FileResponse:
    """The example picture for a finishing-touch play: the same for everyone, so it caches for a week."""
    from .planning import TOUCH_EXAMPLES
    path = TOUCH_EXAMPLES / f"{play}.jpg"
    if not play.replace("_", "").isalpha() or not path.exists():
        raise HTTPException(404, "No such example.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800"})


@app.get("/api/renders/{name}.png")
def render_file(name: str) -> FileResponse:
    if not name.replace("-", "").isalnum():
        raise HTTPException(404, "No such render.")
    path = C().tryon.render_dir / f"{name}.png"
    if not path.exists():
        raise HTTPException(404, "No such render.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


class Location(BaseModel):
    name: str
    lat: float
    lon: float


class ProfileIn(BaseModel):
    location: Location | None = None
    calendar: Literal["none", "sample", "ics"] | None = None
    onboarded: bool | None = None


class PreferenceIn(BaseModel):
    text: str
    applies_when: str | None = None


MAX_ICS_BYTES = 2 * 1024 * 1024
_geocode_cache: dict[str, list[dict]] = {}


def _profile_out() -> dict:
    planning = C().planning
    p = planning.profile()
    counts = {}
    for i in C().store.list_items():
        if i["tags"]:
            counts[i["tags"]["category"]] = counts.get(i["tags"]["category"], 0) + 1
    return {**p, "wardrobe": counts, "can_plan": bool(counts.get("dress") or (counts.get("top") and counts.get("bottom"))),
            "tryon": C().tryon.public_profile()}


class ClosetIn(BaseModel):
    id: str


@app.get("/api/closet")
def closet_info() -> dict:
    """Which closet this browser is on. `id` is the key to it: only show it to its owner."""
    per_device = app.state.settings.per_device
    return {"per_device": per_device, "id": current_id() if per_device else MAIN}


@app.post("/api/closet/open")
def open_closet(body: ClosetIn, request: Request) -> dict:
    """Move this browser to a closet it was given a link to (the owner's other device)."""
    if not app.state.settings.per_device:
        raise HTTPException(409, "There is only one closet here.")
    if not app.state.closets.exists(body.id):
        raise HTTPException(404, "That closet link doesn't work any more.")
    request.scope[SCOPE_KEY]["cookie"] = body.id
    return {"id": body.id}


@app.post("/api/closet/sample")
def load_sample_closet() -> dict:
    """Fill this closet with the sample closet: 9 made-up garments, some long forgotten."""
    return C().pipeline.load_sample(today_local())


@app.post("/api/closet/new")
def new_closet(request: Request) -> dict:
    """Start over in a fresh, empty closet. The old one stays reachable through its link."""
    if not app.state.settings.per_device:
        raise HTTPException(409, "There is only one closet here.")
    new = app.state.closets.new_id()
    request.scope[SCOPE_KEY]["cookie"] = new
    return {"id": new}


@app.get("/api/profile")
def get_profile() -> dict:
    """Getting-started state: location, calendar, whether onboarding is done, and closet counts."""
    return _profile_out()


@app.put("/api/profile")
def put_profile(body: ProfileIn) -> dict:
    if body.calendar == "ics" and not C().planning.calendar_path.exists():
        raise HTTPException(422, "Upload a calendar file first.")
    changes = body.model_dump(exclude_none=True)
    if changes.get("onboarded"):
        changes["onboarded_at"] = now_iso()
    C().planning.update_profile(**changes)
    return _profile_out()


@app.post("/api/profile/calendar")
async def upload_calendar(file: UploadFile = File(...)) -> dict:
    """An .ics export (Google or Apple Calendar). Only event titles, times and places are read."""
    data = await file.read()
    if len(data) > MAX_ICS_BYTES:
        raise HTTPException(413, "That calendar file is over 2 MB.")
    from closet import tools
    events = tools._parse_ics(data.decode("utf-8", errors="replace"))
    if not events:
        raise HTTPException(422, "No events found. Export an .ics file from your calendar app (unzip it first if it came as a .zip).")
    path = C().planning.calendar_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    C().planning.update_profile(calendar="ics", calendar_name=file.filename or "calendar.ics")
    today = C().planning.calendar(today_local())
    return {"events": len(events), "today": today["events"], "profile": _profile_out()}


@app.delete("/api/profile/calendar")
def delete_calendar() -> dict:
    C().planning.calendar_path.unlink(missing_ok=True)
    C().planning.store.put_setting("profile", {**C().planning.profile(), "calendar": "none", "calendar_name": None})
    return _profile_out()


@app.get("/api/geocode")
async def geocode(q: str) -> list[dict]:
    """City search for the weather location (Open-Meteo geocoding: free, no key)."""
    q = q.strip()
    if len(q) < 2:
        return []
    if q.lower() in _geocode_cache:
        return _geocode_cache[q.lower()]
    import httpx
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get("https://geocoding-api.open-meteo.com/v1/search",
                                 params={"name": q, "count": 6, "language": "en", "format": "json"})
            r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(502, "City search is unavailable right now.")
    out = [{"name": ", ".join(x for x in (g.get("name"), g.get("admin1"), g.get("country")) if x),
            "lat": round(g["latitude"], 4), "lon": round(g["longitude"], 4)} for g in r.json().get("results", [])]
    _geocode_cache[q.lower()] = out
    return out


@app.post("/api/preferences")
def add_preference(body: PreferenceIn) -> dict:
    """A preference the user states directly (getting started), stored like learned ones."""
    text = body.text.strip()
    if not 3 <= len(text) <= 200:
        raise HTTPException(422, "Preferences are 3-200 characters.")
    return {"new": C().store.add_preference(text, body.applies_when, None)}


class StyleIn(BaseModel):
    basics: list[str] | None = None  # keys from GET /api/style catalog
    skip: list[str] | None = None  # playbook ids the user said aren't their style


@app.get("/api/style")
def get_style() -> dict:
    """The basics checklist (with its catalog) and skipped touches."""
    from closet import styling
    return {**C().planning.style(),
            "catalog": [{"group": g, "items": [{"key": k, "label": label} for k, label in items]} for g, items in styling.BASICS.items()]}


@app.put("/api/style")
def put_style(body: StyleIn) -> dict:
    C().planning.update_style(body.basics, body.skip)
    return get_style()


@app.get("/api/plans/{plan_id}/touches")
async def look_touches(plan_id: str, look: int = 0) -> dict:
    """Finishing touches for one look: underlayers, accessories and small techniques from the styling
    playbook, using basics the user owns first. Never a shopping suggestion."""
    try:
        return await C().planning.touches(plan_id, look)
    except KeyError as e:
        raise HTTPException(404, str(e).strip("'\""))
    except IndexError as e:
        raise HTTPException(422, str(e))


@app.get("/api/oni")
def oni(day: date | None = None) -> dict:
    """The oni's mood and the closet-alive meter, for the Today header."""
    return C().planning.oni(day or today_local())


@app.post("/api/dev/seed")
def seed(body: SeedIn) -> dict:
    """Import a spike run (out/<run>) as wardrobe items and fixtures. Local development only."""
    out_root = (config.ROOT / "out").resolve()
    run_dir = (config.ROOT / body.run).resolve()
    if out_root not in run_dir.parents or not (run_dir / "cutouts").is_dir():
        raise HTTPException(422, "run must be a spike output folder under out/ with a cutouts/ folder.")
    return C().pipeline.seed_from_run(Path(run_dir))
