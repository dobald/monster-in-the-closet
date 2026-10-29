"""Server settings, read once from the environment (.env is loaded by closet.config).

MONSTER_MODE
  fixture (default) - never calls a paid API. Scans and tags come from the cache of
                      earlier live calls; an unseen photo replays a recorded scan.
                      Use this for front-end work: zero credits.
  live              - calls SAM 3.1 and Muse Spark, and records every result to the cache.

MONSTER_CLOSETS
  single (default)  - one closet for everyone, in MONSTER_VAR_DIR. Fine on your own laptop.
  device            - every browser gets its own closet under var/closets/<id>/, picked by a
                      cookie. Use this whenever anyone else opens the app (testers, a hosted demo).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from closet import config

MODES = ("fixture", "live")
CLOSET_MODES = ("single", "device")


@dataclass(frozen=True)
class Settings:
    mode: str
    var_dir: Path  # this closet's own files: database, cutouts, renders, private uploads
    shared_dir: Path | None = None  # what every closet shares (the model cache); defaults to var_dir
    closets: str = "single"

    @property
    def live(self) -> bool:
        return self.mode == "live"

    @property
    def db_path(self) -> Path:
        return self.var_dir / "wardrobe.sqlite3"

    @property
    def cutout_dir(self) -> Path:
        return self.var_dir / "cutouts"

    @property
    def cache_dir(self) -> Path:
        return (self.shared_dir or self.var_dir) / "cache"

    @property
    def per_device(self) -> bool:
        return self.closets == "device"


def load() -> Settings:
    mode = os.environ.get("MONSTER_MODE", "fixture").strip().lower()
    if mode not in MODES:
        raise SystemExit(f"MONSTER_MODE must be one of {MODES}, got {mode!r}")
    closets = os.environ.get("MONSTER_CLOSETS", "single").strip().lower()
    if closets not in CLOSET_MODES:
        raise SystemExit(f"MONSTER_CLOSETS must be one of {CLOSET_MODES}, got {closets!r}")
    var_dir = Path(os.environ.get("MONSTER_VAR_DIR", config.ROOT / "var")).resolve()
    s = Settings(mode=mode, var_dir=var_dir, shared_dir=var_dir, closets=closets)
    prepare(s)
    return s


def prepare(s: Settings) -> None:
    for d in (s.var_dir, s.cutout_dir, s.cache_dir):
        d.mkdir(parents=True, exist_ok=True)
