"""SQLite wardrobe store: garments, their tags, wear history, and scan records."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from closet.schema import Garment

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,        -- sha256 of the cutout PNG (first 16 hex)
    scan_id     TEXT NOT NULL,
    source      TEXT NOT NULL,           -- photo file name it came from
    created_at  TEXT NOT NULL,
    confidence  REAL,
    tags        TEXT,                    -- Garment JSON, NULL until tagged
    tag_error   TEXT,
    is_garment  INTEGER NOT NULL DEFAULT 1,
    user_edited INTEGER NOT NULL DEFAULT 0,
    wear_count  INTEGER NOT NULL DEFAULT 0,
    last_worn   TEXT
);
CREATE TABLE IF NOT EXISTS scans (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    mode          TEXT NOT NULL,
    seconds       REAL NOT NULL,
    photos        INTEGER NOT NULL,
    cached_photos INTEGER NOT NULL,
    replayed      INTEGER NOT NULL,
    item_ids      TEXT NOT NULL,         -- JSON list
    dropped       TEXT NOT NULL          -- JSON list of {source, reason}
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    # -- items

    def upsert_item(self, item_id: str, scan_id: str, source: str, confidence: float | None,
                    tags: Garment | None, tag_error: str | None) -> None:
        """Insert a scanned garment. A rescan of the same cutout keeps wear history and user edits."""
        tags_json = tags.model_dump_json() if tags else None
        is_garment = int(tags.is_garment) if tags else 1
        with self._lock, self._db:
            self._db.execute(
                """INSERT INTO items (id, scan_id, source, created_at, confidence, tags, tag_error, is_garment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     scan_id = excluded.scan_id,
                     tags = CASE WHEN items.user_edited THEN items.tags ELSE COALESCE(excluded.tags, items.tags) END,
                     tag_error = excluded.tag_error,
                     is_garment = CASE WHEN items.user_edited THEN items.is_garment ELSE excluded.is_garment END""",
                (item_id, scan_id, source, now(), confidence, tags_json, tag_error, is_garment),
            )

    def get_item(self, item_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return _item(row) if row else None

    def list_items(self, include_hidden: bool = False, category: str | None = None) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM items ORDER BY created_at, id").fetchall()
        items = [_item(r) for r in rows]
        if not include_hidden:
            items = [i for i in items if i["is_garment"]]
        if category:
            items = [i for i in items if i["tags"] and i["tags"]["category"] == category]
        return items

    def update_tags(self, item_id: str, tags: Garment) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE items SET tags = ?, is_garment = ?, tag_error = NULL, user_edited = 1 WHERE id = ?",
                (tags.model_dump_json(), int(tags.is_garment), item_id),
            )

    def delete_item(self, item_id: str) -> bool:
        with self._lock, self._db:
            return self._db.execute("DELETE FROM items WHERE id = ?", (item_id,)).rowcount > 0

    # -- scans

    def add_scan(self, scan: dict) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO scans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (scan["id"], scan["created_at"], scan["mode"], scan["seconds"], scan["photos"],
                 scan["cached_photos"], int(scan["replayed"]), json.dumps(scan["item_ids"]), json.dumps(scan["dropped"])),
            )

    def get_scan(self, scan_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["replayed"] = bool(d["replayed"])
        d["item_ids"] = json.loads(d["item_ids"])
        d["dropped"] = json.loads(d["dropped"])
        return d

    def counts(self) -> dict:
        with self._lock:
            items = self._db.execute("SELECT COUNT(*) FROM items WHERE is_garment = 1").fetchone()[0]
            scans = self._db.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        return {"garments": items, "scans": scans}


def _item(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d["tags"]) if d["tags"] else None
    d["is_garment"] = bool(d["is_garment"])
    d["user_edited"] = bool(d["user_edited"])
    return d
