"""A daily spend cap for a public live deploy.

Every request that can call a paid model (a scan, a plan, a product shot, a try-on...) counts
against two daily limits: one for the whole server and one per closet. Over either, that
request runs in fixture mode instead: recorded results and the rule planner, labelled as
demo data in the app, at no cost. The counts reset at midnight UTC and are kept in a small
JSON file next to the model cache, so a restart doesn't hand out a fresh budget.

MONSTER_DAILY_CALLS          paid requests per day for the whole server (0 = no cap, the default)
MONSTER_CLOSET_DAILY_CALLS   paid requests per day for one closet (0 = no cap, the default)
"""

from __future__ import annotations

import json
import os
import re
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

# Requests a user makes that can call a paid model. Everything else (reading the closet, settings,
# the dress-up stack) is free and never counted. Follow-on work whose cost is bounded by these (product
# shots and dress-up layers for scanned pieces, the taste summary, finishing touches, all cached) isn't
# counted either, so browsing never uses up the day's budget.
PAID = [re.compile(p) for p in (
    r"^POST /api/scans$", r"^POST /api/plan$", r"^POST /api/occasions/plan$", r"^POST /api/gaps$",
    r"^POST /api/thrift/example$", r"^POST /api/checkins$", r"^POST /api/wardrobe/duplicates/check$",
    r"^POST /api/tryon$", r"^POST /api/tryon/photo$", r"^POST /api/tryon/layers$",
    r"^POST /api/wardrobe/[^/]+/(retag|rescan)$",
    r"^POST /api/plans/[^/]+/wear$",  # wearing a look builds tomorrow's plan ahead
)]

_over: ContextVar[bool] = ContextVar("over_budget", default=False)


def exhausted() -> bool:
    """True while handling a request that is over today's budget (settings.live reads this)."""
    return _over.get()


class Budget:
    def __init__(self, path: Path):
        self.path = path
        self.total = int(os.environ.get("MONSTER_DAILY_CALLS", "0"))
        self.per_closet = int(os.environ.get("MONSTER_CLOSET_DAILY_CALLS", "0"))
        self._lock = threading.Lock()
        try:
            self._state = json.loads(path.read_text())
        except (OSError, ValueError):
            self._state = {}

    @property
    def capped(self) -> bool:
        return bool(self.total or self.per_closet)

    def spend(self, closet: str) -> bool:
        """Count one paid request. False if it is over a limit (it is then not counted)."""
        today = datetime.now(timezone.utc).date().isoformat()
        with self._lock:
            if self._state.get("day") != today:
                self._state = {"day": today, "total": 0, "closets": {}}
            used = self._state["closets"].get(closet, 0)
            if (self.total and self._state["total"] >= self.total) or (self.per_closet and used >= self.per_closet):
                return False
            self._state["total"] += 1
            self._state["closets"][closet] = used + 1
            try:
                self.path.write_text(json.dumps(self._state))
            except OSError:
                pass
            return True

    def left(self, closet: str) -> int | None:
        """Paid requests this closet has left today, or None without a cap."""
        if not self.capped:
            return None
        today = datetime.now(timezone.utc).date().isoformat()
        state = self._state if self._state.get("day") == today else {"total": 0, "closets": {}}
        lefts = []
        if self.total:
            lefts.append(self.total - state["total"])
        if self.per_closet:
            lefts.append(self.per_closet - state["closets"].get(closet, 0))
        return max(0, min(lefts))


class BudgetMiddleware:
    """Pure ASGI middleware, inside ClosetMiddleware (so it knows the closet). Live mode only."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        state = scope["app"].state if scope["type"] == "http" else None
        budget: Budget | None = getattr(state, "budget", None) if state else None
        if (budget is None or not budget.capped or state.settings.mode != "live"
                or not any(p.match(f"{scope['method']} {scope['path']}") for p in PAID)):
            return await self.app(scope, receive, send)
        from .closets import current_id
        token = _over.set(not budget.spend(current_id()))
        try:
            return await self.app(scope, receive, send)
        finally:
            _over.reset(token)
