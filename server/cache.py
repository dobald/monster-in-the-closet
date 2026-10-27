"""Content-addressed cache for paid model results.

Every SAM scan and every tag is stored under a hash of its input plus a version
string, so the same photo or cutout is never paid for twice, and fixture mode can
replay real results with zero API calls. Versions include the schema, so changing
the Garment fields or the scan settings invalidates old entries automatically.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from closet import config, scan
from closet.schema import Garment


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _schema_hash() -> str:
    return sha256(json.dumps(Garment.model_json_schema(), sort_keys=True).encode())[:8]


SCAN_VERSION = f"scan1-{scan.PROMPT}-{scan.SEGMENT_EDGE}px-conf{scan.MIN_CONFIDENCE}"
TAG_VERSION = f"tag-{config.TAG_PROVIDER}-{config.TAG_MODEL[config.TAG_PROVIDER]}-{_schema_hash()}"


class Cache:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, kind: str, key: str) -> Path:
        return self.root / kind / f"{key}.json"

    def get(self, kind: str, key: str) -> dict | None:
        p = self._path(kind, key)
        return json.loads(p.read_text()) if p.exists() else None

    def put(self, kind: str, key: str, value: dict) -> None:
        p = self._path(kind, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, indent=1))
        tmp.replace(p)

    def keys(self, kind: str) -> list[str]:
        d = self.root / kind
        return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


def scan_key(photo_bytes: bytes) -> str:
    return sha256(photo_bytes + SCAN_VERSION.encode())


def tag_key(cutout_png: bytes) -> str:
    return sha256(cutout_png + TAG_VERSION.encode())
