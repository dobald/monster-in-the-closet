"""Muse Spark tagging and judging, and Muse Image rendering."""

from __future__ import annotations

import base64
import io
from pathlib import Path

import openai
from PIL import Image

from . import config
from .media import on_white, to_data_url
from .schema import FidelityCheck, Garment

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
    )
    return resp.choices[0].message.parsed


def render_outfit(person: Image.Image, garments: list[Image.Image], note: str = "") -> tuple[Image.Image | None, str]:
    """Muse Image edit: dress the person in the exact garments. Returns (image, status)."""
    client = config.client_for("meta")

    def png(img: Image.Image, name: str) -> tuple[str, bytes, str]:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return (name, buf.getvalue(), "image/png")

    files = [png(person, "person.png")] + [png(on_white(g), f"garment_{i}.png") for i, g in enumerate(garments)]
    prompt = (
        "Image 1 is a person. The other images are real clothing items they own. "
        "Dress the person from image 1 in exactly these items. Preserve every garment's "
        "color, pattern, logos, prints and cut precisely; do not invent or restyle details. "
        "Keep the person's face, body shape and skin tone unchanged. Full-body, neutral "
        "studio background, natural pose. " + note
    )
    try:
        resp = client.images.edit(model=config.IMAGE_MODEL, image=files, prompt=prompt)
    except openai.BadRequestError as e:
        body = getattr(e, "body", None) or {}
        code = body.get("code") if isinstance(body, dict) else None
        return None, f"refused ({code or 'bad_request'}): {e.message}"

    item = resp.data[0]
    if getattr(item, "b64_json", None):
        return Image.open(io.BytesIO(base64.b64decode(item.b64_json))).convert("RGB"), "ok"
    if getattr(item, "url", None):
        import urllib.request

        with urllib.request.urlopen(item.url) as r:
            return Image.open(io.BytesIO(r.read())).convert("RGB"), "ok"
    return None, "no image in response"


def judge_fidelity(garment: Image.Image, render: Image.Image, person: Image.Image) -> FidelityCheck:
    """Ask Muse Spark how faithfully the render kept the real garment and person."""
    client = config.client_for("meta")
    resp = client.responses.parse(
        model=config.REASON_MODEL,
        instructions=(
            "You are a strict QA reviewer for a virtual try-on. Image 1 is the real garment, "
            "image 2 is the real person, image 3 is the generated render. Score how faithfully "
            "the render reproduces the real garment and person. Be harsh about changed "
            "patterns, logos, colors or cut; those break the product's promise."
        ),
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Garment, person, render:"},
                {"type": "input_image", "image_url": to_data_url(on_white(garment))},
                {"type": "input_image", "image_url": to_data_url(person)},
                {"type": "input_image", "image_url": to_data_url(render)},
            ],
        }],
        text_format=FidelityCheck,
        reasoning={"effort": "high"},
    )
    return resp.output_parsed


def save(img: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path
