"""Morning plans, wearing an outfit, evening check-ins and the oni's mood.

Plans are cached under a hash of everything they depend on (wardrobe and wear state,
learned preferences, weather, calendar, notes, day), so asking twice costs nothing and
fixture mode can replay real plans. Live mode runs the agent on Muse Spark Open, falls
back to Muse Spark 1.3, then to rules. Fixture mode never calls a model.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import numpy as np

from closet import colour, config, gaps, materials, occasions, planner, scoring, styles, styling, taste, tools
from closet.schema import CheckinLearning, Look, OutfitPlan

from . import calfeed
from .cache import Cache, sha256
from .settings import Settings
from .store import Store, now

PLAN_VERSION = "plan2"  # plan2: five candidates, ranked by closet/scoring.py
GAP_VERSION = "gaps2"
TOUCH_VERSION = "touch3"
COLD_C = 8  # feels-like at or below this is "cold" for scarves, beanies and long-sleeve layers
ALIVE_WINDOW_DAYS = 30
RESCUE_DAYS = 30
TOUCH_EXAMPLES = config.ROOT / "fixtures" / "touch_examples"  # one picture per play, scripts/make_touch_examples.py

# Used only in fixture mode before any real forecast has been recorded.
CANNED_WEATHER = {"date": None, "location": None, "parts": {
    "morning": {"temp_c": [6, 9], "feels_like_low_c": 3, "rain_chance_pct": 10, "sky": "partly cloudy"},
    "afternoon": {"temp_c": [10, 13], "feels_like_low_c": 9, "rain_chance_pct": 20, "sky": "partly cloudy"},
    "evening": {"temp_c": [8, 10], "feels_like_low_c": 6, "rain_chance_pct": 60, "sky": "light rain"},
}, "note": "canned fixture weather"}


class Planning:
    def __init__(self, settings: Settings, cache: Cache, store: Store):
        self.settings, self.cache, self.store = settings, cache, store
        self._given: dict[str, dict[int, list[dict]]] = {}  # plan id -> look -> touches shown this session
        self._building: set[str] = set()  # days with a plan being made ahead right now

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

    @property
    def calendar_link_path(self):
        """The calendar's private iCal address: a password to it, so it never leaves this folder."""
        return self.settings.var_dir / "private" / "calendar_link.txt"

    async def connect_calendar(self, url: str) -> int:
        """Check a calendar link, keep a first copy and remember it. Returns the number of events."""
        from urllib.parse import urlsplit
        data = await calfeed.fetch(url)
        count = tools.ics_count(data)
        if not count:
            raise calfeed.FeedError("That link has no events. Check it's the iCal (.ics) address, not the web page.")
        self.calendar_path.parent.mkdir(parents=True, exist_ok=True)
        self.calendar_path.write_bytes(data)
        self.calendar_link_path.write_text(calfeed.normalise(url), encoding="utf-8")
        self.update_profile(calendar="link", calendar_name=urlsplit(calfeed.normalise(url)).hostname)
        return count

    async def sync_calendar(self) -> None:
        """Refresh a linked calendar if its copy is over 15 minutes old. A failed refresh keeps the last copy."""
        if self.profile()["calendar"] != "link" or not self.calendar_link_path.exists():
            return
        if self.calendar_path.exists() and datetime.now().timestamp() - self.calendar_path.stat().st_mtime < calfeed.REFRESH_S:
            return
        try:
            data = await calfeed.fetch(self.calendar_link_path.read_text(encoding="utf-8"))
            if tools.ics_count(data):
                self.calendar_path.write_bytes(data)
        except calfeed.FeedError:
            pass

    def disconnect_calendar(self) -> None:
        self.calendar_path.unlink(missing_ok=True)
        self.calendar_link_path.unlink(missing_ok=True)
        self.store.put_setting("profile", {**self.profile(), "calendar": "none", "calendar_name": None})

    def upcoming(self, today: date, days: int = 7) -> list[dict]:
        """Events coming up, each read as an occasion, with the plan already made for it (if any).
        The demo calendar repeats every day, so only today's and tomorrow's demo events are listed."""
        span = [today + timedelta(days=n) for n in range(days)]
        cal_days = span[:2] if self.profile()["calendar"] == "sample" else span
        made = {}
        for rec in self.store.occasion_plans([d.isoformat() for d in span]):
            ev = rec["occasion"]["event"]
            made.setdefault((rec["day"], ev.get("title"), ev.get("start")), rec["id"])
        out = []
        for d in cal_days:
            for e in self.calendar(d)["events"]:
                out.append({"day": d.isoformat(), **e, "read": occasions.read(e).to_dict(),
                            "plan_id": made.pop((d.isoformat(), e.get("title"), e.get("start")), None)})
        # Occasions typed in rather than on the calendar ("job interview Monday") stay on the list too.
        for rec in self.store.occasion_plans([d.isoformat() for d in span]):
            ev = rec["occasion"]["event"]
            if made.get((rec["day"], ev.get("title"), ev.get("start"))) == rec["id"]:
                out.append({"day": rec["day"], **ev, "read": rec["occasion"]["read"], "plan_id": rec["id"], "typed": True})
        return sorted(out, key=lambda e: (e["day"], e.get("start") != "all day", e.get("start") or ""))

    def profile(self) -> dict:
        # Before getting started, keep the old behaviour: .env location and the sample calendar.
        p = {"location": None, "calendar": "sample", "calendar_name": None, "onboarded": False,
             **(self.store.get_setting("profile") or {})}
        return {**p, "materials": materials.clean(p.get("materials"))}

    def fabrics(self) -> dict:
        """Material families the person loves or won't wear (closet/materials.py)."""
        return self.profile()["materials"]

    def _prefs(self) -> list[dict]:
        """Preferences the oni was told or learned at check-ins, plus the fabric ones from the profile."""
        return self.store.list_preferences() + materials.prompt_lines(self.fabrics())

    def update_profile(self, **changes) -> dict:
        p = {**self.profile(), **{k: v for k, v in changes.items() if v is not None}}
        self.store.put_setting("profile", p)
        return p

    def location(self) -> tuple[float, float]:
        loc = self.profile()["location"]
        return (loc["lat"], loc["lon"]) if loc else (tools.DEFAULT_LAT, tools.DEFAULT_LON)

    def calendar(self, day: date) -> dict:
        kind = self.profile()["calendar"]
        if kind in ("ics", "link") and self.calendar_path.exists():
            return tools.get_calendar(day, self.calendar_path)
        if kind == "sample":
            return tools.get_calendar(day)
        return {"date": day.isoformat(), "events": [], "note": "no calendar connected"}

    def _garments(self) -> list[dict]:
        return [i for i in self.store.list_items() if i["tags"]]

    # -- morning plan

    def basis(self, day: date) -> str:
        """What a plan was built from, minus the weather: if this changes, a plan made ahead is out of date."""
        snapshot = [(i["id"], i["tags"], i["last_worn"], i["wear_count"]) for i in sorted(self._garments(), key=lambda i: i["id"])]
        return sha256(json.dumps([day.isoformat(), snapshot, [p["text"] for p in self._prefs()]],
                                 sort_keys=True, default=str).encode())[:16]

    def current_plan(self, day: date) -> dict | None:
        """The latest plan for a day. A plan made ahead counts only while the closet is as it was then."""
        record = self.store.get_plan(day=day.isoformat())
        if record and record["trace"].get("prebuilt") and record["trace"].get("basis") != self.basis(day):
            return None
        return record

    async def prebuild(self, day: date) -> None:
        """Make the day's plan ahead of time (after a wear or a check-in), so the morning opens on it
        instantly instead of waiting ~15s for the agent. Failures are quiet: the morning plans as usual."""
        key = day.isoformat()
        if key in self._building or planner.outfit_gap(self._garments()):
            return
        if day <= today_local() and self.store.get_plan(day=key):
            return  # never swap out a plan someone may be looking at; only future days are rebuilt
        self._building.add(key)
        try:
            await self.make_plan(day, prebuilt=True)
        except Exception:
            pass
        finally:
            self._building.discard(key)

    async def make_plan(self, day: date, notes: str = "", lat: float | None = None, lon: float | None = None,
                        fresh: bool = False, prebuilt: bool = False, event: dict | None = None) -> dict:
        """The day's looks, or with `event` looks for that one occasion (closet/occasions.py)."""
        home = self.location()
        lat = home[0] if lat is None else lat
        lon = home[1] if lon is None else lon
        items = self._garments()
        gap = planner.outfit_gap(items)
        if gap:
            raise ValueError(gap)
        model = self.taste_model()
        picture = self.style_picture(items)
        prefs = (self._prefs() + taste.prompt_lines(model)  # what it has learned rides along as preferences
                 + styles.prompt_lines(picture["liked"], picture["grow"], picture["answers"]))
        weather = self.weather(day, lat, lon)
        read = None
        if event:
            read = occasions.read(event)
            calendar = {"date": day.isoformat(), "events": [event]}  # the agent's get_calendar sees just this event
            notes = " ".join(filter(None, [read.prompt_line(event), notes.strip()]))
        else:
            await self.sync_calendar()
            calendar = self.calendar(day)
        scorer = self._scorer(weather, calendar, day, model, event)

        snapshot = [(i["id"], i["tags"], i["last_worn"], i["wear_count"]) for i in sorted(items, key=lambda i: i["id"])]
        key = sha256(json.dumps([PLAN_VERSION, day.isoformat(), notes.strip().lower(), snapshot,
                                 [p["text"] for p in prefs], weather, calendar, config.PLAN_PROVIDER],
                                sort_keys=True, default=str).encode())
        cached = None if fresh else self.cache.get("plans", key)

        if cached:
            plan, trace, source = OutfitPlan.model_validate(cached["plan"]), {**cached["trace"], "cached": True}, "cache"
        elif self.settings.live:
            plan, trace, source = await self._live_plan(items, prefs, day, notes, weather, calendar, scorer, not event)
            self.cache.put("plans", key, {"plan": plan.model_dump(), "trace": trace})
        else:
            plan = planner.plan_with_rules(items, weather, calendar, notes, day, scorer, not event)
            trace, source = {"provider": "rules", "reason": "fixture mode",
                             "steps": planner.rule_steps(items, prefs, weather, calendar, notes, plan, "Fixture mode: no model calls")}, "rules"

        plan = self._rank(planner.distinct_looks(plan), scorer, not event)  # for an event: suit it first
        plan, trace = self._with_taste(plan, dict(trace), items, day, weather, model, scorer, picture["grow"], bool(event))
        trace = {**trace, "basis": self.basis(day), **({"prebuilt": True} if prebuilt else {})}
        record = {"id": uuid.uuid4().hex[:12], "day": day.isoformat(), "created_at": now(), "source": source,
                  "plan": plan.model_dump(), "trace": trace, "weather": weather, "calendar": calendar, "notes": notes,
                  "occasion": {"event": event, "read": read.to_dict()} if read else None}
        self.store.add_plan(record)
        return record

    async def _live_plan(self, items, prefs, day, notes, weather, calendar, scorer=None,
                         rescue_first: bool = True) -> tuple[OutfitPlan, dict, str]:
        tool_impls = {"get_weather": lambda: weather, "get_calendar": lambda: calendar}
        failures = []
        providers = [config.PLAN_PROVIDER] + [p for p in ("meta",) if p != config.PLAN_PROVIDER]
        for provider in providers:
            try:
                plan, trace = await asyncio.to_thread(
                    planner.plan_with_agent, items, prefs, day, notes, tool_impls, provider)
                return plan, {**trace, "failures": failures}, "agent"
            except Exception as e:
                failures.append(config.redact(f"{provider}: {type(e).__name__}: {e}")[:300])
        plan = planner.plan_with_rules(items, weather, calendar, notes, day, scorer, rescue_first)
        steps = planner.rule_steps(items, prefs, weather, calendar, notes, plan, "The models didn't answer, so the rules stepped in")
        return plan, {"provider": "rules", "failures": failures, "steps": steps}, "rules"

    # -- "did it make it out?": one tap the next morning instead of logging every wear

    def mark_seen(self, record: dict) -> None:
        """Remember the plan shown on its own day, so tomorrow's question is about what they actually saw."""
        if record["day"] == today_local().isoformat():
            # One entry per day: this morning's visit must not overwrite yesterday's before it's asked about.
            seen = {**(self.store.get_setting("seen_plans") or {}), record["day"]: record["id"]}
            self.store.put_setting("seen_plans", dict(sorted(seen.items())[-3:]))

    def yesterday(self, today: date) -> dict | None:
        """Yesterday's plan, if it was shown, nothing was logged that day, and we haven't asked yet."""
        day = (today - timedelta(days=1)).isoformat()
        plan_id = (self.store.get_setting("seen_plans") or {}).get(day)
        if not plan_id or self.store.worn_on(day) or (self.store.get_setting("asked_worn") or {}).get("day") == day:
            return None
        return self.store.get_plan(plan_id=plan_id)

    def answer_yesterday(self, today: date, look: int | None) -> dict | None:
        """Log yesterday's look (or nothing, for "no"), and never ask about that day again."""
        record = self.yesterday(today)
        if not record:
            raise KeyError("Nothing to ask about yesterday.")
        worn = None if look is None else self.wear(record["id"], look, date.fromisoformat(record["day"]))
        if look is None and record["plan"]["looks"]:
            self.store.add_taste_event("not_worn", a=record["plan"]["looks"][0]["item_ids"])
        self.store.put_setting("asked_worn", {"day": record["day"]})  # after the wear, so a bad look index can be retried
        return worn

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
            # It lives on what you wear: under a third of the closet worn this month and it's starving.
            mood = "starving" if pct < 35 else "calm" if pct <= 70 else "proud"
        # Without any wear history (logged or estimated) the % is a made-up number, so the app hides it.
        return {"mood": mood, "closet_alive_pct": pct, "garments": len(items), "has_history": any(i["last_worn"] for i in items),
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
                    trace["failures"].append(config.redact(f"{provider}: {type(e).__name__}: {e}")[:300])
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
        gap = planner.outfit_gap(items)
        if gap:
            raise ValueError(gap)
        model = self.taste_model()
        picture = self.style_picture(items)
        prefs = (self._prefs() + taste.prompt_lines(model)
                 + styles.prompt_lines(picture["liked"], picture["grow"], picture["answers"]))
        thrift = self.store.list_thrift()
        watching = [t["name"] for t in thrift if t["status"] == "watching"]
        dismissed = [t["name"] for t in thrift if t["status"] == "dismissed"]
        avoid = set(self.fabrics()["avoid"])  # never suggest buying a fabric they won't wear
        weather = self.weather(day, *self.location())
        parts = (weather.get("parts") or {}).values()
        note = (f"{min(t for p in parts for t in p['temp_c'])}-{max(t for p in parts for t in p['temp_c'])}°C, "
                f"feels like {min(p['feels_like_low_c'] for p in parts)}° at the coldest") if parts else "unknown"

        snapshot = sorted((i["id"], i["tags"]) for i in items)
        key = sha256(json.dumps([GAP_VERSION, snapshot, [p["text"] for p in prefs], sorted(watching), sorted(dismissed),
                                 gaps.season_for(day), config.PLAN_PROVIDER], sort_keys=True, default=str).encode())
        cached = None if fresh else self.cache.get("gaps", key)
        if cached:
            return {**cached, "pieces": self.thrift_taste(cached["pieces"], items, model), "trace": {**cached["trace"], "cached": True}}

        pieces, trace, source = [], {"failures": []}, "rules"
        if self.settings.live:
            for provider in [config.PLAN_PROVIDER] + [p for p in ("meta",) if p != config.PLAN_PROVIDER]:
                try:
                    report, t = await asyncio.to_thread(gaps.find_gaps_with_agent, items, prefs, day, note,
                                                        watching, dismissed, provider)
                    pieces = gaps.clean_report(report, items, avoid)
                    if pieces:
                        trace, source, summary = {**t, "failures": trace["failures"]}, "agent", report.summary
                        break
                    trace["failures"].append(f"{provider}: no usable pieces")
                except Exception as e:
                    trace["failures"].append(config.redact(f"{provider}: {type(e).__name__}: {e}")[:300])
        if not pieces:
            report = gaps.find_gaps_with_rules(items, dismissed, watching, avoid)
            pieces, summary = gaps.clean_report(report, items, avoid), report.summary
            trace = {**trace, "provider": "rules"}
        record = {"created_at": now(), "source": source, "summary": summary, "pieces": pieces, "trace": trace}
        if source == "agent":
            self.cache.put("gaps", key, record)
        return {**record, "pieces": self.thrift_taste(pieces, items, model)}


    # -- taste (closet/taste.py): learned from choices, ratings, the warm-up and corrections

    def _vec(self, outfit: list[dict]) -> np.ndarray:
        return taste.vector(outfit, colour.read(outfit, self.settings.cutout_dir))

    def taste_data(self) -> tuple[list[taste.Row], list[tuple]]:
        """Training rows from everything the user has done, plus the worn choices for evaluation."""
        by_id = {i["id"]: i for i in self._garments()}

        def vec(ids: list[str]) -> np.ndarray | None:
            outfit = [by_id[i] for i in ids if i in by_id]
            return self._vec(outfit) if outfit else None

        rows, choices = [], []
        for g, w in enumerate(self.store.worn_looks()):
            plan = self.store.get_plan(plan_id=w["plan_id"])
            looks = [vec(lk["item_ids"]) for lk in plan["plan"]["looks"]] if plan else []
            if len(looks) < 2 or w["look"] >= len(looks) or any(x is None for x in looks):
                continue
            rows += taste.choice_rows(looks[w["look"]], [x for n, x in enumerate(looks) if n != w["look"]], "choice", g)
            choices.append((g, looks, w["look"]))
        worn = self.store.outfits_worn()
        for c in self.store.list_checkins():
            y, ids = taste.RATING.get(c["answers"].get("feeling")), worn.get(c["day"])
            if y is not None and ids and (x := vec(ids)) is not None:
                rows.append(taste.Row(x, y, 0.7, True, "rating"))
        for e in self.store.list_taste_events():
            if e["kind"] == "quiz" and (a := vec(e["a"])) is not None and (b := vec(e["b"])) is not None:
                rows += taste.choice_rows(a, [b], "quiz", -1)
            elif e["kind"] == "not_worn" and (x := vec(e["a"])) is not None:
                rows.append(taste.Row(x, 0.2, 0.3, True, "not_worn"))
            elif e["kind"] == "correct" and e["feature"] in taste.INDEX:
                rows.append(taste.correction_row(e["feature"], e["value"]))
            elif e["kind"] == "style" and e["a"][0] in styles.BY_ID and e["b"][0] in styles.BY_ID:
                # A board pick is a weak outfit-level vote too: this style's features over that one's.
                rows.append(taste.Row(styles.profile(e["a"][0]) - styles.profile(e["b"][0]), 1.0, 0.5, False, "style"))
        return rows, choices

    def taste_model(self) -> taste.Model:
        return taste.fit(self.taste_data()[0])

    def _scorer(self, weather: dict, calendar: dict, day: date, model: taste.Model, event: dict | None = None):
        """closet/scoring.breakdown for this day (or one event): rescue, weather, occasion, colour, the learned taste
        and the fabrics they love or won't wear."""
        ctx = scoring.day_context(weather, calendar, event)
        fabrics = self.fabrics()

        def score(outfit: list[dict]) -> dict:
            read = colour.read(outfit, self.settings.cutout_dir)
            return scoring.breakdown(outfit, read, ctx, day, model.utility(taste.vector(outfit, read)) if model.n else 0.0, fabrics)
        return score

    def _rank(self, plan: OutfitPlan, scorer, rescue_first: bool = True) -> OutfitPlan:
        """Looks A and B by the shared score, whoever proposed them; the rest follow, best first."""
        by_id = {i["id"]: i for i in self._garments()}
        outfits = [[by_id[i] for i in lk.item_ids if i in by_id] for lk in plan.looks]
        scored = [(o, scorer(o)) for o in outfits]
        top = scoring.pick_two(scored, rescue_first)
        rest = sorted((n for n in range(len(plan.looks)) if n not in top), key=lambda n: -scored[n][1]["total"])
        plan.looks = [plan.looks[n] for n in top + rest]
        return plan

    def _candidates(self, items: list[dict], cold: bool) -> list[tuple[list[dict], np.ndarray]]:
        return [(o, self._vec(o)) for o in taste.outfits(items, cold)]

    def _with_taste(self, plan: OutfitPlan, trace: dict, items: list[dict], day: date, weather: dict,
                    model: taste.Model, scorer, grow: dict | None = None, occasion: bool = False) -> tuple[OutfitPlan, dict]:
        """Score each look against the learned taste, and make look C a Stretch: one step outside the
        comfort zone, picked by Thompson sampling. Seeded by the day and closet, so a plan replays the same."""
        parts = (weather.get("parts") or {}).values()
        cold = min((p["feels_like_low_c"] for p in parts), default=15) <= COLD_C
        by_id = {i["id"]: i for i in items}
        cands = self._candidates(items, cold)
        if occasion:  # planning for one event: a stretch still has to suit it
            cands = [c for c in cands if scorer(c[0])["occasion"] >= 0]
        # A stretch is a new idea, not a fabric they won't wear: only outfits with the fewest avoided pieces
        # (none, unless the only coat for a cold day is one).
        bad = [len(materials.avoided(o, self.fabrics())) for o, _ in cands]
        cands = [c for c, n in zip(cands, bad) if n == min(bad)]
        base = float(np.mean([model.utility(x) for _, x in cands])) if cands else 0.0

        # The comfort zone: outfits actually worn, plus today's own picks A and B.
        worn = [[by_id[i] for i in ids if i in by_id] for ids in self.store.outfits_worn().values()]
        comfort = [w for w in worn if w] + [[by_id[i] for i in lk.item_ids if i in by_id] for lk in plan.looks[:2]]
        exposure = sum(((self._vec(o) > 0).astype(float) for o in comfort if o), np.zeros(taste.F))
        pairs_worn = {frozenset(p) for o in worn for p in itertools.combinations({i["id"] for i in o}, 2)}
        taken = [{i for i in lk.item_ids if by_id.get(i, {}).get("tags", {}).get("category") != "outerwear"} for lk in plan.looks[:2]]
        rng = np.random.default_rng(int(sha256(f"stretch:{day}:{self.basis(day)}".encode())[:12], 16))
        lean = styles.profile(grow["id"]) if grow else None
        stretch = taste.pick_stretch(model, cands, exposure, pairs_worn, taken, rng, lean) if cands else None

        steps = list(trace.get("steps") or [])
        done = steps.pop() if steps and steps[-1].get("kind") == "done" else None
        if stretch:
            outfit, x = stretch["outfit"], stretch["x"]
            pct = taste.fit_pct(model, x, base)
            if stretch["feature"]:
                new = f"New for you: {taste.STRETCH_TEXT[stretch['feature']]}."
            else:
                a, b = (by_id[i]["tags"]["subtype"] for i in stretch["pair"])
                new = f"You've never worn your {a} with your {b}."
            idle = max(outfit, key=lambda i: self._idle_days(i, day) or 0)
            look = Look(name="Stretch", item_ids=[i["id"] for i in outfit],
                        why=f"{new} {self._stretch_hunch(pct)} Try it once and I'll learn either way.",
                        rediscovered_id=idle["id"] if (self._idle_days(idle, day) or 0) >= RESCUE_DAYS else None)
            index = min(2, len(plan.looks))
            plan.looks = plan.looks[:index] + [look]
            trace["stretch"] = {"look": index, "feature": stretch["feature"], "pair": stretch["pair"], "pct": pct,
                                "label": taste.STRETCH_TEXT[stretch["feature"]] if stretch["feature"] else "a new pairing",
                                "towards": grow["name"] if grow else None}
            steps.append({"kind": "tool", "label": "stretch()", "ok": True,
                          "detail": f"Thompson-sampled from {len(cands)} outfits you could wear: {new[:-1]} ({pct}% fit)"
                          + (f", leaning towards {grow['name'].lower()}" if grow else "")})
        fits = [taste.fit_pct(model, self._vec([by_id[i] for i in lk.item_ids if i in by_id]), base) for lk in plan.looks]
        trace["taste"] = {"n": model.n, "fit": fits}
        scores = [scorer([by_id[i] for i in lk.item_ids if i in by_id]) for lk in plan.looks]
        trace["scores"] = scores
        steps.append({"kind": "tool", "label": "score()", "ok": True,
                      "detail": " · ".join(scoring.summary("ABC"[n], b) for n, b in enumerate(scores[:3]))})
        steps.append({"kind": "tool", "label": "taste_model()", "ok": True,
                      "detail": (f"Learned from {model.n} signals · fit " + " · ".join(f"{f}%" for f in fits)) if model.n
                      else "No signals yet: the warm-up and your first wears teach it"})
        if done:
            steps.append(done)
        trace["steps"] = steps
        return plan, trace

    @staticmethod
    def _stretch_hunch(pct: int) -> str:
        if pct >= 60:
            return "From what you wear, I think it suits you."
        if pct >= 40:
            return "From what I know it's a coin toss, which is exactly why it's worth one try."
        return "It's a real stretch for you, but small steps are how a style grows."

    async def style_dna(self, day: date) -> dict:
        """What the oni has learned about your style, with evidence, this week's change, and how well it predicts you."""
        rows, choices = self.taste_data()
        model = taste.fit(rows)
        found = taste.traits(model, 4)
        now_w = {fid: round(float(model.w[i]), 3) for i, fid in enumerate(taste.IDS)}
        snaps = self.store.get_setting("taste_snapshots") or {}
        week_ago = (day - timedelta(days=7)).isoformat()
        older = sorted(d for d in snaps if d <= week_ago) or sorted(d for d in snaps if d < day.isoformat())
        week = taste.week_diff(now_w, snaps[older[-1]]) if older else []
        snaps[day.isoformat()] = now_w
        self.store.put_setting("taste_snapshots", dict(sorted(snaps.items())[-60:]))

        items = self._garments()
        main = {i["id"] for i in items if i["tags"]["category"] in ("top", "bottom", "dress")}
        possible = {frozenset(i["id"] for i in o if i["id"] in main) for o in taste.outfits(items, cold=False)}
        worn = {frozenset(i for i in ids if i in main) for ids in self.store.outfits_worn().values()} & possible
        tried = 0
        for w in self.store.worn_looks():
            plan = self.store.get_plan(plan_id=w["plan_id"])
            st = plan["trace"].get("stretch") if plan else None
            tried += int(bool(st) and st["look"] == w["look"])

        key = sha256(json.dumps([[t["feature"], round(t["weight"], 1)] for t in found] + week).encode())
        narrative = self.cache.get("dna", key)
        if narrative is None and self.settings.live and found:
            try:
                text = await asyncio.to_thread(taste.narrate_with_agent, found, week, model.n, config.PLAN_PROVIDER)
                if text:
                    narrative = {"text": text, "source": "agent"}
                    self.cache.put("dna", key, narrative)
            except Exception:
                narrative = None
        narrative = narrative or {"text": taste.narrate_with_rules(found, week, model.n), "source": "rules"}
        return {
            "signals": model.n, "counts": model.counts, "traits": found, "week": week, "narrative": narrative["text"],
            "narrative_source": narrative["source"], "accuracy": taste.evaluate(rows, choices),
            "learning": [taste.LABEL[fid] for i, fid in enumerate(taste.IDS) if model.evidence[i] == 0][:4],
            "coverage": {"worn": len(worn), "possible": len(possible),
                         "pct": round(100 * len(worn) / len(possible)) if possible else 0},
            "stretches_worn": tried,
            "styles": self.style_picture(items),
        }

    # -- style archetypes (closet/styles.py, docs/STYLE_ARCHETYPES.md)

    def style_model(self) -> styles.StyleModel:
        return styles.fit([(e["a"][0], e["b"][0]) for e in self.store.list_taste_events() if e["kind"] == "style"])

    def style_picture(self, items: list[dict] | None = None) -> dict:
        """Styles you're drawn to (board picks), what your closet says (worn outfits against each style's
        profile), and the style to grow into: the one you like most and wear least."""
        items = self._garments() if items is None else items
        model = self.style_model()
        liked = model.mix() if model.answers else []
        by_id = {i["id"]: i for i in items}
        worn = [[by_id[i] for i in ids if i in by_id] for ids in self.store.outfits_worn().values()]
        outfits = [o for o in worn if o] or taste.outfits(items, cold=False)
        closet = styles.closet_mix([self._vec(o) for o in outfits[:60]])
        return {"answers": model.answers, "liked": liked[:4], "closet": closet[:4],
                "grow": styles.grow(liked, closet, model.answers)}

    def style_quiz(self, k: int = 6) -> list[dict]:
        """Pairs of style boards, the ones the style model is least sure about, never one already asked."""
        asked = {frozenset((e["a"][0], e["b"][0])) for e in self.store.list_taste_events() if e["kind"] == "style"}
        boards = {k: v for k, v in styles_boards().items() if len(v) >= 4}  # a board needs enough pieces to read as a style
        pairs = styles.next_pairs(self.style_model(), asked | {frozenset((a, b)) for a in styles.IDS for b in styles.IDS
                                                               if a not in boards or b not in boards}, k)
        return [{"a": board_out(a, boards[a]), "b": board_out(b, boards[b])} for a, b in pairs]

    def answer_style_quiz(self, answers: list[dict]) -> int:
        n = 0
        for ans in answers[:20]:
            if ans["picked"] in styles.BY_ID and ans["other"] in styles.BY_ID and ans["picked"] != ans["other"]:
                self.store.add_taste_event("style", a=[ans["picked"]], b=[ans["other"]])
                n += 1
        return n

    def correct_taste(self, feature: str, value: float) -> None:
        if feature not in taste.INDEX:
            raise KeyError("No such taste feature.")
        self.store.add_taste_event("correct", feature=feature, value=1.0 if value > 0 else -1.0)

    def quiz(self, k: int = 6) -> list[dict]:
        """This-or-that pairs from the user's own closet: the ones the model is least sure about."""
        items = self._garments()
        if planner.outfit_gap(items):
            return []
        asked = {taste.pair_key(e["a"], e["b"]) for e in self.store.list_taste_events() if e["kind"] == "quiz"}
        cands = [(o, self._vec(o)) for o in taste.outfits(items, cold=False, every_layer=True)]
        pairs = taste.quiz_pairs(self.taste_model(), cands, k, asked)
        extras = [i for i in self.store.list_items() if i["tags"] and i["tags"]["category"] in ("shoes", "accessory")]
        return [{"a": [i["id"] for i in a], "b": [i["id"] for i in b],
                 "a_extras": self._matching_extras(a, extras), "b_extras": self._matching_extras(b, extras)} for a, b in pairs]

    def _matching_extras(self, outfit: list[dict], extras: list[dict]) -> list[str]:
        """Up to one pair of shoes and one accessory you own, closest in colour to the outfit: the right-hand
        column of a Pinterest-style collage. Shown, not judged: the quiz answer is about the outfit."""
        def rgb(item: dict) -> tuple[int, ...]:
            h = colour.measured(str(self.settings.cutout_dir / f"{item['id']}.png"))
            return tuple(int(h[k:k + 2], 16) for k in (1, 3, 5))

        pal = [rgb(i) for i in outfit]
        dist = lambda e: min(sum((x - y) ** 2 for x, y in zip(rgb(e), c, strict=True)) for c in pal)  # noqa: E731
        out = []
        for cat in ("shoes", "accessory"):
            mine = sorted((e for e in extras if e["tags"]["category"] == cat), key=dist)
            out += [e["id"] for e in mine[:1]]
        return out

    def answer_quiz(self, answers: list[dict]) -> int:
        known = {i["id"] for i in self._garments()}
        n = 0
        for ans in answers[:20]:
            a, b = [i for i in ans["picked"] if i in known], [i for i in ans["other"] if i in known]
            if a and b and set(a) != set(b):
                self.store.add_taste_event("quiz", a=a, b=b)
                n += 1
        return n

    def thrift_taste(self, pieces: list[dict], items: list[dict], model: taste.Model) -> list[dict]:
        """How well each thrift idea suits the learned taste, from the outfits it would make with what you own.
        A piece that unlocks outfits *and* suits you comes first."""
        if not model.n:
            return pieces  # nothing learned yet: no made-up percentages
        by_id = {i["id"]: i for i in items}
        cands = self._candidates(items, cold=False)
        base = float(np.mean([model.utility(x) for _, x in cands])) if cands else 0.0
        out = []
        for p in pieces:
            colour_name = (p.get("colors") or ["grey"])[0]
            ghost = {"id": f"thrift-{p['name']}", "hex": taste.name_hex(colour_name), "tags": {
                "category": p["category"], "subtype": p["name"].lower(), "primary_color": colour_name, "pattern": "solid",
                "formality": "casual", "fit": "regular", "warmth": 3}}
            mates = [by_id[i] for i in p["pairs_with"] if i in by_id]
            tops = [m for m in mates if m["tags"]["category"] == "top"]
            bottoms = [m for m in mates if m["tags"]["category"] == "bottom"]
            if p["category"] == "top":
                outfits = [[ghost, b] for b in bottoms]
            elif p["category"] == "bottom":
                outfits = [[t, ghost] for t in tops]
            elif p["category"] == "outerwear":
                outfits = [[t, b, ghost] for t, b in itertools.product(tops, bottoms)]
            else:
                outfits = [[ghost]]
            outfits = outfits[:6]
            fit = round(float(np.mean([taste.fit_pct(model, self._vec(o), base) for o in outfits]))) if outfits else 50
            out.append({**p, "taste_fit": fit})
        return sorted(out, key=lambda p: -p["outfits_unlocked"] * (0.6 + 0.8 * p["taste_fit"] / 100))

    # -- finishing touches (closet/styling.py)

    def style(self) -> dict:
        """The user's basics checklist (things they own but don't scan) and touches they said aren't them."""
        return {"basics": [], "skip": [], **(self.store.get_setting("style") or {})}

    def update_style(self, basics: list[str] | None, skip: list[str] | None) -> dict:
        st = self.style()
        if basics is not None:
            st["basics"] = sorted(set(b for b in basics if b in styling.BASIC_LABELS))
        if skip is not None:
            st["skip"] = sorted(set(x for x in skip if x in styling.PLAYS or x in styling.RECALL_BY_ID))
        self.store.put_setting("style", st)
        return st

    async def touches(self, plan_id: str, look_index: int) -> dict:
        record = self.store.get_plan(plan_id=plan_id)
        if not record:
            raise KeyError("No such plan.")
        looks = record["plan"]["looks"]
        if not 0 <= look_index < len(looks):
            raise IndexError(f"look must be 0-{len(looks) - 1}")
        items = [i for i in (self.store.get_item(x) for x in looks[look_index]["item_ids"]) if i and i["tags"]]
        st = self.style()
        owned, skip = set(st["basics"]), set(st["skip"])

        parts = (record["weather"].get("parts") or {}).values()
        coldest = min((p["feels_like_low_c"] for p in parts), default=15)
        cold = coldest <= COLD_C
        events = record["calendar"].get("events", [])
        smart = any(e.get("dress_code") for e in events) or any(i["tags"]["formality"] in ("smart_casual", "business", "formal") for i in items)
        weather_note = f"feels like {coldest}°C at the coldest" + (" (cold: layers and warm accessories welcome)" if cold else "")
        plans_note = ", ".join(f"{e['start']} {e['title']}" + (f" ({e['dress_code']})" if e.get("dress_code") else "") for e in events) or "No plans"
        read = colour.read(items, self.settings.cutout_dir)
        recall = styling.recall_for(self._garments(), cold, smart, skip, look_index)
        colour_out = {k: read[k] for k in ("summary", "plain", "scheme", "contrast", "temperature", "idea")}
        colour_out["palette"] = [{k: p[k] for k in ("item_id", "name", "hex", "neutral")} for p in read["palette"]]

        # Touches already given for this plan's earlier looks, so each look gets its own ideas. Earlier only:
        # look 0 stays stable however the user browses, and its cache entry keeps working.
        elsewhere = {t["play"] for n, ts in (self._given.get(plan_id) or {}).items() if n < look_index for t in ts}
        key = sha256((TOUCH_VERSION + config.PLAN_PROVIDER + styling.cache_parts(items, owned, skip, weather_note, plans_note)
                      + ",".join(sorted(elsewhere)) + (recall.id if recall else "")).encode())
        hit = self.cache.get("touches", key)
        if hit:
            self._given.setdefault(plan_id, {})[look_index] = hit["touches"]
            # The colour read is measured, not generated: always the current one, so older cache entries pick up new fields.
            return {**hit, "touches": with_examples(hit["touches"]), "colour": colour_out, "trace": {**hit["trace"], "cached": True}}

        touches, trace, source, recall_text = [], {"failures": []}, "rules", ""
        if self.settings.live:
            for provider in [config.PLAN_PROVIDER] + [p for p in ("meta",) if p != config.PLAN_PROVIDER]:
                try:
                    picked, t = await asyncio.to_thread(styling.touches_with_agent, items, weather_note, plans_note,
                                                        owned, skip, provider, elsewhere, colour.prompt_line(read), recall)
                    touches = styling.clean(picked, owned, skip)
                    recall_text = picked.recall.strip()
                    if touches:
                        trace, source = {**t, "failures": trace["failures"]}, "agent"
                        break
                    trace["failures"].append(f"{provider}: no usable touches")
                except Exception as e:
                    trace["failures"].append(config.redact(f"{provider}: {type(e).__name__}: {e}")[:300])
        if not touches:
            touches = styling.touches_with_rules(items, cold, smart, owned, skip, read["idea_play"])
            trace = {**trace, "provider": "rules"}
        recall_out = None
        if recall:
            text = recall_text or f"Got {recall.name}? It would {recall.lift}. If it's tucked away somewhere, scan it in."
            recall_out = {"id": recall.id, "name": recall.name, "text": text}
        out = {"plan_id": plan_id, "look": look_index, "touches": touches, "source": source, "trace": trace,
               "colour": colour_out, "recall": recall_out}
        if source == "agent":
            self.cache.put("touches", key, out)
        self._given.setdefault(plan_id, {})[look_index] = touches
        return {**out, "touches": with_examples(touches)}


STYLE_BOARDS = config.ROOT / "fixtures" / "style_boards"  # scripts/make_style_boards.py


def styles_boards() -> dict[str, list[dict]]:
    path = STYLE_BOARDS / "boards.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def board_out(style_id: str, pieces: list[dict]) -> dict:
    return {"style": style_id, "name": styles.BY_ID[style_id].name, "pieces": [
        {"id": f"{style_id}/{p['id']}", "category": p["category"], "name": p["name"],
         "cutout_url": f"/api/style-boards/{style_id}/{p['id']}.webp"} for p in pieces]}


def with_examples(touches: list[dict]) -> list[dict]:
    """Each touch with its example picture, when the playbook has one."""
    return [{**t, "example_url": f"/api/touch-examples/{t['play']}.jpg" if (TOUCH_EXAMPLES / f"{t['play']}.jpg").exists() else None}
            for t in touches]


def today_local() -> date:
    return datetime.now(timezone.utc).astimezone().date()
