"""Muse Spark tagging and judging, and Muse Image rendering."""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import httpx
from PIL import Image

from . import config
from .media import dominant_color, on_white, to_data_url
from .schema import BodyProfile, FidelityCheck, Garment, PersonPhotoCheck

TAG_INSTRUCTIONS = (
    "You catalog a person's real wardrobe. The image is one item cut out of a closet "
    "photo or video by a segmentation model. Describe only what is visible. If it is not "
    "a single wearable item (a hanger, furniture, two items merged, or too blurry), set "
    "is_garment=false and lower confidence. Describe the fit as it really is (a loose, "
    "wide-leg pair of jeans must not be called slim), and say which side faces the camera: "
    "flat-lays are often shot back-up, and prints are often on the back."
)


def tag_garment(cutout: Image.Image, provider: str | None = None) -> Garment:
    """Structured tags for one cutout.

    Meta: Responses API with text_format (the documented image path).
    Baseten: Chat Completions with response_format, the OpenAI-compatible surface it serves.
    """
    provider = provider or config.TAG_PROVIDER
    client = config.client_for(provider)
    model = config.TAG_MODEL[provider]
    image_url = to_data_url(on_white(cutout))

    if provider == "meta":
        resp = client.responses.parse(
            model=model,
            instructions=TAG_INSTRUCTIONS,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Tag this item."},
                    {"type": "input_image", "image_url": image_url},
                ],
            }],
            text_format=Garment,
            reasoning={"effort": "low"},
        )
        return resp.output_parsed

    resp = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": TAG_INSTRUCTIONS},
            {"role": "user", "content": [
                {"type": "text", "text": "Tag this item."},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]},
        ],
        response_format=Garment,
        # Muse Spark Open always reasons and defaults to xhigh. At "high" it can run away
        # (32k tokens on one garment in our bake-off), so keep effort low and cap output.
        reasoning_effort="low",
        max_tokens=4000,
    )
    return resp.choices[0].message.parsed


GARMENT_RULES = (
    "Preserve every garment's color, pattern, logos, prints and cut precisely; "
    "do not invent, add or restyle details. Full-body, neutral studio background."
)


def outfit_brief(
    tags: list[Garment | None] | None,
    garments: list[Image.Image] | None = None,
    first_image: int = 1,
    short: bool = False,
) -> tuple[str, str]:
    """Per-item descriptions plus the camera view, from the wardrobe tags and the cutouts.

    Day-0 renders lost a tour tee's back print, slimmed baggy jeans and lightened denim.
    Each line carries the item's fit, print side and measured colour. Returns
    (items text, view instruction).
    """
    tags = tags or []
    colors = [dominant_color(g) for g in garments] if garments else []
    lines = []
    for i, t in enumerate(tags):
        if t:
            hex_ = colors[i] if i < len(colors) else None
            lines.append(f"Image {first_image + i}: {t.render_line(hex_, short=short)}.")
    back = [t for t in tags if t and t.print_side == "back"]
    front = [t for t in tags if t and t.print_side == "front"]
    if back and not front:
        view = ("Back view: show the figure from behind so the back print is fully visible and legible, "
                "exactly as in the item image.")
    else:
        view = "Front view."
    return ("Items: " + " ".join(lines)) if lines else "", view


# Retry ladder when Muse Image's content filter refuses (refusals aren't billed).
# Item details go before body details: Day-0 refusals came from long combined prompts,
# and losing a free-text detail line costs less than losing the user's body shape.
MANNEQUIN_LADDER = [(2, False), (2, True), (1, True), (0, True)]  # (body detail, short items)


def render_on_person(
    person: Image.Image, garments: list[Image.Image], tags: list[Garment | None] | None = None, note: str = ""
) -> tuple[Image.Image | None, str]:
    """Face version: dress the user's own photo in their real garments. Opt-in only."""
    images = [person] + [on_white(g) for g in garments]
    status = "error: not attempted"
    for short in (False, True):
        items, view = outfit_brief(tags, garments, first_image=2, short=short)
        prompt = (
            "Image 1 is a person. The other images are real clothing items they own. "
            "Dress the person from image 1 in exactly these items. " + items + " " + GARMENT_RULES + " " + view +
            " Keep the person's face, body shape and skin tone unchanged, natural pose. " + note
        )
        img, status = _edit(images, prompt)
        if img is not None or not status.startswith("refused"):
            return img, status if not short else f"{status} (short item details)"
    return None, status


def render_on_mannequin(
    profile: BodyProfile, garments: list[Image.Image], tags: list[Garment | None] | None = None, note: str = ""
) -> tuple[Image.Image | None, str]:
    """No-photo version: a faceless stand-in built from the user's body details.

    On a content-filter refusal, walk MANNEQUIN_LADDER: shorten item details first, then
    body details. A slightly less specific prompt beats no try-on.
    """
    images = [on_white(g) for g in garments]
    status = "error: not attempted"
    for detail, short in MANNEQUIN_LADDER:
        items, view = outfit_brief(tags, garments, first_image=1, short=short)
        prompt = ("Show these exact clothing items worn together by " + profile.describe(detail) + ". "
                  + items + " " + GARMENT_RULES + " " + view + " " + note)
        img, status = _edit(images, prompt)
        if img is not None or not status.startswith("refused"):
            simplified = (detail, short) != MANNEQUIN_LADDER[0]
            return img, status if not simplified else f"{status} (simplified: body detail={detail}, short items={short})"
    return None, status


