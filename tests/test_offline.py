"""Offline check of the segment step: synthetic video + a fake SAM stream, no API calls.

Run: python tests/test_offline.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "spike"))

import spike  # noqa: E402
from meta_sam_parser._mask_codec import _encode_raster  # noqa: E402  (test-only: build valid mask payloads)

from closet import sam  # noqa: E402

W, H, FRAMES = 320, 240, 60
RED = (40, 30, 120, 200)  # a "shirt": left, top, right, bottom
BLUE = (180, 60, 260, 220)  # "pants"


def make_video(path: Path) -> None:
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (W, H))
    for _ in range(FRAMES):
        img = np.full((H, W, 3), 230, np.uint8)
        cv2.rectangle(img, RED[:2], (RED[2] - 1, RED[3] - 1), (0, 0, 200), -1)
        cv2.rectangle(img, BLUE[:2], (BLUE[2] - 1, BLUE[3] - 1), (200, 0, 0), -1)
        out.write(img)
    out.release()


def record(obj: int, box: tuple[int, int, int, int]) -> str:
    l, t, r, b = box
    w, h = r - l, b - t
    payload = _encode_raster([1] * (w * h), w, h)
    return (f"{obj}<|box;x1={l};y1={t};x2={r - 1};y2={b - 1};w={W};h={H};c=0.9|>"
            f"<|mask;x=0;y=0;c=0.9;data={h},{w},{payload}|>")


# Which rectangles each prompt "finds". jacket re-finds the shirt -> a cross-prompt duplicate.
FAKE_HITS = {"clothing": [RED, BLUE], "shirt": [RED], "jacket": [RED], "pants": [BLUE]}


class FakeResponses:
    async def create(self, *, input, **_):
        prompt = input[0]["content"][0]["text"]
        hits = FAKE_HITS.get(prompt, [])

        async def events():
            yield {"type": "response.created", "response": {"id": "r", "status": "in_progress"}}
            text = ""
            if hits:
                for f in range(FRAMES):
                    line = f"<{f}f>" + ",".join(record(i, b) for i, b in enumerate(hits)) + "\n"
                    text += line
                    yield {"type": "response.output_text.delta", "item_id": "m", "output_index": 0,
                           "content_index": 0, "delta": line}
                yield {"type": "response.output_text.done", "item_id": "m", "output_index": 0,
                       "content_index": 0, "text": text}
            yield {"type": "response.completed", "response": {"id": "r", "status": "completed"}}

        return events()


class FakeClient:
    responses = FakeResponses()


async def fake_upload(client, path):
    return "file-fake"


def main() -> None:
    spike.config.async_client_for = lambda provider="meta": FakeClient()
    sam.upload_video = fake_upload

    with tempfile.TemporaryDirectory() as tmp:
        video = Path(tmp) / "closet.mp4"
        make_video(video)
        args = argparse.Namespace(media=str(video), prompts=list(FAKE_HITS) + ["dress"],
                                  expected=2, dry_run=False, raw_video=True)
        run_dir = spike.cmd_segment(args)

    report = json.loads((run_dir / "segment_report.json").read_text())
    cutouts = sorted(p.name for p in (run_dir / "cutouts").glob("*.png"))
    summary = (run_dir / "SUMMARY.md").read_text()

    assert report["sam_frame_size"] == [W, H], report["sam_frame_size"]
    assert len(report["tracks"]) == 5, report["tracks"]
    assert report["unique_garments_estimate"] == 2, report["unique_garments_estimate"]
    assert len(cutouts) == 5, cutouts
    assert report["mask_modes_seen"] == ["bounds"], report["mask_modes_seen"]
    assert "Segmentation holds up: **PASS**" in summary, summary
    assert "No serious double-counting: **PASS**" in summary, summary
    assert next(p for p in report["prompts"] if p["prompt"] == "dress")["outcome"] == "no_matches"
    shutil.rmtree(run_dir)
    print("OK: segment pipeline, duplicate merging and summary all behave.")


if __name__ == "__main__":
    main()
