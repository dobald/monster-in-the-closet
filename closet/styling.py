"""Finishing touches: the small things that make a look, from basics the user probably owns.

The playbook below is distilled from stylist guides and editorial advice on layering and
accessorizing (Oct 2026 research). It covers hems and collars peeking from under knits, front
tucks to balance wide trousers, pushed sleeves to show the wrist, one dominant metal, belts
that match the shoe leather, echoing a print's colour in one accessory, shoe weight that matches
trouser volume, and no more than three accessories. Each entry says when it applies and which
basics it needs. The oni (Muse Spark Open) picks 2-3 entries for a look and writes them for the
actual pieces; the code checks the picks, works out from the user's own checklist whether they
own what's needed, and puts owned ones first. Nothing here is a shopping suggestion: anything
the user hasn't ticked is phrased "if you have one".
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from . import config
from .planner import PERSONA
from .schema import TouchSet

# Things people own but rarely scan: underlayers, jewelry, small accessories and shoes.
BASICS: dict[str, list[tuple[str, str]]] = {
    "Underlayers": [
        ("white_tee", "Plain white tee"), ("long_tee", "Longline tee"), ("long_sleeve_tee", "Long-sleeve tee"),
        ("button_up", "Button-up shirt"), ("turtleneck", "Turtleneck or mock neck"), ("hoodie", "Hoodie"),
        ("tank", "Tank top"),
    ],
    "Jewelry": [
        ("silver_rings", "Silver rings"), ("gold_rings", "Gold rings"), ("silver_chain", "Silver chain"),
        ("gold_chain", "Gold chain"), ("watch", "Watch"), ("earrings", "Earrings"), ("bracelet", "Bracelet or bangle"),
    ],
    "Accessories": [
        ("belt_black", "Black leather belt"), ("belt_brown", "Brown leather belt"), ("cap", "Cap"),
        ("beanie", "Beanie"), ("scarf", "Scarf"), ("tote", "Tote bag"), ("crossbody", "Crossbody bag"),
        ("sunglasses", "Sunglasses"), ("white_socks", "White socks"), ("fun_socks", "Patterned or colour socks"),
    ],
    "Shoes": [
        ("white_sneakers", "Clean white sneakers"), ("chunky_sneakers", "Chunky sneakers"), ("loafers", "Loafers"),
        ("boots", "Boots"),
    ],
}
BASIC_LABELS = {k: label for group in BASICS.values() for k, label in group}


@dataclass(frozen=True)
class Play:
    id: str
    kind: str  # underlayer | accessory | technique
    name: str
    when: str  # when it works, in words the model reads
    how: str  # the move itself
    needs: tuple[str, ...] = ()  # basics, any one of which will do; empty = a technique, no item needed


PLAYBOOK: list[Play] = [
    # underlayers
    Play("hem_peek", "underlayer", "Hem peeking under a knit",
         "A sweater, sweatshirt or knit top over trousers, casual day; best when the knit is cropped or boxy.",
         "Let a plain tee's hem show 1-3 cm below the knit. It breaks the block of colour and adds a clean line. "
         "The underlayer should be only a little longer, never a full tunic.", ("long_tee", "white_tee")),
    Play("collar_peek", "underlayer", "Collar out over a crewneck",
         "A crewneck sweater or sweatshirt on a smart-casual or work day.",
         "Wear a button-up under the crewneck and pull the collar out over the neckline; a crisp collar holds its shape.",
         ("button_up",)),
    Play("sleeve_layer", "underlayer", "Long sleeves under a short-sleeve tee",
         "A short-sleeve tee (especially graphic) on a cool day, relaxed or streetwear mood.",
         "Put a fitted long-sleeve tee underneath so the sleeves and maybe the hem show; pick a quiet colour from the print.",
         ("long_sleeve_tee",)),
    Play("turtleneck_under", "underlayer", "Turtleneck under a layer",
         "A shirt, overshirt or jacket on a cold day, when it should look polished.",
         "A thin turtleneck or mock neck underneath reads sharp and warm with no extra bulk.", ("turtleneck",)),
    Play("open_shirt", "underlayer", "Open shirt as a light layer",
         "A plain tee on a mild day that needs one more layer, casual.",
         "Wear a button-up open over the tee like a light jacket; sleeves pushed.", ("button_up",)),
    # techniques
    Play("front_tuck", "technique", "Front tuck",
         "A loose, boxy or long top with wide-leg, high-rise or relaxed trousers.",
         "Tuck just the front of the top into the waistband so the waist shows; keeps the top-to-bottom balance at about a "
         "third to two-thirds without looking stiff."),
    Play("sleeve_push", "technique", "Push the sleeves",
         "Any long-sleeve knit, sweatshirt or shirt, especially indoors or when it warms up.",
         "Push the sleeves to mid-forearm. Showing the wrist breaks up the fabric and shows off rings or a watch."),
    Play("cuff_roll", "technique", "Cuff the hem",
         "Straight or wide jeans or chinos that sit on the shoe; not for track pants or elastic cuffs.",
         "Roll the hem once or twice, about 3 cm, to show a slice of sock or ankle and the shoe."),
    # accessories
    Play("rings", "accessory", "Rings",
         "Almost any look, best with pushed sleeves or short sleeves.",
         "Two or three rings on different fingers. One main metal: silver with greys, blacks, whites and blues; gold with "
         "browns, creams, olives and tans.", ("silver_rings", "gold_rings")),
    Play("chain", "accessory", "A fine chain",
         "A crew-neck tee or an open collar, relaxed or dinner plans.",
         "A thin chain sitting just on the collarbone, in the same metal as any rings.", ("silver_chain", "gold_chain")),
    Play("watch", "accessory", "A watch",
         "Short or pushed sleeves, smart-casual plans like a crit, meeting or dinner.",
         "A simple watch makes a plain outfit look deliberate.", ("watch",)),
    Play("belt", "accessory", "A leather belt",
         "Jeans or trousers with belt loops, especially with a tuck.",
         "Match the belt leather to the shoes (black with black, brown with brown); it frames the tuck.",
         ("belt_black", "belt_brown")),
    Play("cap", "accessory", "A cap",
         "Casual or streetwear looks, daytime.",
         "A cap in a colour that echoes the outfit (or plain black) finishes a tee-and-trousers look with no other "
         "accessories.", ("cap",)),
    Play("beanie", "accessory", "A beanie",
         "Cold mornings or evenings outside.",
         "A beanie in one colour already in the outfit keeps you warm and ties the look together.", ("beanie",)),
    Play("scarf", "accessory", "A scarf",
         "A cold evening or a long time outdoors.",
         "Loop a scarf once; pick a colour or texture that contrasts the top (soft knit against a smooth jacket).",
         ("scarf",)),
    Play("socks", "accessory", "Socks that show",
         "Cuffed trousers with sneakers or loafers.",
         "Clean white socks look crisp; a colour sock can echo one shade from a print.", ("white_socks", "fun_socks")),
    Play("bag", "accessory", "The right bag",
         "A long day out, a studio or office day, or plans that move from day to evening.",
         "A tote for a busy day (carry a spare layer); a small crossbody for hands-free evenings.", ("tote", "crossbody")),
    Play("shoe_weight", "accessory", "Shoes that match the trouser volume",
         "Any look with full-length trousers.",
         "Wide or heavy trousers want a chunky sneaker or boot; slimmer trousers want a slim sneaker or loafer.",
         ("chunky_sneakers", "boots", "white_sneakers", "loafers")),
    Play("colour_echo", "colour", "Echo a colour from the print",
         "A graphic or printed piece in the look.",
         "Repeat one colour from the print in a single accessory (cap, socks, bag or beanie) so the look feels planned.",
         ("cap", "fun_socks", "beanie", "scarf", "tote")),
]
PLAYBOOK += [
    # colour, texture and formality (docs/STYLE_GUIDE.md sections 1, 4 and 6)
    Play("accent_pop", "colour", "One accent colour",
         "An all-neutral look (greys, black, white, navy, denim, browns).",
         "Add one small accent colour in a single accessory and keep everything else neutral, so the eye has one focal "
         "point.", ("cap", "fun_socks", "scarf", "beanie", "tote")),
    Play("bookend", "colour", "Bookend the colour",
         "A look with a clear top colour.",
         "Repeat the top's colour in your shoes (or a cap), with the trousers in between: it makes the colours look "
         "chosen.", ("white_sneakers", "chunky_sneakers", "boots", "loafers", "cap", "white_socks")),
    Play("light_break", "colour", "A light break",
         "Head-to-toe dark: black, charcoal, navy, dark brown.",
         "Add one light note (a white tee hem, white socks or clean white sneakers) so the dark doesn't go flat.",
         ("white_tee", "long_tee", "white_socks", "white_sneakers")),
    Play("texture_contrast", "colour", "Contrast the textures",
         "Tonal looks, close colours, or everything matte and soft.",
         "Bring in a contrasting finish (smooth leather against knit, a chunky knit against smooth cotton) so a narrow "
         "palette still has depth.", ("belt_black", "belt_brown", "scarf", "beanie", "watch")),
    Play("high_low", "accessory", "One polished piece",
         "A very casual base (sweatshirt, hoodie, track pants) on a day with plans, or a smart look on a relaxed day.",
         "Pair the casual pieces with one polished one (a watch, a fine chain or loafers), or relax a smart look with "
         "sneakers.", ("watch", "silver_chain", "gold_chain", "loafers", "white_sneakers")),
]
PLAYS = {p.id: p for p in PLAYBOOK}


# "Got one?": core pieces (docs/STYLE_GUIDE.md section 8) the closet has none of. They are most likely sitting in a
# drawer unscanned, so the prompt asks the user to scan theirs in, never to buy one.
@dataclass(frozen=True)
class Recall:
    id: str
    category: str
    keywords: tuple[str, ...]  # an owned item matches if its subtype contains any; empty = any item of the category
    name: str
    lift: str  # what it would do for a look, for the fallback wording
    when: str = "any"  # any | cold | smart


RECALLS: list[Recall] = [
    Recall("rec_jacket", "outerwear", (), "a jacket or coat", "frame the outfit and keep you warm", "cold"),
    Recall("rec_knit", "top", ("sweater", "knit", "cardigan", "jumper"), "a knit sweater or cardigan",
           "add a soft mid layer over your tees"),
    Recall("rec_shirt", "top", ("button", "oxford", "flannel", "dress shirt", "overshirt"), "a button-up shirt",
           "smarten this up for your plans", "smart"),
    Recall("rec_trousers", "bottom", ("trouser", "chino", "slack"), "a pair of tailored trousers or chinos",
           "give you a smarter bottom option", "smart"),
    Recall("rec_jeans", "bottom", ("jean", "denim"), "a pair of jeans", "give you an easy everyday bottom"),
    Recall("rec_overshirt", "outerwear", ("overshirt", "shacket", "shirt jacket", "chore"), "an overshirt",
           "work as a light layer over this"),
]
RECALL_BY_ID = {r.id: r for r in RECALLS}


def recall_for(closet: list[dict], cold: bool, smart: bool, skip: set[str], look_index: int = 0) -> Recall | None:
    """A core piece the closet has none of, suited to today's weather and plans. Each look of the day asks
    about a different one (most useful first), so the three looks don't all ask for the same jacket."""
    def owns(r: Recall) -> bool:
        return any(i["tags"]["category"] == r.category and (not r.keywords or any(k in i["tags"]["subtype"].lower()
                                                                                  for k in r.keywords)) for i in closet)
    fits = [r for r in RECALLS if r.id not in skip and not owns(r)
            and (r.when == "any" or (r.when == "cold" and cold) or (r.when == "smart" and smart))]
    return fits[look_index % len(fits)] if fits else None
