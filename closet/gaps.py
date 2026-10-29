"""The gap finder: the few pieces that would unlock the most outfits, to find second-hand.

Same shape as the planner: Muse Spark Open (Baseten) reasons over the wardrobe and
returns pieces in a fixed schema, each with the wardrobe items it pairs with. The
"+N outfits" number is never the model's claim: it is counted here from those
pairings, and pieces are ranked by it. A rule-based finder covers fixture mode and
failures. Shoes and accessories are left out: scans cover clothes, so a missing pair
of shoes probably just wasn't photographed.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from datetime import date

from . import config
from .planner import PERSONA, preference_lines, wardrobe_lines
from .schema import GapPiece, GapReport

GAP_RULES = (
    "Find the 3 pieces this person's closet is missing: the ones that would create the most new outfits with "
    "what they already own and suit the coming weeks' weather. Each piece must be a top, bottom, dress or "
    "outerwear (no shoes or accessories), must not duplicate something they own, and must pair with at least "
    "2 of their items (list those ids in pairs_with). Favour versatile, durable pieces that are easy to find "
    "second-hand; never name a fast-fashion brand. Respect their learned preferences and skip anything in "
    "the 'already watching' or 'not for me' lists."
)
# Spark Open ignores field descriptions in the JSON schema, so every format rule is spelled out here.
VOICE = (
    "Format rules: 'summary' is one plain sentence under 20 words, normal capitalisation, no emoji. 'name' is "
    "2-4 words with no category prefix, e.g. 'Wool overshirt' or 'Brown corduroy trousers'. 'colors' are 1-2 "
    "plain colour names. 'pairs_with' lists EVERY wardrobe id the piece works with, not just a few. 'why' is at "
    "most 2 short sentences, under 30 words, in plain warm words; never mention ids or warmth scores. "
    "'look_for' is 2-3 short sentences of concrete second-hand tips: fabric content to check on the label, fit, "
    "quality details, condition checks. 'price_range' is a typical second-hand price in dollars like '$20-45'. "
    "'search_terms' are 2-3 short phrases without the words 'second hand' or 'thrifted'."
)


def season_for(day: date) -> str:
    return ("winter", "winter", "spring", "spring", "spring", "summer",
            "summer", "summer", "fall", "fall", "fall", "winter")[day.month - 1]


# ---------------------------------------------------------------- the count


def outfits_unlocked(category: str, pairs_with: list[str], items: list[dict]) -> int:
    """New outfit combinations a piece creates with the items it pairs with."""
    by_id = {i["id"]: i for i in items}
    cats = Counter(by_id[i]["tags"]["category"] for i in set(pairs_with) if i in by_id)
    if category == "top":
        return cats["bottom"]
    if category == "bottom":
        return cats["top"]
    if category == "dress":
        return 1 + cats["outerwear"]
    if category == "outerwear":  # layered over every paired top + bottom, and paired dresses
        return cats["top"] * cats["bottom"] + cats["dress"]
    return 0


def clean_report(report: GapReport, items: list[dict]) -> list[dict]:
    """Drop invented ids and pieces that pair with too little; attach the count; most outfits first."""
    known = {i["id"] for i in items}
    out, seen = [], set()
    for p in report.pieces:
        pairs = list(dict.fromkeys(i for i in p.pairs_with if i in known))
        name = _tidy_name(p.name, p.category)
        if len(pairs) < 2 or name.lower() in seen:
            continue
        seen.add(name.lower())
        n = outfits_unlocked(p.category, pairs, items)
        if n > 0:
            out.append({**p.model_dump(), "name": name, "pairs_with": pairs, "outfits_unlocked": n,
                        "price_range": p.price_range if re.search(r"\d.*\d", p.price_range) else "",
                        "search_terms": [_tidy_search(s) for s in p.search_terms][:3]})
    return sorted(out, key=lambda p: -p["outfits_unlocked"])[:3]


def _tidy_name(name: str, category: str) -> str:
    """'outerwear — mid-weight wool shacket in oatmeal or grey' -> 'Mid-weight wool shacket'."""
    name = re.sub(rf"^\s*{category}\s*[-–—:|]\s*", "", name, flags=re.I)
    name = re.split(r"\s+in\s+|,|\(", name)[0].strip()
    return name[:1].upper() + name[1:]


def _tidy_search(term: str) -> str:
    return re.sub(r"\b(second[- ]hand|thrifted|vintage thrift)\b", "", term, flags=re.I).strip()


# ---------------------------------------------------------------- the agent


def find_gaps_with_agent(items: list[dict], prefs: list[dict], today: date, weather_note: str,
                         watching: list[str], dismissed: list[str], provider: str) -> tuple[GapReport, dict]:
    client = config.client_for(provider)
    model = config.PLAN_MODEL[provider]
    t0 = time.time()
    context = (
        f"{PERSONA}\n\n{GAP_RULES}\n\nWardrobe ({len(items)} garments):\n{wardrobe_lines(items, today)}\n\n"
        f"Learned preferences:\n{preference_lines(prefs)}\n\n"
        f"Season: {season_for(today)} ({today:%B}). Weather lately: {weather_note}\n"
        f"Already watching: {', '.join(watching) or 'nothing'}\nNot for me: {', '.join(dismissed) or 'nothing'}"
    )
    resp = client.chat.completions.parse(
        model=model,
        messages=[{"role": "system", "content": context},
                  {"role": "user", "content": "What should I keep an eye out for when thrifting? " + VOICE}],
        response_format=GapReport, reasoning_effort="medium", max_tokens=6000,
    )
    usage = resp.usage
    return resp.choices[0].message.parsed, {
        "provider": provider, "model": model, "seconds": round(time.time() - t0, 1),
        "tokens_in": usage.prompt_tokens if usage else 0, "tokens_out": usage.completion_tokens if usage else 0,
    }


# ---------------------------------------------------------------- rules (fixture mode and fallback)

# A few versatile staples per category; the first one not already owned and not dismissed wins.
STAPLES: dict[str, list[dict]] = {
    "outerwear": [
        {"name": "Wool overcoat", "owns": ["coat", "overcoat"], "colors": ["camel"], "look_for": "Check the label for 70%+ wool, a full lining "
         "and shoulders that sit at yours. Skip pilling under the arms.", "price_range": "$30-80",
         "search_terms": ["wool overcoat camel", "vintage wool coat"]},
        {"name": "Denim jacket", "owns": ["denim", "jean", "trucker"], "colors": ["mid blue"], "look_for": "Look for heavy 100% cotton denim, metal "
         "buttons and even fading; avoid stretch denim.", "price_range": "$15-40",
         "search_terms": ["vintage denim jacket", "trucker jacket"]},
    ],
    "bottom": [
        {"name": "Straight dark jeans", "owns": ["jean", "denim"], "colors": ["indigo"], "look_for": "Rigid or low-stretch cotton, a clean "
         "dark wash and an intact hem; check the crotch for wear.", "price_range": "$15-35",
         "search_terms": ["dark straight jeans", "raw denim straight"]},
        {"name": "Pleated wool trousers", "owns": ["trouser", "slack"], "colors": ["grey"], "look_for": "Wool or wool blend with a lining to "
         "the knee; check the seat and pockets for shine.", "price_range": "$15-40",
         "search_terms": ["pleated wool trousers", "vintage wool pants grey"]},
    ],
    "top": [
        {"name": "Oxford shirt", "owns": ["oxford", "button-down", "button down", "dress shirt"], "colors": ["light blue"], "look_for": "100% cotton oxford cloth, a button-down "
         "collar and a clean, unfrayed collar edge.", "price_range": "$10-25",
         "search_terms": ["oxford button down shirt", "vintage oxford shirt"]},
        {"name": "Merino crewneck", "owns": ["sweater", "jumper", "merino", "knit"], "colors": ["navy"], "look_for": "100% merino or lambswool on the label; hold "
         "it to the light for thin spots and check the elbows.", "price_range": "$12-35",
         "search_terms": ["merino crewneck sweater", "lambswool jumper"]},
    ],
}


PLURAL = {"outerwear": "layers", "top": "tops", "bottom": "bottoms"}


def find_gaps_with_rules(items: list[dict], dismissed: list[str], watching: list[str]) -> GapReport:
    """Whichever category is thinnest gets a versatile staple that pairs with everything opposite it.
    Never one the closet already has: suggesting a second pair of dark jeans to someone who owns
    them is exactly the shopping app this isn't."""
    skip = {n.lower() for n in dismissed + watching}
    cats = Counter(i["tags"]["category"] for i in items)
    ids = lambda *c: [i["id"] for i in items if i["tags"]["category"] in c]  # noqa: E731

    def owned(cat: str, staple: dict) -> bool:
        return any(i["tags"]["category"] == cat and any(w in i["tags"]["subtype"].lower() for w in staple["owns"]) for i in items)

    pieces = []
    for cat in sorted(STAPLES, key=lambda c: cats[c]):
        staple = next((s for s in STAPLES[cat] if s["name"].lower() not in skip and not owned(cat, s)), None)
        if not staple:
            continue
        pairs = ids("top", "bottom") if cat == "outerwear" else ids("bottom") if cat == "top" else ids("top")
        if len(pairs) < 2:
            continue
        why = {"outerwear": ("Nothing to wear over your outfits yet. One good layer covers every cold morning." if not cats["outerwear"]
                             else "A second layer means one for cold mornings and one for the in-between days."),
               "bottom": ("Your tops outnumber your bottoms. One more pair doubles your options." if cats["top"] > cats["bottom"]
                          else "One more bottom gives every top a new partner."),
               "top": "Your bottoms need more tops to rotate with."}[cat]
        pieces.append(GapPiece(category=cat, pairs_with=pairs, why=why, **{k: v for k, v in staple.items() if k != "owns"}))
    thin = min(STAPLES, key=lambda c: cats[c])
    summary = "Nothing to wear over your outfits yet." if cats["outerwear"] == 0 else f"Your closet is lightest on {PLURAL[thin]}."
    return GapReport(summary=summary, pieces=pieces)
