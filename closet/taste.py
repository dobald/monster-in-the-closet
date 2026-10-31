"""The taste model: what this person likes, learned from what they actually do.

Every outfit becomes a small vector of named, human-readable features (one pop of colour,
relaxed top, a layer on top...), built from the tags and the *measured* colour read. A
Bayesian logistic model (Bradley-Terry for choices, plus ratings) learns a weight per
feature from:

- choices: wearing look B of a plan means B beat A and C that day (read from the wears table)
- ratings: the evening check-in's meh / fine / good / iconic for what was worn
- the this-or-that warm-up: explicit pairs from the user's own closet
- "no" to the morning question: a weak vote against the pick that didn't get worn
- corrections on the Style DNA card ("not me"), as strong pseudo-evidence

The posterior is a Laplace approximation, so the model knows how sure it is. That
uncertainty drives the two things that make it more than a ranker: the Stretch look
(Thompson sampling over outfits with exactly one thing the user has never worn) and the
warm-up's pair choice (ask about the pairs the model is least sure of). Everything here is
plain numpy and runs in milliseconds on a phone-sized closet; the models only phrase it.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np

# id, how the app says it, and how a stretch introduces it.
FEATURES: list[tuple[str, str, str]] = [
    ("neutrals", "all-neutral outfits", "an all-neutral look"),
    ("one_pop", "neutrals with one pop of colour", "one pop of colour"),
    ("tonal", "one colour family head to toe", "a tonal, one-colour look"),
    ("colour_mix", "mixing two or more colours", "mixing two colours"),
    ("high_contrast", "crisp light-and-dark contrast", "crisp light-and-dark contrast"),
    ("low_contrast", "soft, blended colours", "soft, blended colours"),
    ("warm_tones", "warm, earthy tones", "warm, earthy tones"),
    ("cool_tones", "cool tones", "cool tones"),
    ("all_dark", "head-to-toe dark", "head-to-toe dark"),
    ("smart", "smarter pieces", "a smarter piece"),
    ("mixed_formality", "mixing casual and smart", "mixing casual and smart"),
    ("sporty", "sporty pieces", "something sporty"),
    ("relaxed_top", "relaxed or oversized tops", "a relaxed, oversized top"),
    ("wide_bottom", "wide or loose trousers", "wide, loose trousers"),
    ("slim_bottom", "slim or straight trousers", "slim, straight trousers"),
    ("print", "a print or stripe", "a print or stripe"),
    ("layered", "a layer on top", "a layer on top"),
    ("knit", "knitwear", "knitwear"),
    ("denim", "denim", "denim"),
    ("dress", "dresses", "a dress"),
]
IDS = [f[0] for f in FEATURES]
LABEL = {f[0]: f[1] for f in FEATURES}
STRETCH_TEXT = {f[0]: f[2] for f in FEATURES}
F = len(FEATURES)
INDEX = {fid: i for i, fid in enumerate(IDS)}

RATING = {"iconic": 1.0, "good": 0.85, "fine": 0.5, "meh": 0.0}
PRIOR = 1.0  # L2 / Gaussian prior precision: with no data every weight is 0 +- 1

# Plain colour names to a typical hex, for pieces with no cutout (thrift ideas).
NAME_HEX = {
    "black": "#1a1a1a", "white": "#f2f2f0", "cream": "#efe6d2", "ivory": "#f3eee0", "beige": "#d8c8a8", "tan": "#c8a27a",
    "camel": "#c19a6b", "khaki": "#bfae84", "brown": "#6b4a2e", "olive": "#6b6b3a", "green": "#2f6b3a", "navy": "#1f2a44",
    "indigo": "#2e3a5c", "blue": "#3d5a8a", "light blue": "#a9c4e0", "mid blue": "#5b7fa6", "grey": "#8a8a8a",
    "gray": "#8a8a8a", "charcoal": "#3a3a3a", "red": "#b03030", "burgundy": "#6d1f2b", "rust": "#a5502a", "pink": "#e3a1b0",
    "yellow": "#e3c14b", "orange": "#e07a2e", "purple": "#5e3a7a",
}


def name_hex(name: str) -> str:
    n = name.lower()
    return next((h for k, h in sorted(NAME_HEX.items(), key=lambda kv: -len(kv[0])) if k in n), "#888888")


# ---------------------------------------------------------------- features


def vector(items: list[dict], read: dict) -> np.ndarray:
    """Features of one outfit: its garments' tags plus its colour read (closet/colour.read)."""
    tags = [i["tags"] for i in items if i.get("tags")]
    v = np.zeros(F)
    if not tags:
        return v
    scheme, lights = read["scheme"], [p["light"] for p in read["palette"]]
    forms = {t["formality"] for t in tags}
    smart = bool(forms & {"smart_casual", "business", "formal"})
    tops = [f"{t['subtype']} {t['fit']}".lower() for t in tags if t["category"] == "top"]
    bottoms = [f"{t['subtype']} {t['fit']}".lower() for t in tags if t["category"] == "bottom"]
    every = [f"{t['subtype']} {t['fit']}".lower() for t in tags]
    has = lambda texts, *ws: any(w in x for x in texts for w in ws)  # noqa: E731

    flags = {
        "neutrals": scheme == "all neutral",
        "one_pop": scheme == "neutral + accent",
        "tonal": scheme == "tonal",
        "colour_mix": scheme in ("analogous", "complementary", "contrasting"),
        "high_contrast": read["contrast"] == "high",
        "low_contrast": read["contrast"] == "low",
        "warm_tones": read["temperature"] == "warm",
        "cool_tones": read["temperature"] == "cool",
        "all_dark": bool(lights) and max(lights) < 0.3,
        "smart": smart,
        "mixed_formality": smart and bool(forms & {"casual", "athleisure"}),
        "sporty": "athleisure" in forms,
        "relaxed_top": has(tops, "oversized", "relaxed", "boxy", "loose"),
        "wide_bottom": has(bottoms, "wide", "loose", "baggy", "relaxed", "pleated"),
        "slim_bottom": has(bottoms, "slim", "straight", "skinny", "tapered"),
        "print": any(t["pattern"] != "solid" for t in tags),
        "layered": any(t["category"] == "outerwear" for t in tags),
        "knit": has(every, "sweater", "knit", "cardigan", "jumper"),
        "denim": has(every, "jean", "denim"),
        "dress": any(t["category"] == "dress" for t in tags),
    }
    for fid, yes in flags.items():
        if yes:
            v[INDEX[fid]] = 1.0
    return v


