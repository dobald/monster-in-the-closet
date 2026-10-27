"""The oni's brain: the morning outfit pick and what it learns from evening check-ins.

Runs on Muse Spark Open (open weights, via Baseten) by default, as a small tool-using
agent: it calls get_weather and get_calendar, reasons over the wardrobe and the user's
learned preferences, then returns three looks in a fixed schema. Every look is checked
against the real wardrobe; one repair round fixes invented ids or missing bottoms. If
the open model fails, the same agent runs on Muse Spark 1.3; if that fails too (or in
fixture mode), a transparent rule-based picker answers so the morning never breaks.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime
from typing import Callable

from . import config
from .schema import CheckinLearning, Look, OutfitPlan
from .tools import TOOL_SPECS

PERSONA = (
    "You are the oni from Monster in the Closet: a small, kind closet monster who lives on forgotten clothes. "
    "Every morning you dress the user from clothes they already own, never suggesting purchases. You favour "
    "pieces they haven't worn in a while, but only when they genuinely suit the weather and the day's plans. "
    "Speak warmly and briefly, like a stylish friend."
)
RULES = (
    "Rules: use only wardrobe ids from the list. Each look is one top + one bottom, or one dress, plus "
    "outerwear when it is cold or wet, and shoes/accessories if listed. Dress for the coldest part of the day "
    "the user is out (use feels-like temperatures) and for any dress code. Follow the user's notes and learned "
    "preferences. Look 1 should rescue a forgotten item when one fits; look 3 can be a safe favourite. "
    "Make the three looks genuinely different: vary the top and the bottom when the wardrobe allows."
)
# Spark Open ignores field descriptions in the JSON schema, so the house style is spelled out in the prompt.
VOICE = (
    "Style for every text field: plain, warm everyday words, like a stylish friend texting. Never mention ids, "
    "warmth scores like '3/5', or raw numbers like '-2C' (say 'a chilly morning'). Look names are 2-3 words "
    "with no 'Look 1' prefix, e.g. 'Rescued henley'. Each 'why' is at most 2 short sentences, under 35 words."
)


# ---------------------------------------------------------------- context


def days_since(iso: str | None, today: date) -> int | None:
    return None if not iso else (today - datetime.fromisoformat(iso).date()).days


def wardrobe_lines(items: list[dict], today: date) -> str:
    """One compact line per garment. Stable ordering keeps the prompt prefix cacheable."""
    lines = []
    for it in sorted(items, key=lambda i: i["id"]):
        t = it["tags"]
        d = days_since(it.get("last_worn"), today)
        worn = f"last worn {d} days ago" if d is not None else "not worn since added"
        colors = t["primary_color"] + (f" + {', '.join(t['secondary_colors'])}" if t["secondary_colors"] else "")
        lines.append(
            f"- {it['id']}: {t['category']} | {colors} {t['subtype']} | fit {t['fit']} | pattern {t['pattern']} | "
            f"warmth {t['warmth']}/5 | {t['formality']} | seasons {','.join(t['seasons'])} | {worn}, worn {it['wear_count']}x"
        )
    return "\n".join(lines)


def preference_lines(prefs: list[dict]) -> str:
    if not prefs:
        return "No learned preferences yet."
    return "\n".join(f"- {p['text']}" + (f" (when: {p['applies_when']})" if p.get("applies_when") else "") for p in prefs)


# ---------------------------------------------------------------- validation


def validate_plan(plan: OutfitPlan, items: list[dict]) -> list[str]:
    """Problems a model plan can have that would break the app. Empty list = usable."""
    by_id = {i["id"]: i for i in items}
    errors = []
    if len(plan.looks) < 1:
        errors.append("Return 3 looks.")
    for n, look in enumerate(plan.looks, 1):
        unknown = [i for i in look.item_ids if i not in by_id]
        if unknown:
            errors.append(f"Look {n} uses ids that are not in the wardrobe: {unknown}.")
            continue
        if len(set(look.item_ids)) != len(look.item_ids):
            errors.append(f"Look {n} repeats an item.")
        cats = [by_id[i]["tags"]["category"] for i in look.item_ids]
        if "dress" not in cats and not ("top" in cats and "bottom" in cats):
            errors.append(f"Look {n} needs a top and a bottom (or a dress); it has {cats}.")
        if cats.count("bottom") > 1:
            errors.append(f"Look {n} has more than one bottom.")
        if look.rediscovered_id and look.rediscovered_id not in look.item_ids:
            look.rediscovered_id = None
    return errors


def variety_problems(plan: OutfitPlan, items: list[dict]) -> list[str]:
    """Soft check: three looks built on the same top (or bottom) when the wardrobe has others.
    Worth one repair request, never worth failing the plan."""
    by_id = {i["id"]: i for i in items}
    problems = []
    for cat in ("top", "bottom"):
        picks = [next((i for i in look.item_ids if i in by_id and by_id[i]["tags"]["category"] == cat), None)
                 for look in plan.looks]
        owned = sum(1 for i in items if i["tags"]["category"] == cat)
        if len(picks) > 1 and None not in picks and len(set(picks)) == 1 and owned > 1:
            problems.append(f"Every look uses the same {cat} ({by_id[picks[0]]['tags']['subtype']}); "
                            f"use a different {cat} in at least one look.")
    return problems


# ---------------------------------------------------------------- the agent


def plan_with_agent(
    items: list[dict],
    prefs: list[dict],
    today: date,
    notes: str,
    tool_impls: dict[str, Callable[[], dict]],
    provider: str,
) -> tuple[OutfitPlan, dict]:
    """Tool-calling loop on `provider`, then a structured final answer, then validation/repair."""
    client = config.client_for(provider)
    model = config.PLAN_MODEL[provider]
    trace = {"provider": provider, "model": model, "tool_calls": [], "repairs": 0, "tokens_in": 0, "tokens_out": 0}
    t0 = time.time()

    def count(resp) -> None:
        if resp.usage:
            trace["tokens_in"] += resp.usage.prompt_tokens
            trace["tokens_out"] += resp.usage.completion_tokens

    system = (f"{PERSONA}\n\n{RULES}\n\nWardrobe ({len(items)} garments):\n{wardrobe_lines(items, today)}\n\n"
              f"Learned preferences:\n{preference_lines(prefs)}")
    ask = f"Pick my outfits for {today:%A %d %B %Y}. Check the weather and my calendar first."
    if notes:
        ask += f" My notes for today: {notes}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": ask}]

    called: set[str] = set()
    for _ in range(4):  # a couple of tool rounds is plenty; bound it so a loop can't burn credits
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=TOOL_SPECS, reasoning_effort="medium", max_tokens=6000,
        )
        count(resp)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            break
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
            for tc in msg.tool_calls
        ]})
        for tc in msg.tool_calls:
            fn = tool_impls.get(tc.function.name)
            result = fn() if fn else {"error": f"unknown tool {tc.function.name}"}
            called.add(tc.function.name)
            trace["tool_calls"].append(tc.function.name)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    # Never plan blind: if the model skipped a tool, give it the data anyway.
    for name, fn in tool_impls.items():
        if name not in called:
            messages.append({"role": "user", "content": f"(For reference, {name} returns: {json.dumps(fn())})"})
            trace["tool_calls"].append(f"{name} (injected)")

    final_ask = {"role": "user", "content": "Now return exactly three looks as JSON. Use only wardrobe ids from the list. "
                                            + VOICE}
    plan = _parse_plan(client, model, messages + [final_ask], count)
    errors = validate_plan(plan, items)
    problems = errors + variety_problems(plan, items)
    if problems:
        trace["repairs"] = 1
        repair = messages + [final_ask, {"role": "assistant", "content": plan.model_dump_json()},
                             {"role": "user", "content": "That plan has problems: " + " ".join(problems) + " Return a corrected plan."}]
        fixed = _parse_plan(client, model, repair, count)
        fixed_errors = validate_plan(fixed, items)
        if not fixed_errors:
            plan = fixed
        elif errors:  # a broken plan we couldn't fix; a merely repetitive one is still usable
            raise ValueError("plan still invalid after repair: " + " ".join(fixed_errors))
    plan.looks = plan.looks[:3]
    trace["seconds"] = round(time.time() - t0, 1)
    return plan, trace


def _parse_plan(client, model: str, messages: list[dict], count) -> OutfitPlan:
    resp = client.chat.completions.parse(
        model=model, messages=messages, response_format=OutfitPlan, reasoning_effort="low", max_tokens=4000,
    )
    count(resp)
    return resp.choices[0].message.parsed


# ---------------------------------------------------------------- rules (fixture mode and last-resort fallback)


def _coldest_feels_like(weather: dict) -> float:
    parts = weather.get("parts") or {}
    return min((p["feels_like_low_c"] for p in parts.values()), default=15)


def plan_with_rules(items: list[dict], weather: dict, calendar: dict, notes: str, today: date) -> OutfitPlan:
    """Deterministic picker: warmth from the coldest feels-like, formality from events, forgotten pieces first."""
    cold = _coldest_feels_like(weather)
    target_warmth = 4 if cold < 3 else 3 if cold < 10 else 2 if cold < 18 else 1
    dressy = any(e.get("dress_code") for e in calendar.get("events", []))
    avoid_black = "black" in notes.lower() and any(w in notes.lower() for w in ("no ", "not ", "nothing", "avoid"))

    def ok(it: dict) -> bool:
        return not (avoid_black and "black" in it["tags"]["primary_color"].lower())

    def forgotten(it: dict) -> int:
        d = days_since(it.get("last_worn"), today)
        return 60 if d is None else d

    def score(it: dict) -> float:
        t = it["tags"]
        fit = -abs(t["warmth"] - target_warmth) * 6
        form = 4 if dressy and t["formality"] in ("smart_casual", "business") else 0
        return forgotten(it) * 0.5 + fit + form

    pool = [i for i in items if ok(i)] or items
    tops = sorted((i for i in pool if i["tags"]["category"] == "top"), key=score, reverse=True)
    bottoms = sorted((i for i in pool if i["tags"]["category"] == "bottom"), key=score, reverse=True)
    outer = sorted((i for i in pool if i["tags"]["category"] == "outerwear"), key=score, reverse=True)
    if not tops or not bottoms:
        raise ValueError("The wardrobe needs at least one top and one bottom for a plan.")

    combos = [(tops[0], bottoms[0]), (tops[min(1, len(tops) - 1)], bottoms[min(1, len(bottoms) - 1)])]
    favourites = sorted(pool, key=lambda i: i["wear_count"], reverse=True)
    fav_top = next((i for i in favourites if i["tags"]["category"] == "top"), tops[-1])
    fav_bottom = next((i for i in favourites if i["tags"]["category"] == "bottom"), bottoms[-1])
    combos.append((fav_top, fav_bottom))

    looks = []
    for n, (top, bottom) in enumerate(combos):
        ids = [top["id"], bottom["id"]] + ([outer[0]["id"]] if outer and cold < 12 else [])
        rescued = max((top, bottom), key=forgotten)
        name = ["Rediscovered pick", "Fresh mix", "Safe favourite"][n]
        why = (f"{top['tags']['subtype'].capitalize()} with {bottom['tags']['subtype']}"
               f" — warm enough for a feels-like low of {round(cold)}°" + (", and smart enough for today's plans." if dressy else "."))
        looks.append(Look(name=name, item_ids=ids, why=why,
                          rediscovered_id=rescued["id"] if forgotten(rescued) >= 30 else None))

    parts = weather.get("parts") or {}
    temps = [t for p in parts.values() for t in p["temp_c"]]
    weather_summary = (f"{min(temps)}–{max(temps)}°, feels like {round(cold)}° at the coldest"
                       if temps else "Weather unavailable")
    events = calendar.get("events", [])
    plans_summary = ", ".join(f"{e['start']} {e['title']}" for e in events) or "No plans today"
    return OutfitPlan(weather_summary=weather_summary, plans_summary=plans_summary, looks=looks)


# ---------------------------------------------------------------- evening check-in


def learn_with_agent(checkin: dict, worn: list[dict], weather: dict, prefs: list[dict], provider: str) -> tuple[CheckinLearning, dict]:
    client = config.client_for(provider)
    model = config.PLAN_MODEL[provider]
    outfit = "; ".join(f"{i['tags']['primary_color']} {i['tags']['subtype']} (warmth {i['tags']['warmth']}/5)" for i in worn)
    resp = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": PERSONA + " It is evening. The user just told you how today's outfit went. "
                                                   "Reply briefly and kindly, and extract at most one durable preference that "
                                                   "will improve future picks. Don't repeat a preference that is already known. "
                                                   "oni_reply: at most 2 short sentences, under 35 words, normal capitalisation, "
                                                   "no emoji or *actions*. preference: one general rule under 15 words that does "
                                                   "not name specific garments, e.g. 'Go lighter on layers for heated indoor days'. "
                                                   "applies_when: a few plain words, e.g. 'indoor days', or null. "
                                                   "Never mention warmth scores or raw temperatures."},
            {"role": "user", "content": json.dumps({
                "outfit_worn": outfit or "unknown", "weather_today": weather, "check_in": checkin,
                "already_known_preferences": [p["text"] for p in prefs],
            })},
        ],
        response_format=CheckinLearning, reasoning_effort="low", max_tokens=3000,
    )
    usage = resp.usage
    return resp.choices[0].message.parsed, {
        "provider": provider, "model": model,
        "tokens_in": usage.prompt_tokens if usage else 0, "tokens_out": usage.completion_tokens if usage else 0,
    }


def learn_with_rules(checkin: dict, weather: dict) -> CheckinLearning:
    evening = (weather.get("parts") or {}).get("evening", {})
    low = evening.get("feels_like_low_c")
    temp = checkin.get("temperature")
    if temp == "cold":
        when = f"evenings with a feels-like low under {low + 2}°C" if low is not None else "cool evenings"
        return CheckinLearning(oni_reply="Noted: you ran cold tonight. Tomorrow I'll add a layer before you ask.",
                               preference="Add a warmer layer; the user runs cold.", applies_when=when)
    if temp == "warm":
        return CheckinLearning(oni_reply="Too toasty? I'll go lighter next time.",
                               preference="Choose lighter layers; the user runs warm.", applies_when="mild days")
    reply = "Perfect. I'll remember this combo works." if checkin.get("feeling") != "iconic" else "Iconic. Noted, and framed."
    return CheckinLearning(oni_reply=reply, preference=None, applies_when=None)
