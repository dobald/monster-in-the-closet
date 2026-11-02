"""Fabrics people love or won't wear.

The tagger writes a free-text material_guess ("cotton-blend fleece", "suiting twill, likely
polyester-viscose blend"); this sorts it into a few families a person can have a feeling about.
A piece can be in more than one ("cotton-blend fleece" is cotton and fleece). Loving a family nudges
looks towards it; avoiding one (itchy wool, sweaty polyester) costs much more, so an avoided piece
only turns up when the closet has nothing else that works.
"""

from __future__ import annotations

import re

# family -> (label, pattern on material_guess)
FAMILIES: dict[str, tuple[str, re.Pattern]] = {
    "cotton": ("Cotton", re.compile(r"cotton|jersey|oxford|poplin|chambray|canvas|terry|seersucker|corduroy")),
    "denim": ("Denim", re.compile(r"denim|jean")),
    "linen": ("Linen", re.compile(r"linen|flax|hemp")),
    "wool": ("Wool", re.compile(r"wool|merino|cashmere|alpaca|mohair|angora|tweed")),
    "silk": ("Silk & satin", re.compile(r"silk|satin|chiffon")),
    "leather": ("Leather & suede", re.compile(r"(?<!faux )(?<!vegan )leather|suede|nubuck")),
    "fleece": ("Fleece", re.compile(r"fleece|sherpa|polar")),
    "synthetic": ("Synthetics", re.compile(r"polyester|nylon|acrylic|spandex|elastane|lycra|polyamide|synthetic|faux leather|vegan leather|pleather")),
}

LOVE_POINTS = 0.35  # per loved piece, for up to LOVE_CAP pieces
LOVE_CAP = 3
AVOID_POINTS = 1.5  # per avoided piece: more than any colour or occasion nudge, less than a wrong-weather outfit


def families(material_guess: str | None) -> set[str]:
    text = (material_guess or "").lower()
    return {f for f, (_, pattern) in FAMILIES.items() if pattern.search(text)}


def clean(prefs: dict | None) -> dict[str, list[str]]:
    """{"love": [...], "avoid": [...]} with unknown families dropped; a family can't be both (avoid wins)."""
    prefs = prefs or {}
    avoid = [f for f in FAMILIES if f in (prefs.get("avoid") or [])]
    love = [f for f in FAMILIES if f in (prefs.get("love") or []) and f not in avoid]
    return {"love": love, "avoid": avoid}


def avoided(outfit: list[dict], prefs: dict | None) -> list[dict]:
    """The pieces in an outfit made of something the person won't wear."""
    avoid = set(clean(prefs)["avoid"])
    return [i for i in outfit if families(i["tags"].get("material_guess")) & avoid] if avoid else []


def score(outfit: list[dict], prefs: dict | None) -> float:
    p = clean(prefs)
    if not (p["love"] or p["avoid"]):
        return 0.0
    love, avoid = set(p["love"]), set(p["avoid"])
    kinds = [families(i["tags"].get("material_guess")) for i in outfit]
    loved = sum(1 for k in kinds if k & love and not k & avoid)
    bad = sum(1 for k in kinds if k & avoid)
    return LOVE_POINTS * min(loved, LOVE_CAP) - AVOID_POINTS * bad


def prompt_lines(prefs: dict | None) -> list[dict]:
    """The same preferences, as lines for the planner and the thrift agent."""
    p = clean(prefs)
    names = lambda fs: ", ".join(FAMILIES[f][0].lower() for f in fs)  # noqa: E731
    lines = []
    if p["love"]:
        lines.append({"text": f"Loves wearing {names(p['love'])}: lean towards pieces made of it", "applies_when": None})
    if p["avoid"]:
        lines.append({"text": f"Won't wear {names(p['avoid'])}: leave those pieces out unless nothing else works, "
                              "and never suggest buying them", "applies_when": None})
    return lines


def owned(items: list[dict]) -> dict[str, int]:
    """How many tagged pieces in the closet are in each family."""
    counts = {f: 0 for f in FAMILIES}
    for i in items:
        for f in families((i.get("tags") or {}).get("material_guess")):
            counts[f] += 1
    return counts
