"""One score for an outfit, shared by every way a plan is made.

The rule picker chooses from every outfit the closet can make by this score; in live mode Muse
Spark Open proposes five candidates and this score picks looks A and B from them. Five parts,
each on a similar scale so none can drown the others (the old rule picker gave half a point
per idle day, uncapped, so a 400-day coat beat the weather):

- rescue:   up to +3 for the most forgotten piece, capped at 90 days idle
- weather:  outfit warmth against the day's target, a layer when it's cold (and not when it isn't),
            an evening that gets much colder, pale trousers on a rainy day
- occasion: smart pieces on a day with a dress code, nothing sporty to a crit, not overdressed otherwise.
            Planning for one event (closet/occasions.py), it is the distance from that event's rung on the
            formality ladder instead, weighted up, and the weather is only the hours the event covers
- colour:   docs/STYLE_GUIDE.md section 1 on the measured colour read: neutrals with one pop score best,
            two clashing colours worst; head-to-toe dark and two patterns at once cost a little
- taste:    the learned taste's utility for this outfit (closet/taste.py), 0 until it has learned anything
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

RESCUE_MAX = 3.0
RESCUE_CAP_DAYS = 90
RESCUE_FROM_DAYS = 14  # worn in the last two weeks isn't a rescue
NEVER_WORN_DAYS = 30  # no history at all: probably a bit forgotten, not very
LAYER_BELOW_C = 12
TASTE_WEIGHT = 1.2
OCCASION_WEIGHT = 1.5  # planning for one event: suiting it matters more than on an ordinary day

SCHEME = {"all neutral": 0.6, "neutral + accent": 0.9, "tonal": 0.5, "analogous": 0.6, "complementary": 0.2,
          "contrasting": -0.4}


@dataclass(frozen=True)
class Day:
    target: int  # outfit warmth wanted, 1-4
    cold: bool  # a layer is wanted
    evening_drop: bool  # the evening is much colder than the afternoon
    rainy: bool
    dressy: bool  # an event with a dress code
    formality: int | None = None  # planning for one event: its rung, 0 sporty … 4 formal (closet/occasions.py)
    active: bool = False  # that event is sport


def day_context(weather: dict, calendar: dict, event: dict | None = None) -> Day:
    """The day as the scorer sees it. With `event`, just that occasion: its formality and the weather
    for the hours it covers."""
    parts = weather.get("parts") or {}
    occasion = None
    if event:
        from . import occasions
        occasion = occasions.read(event)
        parts = occasions.parts_for(event, parts)
    feels = [p["feels_like_low_c"] for p in parts.values()]
    coldest = min(feels, default=15)
    after, eve = parts.get("afternoon"), parts.get("evening")
    return Day(
        target=4 if coldest < 3 else 3 if coldest < 10 else 2 if coldest < 18 else 1,
        cold=coldest < LAYER_BELOW_C,
        evening_drop=bool(after and eve and eve["feels_like_low_c"] <= after["feels_like_low_c"] - 6),
        rainy=any(p.get("rain_chance_pct", 0) >= 50 for p in parts.values()),
        dressy=occasion.formality >= 2 if occasion else any(e.get("dress_code") for e in calendar.get("events", [])),
        formality=occasion.formality if occasion else None,
        active=bool(occasion and occasion.active),
    )


def idle_days(item: dict, today: date) -> int:
    worn = item.get("last_worn")
    return NEVER_WORN_DAYS if not worn else (today - datetime.fromisoformat(worn).date()).days


def breakdown(outfit: list[dict], read: dict, day: Day, today: date, taste_utility: float = 0.0) -> dict:
    """The score of one outfit, part by part. `read` is its colour read (closet/colour.read)."""
    tags = [i["tags"] for i in outfit]
    core = [i for i in outfit if i["tags"]["category"] in ("top", "bottom", "dress")]
    layers = [t for t in tags if t["category"] == "outerwear"]

    longest = max((idle_days(i, today) for i in core), default=0)
    rescue = RESCUE_MAX * min(longest, RESCUE_CAP_DAYS) / RESCUE_CAP_DAYS if longest >= RESCUE_FROM_DAYS else 0.0

    main = max((t["warmth"] for t in tags if t["category"] in ("top", "dress")), default=2)
    warmth = main + (0.5 * max(t["warmth"] for t in layers) if layers else 0)
    weather = -0.9 * abs(warmth - day.target)
    if day.cold != bool(layers):
        weather -= 0.4  # cold with no layer, or carrying a coat on a warm day
    if day.evening_drop and not layers:
        weather -= 0.3
    pale_bottom = any(p["category"] == "bottom" and p["light"] > 0.8 for p in read["palette"])
    if day.rainy and pale_bottom:
        weather -= 0.3

    forms = {t["formality"] for t in tags}
    smart = bool(forms & {"smart_casual", "business", "formal"})
    if day.formality is not None:
        from .occasions import rung
        core_forms = [rung(i["tags"]["formality"]) for i in core] or [1]
        mean = sum(core_forms) / len(core_forms)
        occasion = OCCASION_WEIGHT * (0.8 - 0.7 * abs(mean - day.formality))
        if day.formality >= 2 and "athleisure" in forms:
            occasion -= 0.6  # trackpants to a dinner, whatever else is on
    elif day.dressy:
        occasion = (0.8 if smart else -0.6) - (0.6 if "athleisure" in forms else 0)
    else:
        occasion = -0.3 if forms & {"business", "formal"} else 0.0

    lights = [p["light"] for p in read["palette"]]
    colour = SCHEME.get(read["scheme"], 0.0)
    if lights and max(lights) < 0.3:
        colour -= 0.3  # head-to-toe dark wants a light break
    if sum(t["pattern"] != "solid" for t in tags) >= 2:
        colour -= 0.6

    parts = {"rescue": rescue, "weather": weather, "occasion": occasion, "colour": colour,
             "taste": TASTE_WEIGHT * taste_utility}
    return {**{k: round(v, 2) for k, v in parts.items()}, "total": round(sum(parts.values()), 2)}


def pick_two(scored: list[tuple[list[dict], dict]]) -> list[int]:
    """Indexes of looks A and B. A is the best look that rescues something (or simply the best);
    B is the best look that shares no top, bottom or dress with A."""
    if not scored:
        return []
    best = lambda idx: max(idx, key=lambda n: scored[n][1]["total"])  # noqa: E731
    everything = range(len(scored))
    rescuing = [n for n in everything if scored[n][1]["rescue"] > 0]
    a = best(rescuing or everything)
    core = lambda n: {i["id"] for i in scored[n][0] if i["tags"]["category"] in ("top", "bottom", "dress")}  # noqa: E731
    apart = [n for n in everything if n != a and not core(n) & core(a)]
    others = apart or [n for n in everything if n != a]
    return [a, best(others)] if others else [a]


def summary(label: str, b: dict) -> str:
    """One trace line: 'A 4.1 = rescue 3.0 · weather -0.9 · colour 0.9 · taste 1.1'."""
    parts = " · ".join(f"{k} {v:+.1f}" for k, v in b.items() if k != "total" and abs(v) >= 0.05)
    return f"{label} {b['total']:.1f}" + (f" = {parts}" if parts else "")
