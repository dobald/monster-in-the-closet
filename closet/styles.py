"""Style archetypes: which styles someone is drawn to, learned from Pinterest-style boards.

The research behind each style is in docs/STYLE_ARCHETYPES.md. Every archetype has:
- a board: 6-7 pieces (garments, shoes, bag, accessories) drawn by Muse Image and cut out by SAM 3.1,
  laid out like the outfit collages people pin (fixtures/style_boards/, scripts/make_style_boards.py)
- a profile on the taste model's 20 outfit features (closet/taste.py), so a style a user likes can
  teach the outfit model too, and their own closet can be read in the same terms

The warm-up shows two boards and asks which is more them. A Bradley-Terry model with a Gaussian prior
learns one weight per style; its Laplace posterior says how sure it is, so the next pair asked is the
one it is least sure about. The result is a style mix ("40% dark academia, 25% minimalist...") next to
what the closet already says, and the gap between them is where the oni helps you grow.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np

from . import taste


@dataclass(frozen=True)
class Piece:
    id: str
    category: str  # top | bottom | outerwear | dress | shoes | bag | hat | eyewear | jewelry | accessory
    desc: str  # what Muse Image draws
    noun: str  # what SAM is asked to find


@dataclass(frozen=True)
class Style:
    id: str
    name: str
    ja: str
    essence: str
    pieces: tuple[Piece, ...]
    profile: dict[str, float] = field(default_factory=dict)  # taste feature -> -1..1
    signature: tuple[str, ...] = ()  # pieces to borrow first when growing into it


def P(cat: str, desc: str, noun: str) -> Piece:
    return Piece(f"{cat}", cat, desc, noun)


STYLES: list[Style] = [
    Style("streetwear", "Streetwear", "ストリート",
          "Skate, hip-hop and surf culture: oversized on top, roomy below, sneakers as the anchor.",
          (P("top", "an oversized heather grey hoodie with a bold graphic print on the chest", "hoodie"),
           P("bottom", "baggy black cargo pants with big side pockets", "pants"),
           P("outerwear", "a black and cream wool varsity jacket with leather sleeves", "jacket"),
           P("shoes", "a pair of chunky white and grey retro basketball sneakers", "sneakers"),
           P("bag", "a small black nylon crossbody sling bag", "bag"),
           P("hat", "a black fitted baseball cap", "cap"),
           P("jewelry", "a thick silver curb chain necklace", "necklace")),
          {"relaxed_top": 1, "wide_bottom": 1, "sporty": 0.8, "print": 0.8, "high_contrast": 0.4, "neutrals": 0.3,
           "smart": -0.6, "slim_bottom": -0.5},
          ("an oversized hoodie", "chunky sneakers", "a baseball cap")),
    Style("dark_academia", "Dark academia", "ダークアカデミア",
          "Old libraries and Ivy League tailoring: tweed, knits and leather in browns, burgundy and forest green.",
          (P("top", "a dark brown argyle knit sweater vest", "sweater vest"),
           P("bottom", "charcoal grey wool pleated trousers", "trousers"),
           P("outerwear", "a brown herringbone tweed blazer", "blazer"),
           P("shoes", "a pair of dark brown leather penny loafers", "loafers"),
           P("bag", "a worn brown leather satchel bag", "satchel"),
           P("eyewear", "a pair of round tortoiseshell glasses", "glasses"),
           P("jewelry", "a vintage gold watch with a brown leather strap", "watch")),
          {"knit": 1, "smart": 0.8, "layered": 0.8, "warm_tones": 0.8, "tonal": 0.5, "low_contrast": 0.4,
           "mixed_formality": 0.4, "print": 0.2, "sporty": -0.8, "colour_mix": -0.4},
          ("a knit vest or cardigan", "a tweed or wool blazer", "leather loafers")),
    Style("cyberpunk", "Cyberpunk / techwear", "サイバー",
          "Function as costume: black technical shells, straps and buckles, one cold neon accent.",
          (P("top", "a black fitted technical long-sleeve top with reflective panels", "shirt"),
           P("bottom", "black tapered techwear cargo pants with straps and buckles", "pants"),
           P("outerwear", "a black waterproof shell jacket with a high collar and taped seams", "jacket"),
           P("shoes", "a pair of black chunky high-top tactical sneaker boots", "boots"),
           P("bag", "a black modular chest rig bag with buckles", "bag"),
           P("eyewear", "black wraparound shield sunglasses with a cyan tint", "sunglasses"),
           P("jewelry", "a silver chain choker necklace with a small metal plate", "necklace")),
          {"all_dark": 1, "layered": 0.8, "tonal": 0.6, "sporty": 0.5, "cool_tones": 0.5, "slim_bottom": 0.4,
           "warm_tones": -0.6, "print": -0.4},
          ("a black technical shell", "tapered cargo pants", "a chest or sling bag")),
    Style("gothic", "Gothic", "ゴシック",
          "Post-punk and Victorian romance: black on black in velvet, lace and leather, with silver.",
          (P("top", "a black velvet blouse with lace trim at the collar and cuffs", "blouse"),
           P("bottom", "black velvet wide-leg trousers", "trousers"),
           P("outerwear", "a long black leather trench coat", "coat"),
           P("shoes", "a pair of black leather platform combat boots with silver buckles", "boots"),
           P("bag", "a small black handbag with silver hardware", "handbag"),
           P("jewelry", "a silver cross pendant necklace", "necklace"),
           P("accessory", "a black lace choker", "choker")),
          {"all_dark": 1, "tonal": 0.7, "layered": 0.6, "smart": 0.3, "high_contrast": 0.2, "warm_tones": -0.4,
           "sporty": -0.6, "colour_mix": -0.6},
          ("one velvet or lace piece", "platform boots", "silver jewellery")),
    Style("brutalist", "Brutalist", "ブルータリスト",
          "Architecture as clothing (Rick Owens, Margiela): raw edges, drape, oversized volume, monochrome.",
          (P("top", "a draped asymmetric dark grey jersey top with raw edges", "top"),
           P("bottom", "black dropped-crotch wide trousers", "trousers"),
           P("outerwear", "a black boxy oversized architectural wool coat", "coat"),
           P("shoes", "a pair of chunky black square-toe leather boots", "boots"),
           P("bag", "a black geometric structured leather bag", "bag"),
           P("eyewear", "black angular oversized sunglasses", "sunglasses"),
           P("jewelry", "a chunky sculptural silver cuff bracelet", "silver cuff")),
          {"tonal": 0.8, "wide_bottom": 0.8, "all_dark": 0.6, "relaxed_top": 0.6, "layered": 0.6, "print": -0.8,
           "colour_mix": -0.8, "sporty": -0.3},
          ("one oversized structured coat", "wide dropped trousers", "chunky square-toe boots")),
    Style("parisian_chic", "Parisian chic", "パリシック",
          "Effortless French staples: trench, Breton stripes, good jeans, ballet flats and one red note.",
          (P("top", "a navy and white Breton striped long-sleeve top", "top"),
           P("bottom", "straight-leg dark indigo jeans", "jeans"),
           P("outerwear", "a beige double-breasted trench coat", "coat"),
           P("shoes", "a pair of black leather ballet flats", "shoes"),
           P("bag", "a small woven straw basket bag with leather handles", "basket bag"),
           P("accessory", "a red silk neck scarf", "red fabric"),
           P("eyewear", "black cat-eye sunglasses", "sunglasses")),
          {"one_pop": 0.6, "high_contrast": 0.6, "denim": 0.6, "slim_bottom": 0.6, "mixed_formality": 0.6,
           "print": 0.5, "layered": 0.5, "smart": 0.4, "sporty": -0.6},
          ("a Breton stripe", "a trench coat", "ballet flats")),
    Style("soft", "Soft", "ソフト",
          "Gentle and cosy: pastels, fluffy knits, pleats and dainty gold, never harsh contrast.",
          (P("top", "a fluffy pastel pink cropped cardigan", "cardigan"),
           P("bottom", "a cream pleated midi skirt", "skirt"),
           P("shoes", "a pair of white and pastel pink retro sneakers", "sneakers"),
           P("bag", "a small pastel lilac shoulder bag", "bag"),
           P("hat", "a cream knitted bucket hat", "hat"),
           P("jewelry", "a dainty gold heart pendant necklace", "necklace")),
          {"low_contrast": 0.8, "knit": 0.8, "dress": 0.5, "warm_tones": 0.4, "colour_mix": 0.4, "relaxed_top": 0.4,
           "all_dark": -1, "high_contrast": -0.5},
          ("a fluffy pastel knit", "a pleated skirt or soft trousers", "dainty gold")),
    Style("minimalist", "Minimalist", "ミニマル",
          "Scandinavian clean lines: a few perfect neutrals, no prints, quality over quantity.",
          (P("top", "a crisp white heavyweight t-shirt", "t-shirt"),
           P("bottom", "black straight tailored trousers", "trousers"),
           P("outerwear", "a black oversized wool blazer", "blazer"),
           P("shoes", "a pair of clean white leather minimalist sneakers", "sneakers"),
           P("bag", "a black leather tote bag", "tote bag"),
           P("jewelry", "a simple silver watch with a mesh strap", "watch")),
          {"neutrals": 1, "tonal": 0.4, "smart": 0.4, "slim_bottom": 0.4, "print": -1, "colour_mix": -0.8,
           "sporty": -0.2},
          ("a heavyweight white tee", "black tailored trousers", "clean white sneakers")),
    Style("y2k", "Y2K", "Y2K",
          "Early-2000s pop: baby tees, low-rise flares, platforms, tinted shades and shiny little bags.",
          (P("top", "a baby pink cropped baby tee with a rhinestone heart", "t-shirt"),
           P("bottom", "low-rise flared light-wash jeans", "jeans"),
           P("shoes", "a pair of chunky white and silver platform sneakers", "sneakers"),
           P("bag", "a small silver metallic baguette shoulder bag", "bag"),
           P("eyewear", "rimless sunglasses with blue tinted lenses", "sunglasses"),
           P("jewelry", "a colourful beaded charm necklace", "necklace")),
          {"colour_mix": 0.8, "print": 0.6, "denim": 0.6, "one_pop": 0.4, "sporty": 0.4, "smart": -0.6,
           "all_dark": -0.6, "knit": -0.3},
          ("a baby tee", "flared jeans", "a small shiny bag")),
    Style("gorpcore", "Gorpcore", "ゴープコア",
          "Trail gear in the city: fleece, technical shells, hiking pants and trail runners, one bright colour.",
          (P("top", "a forest green half-zip fleece pullover", "fleece"),
           P("bottom", "khaki nylon hiking pants", "pants"),
           P("outerwear", "a bright orange technical shell jacket", "jacket"),
           P("shoes", "a pair of grey and black trail running shoes", "shoes"),
           P("bag", "a black hiking belt bag", "belt bag"),
           P("hat", "a tan nylon bucket hat", "hat")),
          {"sporty": 1, "layered": 0.8, "one_pop": 0.6, "colour_mix": 0.4, "relaxed_top": 0.3, "smart": -0.8},
          ("a fleece", "a technical shell", "trail runners")),
    Style("old_money", "Old money", "オールドマネー",
          "Quiet luxury: cashmere, tailoring and loafers in cream, navy and camel, logos nowhere.",
          (P("top", "a cream cable-knit cashmere sweater", "sweater"),
           P("bottom", "beige pleated wool trousers", "trousers"),
           P("outerwear", "a navy blazer with gold buttons", "blazer"),
           P("shoes", "a pair of brown suede loafers", "loafers"),
           P("bag", "a tan leather structured top-handle bag", "handbag"),
           P("eyewear", "tortoiseshell sunglasses", "sunglasses"),
           P("jewelry", "a thin gold chain bracelet", "bracelet")),
          {"smart": 1, "knit": 0.8, "neutrals": 0.7, "warm_tones": 0.6, "layered": 0.6, "low_contrast": 0.4,
           "sporty": -1, "print": -0.4},
          ("a cashmere or cable knit", "pleated trousers", "suede loafers")),
    Style("grunge", "Grunge", "グランジ",
          "90s Seattle: flannel over a band tee, ripped denim, beat-up boots and a beanie.",
          (P("top", "a faded black band t-shirt", "t-shirt"),
           P("bottom", "ripped light-wash baggy jeans", "jeans"),
           P("outerwear", "an oversized red and black plaid flannel shirt", "shirt"),
           P("shoes", "a pair of scuffed black leather combat boots", "boots"),
           P("hat", "a charcoal rib-knit beanie", "beanie"),
           P("jewelry", "a silver wallet chain", "chain")),
          {"denim": 0.8, "layered": 0.8, "print": 0.6, "relaxed_top": 0.6, "all_dark": 0.3, "low_contrast": 0.3,
           "smart": -0.8},
          ("a flannel overshirt", "ripped denim", "combat boots")),
]
BY_ID = {s.id: s for s in STYLES}
IDS = [s.id for s in STYLES]
S = len(STYLES)
PRIOR = 1.0


def profile(style_id: str) -> np.ndarray:
    v = np.zeros(taste.F)
    for fid, w in BY_ID[style_id].profile.items():
        v[taste.INDEX[fid]] = w
    return v


# ---------------------------------------------------------------- the style model


@dataclass
class StyleModel:
    w: np.ndarray
    cov: np.ndarray
    answers: int

    def mix(self) -> list[dict]:
        """Each style's preference score: the chance they'd pick its board over an average style's,
        sigmoid(w - mean w). 50% is "no opinion yet"; a clear favourite reads 75%+, a clear no 25%-."""
        mean = float(self.w.mean())
        out = [{"id": s.id, "name": s.name, "ja": s.ja, "pct": round(100 / (1 + math.exp(-(float(self.w[i]) - mean)))),
                "weight": round(float(self.w[i]), 2), "sure": bool(abs(self.w[i]) > 2 * math.sqrt(self.cov[i, i]))}
               for i, s in enumerate(STYLES)]
        return sorted(out, key=lambda x: -x["pct"])


def fit(choices: list[tuple[str, str]]) -> StyleModel:
    """Bradley-Terry over styles: P(a beats b) = sigmoid(w_a - w_b), Gaussian prior, Newton's method."""
    reg = PRIOR * np.eye(S)
    w = np.zeros(S)
    rows = [(IDS.index(a), IDS.index(b)) for a, b in choices if a in BY_ID and b in BY_ID and a != b]
    if not rows:
        return StyleModel(w, np.linalg.inv(reg), 0)
    X = np.zeros((len(rows), S))
    for r, (a, b) in enumerate(rows):
        X[r, a], X[r, b] = 1.0, -1.0
    for _ in range(25):
        p = 1 / (1 + np.exp(-(X @ w)))
        grad = X.T @ (p - 1.0) + reg @ w
        H = X.T @ (X * (p * (1 - p))[:, None]) + reg
        step = np.linalg.solve(H, grad)
        w -= step
        if np.abs(step).max() < 1e-6:
            break
    p = 1 / (1 + np.exp(-(X @ w)))
    H = X.T @ (X * (p * (1 - p))[:, None]) + reg
    return StyleModel(w, np.linalg.inv(H), len(rows))


