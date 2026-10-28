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
CREATE TABLE IF NOT EXISTS plans (
    id          TEXT PRIMARY KEY,
    day         TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    source      TEXT NOT NULL,           -- agent | rules | cache
    plan        TEXT NOT NULL,           -- OutfitPlan JSON
    trace       TEXT NOT NULL,           -- provider, tool calls, tokens
    weather     TEXT NOT NULL,
    calendar    TEXT NOT NULL,
    notes       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wears (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    day      TEXT NOT NULL,
    item_id  TEXT NOT NULL,
    plan_id  TEXT,
    look     INTEGER
);
CREATE TABLE IF NOT EXISTS checkins (
    id          TEXT PRIMARY KEY,
    day         TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    plan_id     TEXT,
    answers     TEXT NOT NULL,           -- JSON: temperature, feeling, tags, note
    reply       TEXT NOT NULL,
    learned     TEXT                     -- CheckinLearning JSON
);
CREATE TABLE IF NOT EXISTS aliases (
    alias_id    TEXT PRIMARY KEY,        -- a cutout id merged into...
    item_id     TEXT NOT NULL,           -- ...this canonical item
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS distinct_pairs (
    a TEXT NOT NULL,                     -- the user said these two are different items (a < b)
    b TEXT NOT NULL,
    PRIMARY KEY (a, b)
);
CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,             -- e.g. "tryon": mode, body profile, photo check
    value  TEXT NOT NULL                 -- JSON
);
CREATE TABLE IF NOT EXISTS thrift (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL,           -- watching | found | dismissed
    piece       TEXT NOT NULL            -- GapPiece JSON + outfits_unlocked
);
CREATE TABLE IF NOT EXISTS preferences (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    text         TEXT NOT NULL UNIQUE,
    applies_when TEXT,
    checkin_id   TEXT
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
                    tags: Garment | None, tag_error: str | None) -> str:
        """Insert a scanned garment and return its id. A rescan of the same cutout keeps wear history and
        user edits; a cutout already merged into another item returns that item's id untouched."""
        tags_json = tags.model_dump_json() if tags else None
        is_garment = int(tags.is_garment) if tags else 1
        with self._lock, self._db:
            alias = self._db.execute("SELECT item_id FROM aliases WHERE alias_id = ?", (item_id,)).fetchone()
            if alias:
                return alias[0]
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
        return item_id

    def get_item(self, item_id: str) -> dict | None:
        """An item by id, following merges so old plans and scans still resolve."""
        with self._lock:
            row = self._db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                row = self._db.execute(
                    "SELECT items.* FROM aliases JOIN items ON items.id = aliases.item_id WHERE aliases.alias_id = ?",
                    (item_id,)).fetchone()
        return _item(row) if row else None

    # -- duplicates

    def merge_items(self, keep: str, drop: str) -> None:
        """Fold `drop` into `keep`: wear history moves over, and `drop`'s cutout id (plus anything
        already merged into it) becomes an alias so a rescan doesn't bring it back."""
        with self._lock, self._db:
            k = self._db.execute("SELECT wear_count, last_worn FROM items WHERE id = ?", (keep,)).fetchone()
            d = self._db.execute("SELECT wear_count, last_worn FROM items WHERE id = ?", (drop,)).fetchone()
            if not k or not d:
                raise KeyError("No such item.")
            last = max(filter(None, (k["last_worn"], d["last_worn"])), default=None)
            self._db.execute("UPDATE items SET wear_count = ?, last_worn = ? WHERE id = ?",
                             (k["wear_count"] + d["wear_count"], last, keep))
            self._db.execute("UPDATE wears SET item_id = ? WHERE item_id = ?", (keep, drop))
            self._db.execute("UPDATE aliases SET item_id = ? WHERE item_id = ?", (keep, drop))
            self._db.execute("INSERT OR REPLACE INTO aliases VALUES (?, ?, ?)", (drop, keep, now()))
            self._db.execute("DELETE FROM distinct_pairs WHERE a = ? OR b = ?", (drop, drop))
            self._db.execute("DELETE FROM items WHERE id = ?", (drop,))

    def mark_distinct(self, a: str, b: str) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT OR IGNORE INTO distinct_pairs VALUES (?, ?)", tuple(sorted((a, b))))

    def distinct_pairs(self) -> set[tuple[str, str]]:
        with self._lock:
            return {(r[0], r[1]) for r in self._db.execute("SELECT a, b FROM distinct_pairs").fetchall()}

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
            self._db.execute("DELETE FROM aliases WHERE item_id = ?", (item_id,))
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

    # -- plans, wears, check-ins, preferences

    def add_plan(self, plan: dict) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO plans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (plan["id"], plan["day"], plan["created_at"], plan["source"], json.dumps(plan["plan"]),
                 json.dumps(plan["trace"]), json.dumps(plan["weather"]), json.dumps(plan["calendar"]), plan["notes"]),
            )

    def get_plan(self, plan_id: str | None = None, day: str | None = None) -> dict | None:
        """A plan by id, or the latest plan for a day."""
        with self._lock:
            if plan_id:
                row = self._db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            else:
                row = self._db.execute("SELECT * FROM plans WHERE day = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                                       (day,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for k in ("plan", "trace", "weather", "calendar"):
            d[k] = json.loads(d[k])
        return d

    def record_wear(self, day: str, item_ids: list[str], plan_id: str | None, look: int | None) -> None:
        with self._lock, self._db:
            for item_id in item_ids:
                self._db.execute("INSERT INTO wears (day, item_id, plan_id, look) VALUES (?, ?, ?, ?)",
                                 (day, item_id, plan_id, look))
                self._db.execute(
                    "UPDATE items SET wear_count = wear_count + 1, "
                    "last_worn = CASE WHEN last_worn IS NULL OR last_worn < ? THEN ? ELSE last_worn END WHERE id = ?",
                    (day, day, item_id),
                )

    def worn_on(self, day: str) -> list[str]:
        with self._lock:
            rows = self._db.execute("SELECT DISTINCT item_id FROM wears WHERE day = ?", (day,)).fetchall()
        return [r[0] for r in rows]

    def wear_days(self) -> list[str]:
        with self._lock:
            return [r[0] for r in self._db.execute("SELECT DISTINCT day FROM wears ORDER BY day DESC").fetchall()]

    def add_checkin(self, checkin: dict) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO checkins VALUES (?, ?, ?, ?, ?, ?, ?)",
                (checkin["id"], checkin["day"], checkin["created_at"], checkin.get("plan_id"),
                 json.dumps(checkin["answers"]), checkin["reply"],
                 json.dumps(checkin["learned"]) if checkin.get("learned") else None),
            )

    def add_preference(self, text: str, applies_when: str | None, checkin_id: str | None) -> bool:
        """Store a learned preference; returns False if the exact text was already known."""
        with self._lock, self._db:
            cur = self._db.execute(
                "INSERT OR IGNORE INTO preferences (created_at, text, applies_when, checkin_id) VALUES (?, ?, ?, ?)",
                (now(), text.strip(), applies_when, checkin_id),
            )
            return cur.rowcount > 0

    def list_preferences(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._db.execute("SELECT * FROM preferences ORDER BY id").fetchall()]

    def delete_preference(self, pref_id: int) -> bool:
        with self._lock, self._db:
            return self._db.execute("DELETE FROM preferences WHERE id = ?", (pref_id,)).rowcount > 0

    # -- settings

    def get_setting(self, key: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_setting(self, key: str, value: dict) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, json.dumps(value)))

    # -- thrift list

    def add_thrift(self, piece: dict, status: str) -> int:
        """Watch (or dismiss) a gap piece. Re-adding a name updates it instead of duplicating."""
        with self._lock, self._db:
            row = self._db.execute("SELECT id FROM thrift WHERE lower(name) = lower(?)", (piece["name"],)).fetchone()
            if row:
                self._db.execute("UPDATE thrift SET status = ?, piece = ? WHERE id = ?", (status, json.dumps(piece), row[0]))
                return row[0]
            return self._db.execute("INSERT INTO thrift (created_at, name, status, piece) VALUES (?, ?, ?, ?)",
                                    (now(), piece["name"], status, json.dumps(piece))).lastrowid

    def list_thrift(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM thrift ORDER BY id DESC").fetchall()
        return [{**dict(r), "piece": json.loads(r["piece"])} for r in rows]

    def set_thrift_status(self, thrift_id: int, status: str) -> bool:
        with self._lock, self._db:
            return self._db.execute("UPDATE thrift SET status = ? WHERE id = ?", (status, thrift_id)).rowcount > 0

    def delete_thrift(self, thrift_id: int) -> bool:
        with self._lock, self._db:
            return self._db.execute("DELETE FROM thrift WHERE id = ?", (thrift_id,)).rowcount > 0

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
