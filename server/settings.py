"""Server settings, read once from the environment (.env is loaded by closet.config).

MONSTER_MODE
  fixture (default) - never calls a paid API. Scans and tags come from the cache of
                      earlier live calls; an unseen photo replays a recorded scan.
                      Use this for front-end work: zero credits.
  live              - calls SAM 3.1 and Muse Spark, and records every result to the cache.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from closet import config

MODES = ("fixture", "live")


@dataclass(frozen=True)
class Settings:
    mode: str
    var_dir: Path

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
        return self.var_dir / "cache"


def load() -> Settings:
    mode = os.environ.get("MONSTER_MODE", "fixture").strip().lower()
    if mode not in MODES:
        raise SystemExit(f"MONSTER_MODE must be one of {MODES}, got {mode!r}")
    var_dir = Path(os.environ.get("MONSTER_VAR_DIR", config.ROOT / "var")).resolve()
    for d in (var_dir, var_dir / "cutouts", var_dir / "cache"):
        d.mkdir(parents=True, exist_ok=True)
    return Settings(mode=mode, var_dir=var_dir)