def next_pairs(model: StyleModel, asked: set[frozenset], k: int = 6) -> list[tuple[str, str]]:
    """Active learning: the pairs with the most expected information, var(w_a - w_b) * p(1 - p),
    never one already asked, and each style at most twice per round."""
    scored = []
    for a, b in itertools.combinations(range(S), 2):
        if frozenset((IDS[a], IDS[b])) in asked:
            continue
        var = model.cov[a, a] + model.cov[b, b] - 2 * model.cov[a, b]
        p = 1 / (1 + math.exp(-(model.w[a] - model.w[b])))
        scored.append((var * p * (1 - p), a, b))
    scored.sort(key=lambda x: -x[0])
    out, used = [], {}
    for _, a, b in scored:
        if used.get(a, 0) >= 2 or used.get(b, 0) >= 2:
            continue
        out.append((IDS[a], IDS[b]))
        used[a], used[b] = used.get(a, 0) + 1, used.get(b, 0) + 1
        if len(out) == k:
            break
    return out


# ---------------------------------------------------------------- the closet in the same terms


def closet_mix(outfit_vectors: list[np.ndarray]) -> list[dict]:
    """Which styles the clothes you wear already express: each style's profile against the average
    outfit, as a share of the positive matches."""
    if not outfit_vectors:
        return []
    mean = np.mean(outfit_vectors, axis=0)
    raw = []
    for s in STYLES:
        prof = profile(s.id)
        raw.append(max(0.0, float(prof @ mean) / float(np.abs(prof).sum() or 1)))
    total = sum(raw) or 1.0
    out = [{"id": s.id, "name": s.name, "ja": s.ja, "pct": round(100 * r / total)} for s, r in zip(STYLES, raw, strict=True)]
    return sorted(out, key=lambda x: -x["pct"])


def grow(liked: list[dict], closet: list[dict], answers: int) -> dict | None:
    """Of the styles they clearly like (top three, preference 60%+), the one their closet says least:
    where to stretch next."""
    fans = [s for s in liked[:3] if s["pct"] >= 60]
    if answers < 3 or not fans:
        return None
    worn = {c["id"]: c["pct"] for c in closet}
    best = min(fans, key=lambda s: (worn.get(s["id"], 0), -s["pct"]))
    st = BY_ID[best["id"]]
    return {"id": st.id, "name": st.name, "ja": st.ja, "essence": st.essence, "signature": list(st.signature),
            "liked_pct": best["pct"], "closet_pct": worn.get(st.id, 0)}


def prompt_lines(liked: list[dict], growth: dict | None, answers: int) -> list[dict]:
    """The style picture as preference lines for the planning and thrift agents."""
    if answers < 3:
        return []
    top = ", ".join(f"{s['name'].lower()} ({s['pct']}%)" for s in liked[:3])
    lines = [{"text": f"Style boards they picked: {top}", "applies_when": None}]
    if growth:
        lines.append({"text": f"Wants to grow into {growth['name'].lower()}: lean on {', '.join(growth['signature'])}",
                      "applies_when": None})
    return lines