PRINCIPLES = (
    "Styling principles: balance volume (one relaxed piece with one fitted or cropped one); a top that's about a third "
    "of the look and trousers two-thirds reads well, and a front tuck gets you there. Underlayers should only just show. "
    "Accessories complement and never compete: at most three, one dominant metal, belt leather matching shoes. "
    "Dress for the weather (scarf and beanie only when it's cold out) and the occasion (collars, watches and belts for "
    "smart plans; caps for casual daytime). Colour: count navy, denim, browns, olive and greys as neutrals; an all-neutral "
    "look wants one small accent; a print's colour can be echoed once; head-to-toe dark wants a light break; a tonal look "
    "wants texture contrast. Pair a casual base with one polished piece."
)


def look_lines(items: list[dict]) -> str:
    return "\n".join(f"- {i['tags']['category']}: {i['tags']['primary_color']} {i['tags']['subtype']} (fit {i['tags']['fit']}, "
                     f"pattern {i['tags']['pattern']}, {i['tags']['formality']})" for i in items)


def playbook_lines(owned: set[str]) -> str:
    out = []
    for p in PLAYBOOK:
        has = [BASIC_LABELS[n] for n in p.needs if n in owned]
        need = ("no item needed" if not p.needs else
                f"needs one of: {', '.join(BASIC_LABELS[n] for n in p.needs)}" + (f" (the user HAS: {', '.join(has)})" if has else ""))
        out.append(f"- {p.id} [{p.kind}] {p.name}. When: {p.when} How: {p.how} ({need})")
    return "\n".join(out)


