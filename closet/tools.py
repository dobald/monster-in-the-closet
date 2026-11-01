"""The planner's tools: today's weather (Open-Meteo, free, no key) and the user's calendar.

Both return small JSON-able dicts so they can be handed to a model as tool results,
recorded for fixture mode, and hashed into the plan cache key.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

import httpx

from . import config

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
# Day parts the outfit has to survive. Hours are local to the forecast location.
DAY_PARTS = {"morning": range(7, 12), "afternoon": range(12, 18), "evening": range(18, 23)}
WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "fog",
       51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
       71: "light snow", 73: "snow", 75: "heavy snow", 80: "showers", 81: "showers", 82: "heavy showers",
       95: "thunderstorm", 96: "thunderstorm", 99: "thunderstorm"}

# Where to forecast. Set MONSTER_LAT / MONSTER_LON in .env; requests can override.
DEFAULT_LAT = float(os.environ.get("MONSTER_LAT", "43.6532"))
DEFAULT_LON = float(os.environ.get("MONSTER_LON", "-79.3832"))
CALENDAR_PATH = Path(os.environ.get("MONSTER_CALENDAR", config.ROOT / "fixtures" / "calendar_sample.json"))


def get_weather(day: date, lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON) -> dict:
    """Per day-part temperature range, feels-like low and rain chance for one day."""
    r = httpx.get(OPEN_METEO, timeout=20, params={
        "latitude": lat, "longitude": lon, "timezone": "auto",
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,weather_code",
        "start_date": day.isoformat(), "end_date": day.isoformat(),
    })
    r.raise_for_status()
    h = r.json()["hourly"]
    parts = {}
    for name, hours in DAY_PARTS.items():
        idx = [i for i, t in enumerate(h["time"]) if int(t[11:13]) in hours]
        if not idx:
            continue
        codes = [h["weather_code"][i] for i in idx]
        worst = max(codes)
        parts[name] = {
            "temp_c": [round(min(h["temperature_2m"][i] for i in idx)), round(max(h["temperature_2m"][i] for i in idx))],
            "feels_like_low_c": round(min(h["apparent_temperature"][i] for i in idx)),
            "rain_chance_pct": max((h["precipitation_probability"][i] or 0) for i in idx),
            "sky": WMO.get(worst, f"code {worst}"),
        }
    return {"date": day.isoformat(), "location": {"lat": lat, "lon": lon}, "parts": parts}


def get_calendar(day: date, path: Path = CALENDAR_PATH) -> dict:
    """Events for one day from a JSON list or an .ics file. Missing file -> no events."""
    if not path.exists():
        return {"date": day.isoformat(), "events": [], "note": "no calendar connected"}
    if path.suffix.lower() == ".ics":
        today = ics_events(path.read_bytes(), day)
    else:
        today = []
        for e in json.loads(path.read_text()):
            start = e["start"]
            # JSON sample events may give just "HH:MM" (they recur daily for demos).
            if len(start) == 5:
                today.append(e)
            elif start[:10] == day.isoformat():
                today.append({**e, "start": start[11:16], "end": (e.get("end") or "")[11:16] or None})
    today.sort(key=lambda e: (e["start"] != "all day", e["start"]))
    return {"date": day.isoformat(), "events": [
        {k: e.get(k) for k in ("start", "end", "title", "location", "dress_code") if e.get(k)} for e in today
    ]}


def _calendar(data: bytes):
    import icalendar
    try:
        return icalendar.Calendar.from_ical(data)
    except ValueError:
        return None


MAX_EVENTS_PER_DAY = 40


def ics_count(data: bytes) -> int:
    """How many events an .ics file holds (0 if it isn't one)."""
    cal = _calendar(data)
    return len(cal.walk("VEVENT")) if cal else 0


def ics_events(data: bytes, day: date) -> list[dict]:
    """One day's events from an .ics file, repeating events included, in this computer's local time.

    Google, Apple and Outlook feeds mix UTC times, TZID times and all-day dates;
    recurring_ical_events expands RRULEs (a weekly class) and drops EXDATEs.
    """
    import recurring_ical_events
    cal = _calendar(data)
    if cal is None:
        return []
    for ev in cal.walk("VEVENT"):
        # An event repeating every hour, minute or second is never a plan to dress for, and expanding
        # one from an uploaded or linked file could take minutes: keep just its first occurrence.
        rule = ev.get("RRULE")
        if rule and str((rule.get("FREQ") or [""])[0]).upper() in ("HOURLY", "MINUTELY", "SECONDLY"):
            del ev["RRULE"]
    out = []
    for ev in list(recurring_ical_events.of(cal).at(day))[:MAX_EVENTS_PER_DAY]:
        start, end = ev.get("DTSTART"), ev.get("DTEND")
        s, e = (start.dt if start else None), (end.dt if end else None)
        if s is None:
            continue
        timed = isinstance(s, datetime)
        if timed and s.tzinfo:
            s = s.astimezone()  # to local time
            e = e.astimezone() if isinstance(e, datetime) and e.tzinfo else e
        if timed and s.date() != day:
            continue  # a late event in another time zone that lands on the next day here
        out.append({"start": s.strftime("%H:%M") if timed else "all day",
                    "end": e.strftime("%H:%M") if timed and isinstance(e, datetime) else None,
                    "title": str(ev.get("SUMMARY", "Event")).strip() or "Event",
                    "location": str(ev.get("LOCATION", "")).strip() or None})
    return out


TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "Today's forecast for the user's location, split into morning, afternoon and evening: "
                       "temperature range, feels-like low, rain chance and sky.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "get_calendar",
        "description": "The user's events today with start time, title, location and any dress code.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    }},
]
