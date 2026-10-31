"""Reading a calendar event as an occasion to dress for.

An event is a title, a time, maybe a place and a dress code. This turns it into what the
scorer and the planning agent need: how dressed up (a rung on the formality ladder the
tags use), whether it's in the evening, outdoors or active, and one line of advice for the
agent. A stated dress code always wins over the title; the title wins over a guess.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

LADDER = ["athleisure", "casual", "smart_casual", "business", "formal"]
WORDS = {"athleisure": "sporty", "casual": "casual", "smart_casual": "smart casual", "business": "business", "formal": "formal"}

# (pattern, kind, rung, advice). First match wins, so the more specific kinds come first.
KINDS = [
    (r"black.?tie|gala|wedding|ball\b|opera|formal", "formal", 4,
     "Your most formal pieces, pressed. Dark or deep colours, nothing sporty, nothing distressed."),
    (r"funeral|memorial|wake\b", "funeral", 4,
     "Quiet and dark: black, navy or charcoal, plain fabrics, no prints or logos."),
    (r"interview|pitch|presentation|present\b|client|board|court|conference|networking|career fair",
     "interview", 3,
     "Polished and plain: a collar or a clean knit, tidy trousers, nothing loud or creased. It should not be the story."),
    (r"\bdate\b|anniversary", "date", 2,
     "One step up from every day, with one thing that feels like you: a colour, a texture, a good layer."),
    (r"dinner|drinks|cocktail|bar\b|party|birthday|celebrat|theat(er|re)|show\b|gallery|exhibition|opening|church",
     "evening_out", 2,
     "Smart casual: a better top than usual, dark trousers or jeans, a layer you can take off indoors."),
    (r"gym|workout|run\b|running|yoga|pilates|climb|hike|tennis|soccer|football|basketball|swim|practice|training|match",
     "active", 0,
     "Clothes you can move and sweat in, with a warm layer for before and after."),
    (r"crit|review|meeting|1:1|one.on.one|standup|work\b|office|shift|seminar", "work", 2,
     "Neat and easy to move in: smart casual that still feels like you."),
    (r"concert|gig|festival|rave|club", "gig", 1,
     "Expressive and practical: something with character, sturdy shoes, a layer you can tie round your waist."),
    (r"class|lecture|lab\b|tutorial|study|library|exam", "class", 1,
     "Comfortable for sitting a long time, with a layer for cold lecture halls."),
    (r"brunch|lunch|coffee|cafe|movie|cinema|shopping|errand|hangout|hang out|picnic|park|walk|travel|flight|train",
     "casual", 1, "Relaxed and comfortable, still put together."),
]
OUTDOORS = r"outside|outdoor|patio|terrace|rooftop|park|picnic|garden|beach|hike|festival|bbq|barbecue|walk|market|field|stadium"
DRESS_CODES = [
    (r"black.?tie|formal|cocktail", 4), (r"business|professional|suit", 3),
    (r"smart|dressy|semi", 2), (r"casual|relaxed", 1), (r"sport|athletic|active", 0),
]


@dataclass(frozen=True)
class Occasion:
    kind: str  # formal | funeral | interview | date | evening_out | work | active | gig | class | casual | everyday
    formality: int  # 0 sporty … 4 formal, the same ladder as the garment tags
    evening: bool
    outdoors: bool
    advice: str
    why: str  # what the read was based on, for the trace and the app

    @property
    def active(self) -> bool:
        return self.kind == "active"

    def label(self) -> str:
        bits = [WORDS[LADDER[self.formality]]]
        if self.evening:
            bits.append("evening")
        if self.outdoors:
            bits.append("outdoors")
        return " · ".join(bits)

    def prompt_line(self, event: dict) -> str:
        """The occasion as one paragraph for the planning agent."""
        when = f" at {event['start']}" if event.get("start") and event["start"] != "all day" else ""
        where = f" ({event['location']})" if event.get("location") else ""
        return (f"Dress me for one occasion, not the whole day: {event.get('title', 'an event')}{when}{where}. "
                f"Read: {self.label()}. {self.advice} Every look must suit this occasion.")

    def to_dict(self) -> dict:
        return {**asdict(self), "label": self.label()}


def rung(form: str) -> int:
    return LADDER.index(form) if form in LADDER else 1


def read(event: dict) -> Occasion:
    title = (event.get("title") or "").lower()
    place = (event.get("location") or "").lower()
    text = f"{title} {place}"
    start = event.get("start") or ""
    hour = int(start[:2]) if re.match(r"\d\d:", start) else None
    evening = hour is not None and hour >= 17

    kind, form, advice, why = "everyday", 2 if evening else 1, "Your usual, just right for the weather.", "no keyword matched"
    for pattern, k, f, a in KINDS:
        m = re.search(pattern, text)
        if m:
            kind, form, advice, why = k, f, a, f"“{m.group(0)}” in the title"
            break
    code = (event.get("dress_code") or "").lower()
    for pattern, f in DRESS_CODES:
        if code and re.search(pattern, code):
            form, why = f, f"dress code “{event['dress_code']}”"
            break
    outdoors = bool(re.search(OUTDOORS, text))
    return Occasion(kind, form, evening, outdoors, advice, why)


def parts_for(event: dict, parts: dict) -> dict:
    """The weather day-parts an event overlaps (all of them for an all-day or untimed event)."""
    from .tools import DAY_PARTS
    start, end = event.get("start") or "", event.get("end") or ""
    if not re.match(r"\d\d:", start):
        return parts
    h0 = int(start[:2])
    h1 = int(end[:2]) if re.match(r"\d\d:", end) else h0 + 2
    hours = set(range(h0, max(h1, h0 + 1)))
    hit = {name: p for name, p in parts.items() if hours & set(DAY_PARTS.get(name, ()))}
    if hit:
        return hit
    # Before 07:00 or after 23:00: the nearest part.
    name = "morning" if h0 < 12 else "evening"
    return {name: parts[name]} if name in parts else parts