VOICE = (
    "Return 3 touches. Use only playbook ids from the list, at most one underlayer, and never suggest buying anything. "
    "Prefer touches the user HAS items for and techniques; otherwise the app shows 'if you have one'. Write 'suggestion' "
    "as one short instruction under 18 words that names the actual pieces in this look, e.g. 'Let a white tee peek 2 cm "
    "below the cropped sweatshirt.' Write 'why' in under 14 words, in everyday words: never quote the playbook or its "
    "rules (no 'one-third to two-thirds'). 'item' is the basic you'd use, in plain words, or empty for a technique. "
    "Make one of the 3 a colour play that follows the measured colour read when it fits. "
    "If a 'Got one?' piece is given, write 'recall' as one friendly sentence under 24 words asking if they have one "
    "and how it would lift this look, ending with 'Scan it in.'; otherwise leave 'recall' empty. No emoji."
)


def touches_with_agent(items: list[dict], weather_note: str, plans_note: str, owned: set[str], skip: set[str],
                       provider: str, elsewhere: set[str] = frozenset(), colour_line: str = "",
                       recall: Recall | None = None) -> tuple[TouchSet, dict]:
    client = config.client_for(provider)
    model = config.PLAN_MODEL[provider]
    t0 = time.time()
    skip_line = f"The user said these aren't their style, so skip them: {', '.join(sorted(skip))}." if skip else ""
    if elsewhere:  # keep the three looks from all getting the same scarf
        skip_line += f" Already suggested for today's other looks, so pick different ones: {', '.join(sorted(elsewhere))}."
    system = (f"{PERSONA}\n\nYou add finishing touches to an outfit the user is about to wear, using a stylist's "
              f"playbook.\n\n{PRINCIPLES}\n\nPlaybook:\n{playbook_lines(owned)}\n\n{skip_line}")
    recall_line = (f"'Got one?' piece: {recall.name}. The closet has none scanned; it would {recall.lift}."
                   if recall else "'Got one?' piece: none.")
    user = (f"Today's look:\n{look_lines(items)}\n\n{colour_line}\nWeather: {weather_note}\nPlans: {plans_note}\n"
            f"{recall_line}\n\n{VOICE}")
    resp = client.chat.completions.parse(
        model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format=TouchSet, reasoning_effort="low", max_tokens=3000,
    )
    usage = resp.usage
    return resp.choices[0].message.parsed, {
        "provider": provider, "model": model, "seconds": round(time.time() - t0, 1),
        "tokens_in": usage.prompt_tokens if usage else 0, "tokens_out": usage.completion_tokens if usage else 0,
    }


