"""SAM 3.1 over the Meta Model API: text-prompted segmentation of a photo or video.

One request per noun phrase (the API doesn't support lists like "shirt, pants").
In video, SAM keeps an object's id stable across frames, which is how we avoid
cataloging the same garment once per frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import meta_sam_parser as sp
from openai import AsyncOpenAI

from . import config

# $ per request, from https://dev.meta.ai/docs/pricing-rate-limits
PRICE_PER_IMAGE = 2.50 / 1000
PRICE_PER_FRAME = 0.20 / 1000
MIN_BILLED_FRAMES = 50
MAX_OBJECTS_PER_FRAME = 16


@dataclass
class Track:
    """Everything SAM returned for one object id under one prompt."""

    prompt: str
    object_id: str
    boxes: dict[int, tuple[int, int, int, int]] = field(default_factory=dict)  # frame -> box
    masks: dict[int, sp.SegmentationMaskRecord] = field(default_factory=dict)  # frame -> mask
    confidence: dict[int, float] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.prompt}#{self.object_id}"

    @property
    def frames(self) -> list[int]:
        return sorted(self.boxes)

    def area(self, frame: int) -> int:
        l, t, r, b = self.boxes[frame]
        return (r - l) * (b - t)

    def best_frame(self) -> int:
        """Frame where the garment is biggest (and most confident, if we have scores)."""
        return max(self.boxes, key=lambda f: (self.area(f) * self.confidence.get(f, 1.0)))


@dataclass
class SegmentationRun:
    prompt: str
    tracks: list[Track]
    max_objects_in_a_frame: int
    diagnostics: list[str]
    outcome: str
    frame_size: tuple[int, int] | None  # (w, h) as SAM saw it


def _content(media: dict, prompt: str) -> list[dict]:
    return [{
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": prompt}, media],
    }]


async def upload_video(client: AsyncOpenAI, path: Path) -> str:
    with path.open("rb") as f:
        uploaded = await client.files.create(purpose="user_data", file=f)
    return uploaded.id


async def segment(
    client: AsyncOpenAI,
    prompt: str,
    *,
    video_file_id: str | None = None,
    image_data_url: str | None = None,
) -> SegmentationRun:
    if video_file_id:
        media = {"type": "input_video", "file_id": video_file_id}
        fmt = sp.video_segmentation_format()
    else:
        media = {"type": "input_image", "image_url": image_data_url}
        fmt = sp.image_segmentation_format()

    stream = await client.responses.create(
        model=config.SAM_MODEL,
        input=_content(media, prompt),
        stream=True,
        metadata={"include_confidence": "true"},
    )
    try:
        result = await sp.parse_responses_stream(stream, fmt).final_result()
    except sp.ResponsesStreamLaneError as e:
        # Zero matches can arrive as a stream with no text lane at all.
        return SegmentationRun(prompt, [], 0, [f"no output lane: {e}"], "no_matches", None)

    tracks: dict[str, Track] = {}
    per_frame: dict[int, int] = {}
    frame_size = None
    for rec in result.records:
        if rec.kind not in ("box", "mask"):
            continue
        frame = rec.frame.frame_index if getattr(rec, "frame", None) else 0
        t = tracks.setdefault(rec.object_id, Track(prompt, rec.object_id))
        if rec.kind == "box":
            t.boxes[frame] = (rec.left, rec.top, rec.right, rec.bottom)
            per_frame[frame] = per_frame.get(frame, 0) + 1
            if rec.confidence is not None:
                t.confidence[frame] = rec.confidence
        else:
            t.masks[frame] = rec

    # The box token carries the source size (w, h) but the parser doesn't surface it,
    # so read it from the first box token in the raw text.
    raw = result.raw_output or ""
    i = raw.find("<|box;")
    if i >= 0:
        token = raw[i : raw.find("|>", i)]
        kv = dict(p.split("=", 1) for p in token.split(";")[1:] if "=" in p)
        if "w" in kv and "h" in kv:
            frame_size = (int(kv["w"]), int(kv["h"]))

    return SegmentationRun(
        prompt=prompt,
        tracks=[t for t in tracks.values() if t.boxes],
        max_objects_in_a_frame=max(per_frame.values(), default=0),
        diagnostics=[f"{d.code}: {d.message}" for d in result.diagnostics],
        outcome=getattr(result.outcome, "status", str(result.outcome)),
        frame_size=frame_size,
    )


def iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    l, t = max(a[0], b[0]), max(a[1], b[1])
    r, btm = min(a[2], b[2]), min(a[3], b[3])
    inter = max(r - l, 0) * max(btm - t, 0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def cross_prompt_duplicates(tracks: list[Track], threshold: float = 0.6) -> list[tuple[str, str, float]]:
    """Pairs of tracks from different prompts that cover the same pixels.

    e.g. one garment matched by both "shirt" and "jacket". Mean IoU over shared frames.
    """
    dupes = []
    for i, a in enumerate(tracks):
        for b in tracks[i + 1 :]:
            if a.prompt == b.prompt:
                continue
            shared = set(a.boxes) & set(b.boxes)
            if not shared:
                continue
            score = sum(iou(a.boxes[f], b.boxes[f]) for f in shared) / len(shared)
            if score >= threshold:
                dupes.append((a.key, b.key, round(score, 2)))
    return dupes


def estimate_cost(n_prompts: int, frames: int | None) -> float:
    if frames is None:
        return n_prompts * PRICE_PER_IMAGE
    return n_prompts * max(frames, MIN_BILLED_FRAMES) * PRICE_PER_FRAME
