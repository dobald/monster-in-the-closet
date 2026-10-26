"""Local image/video helpers: frames, masks, cutouts, contact sheets, flat-lays."""

from __future__ import annotations

import base64
import io
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
MAX_IMAGE_EDGE = 2048


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def load_image(path: Path, max_edge: int = MAX_IMAGE_EDGE) -> Image.Image:
    """Load a photo upright (EXIF rotation applied) and capped in size.

    SAM coordinates refer to the image we send, so we always cut from this same copy.
    """
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((max_edge, max_edge))
    return img


def to_data_url(img: Image.Image, fmt: str = "JPEG") -> str:
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(buf, format="JPEG", quality=90)
        mime = "image/jpeg"
    else:
        img.save(buf, format="PNG")
        mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"


def video_info(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise SystemExit(f"OpenCV could not open {path}")
    info = {
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    cap.release()
    return info


def read_frame(path: Path, index: int) -> Image.Image:
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, bgr = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Could not read frame {index} of {path}")
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def place_mask(
    raster: bytes,
    mask_w: int,
    mask_h: int,
    bounds: tuple[int, int, int, int],
    frame_w: int,
    frame_h: int,
) -> tuple[np.ndarray, str]:
    """Turn a decoded SAM raster into a full-frame boolean mask.

    The docs say the raster's size is not the frame size and that masks share the
    box's bounds, but not exactly how the two relate. We infer it and return which
    mode we used so the spike report shows what the API actually does.
    """
    m = np.frombuffer(raster, dtype=np.uint8).reshape(mask_h, mask_w)
    left, top, right, bottom = bounds
    bw, bh = max(right - left, 1), max(bottom - top, 1)

    if (mask_w, mask_h) == (frame_w, frame_h):
        return m.astype(bool), "full_frame"

    bounds_ratio, mask_ratio = bw / bh, mask_w / mask_h
    frame_ratio = frame_w / frame_h
    if abs(mask_ratio - bounds_ratio) <= abs(mask_ratio - frame_ratio):
        full = np.zeros((frame_h, frame_w), dtype=bool)
        crop = cv2.resize(m, (bw, bh), interpolation=cv2.INTER_NEAREST).astype(bool)
        full[top : top + bh, left : left + bw] = crop[: frame_h - top, : frame_w - left]
        return full, "bounds"

    resized = cv2.resize(m, (frame_w, frame_h), interpolation=cv2.INTER_NEAREST)
    return resized.astype(bool), "scaled_full_frame"


def cutout(frame: Image.Image, mask: np.ndarray, pad: int = 8) -> Image.Image:
    """RGBA crop of just the masked garment on a transparent background."""
    rgba = frame.convert("RGBA")
    alpha = Image.fromarray((mask * 255).astype(np.uint8))
    rgba.putalpha(alpha)
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return rgba.crop((0, 0, 1, 1))
    box = (
        max(xs.min() - pad, 0),
        max(ys.min() - pad, 0),
        min(xs.max() + pad, frame.width),
        min(ys.max() + pad, frame.height),
    )
    return rgba.crop(box)


def on_white(img: Image.Image) -> Image.Image:
    """Flatten an RGBA cutout onto white, for models that expect RGB input."""
    bg = Image.new("RGB", img.size, "white")
    bg.paste(img, mask=img.getchannel("A") if img.mode == "RGBA" else None)
    return bg


def contact_sheet(items: list[tuple[str, Image.Image]], cell: int = 220, cols: int = 6) -> Image.Image:
    rows = max(math.ceil(len(items) / cols), 1)
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 24)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (label, img) in enumerate(items):
        thumb = on_white(img)
        thumb.thumbnail((cell - 10, cell - 10))
        x, y = (i % cols) * cell, (i // cols) * (cell + 24)
        sheet.paste(thumb, (x + (cell - thumb.width) // 2, y + 5))
        draw.text((x + 6, y + cell + 4), label[:34], fill="black")
    return sheet


def flat_lay(items: list[Image.Image], size: int = 1024) -> Image.Image:
    """Arrange real cutouts on a neutral board: the always-faithful outfit view."""
    board = Image.new("RGB", (size, size), (243, 240, 235))
    n = max(len(items), 1)
    cols = 1 if n == 1 else 2
    rows = math.ceil(n / cols)
    cw, ch = size // cols, size // rows
    for i, img in enumerate(items):
        piece = img.copy()
        piece.thumbnail((int(cw * 0.85), int(ch * 0.85)))
        x = (i % cols) * cw + (cw - piece.width) // 2
        y = (i // cols) * ch + (ch - piece.height) // 2
        board.paste(piece, (x, y), piece if piece.mode == "RGBA" else None)
    return board
