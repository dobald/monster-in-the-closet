"""How garments layer on a body: which goes over which, and what the outer one hides.

The paper-doll try-on (server/layers.py) renders every garment on the mannequin on its own, so
an oversized tee comes out wider than the hoodie over it and its sleeves stick out past the
hoodie's shoulders. Two things fix that, for every combination rather than one look:

1. **Layer rank** from the tags, not just the category: base tops (tee, shirt, henley) sit
   under mid layers (sweatshirt, knit, cardigan), which sit under outer layers (jacket, coat,
   zip-up hoodie). Ties go to the warmer piece on top.
2. **Occlusion.** An inner garment only shows outside the garments over it where clothes really
   peek out: at the neckline and an open front, below the outer hem or cuffs, and on the arms when
   the outer piece is short-sleeved or sleeveless. Everywhere else outside the outer silhouette
   (a tee sleeve beside a hoodie sleeve, a shirt's side seam past a jacket) is hidden.
"""

from __future__ import annotations

import re

import numpy as np

UPPER = {"top", "outerwear", "dress"}  # garments that layer over each other on the upper body

# Layer rank: lower is closer to the body.
RANK = {"bottom": 1.0, "dress": 1.5, "top": 2.0, "outerwear": 3.0}
BASE = r"\b(t-?shirt|tee|tank|cami|henley|shirt|blouse|polo|turtleneck|bodysuit|crop top)\b"
MID = r"\b(sweatshirt|sweater|jumper|pullover|hoodie|knit|cardigan|fleece|vest|gilet|quarter-?zip|crewneck)\b"
OUTER = r"\b(jacket|coat|parka|blazer|bomber|trench|anorak|overshirt|shacket|puffer|windbreaker|zip-?up)\b"
SHORT = r"short[- ]?sleeve|t-?shirt|\btee\b|polo|cap sleeve"
NONE = r"sleeveless|tank|cami|\bvest\b|gilet|strapless|halter"

NECK_SPAN = 0.17  # half-width of the front zone (neckline, open front), as a share of the outer's width


def rank(tags: dict) -> float:
    """Where a garment sits in the stack (higher is further out)."""
    cat = tags.get("category", "top")
    r = RANK.get(cat, 2.0)
    words = f"{tags.get('subtype', '')} {tags.get('fit', '')}".lower()
    if cat in ("top", "outerwear"):
        if re.search(OUTER, words):
            r = 3.0
        elif re.search(MID, words):
            r = 2.5
        elif re.search(BASE, words):
            r = 2.0
    return r + 0.01 * int(tags.get("warmth", 2))  # the warmer of two equals goes on top


def sleeves(tags: dict) -> str:
    """none | short | long, from the tags. Outerwear and knits are long unless they say otherwise."""
    words = f"{tags.get('subtype', '')} {tags.get('fit', '')} {tags.get('distinctive_details', '')}".lower()
    if re.search(r"long[- ]?sleeve", words):
        return "long"
    if re.search(NONE, words):
        return "none"
    if re.search(SHORT, words):
        return "short"
    return "long"


def order(items: list[dict]) -> list[dict]:
    """Items bottom of the stack first."""
    return sorted(items, key=lambda i: (rank(i["tags"]), i["id"]))


def occlude(inner: np.ndarray, outer: np.ndarray, outer_long_sleeves: bool) -> np.ndarray:
    """The inner layer's alpha with everything the outer garments hide taken out.

    `inner` and `outer` are alpha arrays on the same canvas (0-1 or 0-255); `outer` is the union of
    every garment over the inner one. Inner pixels under the outer silhouette are left alone (the
    outer is drawn over them anyway). Outside it they stay only where clothes peek out:
    - the front zone around the outer's centre line: a neckline or an open front;
    - below the outer garment in that column: a longer hem, or a cuff past the outer cuff;
    - columns the outer doesn't reach at all, when its sleeves are short or missing (the inner
      garment's own sleeves on bare arms).
    """
    out_mask = outer > (0.5 if outer.max() <= 1 else 127)
    if not out_mask.any():
        return inner
    h, w = out_mask.shape
    cols = out_mask.any(axis=0)
    ys, xs = np.nonzero(out_mask)
    cx, width = (xs.min() + xs.max()) / 2, xs.max() - xs.min() + 1

    # The lowest outer pixel in each column (-1 where the outer doesn't reach).
    lowest = np.where(cols, h - 1 - np.argmax(out_mask[::-1, :], axis=0), -1)
    rows = np.arange(h)[:, None]
    below = rows > lowest[None, :]
    front = np.abs(np.arange(w) - cx)[None, :] <= NECK_SPAN * width
    bare_arms = ~cols[None, :] if not outer_long_sleeves else np.zeros((1, w), bool)

    keep = out_mask | front | (below & cols[None, :]) | bare_arms
    return np.where(keep, inner, 0).astype(inner.dtype)
