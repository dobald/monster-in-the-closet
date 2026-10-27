"""Muse Spark tagging and judging, and Muse Image rendering."""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import httpx
from PIL import Image

from . import config
from .media import on_white, to_data_url
from .schema import BodyProfile, FidelityCheck, Garment

TAG_INSTRUCTIONS = (
    "You catalog a person's real wardrobe. The image is one item cut out of a closet "
    "photo or video by a segmentation model. Describe only what is visible. If it is not "
    "a single wearable item (a hanger, furniture, two items merged, or too blurry), set "
    "is_garment=false and lower confidence."
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
    "do not invent, add or restyle details. Full-body, front view, neutral studio background."
)


def render_on_person(person: Image.Image, garments: list[Image.Image], note: str = "") -> tuple[Image.Image | None, str]:
    """Face version: dress the user's own photo in their real garments. Opt-in only."""
    images = [person] + [on_white(g) for g in garments]
    prompt = (
        "Image 1 is a person. The other images are real clothing items they own. "
        "Dress the person from image 1 in exactly these items. " + GARMENT_RULES +
        " Keep the person's face, body shape and skin tone unchanged, natural pose. " + note
    )
    return _edit(images, prompt)


def render_on_mannequin(profile: BodyProfile, garments: list[Image.Image], note: str = "") -> tuple[Image.Image | None, str]:
    """No-photo version: a faceless stand-in built from the user's body details.

    If Muse Image's content filter objects, retry with fewer body details rather than
    failing: a slightly less personalised mannequin beats no try-on. Refusals aren't billed.
    """
    images = [on_white(g) for g in garments]
    status = "error: not attempted"
    for detail in (2, 1, 0):
        prompt = ("Show these exact clothing items worn together by " + profile.describe(detail) + ". "
                  + GARMENT_RULES + " " + note)
        img, status = _edit(images, prompt)
        if img is not None or not status.startswith("refused"):
            return img, status if detail == 2 else f"{status} (simplified mannequin, detail={detail})"
    return None, status


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
