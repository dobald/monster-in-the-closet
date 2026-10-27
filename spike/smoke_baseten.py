"""One-cent smoke test for Muse Spark Open on Baseten.

Checks the three things the app relies on: plain chat with low reasoning effort,
structured garment tags from an image, and tool calling.

Run: python spike/smoke_baseten.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from closet import config, models  # noqa: E402

# Third-party listed rate for Muse Spark Open on Baseten; check your dashboard.
PRICE_IN, PRICE_OUT = 1.25 / 1e6, 4.25 / 1e6
MODEL = config.TAG_MODEL["baseten"]
spent = 0.0


def cost(usage) -> float:
    global spent
    c = usage.prompt_tokens * PRICE_IN + usage.completion_tokens * PRICE_OUT
    spent += c
    return c


def fake_shirt() -> Image.Image:
    """A crude striped olive shirt on white, so we test vision without personal photos."""
    img = Image.new("RGB", (320, 360), "white")
    d = ImageDraw.Draw(img)
    body = [(70, 60), (120, 40), (200, 40), (250, 60), (300, 130), (260, 150), (240, 120), (240, 330), (80, 330), (80, 120), (60, 150), (20, 130)]
    d.polygon(body, fill=(96, 110, 60), outline="black")
    for y in range(70, 330, 22):
        d.line([(82, y), (238, y)], fill=(230, 225, 205), width=5)
    d.line([(160, 40), (160, 330)], fill="black", width=2)
    return img


def main() -> None:
    client = config.client_for("baseten")
    print(f"Model: {MODEL}\n")

    print("1) Chat, reasoning_effort=low")
    t = time.time()
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "In one short sentence, what should someone wear at 9°C with light rain?"}],
        reasoning_effort="low",
        max_tokens=800,
    )
    msg = r.choices[0].message
    reasoning = getattr(msg, "reasoning_content", None) or (msg.model_extra or {}).get("reasoning_content")
    print(f"   answer: {msg.content!r}")
    print(f"   reasoning field present: {bool(reasoning)} ({len(reasoning or '')} chars)")
    print(f"   tokens in/out: {r.usage.prompt_tokens}/{r.usage.completion_tokens}  "
          f"{time.time() - t:.1f}s  ${cost(r.usage):.5f}\n")

    print("2) Structured garment tags from an image")
    t = time.time()
    g = models.tag_garment(fake_shirt(), provider="baseten")
    print("   " + json.dumps(g.model_dump(), ensure_ascii=False))
    print(f"   {time.time() - t:.1f}s (usage not returned by .parse helper here)\n")

    print("3) Tool calling")
    t = time.time()
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Hourly forecast for the user's city today.",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"], "additionalProperties": False},
        },
    }]
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "I'm in Toronto. Pick tonight's jacket."}],
        tools=tools,
        reasoning_effort="low",
        max_tokens=800,
    )
    calls = r.choices[0].message.tool_calls or []
    print(f"   tool calls: {[(c.function.name, c.function.arguments) for c in calls]}")
    print(f"   tokens in/out: {r.usage.prompt_tokens}/{r.usage.completion_tokens}  "
          f"{time.time() - t:.1f}s  ${cost(r.usage):.5f}\n")

    print(f"Estimated spend (tests 1 + 3): ${spent:.4f}")


if __name__ == "__main__":
    main()
