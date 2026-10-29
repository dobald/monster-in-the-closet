"""Build fixtures/touch_examples/: one example photo per finishing-touch play (closet/styling.py).

Each touch in the app ("let a tee hem peek below the knit", "front-tuck it", "two or three
silver rings") gets a small picture of the idea, so people see it instead of decoding it.
Muse Image draws them once; nobody's real clothes or face are in them: worn ideas are shown
on a faceless display mannequin, accessories as close-up flat-lays. About 25 cents in all.

    .venv/Scripts/python.exe scripts/make_touch_examples.py            # makes the missing ones
    .venv/Scripts/python.exe scripts/make_touch_examples.py hem_peek   # (re)makes just these
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from closet import models, styling  # noqa: E402

OUT = ROOT / "fixtures" / "touch_examples"
WIDTH = 640  # shown as a small thumbnail, and at most phone-width when opened

STYLE = ("Clean editorial fashion detail photo on a plain warm off-white studio background, soft daylight, natural "
         "true-to-life colours, realistic fabric texture. No text, no logos, no brand labels.")
WORN = "worn by a store display mannequin with a smooth featureless head, framed from the shoulders to the hips"
FLAT = "close-up flat-lay shot from directly above"

PROMPTS: dict[str, str] = {
    # underlayers
    "hem_peek": f"A grey crewneck sweater over a plain white t-shirt whose hem shows 2 cm below the sweater's hem, {WORN}.",
    "collar_peek": f"A navy crewneck sweater with a white button-up shirt underneath, the shirt collar pulled out over "
                   f"the sweater's neckline, {WORN}.",
    "sleeve_layer": f"A short-sleeve black t-shirt layered over a fitted grey long-sleeve tee, the long sleeves showing "
                    f"below the short ones, {WORN}.",
    "turtleneck_under": f"A thin black turtleneck worn under an open camel overshirt, {WORN}.",
    "open_shirt": f"An unbuttoned light blue oxford shirt worn open like a light jacket over a white t-shirt, sleeves "
                  f"pushed up, {WORN}.",
    # techniques
    "front_tuck": f"A loose cream t-shirt with only the front tucked into high-waisted wide-leg jeans, the back left "
                  f"untucked, a belt just visible, display mannequin with a smooth featureless head, framed from the "
                  f"chest to the knees.",
    "sleeve_push": f"A heather grey knit sweater with both sleeves clearly pushed up and bunched just below the elbows, "
                   f"the bare forearms and wrists showing, {WORN}.",
    "cuff_roll": "A display mannequin wearing straight-leg dark jeans and a tucked white t-shirt, framed from the waist "
                 "to the floor, the jean hems cuffed once (about 3 cm) to show a slice of white sock above white low-top "
                 "sneakers.",
    # accessories
    "rings": f"Three simple silver rings, two plain bands and one signet, resting on a folded grey knit sleeve, {FLAT}.",
    "chain": f"A fine thin gold chain necklace laid on a folded white t-shirt at the neckline, {FLAT}.",
    "watch": f"A simple minimalist watch with a brown leather strap on a folded navy shirt cuff, {FLAT}.",
    "belt": f"A brown leather belt threaded through folded beige chinos next to brown leather shoes, {FLAT}.",
    "cap": f"A plain black baseball cap next to a folded white t-shirt and folded grey trousers, {FLAT}.",
    "beanie": f"A rib-knit olive beanie next to a folded olive and cream sweater, {FLAT}.",
    "scarf": f"A soft charcoal wool scarf looped once around the neck over a smooth navy coat, {WORN}.",
    "socks": f"Clean white crew socks with white low-top sneakers and the cuffed hem of dark jeans, {FLAT}.",
    "bag": f"A canvas tote bag and a small leather crossbody bag side by side, {FLAT}.",
    "shoe_weight": "A display mannequin in wide-leg black trousers, framed from the waist to the floor, the trousers "
                   "falling over thick-soled chunky white sneakers with a visibly tall, heavy sole.",
    "high_low": f"A grey hooded sweatshirt and track pants paired with a polished silver watch and brown leather "
                f"loafers, {FLAT}.",
    # colour
    "colour_echo": f"A white t-shirt with a red and navy graphic print, laid with a red cap that repeats the print's "
                   f"red, and navy trousers, {FLAT}.",
    "accent_pop": f"An all-neutral outfit, a grey sweater, black trousers and white sneakers, with one bright orange "
                  f"beanie as the only colour, {FLAT}.",
    "bookend": f"A forest green sweater, beige trousers and forest green sneakers laid as an outfit, the green at the "
               f"top and the bottom, {FLAT}.",
    "light_break": f"An all-black outfit, black sweater, black trousers and black shoes, broken by a white t-shirt hem "
                   f"and white socks, {FLAT}.",
    "texture_contrast": f"A chunky cream cable-knit sweater next to a smooth brown leather belt and a crisp cotton "
                        f"shirt, {FLAT}.",
}


def main(only: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [p.id for p in styling.PLAYBOOK if p.id not in PROMPTS]
    if missing:
        raise SystemExit(f"No prompt for: {missing}")
    for play in styling.PLAYBOOK:
        path = OUT / f"{play.id}.jpg"
        if (only and play.id not in only) or (not only and path.exists()):
            continue
        img, status = models.generate_image(f"{PROMPTS[play.id]} {STYLE}")
        if img is None:
            print(f"{play.id}: {status}")
            continue
        img = img.resize((WIDTH, round(img.height * WIDTH / img.width)))
        img.save(path, format="JPEG", quality=82, optimize=True)
        print(f"{play.id}: ok ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
