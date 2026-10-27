"""FastAPI app. Run from the repo root:

    uvicorn server.main:app --reload                      # fixture mode (default): no API calls
    MONSTER_MODE=live uvicorn server.main:app --reload    # live: SAM 3.1 + Muse Spark, cached

Interactive docs at http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError

from closet import config
from closet.schema import Garment

from . import settings as settings_mod
from .cache import Cache
from .pipeline import FixtureMissing, Pipeline
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = settings_mod.load()
    cache = Cache(s.cache_dir)
    store = Store(s.db_path)
    app.state.settings, app.state.store = s, store
    app.state.pipeline = Pipeline(s, cache, store)
    yield


app = FastAPI(title="Monster in the Closet API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _item_out(d: dict) -> ItemOut:
    return ItemOut(**{k: v for k, v in d.items() if k in ItemOut.model_fields and k != "cutout_url"},
                   cutout_url=f"/api/cutouts/{d['id']}.png")


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


@app.post("/api/dev/seed")
def seed(body: SeedIn) -> dict:
    """Import a spike run (out/<run>) as wardrobe items and fixtures. Local development only."""
    out_root = (config.ROOT / "out").resolve()
    run_dir = (config.ROOT / body.run).resolve()
    if out_root not in run_dir.parents or not (run_dir / "cutouts").is_dir():
        raise HTTPException(422, "run must be a spike output folder under out/ with a cutouts/ folder.")
    return app.state.pipeline.seed_from_run(Path(run_dir))