def render_best(
    garments: list[Image.Image],
    tags: list[Garment | None] | None = None,
    person: Image.Image | None = None,
    profile: BodyProfile | None = None,
    max_attempts: int = 2,
    good_enough: int = 4,
) -> dict:
    """Generate, judge, and retry once with the judge's corrections; keep the best render.

    The fidelity judge already writes concrete differences ("jeans lighter than the
    reference, slim instead of wide-leg"). Feeding those back as corrections turns the
    judge into a critic the generator listens to. Stops early once every garment scores
    >= good_enough on colour, pattern, details and cut.
    """
    attempts, note = [], ""
    for n in range(max_attempts):
        if person is not None:
            img, status = render_on_person(person, garments, tags, note)
        else:
            img, status = render_on_mannequin(profile, garments, tags, note)
        attempt = {"n": n + 1, "status": status, "note": note, "image": img, "fidelity": [], "score": 0}
        if img is not None:
            checks = [judge_fidelity(g, img, person=person, profile=profile) for g in garments]
            attempt["fidelity"] = checks
            attempt["score"] = min(
                min(c.color_preserved, c.pattern_preserved, c.details_preserved, c.cut_and_fit_preserved) for c in checks
            )
        attempts.append(attempt)
        if img is None or attempt["score"] >= good_enough:
            break
        fixes = " ".join(f"Item {i + 1}: {c.differences}" for i, c in enumerate(attempt["fidelity"]))
        note = ("Corrections from a reviewer who compared your previous attempt with the real items; "
                "fix all of these: " + fixes[:1200])
    best = max(attempts, key=lambda a: (a["image"] is not None, a["score"]))
    return {"best": best, "attempts": attempts}


def check_person_photo(photo: Image.Image) -> PersonPhotoCheck:
    """Gate for the face version: a hidden face makes Muse Image invent one (seen on Day 0)."""
    client = config.client_for("meta")
    resp = client.responses.parse(
        model=config.REASON_MODEL,
        instructions=(
            "You check a photo someone uploaded for a virtual try-on of their own clothes. It must show exactly "
            "one person, full body head to feet, with the face clearly visible and not covered by a phone, hand, "
            "hair or mask. Mirror selfies are fine if the phone does not cover the face."
        ),
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": "Check this photo."},
            {"type": "input_image", "image_url": to_data_url(photo)},
        ]}],
        text_format=PersonPhotoCheck,
        reasoning={"effort": "low"},
    )
    return resp.output_parsed


def _edit(images: list[Image.Image], prompt: str) -> tuple[Image.Image | None, str]:
    """One Muse Image edit call. Returns (image, status).

    Sent as JSON with an `images` array of data URLs: the OpenAI SDK's multipart upload
    labels files `image[]`, which Meta rejects (it wants `image[0]`, `image[1]`, ...).
    A content-policy refusal is a status, not an exception, so the spike can report it.
    """
    p = config.PROVIDERS["meta"]
    body = {"model": config.IMAGE_MODEL, "prompt": prompt, "n": 1,
            "images": [{"image_url": to_data_url(i, "PNG")} for i in images]}
    r = httpx.post(p.base_url.rstrip("/") + "/images/edits", json=body,
                   headers={"Authorization": f"Bearer {p.api_key}"}, timeout=180)
    if r.status_code != 200:
        try:
            err = r.json().get("error", r.json())
        except ValueError:
            err = {"message": r.text[:300]}
        code = err.get("code") if isinstance(err, dict) else None
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        msg = re.sub(r"data:[^\"' ]{40,}", "data:…", msg)[:300]  # never echo image bytes back
        if code == "content_policy_violation":
            return None, f"refused (content_policy_violation): {msg}"
        return None, f"error ({r.status_code}{', ' + code if code else ''}): {msg}"

    item = r.json()["data"][0]
    if item.get("b64_json"):
        return Image.open(io.BytesIO(base64.b64decode(item["b64_json"]))).convert("RGB"), "ok"
    if item.get("url"):
        return Image.open(io.BytesIO(httpx.get(item["url"], timeout=60).content)).convert("RGB"), "ok"
    return None, "error: no image in response"


def judge_fidelity(
    garment: Image.Image,
    render: Image.Image,
    person: Image.Image | None = None,
    profile: BodyProfile | None = None,
) -> FidelityCheck:
    """Ask Muse Spark how faithfully the render kept the real garment and the person or mannequin spec."""
    client = config.client_for("meta")
    if person is not None:
        subject = "Image 2 is the real person, image 3 is the generated render."
        images = [garment, person, render]
    else:
        subject = ("Image 2 is the generated render. It should show " + (profile.describe() if profile else "a faceless mannequin")
                   + " with no human face.")
        images = [garment, render]
    content = [{"type": "input_text", "text": "Images in order:"}]
    content += [{"type": "input_image", "image_url": to_data_url(on_white(img) if i == 0 else img)} for i, img in enumerate(images)]
    resp = client.responses.parse(
        model=config.REASON_MODEL,
        instructions=(
            "You are a strict QA reviewer for a virtual try-on. Image 1 is the real garment. " + subject +
            " Score how faithfully the render reproduces the real garment and the subject. Be harsh about "
            "changed patterns, logos, colors or cut; those break the product's promise."
        ),
        input=[{"role": "user", "content": content}],
        text_format=FidelityCheck,
        reasoning={"effort": "high"},
    )
    return resp.output_parsed


def save(img: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path