# ---------------------------------------------------------------- the model


@dataclass
class Row:
    x: np.ndarray  # F features (a difference for a choice)
    y: float  # target in [0, 1]
    weight: float
    pointwise: bool  # a rating carries the bias term; a choice cancels it
    kind: str
    group: int = -1  # rows from one choice share a group, for leave-one-out evaluation


@dataclass
class Model:
    w: np.ndarray  # F weights + bias
    cov: np.ndarray  # Laplace posterior covariance
    evidence: np.ndarray  # rows each feature took part in
    counts: dict = field(default_factory=dict)  # rows per kind

    @property
    def n(self) -> int:
        return sum(self.counts.values())

    def utility(self, x: np.ndarray, w: np.ndarray | None = None) -> float:
        return float(x @ (self.w if w is None else w)[:F])

    def sample(self, rng: np.random.Generator) -> np.ndarray:
        return rng.multivariate_normal(self.w, self.cov)


def _design(rows: list[Row]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    X = np.array([np.append(r.x, 1.0 if r.pointwise else 0.0) for r in rows]).reshape(len(rows), F + 1)
    return X, np.array([r.y for r in rows]), np.array([r.weight for r in rows])


def fit(rows: list[Row]) -> Model:
    """Weighted logistic regression with a Gaussian prior, by Newton's method; Laplace covariance."""
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.kind] = counts.get(r.kind, 0) + 1
    w = np.zeros(F + 1)
    reg = PRIOR * np.eye(F + 1)
    if not rows:
        return Model(w, np.linalg.inv(reg), np.zeros(F), counts)
    X, y, c = _design(rows)
    for _ in range(25):
        p = 1 / (1 + np.exp(-(X @ w)))
        grad = X.T @ (c * (p - y)) + reg @ w
        H = X.T @ (X * (c * p * (1 - p))[:, None]) + reg
        step = np.linalg.solve(H, grad)
        w -= step
        if np.abs(step).max() < 1e-6:
            break
    p = 1 / (1 + np.exp(-(X @ w)))
    H = X.T @ (X * (c * p * (1 - p))[:, None]) + reg
    return Model(w, np.linalg.inv(H), (np.abs(X[:, :F]) > 0).sum(axis=0).astype(float), counts)


