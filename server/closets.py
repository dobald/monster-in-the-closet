"""One closet per device, so testers never see each other's clothes.

In MONSTER_CLOSETS=single (the default) there is one closet in var/, as before. In
MONSTER_CLOSETS=device every browser gets a random closet id in a cookie, and its database,
cutouts, renders, try-on photo and calendar live under var/closets/<id>/. The model cache is
shared: it is keyed by content hashes, so one closet can't look up another's entries without
already holding the same photo.

The id is 128 random bits and is the only key to a closet, so the cookie is HttpOnly and a
closet can only be opened on another device through its own "open on another device" link.
"""

from __future__ import annotations

import re
import secrets
import threading
from contextvars import ContextVar
from dataclasses import dataclass, replace
from http.cookies import SimpleCookie

from . import settings as settings_mod
from .cache import Cache
from .layers import Layers
from .pipeline import Pipeline
from .planning import Planning
from .settings import Settings
from .store import Store
from .tryon import TryOn

COOKIE = "closet"
COOKIE_MAX_AGE = 400 * 24 * 3600  # the longest browsers keep a cookie
ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAIN = "main"
SCOPE_KEY = "monster.closet"  # handlers set scope[SCOPE_KEY]["cookie"] to move the browser to another closet


@dataclass
class Closet:
    id: str
    settings: Settings
    store: Store
    pipeline: Pipeline
    planning: Planning
    tryon: TryOn
    layers: Layers


class ClosetsFull(RuntimeError):
    """MONSTER_MAX_CLOSETS closets exist already; a new device can't get one."""


class Closets:
    def __init__(self, settings: Settings, cache: Cache, max_closets: int = 200):
        self.settings, self.cache, self.max_closets = settings, cache, max_closets
        self._open: dict[str, Closet] = {}
        self._lock = threading.Lock()

    @property
    def root(self):
        return self.settings.var_dir / "closets"

    def exists(self, closet_id: str) -> bool:
        if not self.settings.per_device:
            return closet_id == MAIN
        # In device mode the shared var/ root is never a closet anyone can open.
        return bool(ID_RE.match(closet_id)) and (self.root / closet_id).is_dir()

    def get(self, closet_id: str) -> Closet:
        with self._lock:
            if closet_id in self._open:
                return self._open[closet_id]
            if closet_id == MAIN:
                s = self.settings
            else:
                if not ID_RE.match(closet_id):
                    raise ValueError("not a closet id")
                if not (self.root / closet_id).is_dir() and self.count() >= self.max_closets:
                    raise ClosetsFull(f"This demo is full ({self.max_closets} closets).")
                s = replace(self.settings, var_dir=self.root / closet_id)
            settings_mod.prepare(s)
            store = Store(s.db_path)
            c = Closet(closet_id, s, store, Pipeline(s, self.cache, store), Planning(s, self.cache, store),
                       TryOn(s, self.cache, store), Layers(s, store))
            self._open[closet_id] = c
            return c

    def count(self) -> int:
        return sum(1 for p in self.root.glob("*") if p.is_dir()) if self.root.exists() else 0

    @staticmethod
    def new_id() -> str:
        return secrets.token_hex(16)


_current: ContextVar[str] = ContextVar("closet_id", default=MAIN)


def current_id() -> str:
    return _current.get()


class ClosetMiddleware:
    """Pure ASGI middleware: picks the request's closet from its cookie, or hands out a new one.

    Only the id is decided here. The closet itself opens lazily on first use, so a bot hitting
    /api/health never creates a folder.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api"):
            return await self.app(scope, receive, send)
        closets: Closets = scope["app"].state.closets
        if not closets.settings.per_device:
            token = _current.set(MAIN)
            try:
                return await self.app(scope, receive, send)
            finally:
                _current.reset(token)

        cookie = SimpleCookie()
        for k, v in scope.get("headers", []):
            if k == b"cookie":
                try:
                    cookie.load(v.decode("latin-1"))
                except Exception:
                    pass
        sent = cookie[COOKIE].value if COOKIE in cookie else ""
        closet_id = sent if ID_RE.match(sent) else closets.new_id()
        scope[SCOPE_KEY] = {"cookie": closet_id}

        async def send_with_cookie(message):
            # A handler can switch closets (open a link, start over) by changing scope state.
            chosen = scope[SCOPE_KEY]["cookie"]
            if message["type"] == "http.response.start" and chosen != sent:
                secure = "; Secure" if scope.get("scheme") == "https" else ""
                header = f"{COOKIE}={chosen}; Path=/; Max-Age={COOKIE_MAX_AGE}; HttpOnly; SameSite=Lax{secure}"
                message.setdefault("headers", []).append((b"set-cookie", header.encode("latin-1")))
            await send(message)

        token = _current.set(closet_id)
        try:
            await self.app(scope, receive, send_with_cookie)
        finally:
            _current.reset(token)
