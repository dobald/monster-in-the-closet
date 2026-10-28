"""Morning plans, wearing an outfit, evening check-ins and the oni's mood.

Plans are cached under a hash of everything they depend on (wardrobe and wear state,
learned preferences, weather, calendar, notes, day), so asking twice costs nothing and
fixture mode can replay real plans. Live mode runs the agent on Muse Spark Open, falls
back to Muse Spark 1.3, then to rules. Fixture mode never calls a model.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timedelta, timezone

from closet import config, gaps, planner, tools
from closet.schema import CheckinLearning, OutfitPlan

from .cache import Cache, sha256
from .settings import Settings
from .store import Store, now

PLAN_VERSION = "plan1"
GAP_VERSION = "gaps1"
ALIVE_WINDOW_DAYS = 30
RESCUE_DAYS = 30

# Used only in fixture mode before any real forecast has been recorded.
CANNED_WEATHER = {"date": None, "location": None, "parts": {
    "morning": {"temp_c": [6, 9], "feels_like_low_c": 3, "rain_chance_pct": 10, "sky": "partly cloudy"},
    "afternoon": {"temp_c": [10, 13], "feels_like_low_c": 9, "rain_chance_pct": 20, "sky": "partly cloudy"},
    "evening": {"temp_c": [8, 10], "feels_like_low_c": 6, "rain_chance_pct": 60, "sky": "light rain"},
}, "note": "canned fixture weather"}


class Planning:
    def __init__(self, settings: Settings, cache: Cache, store: Store):
        self.settings, self.cache, self.store = settings, cache, store

    # -- inputs

    def weather(self, day: date, lat: float, lon: float) -> dict:
        key = sha256(f"weather:{day}:{lat:.2f}:{lon:.2f}:{datetime.now().hour // 3}".encode())
        hit = self.cache.get("weather", key)
        if hit:
            return hit
        if not self.settings.live:
            recorded = [w for w in (self.cache.get("weather", k) for k in self.cache.keys("weather")) if w]
            near = [w for w in recorded if w.get("location") and abs(w["location"]["lat"] - lat) < 0.2
                    and abs(w["location"]["lon"] - lon) < 0.2]
            same_day = [w for w in near or recorded if w.get("date") == day.isoformat()]
            return (same_day or near or recorded or [{**CANNED_WEATHER, "date": day.isoformat()}])[-1]
        w = tools.get_weather(day, lat, lon)
        self.cache.put("weather", key, w)
        return w

    # -- the user's setup (from getting started): where they are and which calendar to read

    @property
    def calendar_path(self):
        return self.settings.var_dir / "private" / "calendar.ics"

    def profile(self) -> dict:
        # Before getting started, keep the old behaviour: .env location and the sample calendar.
        return {"location": None, "calendar": "sample", "calendar_name": None, "onboarded": False,
                **(self.store.get_setting("profile") or {})}

    def update_profile(self, **changes) -> dict:
        p = {**self.profile(), **{k: v for k, v in changes.items() if v is not None}}
        self.store.put_setting("profile", p)
        return p

    def location(self) -> tuple[float, float]:
        loc = self.profile()["location"]
        return (loc["lat"], loc["lon"]) if loc else (tools.DEFAULT_LAT, tools.DEFAULT_LON)

    def calendar(self, day: date) -> dict:
        kind = self.profile()["calendar"]
        if kind == "ics" and self.calendar_path.exists():
            return tools.get_calendar(day, self.calendar_path)
        if kind == "sample":
            return tools.get_calendar(day)
        return {"date": day.isoformat(), "events": [], "note": "no calendar connected"}

    def _garments(self) -> list[dict]:
        return [i for i in self.store.list_items() if i["tags"]]

    # -- morning plan

    async def make_plan(self, day: date, notes: str = "", lat: float | None = None, lon: float | None = None,
                        fresh: bool = False) -> dict:
        home = self.location()
        lat = home[0] if lat is None else lat
        lon = home[1] if lon is None else lon
        items = self._garments()
        if not items:
            raise ValueError("The wardrobe is empty: scan some clothes first.")
        prefs = self.store.list_preferences()
        weather = self.weather(day, lat, lon)
        calendar = self.calendar(day)

        snapshot = [(i["id"], i["tags"], i["last_worn"], i["wear_count"]) for i in sorted(items, key=lambda i: i["id"])]
        key = sha256(json.dumps([PLAN_VERSION, day.isoformat(), notes.strip().lower(), snapshot,
                                 [p["text"] for p in prefs], weather, calendar, config.PLAN_PROVIDER],
                                sort_keys=True, default=str).encode())
        cached = None if fresh else self.cache.get("plans", key)

        if cached:
            plan, trace, source = OutfitPlan.model_validate(cached["plan"]), {**cached["trace"], "cached": True}, "cache"
        elif self.settings.live:
            plan, trace, source = await self._live_plan(items, prefs, day, notes, weather, calendar)
            self.cache.put("plans", key, {"plan": plan.model_dump(), "trace": trace})
        else:
            plan = planner.plan_with_rules(items, weather, calendar, notes, day)
            trace, source = {"provider": "rules", "reason": "fixture mode",
                             "steps": planner.rule_steps(items, prefs, weather, calendar, notes, plan, "Fixture mode: no model calls")}, "rules"

        record = {"id": uuid.uuid4().hex[:12], "day": day.isoformat(), "created_at": now(), "source": source,
                  "plan": plan.model_dump(), "trace": trace, "weather": weather, "calendar": calendar, "notes": notes}
        self.store.add_plan(record)
        return record

    async def _live_plan(self, items, prefs, day, notes, weather, calendar) -> tuple[OutfitPlan, dict, str]:
        tool_impls = {"get_weather": lambda: weather, "get_calendar": lambda: calendar}
        failures = []
        providers = [config.PLAN_PROVIDER] + [p for p in ("meta",) if p != config.PLAN_PROVIDER]
        for provider in providers:
            try:
                plan, trace = await asyncio.to_thread(
                    planner.plan_with_agent, items, prefs, day, notes, tool_impls, provider)
                return plan, {**trace, "failures": failures}, "agent"
            except Exception as e:
                failures.append(f"{provider}: {type(e).__name__}: {e}"[:300])
        plan = planner.plan_with_rules(items, weather, calendar, notes, day)
        steps = planner.rule_steps(items, prefs, weather, calendar, notes, plan, "The models didn't answer, so the rules stepped in")
        return plan, {"provider": "rules", "failures": failures, "steps": steps}, "rules"

    # -- wearing an outfit

    def wear(self, plan_id: str, look_index: int, day: date) -> dict:
        record = self.store.get_plan(plan_id=plan_id)
        if not record:
            raise KeyError("No such plan.")
        looks = record["plan"]["looks"]
        if not 0 <= look_index < len(looks):
            raise IndexError(f"look must be 0-{len(looks) - 1}")
        look = looks[look_index]
        before = self.oni(day)

        rescued = []
        for item_id in look["item_ids"]:
            item = self.store.get_item(item_id)
            if not item:
                continue
            idle = self._idle_days(item, day)
            if idle is not None and idle >= RESCUE_DAYS:
                rescued.append({"id": item_id, "name": item["tags"]["subtype"] if item["tags"] else "item", "days": idle})
        self.store.record_wear(day.isoformat(), look["item_ids"], plan_id, look_index)
        after = self.oni(day, just_rescued=bool(rescued))
        return {"day": day.isoformat(), "look": look, "rescued": rescued,
                "closet_alive_before": before["closet_alive_pct"], "closet_alive_after": after["closet_alive_pct"],
                "streak_days": after["streak_days"], "oni": after}

    @staticmethod
    def _idle_days(item: dict, day: date) -> int | None:
        """Days since last worn, or since it was added if never worn here."""
        ref = item.get("last_worn") or item.get("created_at")
        return None if not ref else (day - datetime.fromisoformat(ref).date()).days

    # -- the oni's mood

    def oni(self, day: date, just_rescued: bool = False) -> dict:
        items = self.store.list_items()
        cutoff = day - timedelta(days=ALIVE_WINDOW_DAYS)
        alive = [i for i in items if i["last_worn"] and datetime.fromisoformat(i["last_worn"]).date() > cutoff]
        pct = round(100 * len(alive) / len(items)) if items else 0
        forgotten = [i for i in items if (self._idle_days(i, day) or 0) >= 60]

        streak, d = 0, day
        days = set(self.store.wear_days())
        while d.isoformat() in days:
            streak, d = streak + 1, d - timedelta(days=1)

        hour = datetime.now().hour
        if just_rescued:
            mood = "fed"
        elif hour >= 21 or hour < 5:
            mood = "sleepy"
        else:
            mood = "restless" if pct < 25 else "calm" if pct <= 60 else "proud"
        return {"mood": mood, "closet_alive_pct": pct, "garments": len(items),
                "forgotten": len(forgotten), "streak_days": streak}

    # -- evening check-in

    async def checkin(self, day: date, answers: dict, plan_id: str | None = None) -> dict:
        worn_ids = self.store.worn_on(day.isoformat())
        worn = [i for i in (self.store.get_item(x) for x in worn_ids) if i and i["tags"]]
        plan = self.store.get_plan(plan_id=plan_id) if plan_id else self.store.get_plan(day=day.isoformat())
        weather = plan["weather"] if plan else self.weather(day, *self.location())
        prefs = self.store.list_preferences()

        key = sha256(json.dumps([PLAN_VERSION, "checkin", day.isoformat(), answers, worn_ids,
                                 [p["text"] for p in prefs]], sort_keys=True).encode())
        cached = self.cache.get("checkins", key)
        trace: dict
        if cached:
            learned, trace = CheckinLearning.model_validate(cached["learned"]), {**cached["trace"], "cached": True}
        elif self.settings.live:
            learned, trace = None, {"failures": []}
            for provider in [config.PLAN_PROVIDER] + [p for p in ("meta",) if p != config.PLAN_PROVIDER]:
                try:
                    learned, t = await asyncio.to_thread(planner.learn_with_agent, answers, worn, weather, prefs, provider)
                    trace = {**t, "failures": trace["failures"]}
                    break
                except Exception as e:
                    trace["failures"].append(f"{provider}: {type(e).__name__}: {e}"[:300])
            if learned is None:
                learned, trace = planner.learn_with_rules(answers, weather), {**trace, "provider": "rules"}
            self.cache.put("checkins", key, {"learned": learned.model_dump(), "trace": trace})
        else:
            learned, trace = planner.learn_with_rules(answers, weather), {"provider": "rules", "reason": "fixture mode"}

        checkin_id = uuid.uuid4().hex[:12]
        new_pref = False
        if learned.preference:
            new_pref = self.store.add_preference(learned.preference, learned.applies_when, checkin_id)
        self.store.add_checkin({"id": checkin_id, "day": day.isoformat(), "created_at": now(),
                                "plan_id": plan["id"] if plan else None, "answers": answers,
                                "reply": learned.oni_reply, "learned": learned.model_dump()})
        return {"id": checkin_id, "day": day.isoformat(), "worn_item_ids": worn_ids, "oni_reply": learned.oni_reply,
                "learned": learned.model_dump() if learned.preference else None, "new_preference": new_pref,
                "trace": trace}


    # -- gap finder / thrift list

    async def gaps(self, day: date, fresh: bool = False) -> dict:
        items = self._garments()
        if not items:
            raise ValueError("The wardrobe is empty: scan some clothes first.")
        prefs = self.store.list_preferences()
        thrift = self.store.list_thrift()
        watching = [t["name"] for t in thrift if t["status"] == "watching"]
        dismissed = [t["name"] for t in thrift if t["status"] == "dismissed"]
        weather = self.weather(day, *self.location())
        parts = (weather.get("parts") or {}).values()
        note = (f"{min(t for p in parts for t in p['temp_c'])}-{max(t for p in parts for t in p['temp_c'])}°C, "
                f"feels like {min(p['feels_like_low_c'] for p in parts)}° at the coldest") if parts else "unknown"

        snapshot = sorted((i["id"], i["tags"]) for i in items)
        key = sha256(json.dumps([GAP_VERSION, snapshot, [p["text"] for p in prefs], sorted(watching), sorted(dismissed),
                                 gaps.season_for(day), config.PLAN_PROVIDER], sort_keys=True, default=str).encode())
        cached = None if fresh else self.cache.get("gaps", key)
        if cached:
            return {**cached, "trace": {**cached["trace"], "cached": True}}

        pieces, trace, source = [], {"failures": []}, "rules"
        if self.settings.live:
            for provider in [config.PLAN_PROVIDER] + [p for p in ("meta",) if p != config.PLAN_PROVIDER]:
                try:
                    report, t = await asyncio.to_thread(gaps.find_gaps_with_agent, items, prefs, day, note,
                                                        watching, dismissed, provider)
                    pieces = gaps.clean_report(report, items)
                    if pieces:
                        trace, source, summary = {**t, "failures": trace["failures"]}, "agent", report.summary
                        break
                    trace["failures"].append(f"{provider}: no usable pieces")
                except Exception as e:
                    trace["failures"].append(f"{provider}: {type(e).__name__}: {e}"[:300])
        if not pieces:
            report = gaps.find_gaps_with_rules(items, dismissed, watching)
            pieces, summary = gaps.clean_report(report, items), report.summary
            trace = {**trace, "provider": "rules"}
        record = {"created_at": now(), "source": source, "summary": summary, "pieces": pieces, "trace": trace}
        if source == "agent":
            self.cache.put("gaps", key, record)
        return record


def today_local() -> date:
    return datetime.now(timezone.utc).astimezone().date()