def choice_rows(winner: np.ndarray, losers: list[np.ndarray], kind: str, group: int, weight: float = 1.0) -> list[Row]:
    return [Row(winner - lo, 1.0, weight, False, kind, group) for lo in losers]


def correction_row(feature: str, value: float) -> Row:
    x = np.zeros(F)
    x[INDEX[feature]] = 1.0
    return Row(x * (1 if value > 0 else -1), 1.0, 2.0, False, "correct")


def evaluate(rows: list[Row], choices: list[tuple[int, list[np.ndarray], int]]) -> dict | None:
    """Leave-one-choice-out: train without that day's choice, then predict which look was worn.
    choices: (group, the plan's look vectors, index worn). Needs 3+ choices to say anything."""
    if len(choices) < 3:
        return None
    hits, chance = 0, 0.0
    for group, looks, worn in choices:
        m = fit([r for r in rows if r.group != group])
        scores = [m.utility(x) for x in looks]
        hits += int(int(np.argmax(scores)) == worn and len(set(np.round(scores, 6))) > 1)
        chance += 1 / len(looks)
    return {"hits": hits, "n": len(choices), "accuracy": round(hits / len(choices), 2), "chance": round(chance / len(choices), 2)}


def fit_pct(model: Model, x: np.ndarray, baseline: float) -> int:
    """How well an outfit suits them, as a %: the chance they'd pick it over a typical outfit from their closet."""
    return round(100 / (1 + math.exp(-(model.utility(x) - baseline))))


# ---------------------------------------------------------------- what the app says


def traits(model: Model, limit: int = 6) -> list[dict]:
    """The strongest learned likes and dislikes, each with its evidence."""
    out = []
    for i, fid in enumerate(IDS):
        w, sd, ev = float(model.w[i]), float(math.sqrt(model.cov[i, i])), int(model.evidence[i])
        if ev == 0 or abs(w) < 0.25:
            continue
        sure = abs(w) > 2 * sd
        lean = ("clearly lean towards" if sure else "seem to lean towards") if w > 0 else ("clearly steer away from" if sure else "seem to steer away from")
        out.append({"feature": fid, "label": LABEL[fid], "weight": round(w, 2), "evidence": ev, "sure": sure,
                    "sentence": f"You {lean} {LABEL[fid]}."})
    return sorted(out, key=lambda t: -abs(t["weight"]))[:limit]


def prompt_lines(model: Model) -> list[dict]:
    """The learned taste as preference lines for the planning and thrift agents."""
    return [{"text": f"Learned taste ({t['evidence']} signals): {'likes' if t['weight'] > 0 else 'avoids'} {t['label']}",
             "applies_when": None} for t in traits(model, 4) if abs(t["weight"]) >= 0.4]


def week_diff(now: dict[str, float], before: dict[str, float]) -> list[str]:
    lines = []
    for fid in IDS:
        d = now.get(fid, 0) - before.get(fid, 0)
        if d >= 0.35:
            lines.append(f"leaned into {LABEL[fid]}")
        elif d <= -0.35:
            lines.append(f"moved away from {LABEL[fid]}")
    return lines[:3]


# ---------------------------------------------------------------- stretch and warm-up


def outfits(items: list[dict], cold: bool, every_layer: bool = False) -> list[list[dict]]:
    """Every outfit the closet can make: top + bottom (+ the first layer when it's cold), or a dress.
    `every_layer` adds a version with each layer too, for the warm-up: it shows whether layers are you."""
    by = lambda c: [i for i in items if i.get("tags") and i["tags"]["category"] == c]  # noqa: E731
    layer = by("outerwear")[:1] if cold else []
    bases = [[t, b] for t, b in itertools.product(by("top"), by("bottom"))] + [[d] for d in by("dress")]
    combos = [[*o, *layer] for o in bases]
    if every_layer:
        combos += [[*o, coat] for o in bases for coat in by("outerwear")]
    return combos[:600]