MAX_PER_KIND = {"underlayer": 1, "technique": 1, "accessory": 2, "colour": 1}


def clean(touches: TouchSet, owned: set[str], skip: set[str]) -> list[dict]:
    """Drop invented or skipped plays and duplicates, keep a mix (one underlayer, one technique, one colour
    play, two accessories at most) and mark what the user owns from their checklist, not the model's say-so.
    Order is kept, except that once the user has ticked anything, owned touches move up."""
    out, seen, per_kind = [], set(), {k: 0 for k in MAX_PER_KIND}
    for t in touches.touches:
        play = PLAYS.get(t.playbook_id)
        if not play or play.id in seen or play.id in skip or per_kind[play.kind] >= MAX_PER_KIND[play.kind]:
            continue
        per_kind[play.kind] += 1
        seen.add(play.id)
        has = [n for n in play.needs if n in owned]
        out.append({"play": play.id, "kind": play.kind, "name": play.name, "item": t.item.strip(),
                    "suggestion": t.suggestion.strip(), "why": t.why.strip(),
                    "needs": list(play.needs), "owned": bool(has) or not play.needs,
                    "owned_label": BASIC_LABELS[has[0]] if has else None})
    if owned:
        out.sort(key=lambda t: not t["owned"])  # stable: keeps the oni's order within owned / not owned
    return out[:3]


