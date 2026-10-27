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
from .schema import (
    SCORE_RUBRIC,
    SILHOUETTE_WORDS,
    SKIN_TONES,
    BodyProfile,
    FidelityCheck,
    Garment,
    PersonPhotoCheck,
    RenderReview,
)

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

    The judge writes concrete differences ("jeans should be darker indigo and wide-leg").
    Feeding those back as corrections turns it into a critic the generator listens to.
    Stops early once review_score() reaches good_enough.
    """
    attempts, note = [], ""
    _, requested_view = outfit_brief(tags, garments)
    for n in range(max_attempts):
        if person is not None:
            img, status = render_on_person(person, garments, tags, note)
        else:
            img, status = render_on_mannequin(profile, garments, tags, note)
        attempt = {"n": n + 1, "status": status, "note": note, "image": img, "review": None, "score": 0}
        if img is not None:
            review = judge_render(garments, img, person=person, profile=profile, requested_view=requested_view)
            attempt["review"] = review
            attempt["score"] = review_score(review, mannequin=person is None)
        attempts.append(attempt)
        if img is None or attempt["score"] >= good_enough:
            break
        review = attempt["review"]
        fixes = [f"Item {g.garment}: {g.differences}" for g in review.garments if g.score < good_enough]
        if review.subject.matches_request < good_enough or (person is None and review.subject.has_human_face):
            fixes.append(f"Wearer: {review.subject.notes}")
        note = ("Corrections from a reviewer who compared your previous attempt with the real items; "
                "fix all of these: " + " ".join(fixes)[:1200])
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


def _mannequin_spec(profile: BodyProfile | None) -> str:
    """What the judge should expect from a mannequin. Height is left out on purpose: it can't be
    judged from a single studio shot, and asking for it made the old judge mark good renders 1-2/5."""
    if profile is None:
        return "a store display mannequin with a smooth featureless head"
    return (f"a store display mannequin with a smooth featureless head (a head with no facial features is "
            f"correct, not a flaw), {SKIN_TONES[profile.skin_tone][1]} matte finish, {profile.build} build, "
            f"{SILHOUETTE_WORDS[profile.silhouette]}")


def judge_render(
    garments: list[Image.Image],
    render: Image.Image,
    person: Image.Image | None = None,
    profile: BodyProfile | None = None,
    requested_view: str = "Front view.",
) -> RenderReview:
    """One Muse Spark review of a whole render: every garment plus the wearer, in a single call.

    Replaces per-garment judging, which re-scored the wearer once per garment and had no
    rubric. Day-0 problems this fixes: good mannequins marked 1-2/5 (it was judging exact
    height and treating the featureless head as a defect), illegible micro-print dragging an
    otherwise right garment to 2/5, and back-view renders penalised for a front print they
    can't show.
    """
    client = config.client_for("meta")
    n = len(garments)
    images = [on_white(g) for g in garments]
    if person is not None:
        images.append(person)
        layout = (f"Images 1-{n} are the real garments. Image {n + 1} is the real person. "
                  f"Image {n + 2} is the generated render of that person wearing them.")
        wearer = "the same person as the photo, with the same face, body and skin tone"
    else:
        layout = f"Images 1-{n} are the real garments. Image {n + 1} is the generated render of a mannequin wearing them."
        wearer = _mannequin_spec(profile)
    images.append(render)

    content = [{"type": "input_text", "text": layout}]
    content += [{"type": "input_image", "image_url": to_data_url(img)} for img in images]
    resp = client.responses.parse(
        model=config.REASON_MODEL,
        instructions=(
            "You are a fair, exacting QA reviewer for a virtual try-on of someone's real clothes. "
            f"The render should show {wearer}, wearing every real garment exactly. Return one garments row per "
            "garment image, in order. For each, first write the concrete differences, then score. " + SCORE_RUBRIC +
            " A changed fit is a clearly wrong cut and scores 2 or less (e.g. wide-leg or loose rendered as slim, "
            "oversized as fitted, cropped as full length). "
            f"The render was requested as: {requested_view} If it shows that requested side, don't penalise "
            "details that only exist on the other side; mark view_explains_hidden_details. If it shows a different "
            "side than requested and that hides a print or logo the item image shows, score details 2 or less: "
            "the user would not see their print. Judge the wearer separately in `subject`. "
            "Write differences as instructions a renderer could act on (e.g. 'jeans should be darker indigo and "
            "wide-leg, not slim')."
        ),
        input=[{"role": "user", "content": content}],
        text_format=RenderReview,
        reasoning={"effort": "high"},
    )
    review = resp.output_parsed
    # Keep exactly one row per garment, in order, even if the model skipped or repeated one.
    by_index = {g.garment: g for g in review.garments}
    review.garments = [
        by_index.get(i + 1) or FidelityCheck(
            garment=i + 1, differences="not reviewed", garment_visible=False, view_explains_hidden_details=False,
            color_preserved=1, pattern_preserved=1, details_preserved=1, cut_and_fit_preserved=1,
        )
        for i in range(n)
    ]
    return review


def review_score(review: RenderReview, mannequin: bool) -> int:
    """One number for 'is this render good enough': the weakest garment, capped by wearer problems."""
    score = min(g.score for g in review.garments)
    if mannequin and review.subject.has_human_face:
        score = min(score, 2)  # a mannequin with a face breaks the privacy promise
    if review.subject.matches_request <= 2:
        score = min(score, review.subject.matches_request + 1)
    return score


def save(img: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path