def pick_stretch(model: Model, candidates: list[tuple[list[dict], np.ndarray]], exposure: np.ndarray,
                 pairs_worn: set[frozenset], taken: list[set[str]], rng: np.random.Generator) -> dict | None:
    """One step outside the comfort zone. Each candidate is an outfit from their own closet with
    exactly one feature they have never worn (or, failing that, two pieces never worn together).
    Thompson sampling: draw a plausible taste from the posterior, take the outfit it likes best."""
    w = model.sample(rng)
    best = None
    for outfit, x in candidates:
        ids = {i["id"] for i in outfit if i["tags"]["category"] != "outerwear"}
        if any(ids <= t for t in taken):
            continue
        new = [IDS[i] for i in np.flatnonzero(x) if exposure[i] == 0]
        core = [i for i in outfit if i["tags"]["category"] in ("top", "bottom", "dress")]
        new_pair = len(core) == 2 and frozenset(i["id"] for i in core) not in pairs_worn
        if len(new) > 1 or not (new or new_pair):
            continue
        score = float(x @ w[:F]) + (0.5 if new else 0.2)
        if best is None or score > best[0]:
            best = (score, outfit, x, new[0] if new else None, core)
    if not best:
        return None
    _, outfit, x, feature, core = best
    return {"outfit": outfit, "x": x, "feature": feature,
            "pair": None if feature else [i["id"] for i in core]}


def pair_key(a_ids, b_ids) -> frozenset:
    return frozenset((frozenset(a_ids), frozenset(b_ids)))


def quiz_pairs(model: Model, candidates: list[tuple[list[dict], np.ndarray]], k: int = 6,
               asked: set[frozenset] = frozenset()) -> list[tuple[list[dict], list[dict]]]:
    """The pairs the model is least sure about (largest predictive variance of the difference), spread
    over different garments so each answer teaches something different. Never a pair already asked."""
    scored = []
    for (a, xa), (b, xb) in itertools.combinations(candidates, 2):
        d = np.append(xa - xb, 0.0)
        if not d.any() or pair_key([i["id"] for i in a], [i["id"] for i in b]) in asked:
            continue
        scored.append((float(d @ model.cov @ d), a, b))
    scored.sort(key=lambda s: -s[0])
    out, used = [], {}
    for _, a, b in scored:
        ids = [i["id"] for i in a + b]
        if any(used.get(i, 0) >= 3 for i in ids):
            continue
        out.append((a, b))
        for i in ids:
            used[i] = used.get(i, 0) + 1
        if len(out) == k:
            break
    return out


# ---------------------------------------------------------------- narrative


def narrate_with_agent(trait_list: list[dict], week: list[str], n: int, provider: str) -> str:
    """Two warm sentences about their style, in the oni's voice, from the learned traits."""
    from . import config

    client = config.client_for(provider)
    messages = [{"role": "system", "content": (
        "You are the oni who lives in the user's closet: a warm, stylish friend. Write exactly two short "
        "sentences (under 40 words in all) describing their style from what you learned, speaking to them as 'you'. "
        "Plain words, no numbers, no percentages, no emoji. If there's a change this week, mention it in the second "
        "sentence.")},
        {"role": "user", "content": f"Learned from {n} signals: " + " ".join(t["sentence"] for t in trait_list)
         + (f" This week they {', '.join(week)}." if week else "")}]
    for _ in range(2):  # Spark Open now and then spends the whole answer thinking; one retry, then the rules version
        resp = client.chat.completions.create(model=config.PLAN_MODEL[provider], messages=messages, max_tokens=2000)
        text = (resp.choices[0].message.content or "").strip()
        if text:
            return text
    return ""


def narrate_with_rules(trait_list: list[dict], week: list[str], n: int) -> str:
    if not trait_list:
        return ("I'm still getting to know you. Wear a few picks and play this-or-that, and I'll learn what you love."
                if n < 3 else "Your taste is wide open so far: nothing stands out yet, which means lots of room to play.")
    likes = [t["label"] for t in trait_list if t["weight"] > 0][:2]
    head = (f"So far you're drawn to {likes[0]}" + (f", and to {likes[1]}." if len(likes) > 1 else ".")) if likes         else f"So far you tend to skip {trait_list[0]['label']}."
    return head + (f" This week you {week[0]}." if week else "")