# ---------------------------------------------------------------- rules (fixture mode and fallback)


COLOUR_TEMPLATES = {
    "light_break": ("Add one light note: a white tee hem, white socks or white sneakers.", "Keeps all that dark from going flat."),
    "accent_pop": ("Add one small accent colour in a cap, socks or scarf.", "Gives the neutrals a focal point."),
    "colour_echo": ("Repeat one colour from the print in a cap or socks.", "Makes the look feel planned."),
    "bookend": ("Repeat the top's colour in your shoes or a cap.", "Ties the colours together."),
    "texture_contrast": ("Add a leather belt or a contrasting knit.", "Gives a narrow palette some depth."),
}


def touches_with_rules(items: list[dict], cold: bool, smart: bool, owned: set[str], skip: set[str],
                       colour_play: str | None = None) -> list[dict]:
    """A deterministic pick from the playbook by the look's tags, for fixture mode and failures."""
    tags = [i["tags"] for i in items]
    words = " ".join(f"{t['subtype']} {t['fit']}".lower() for t in tags)
    top = next((t for t in tags if t["category"] == "top"), None)
    bottom = next((t for t in tags if t["category"] == "bottom"), None)
    knit = top and any(w in top["subtype"].lower() for w in ("sweater", "sweatshirt", "knit", "jumper", "cardigan"))
    tee = top and any(w in top["subtype"].lower() for w in ("tee", "t-shirt", "henley"))
    wide = bottom and any(w in bottom["fit"].lower() + bottom["subtype"].lower() for w in ("wide", "loose", "relaxed", "baggy"))
    loose_top = top and any(w in top["fit"].lower() for w in ("oversized", "boxy", "loose", "relaxed"))
    denim = bottom and any(w in bottom["subtype"].lower() for w in ("jean", "chino", "denim"))
    printed = any(t["pattern"] in ("graphic", "print") for t in tags)
    cool = all(c not in " ".join(t["primary_color"].lower() for t in tags) for c in ("brown", "tan", "cream", "olive", "camel"))

    ideas: list[tuple[str, str, str]] = []  # (play id, suggestion, why)
    tname = top["subtype"] if top else "top"
    bname = bottom["subtype"] if bottom else "trousers"
    if knit and smart:
        ideas.append(("collar_peek", f"Wear a button-up under the {tname} with the collar out.", "Smart enough for today's plans."))
    elif knit:
        ideas.append(("hem_peek", f"Let a white tee peek a couple of centimetres below the {tname}.", "Breaks up the block of colour."))
    elif tee and cold:
        ideas.append(("sleeve_layer", f"Add a long-sleeve tee under the {tname}.", "Warmer, and the layer adds depth."))
    if loose_top and wide:
        ideas.append(("front_tuck", f"Front-tuck the {tname} into the {bname}.", "Shows your waist so the volume reads intentional."))
    if knit or (top and "long" in words):
        ideas.append(("sleeve_push", "Push the sleeves to mid-forearm.", "Shows your wrists and any rings."))
    if denim and not wide:
        ideas.append(("cuff_roll", f"Cuff the {bname} once to show your shoes.", "Cleaner line at the ankle."))
    if colour_play in COLOUR_TEMPLATES:
        ideas.append((colour_play, *COLOUR_TEMPLATES[colour_play]))
    elif printed:
        ideas.append(("colour_echo", *COLOUR_TEMPLATES["colour_echo"]))
    if smart:
        ideas.append(("watch", "Add a simple watch.", "A small detail that reads put-together."))
    ideas.append(("rings", f"Two or three {'silver' if cool else 'gold'} rings.", "Matches the outfit's cool tones." if cool else "Warms up the earthy colours."))
    if cold:
        ideas.append(("beanie", "A beanie in a colour already in the outfit.", "Warm, and it ties the look together."))
    if wide:
        ideas.append(("shoe_weight", "Chunky sneakers or boots under the wide legs.", "Balances the volume of the trousers."))

    picked = TouchSet(touches=[{"playbook_id": pid, "item": "", "suggestion": s, "why": w} for pid, s, w in ideas])
    return clean(picked, owned, skip)


def cache_parts(items: list[dict], owned: set[str], skip: set[str], weather_note: str, plans_note: str) -> str:
    return json.dumps([sorted(i["id"] for i in items), sorted(owned), sorted(skip), weather_note, plans_note], sort_keys=True)
