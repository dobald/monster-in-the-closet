"""Build fixtures/scan_guide/: the two example photos in the how-to-scan guide.

"Do" shows what scans well: a few pieces laid flat and apart on a plain floor, shot from above in
daylight. "Don't" shows what doesn't: a crumpled, overlapping pile on a busy bedspread. Muse Image
draws them once; no real person's clothes are in them. A few cents in all.

    .venv/Scripts/python.exe scripts/make_scan_guide.py          # makes the missing ones
    .venv/Scripts/python.exe scripts/make_scan_guide.py good     # (re)makes just these
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from closet import models  # noqa: E402

OUT = ROOT / "fixtures" / "scan_guide"
WIDTH = 640

PHONE = "A realistic smartphone photo shot from directly above, no people, no hands, no text, no logos, no brand labels."
PROMPTS = {
    "good": "Four clothing items laid out flat and smoothed on a plain light wooden floor, well apart with clear gaps "
            "between them, none touching or overlapping, each whole and unfolded with sleeves and legs spread out: a "
            "navy t-shirt, blue jeans, a grey hoodie and a striped long-sleeve top. Bright, even daylight, no harsh "
            "shadows. " + PHONE,
    "bad": "A messy crumpled pile of overlapping clothes heaped together on a busy floral-patterned bedspread: a "
           "t-shirt, jeans and a hoodie tangled and folded over each other, partly hidden, in dim yellow lamp light "
           "with dark shadows. " + PHONE,
}


def main(only: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, prompt in PROMPTS.items():
        path = OUT / f"{name}.jpg"
        if (only and name not in only) or (not only and path.exists()):
            continue
        img, status = models.generate_image(prompt)
        if img is None:
            print(f"{name}: {status}")
            continue
        if img.width > WIDTH:
            img = img.resize((WIDTH, round(img.height * WIDTH / img.width)))
        img.convert("RGB").save(path, quality=82)
        print(f"{name}: ok ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
