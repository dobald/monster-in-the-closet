"""Local image/video helpers: frames, masks, cutouts, contact sheets, flat-lays."""

from __future__ import annotations

import base64
import io
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

try:  # iPhone photos are HEIC; Pillow needs this plugin to open them.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
MAX_IMAGE_EDGE = 2048


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def load_image(path: Path | io.BytesIO, max_edge: int = MAX_IMAGE_EDGE) -> Image.Image:
    """Load a photo (file path or in-memory upload) upright, EXIF rotation applied, capped in size.

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


def normalize_video(path: Path, max_edge: int = 1280, fps: float = 10.0) -> Path:
    """Downscale and thin a phone video before upload; cached next to the source.

    A 4K/30fps iPhone clip is ~100 MB and SAM bills per frame. 1280px at 10fps keeps
    garments trackable for a third of the frames, and re-encoding bakes in the phone's
    rotation so SAM and OpenCV agree on frame size. Output is MPEG-4 (accepted by SAM).
    """
    out_dir = path.parent / "_normalized"
    out = out_dir / f"{path.stem}_{max_edge}px_{int(fps)}fps.mp4"
    if out.exists():
        return out
    out_dir.mkdir(exist_ok=True)

    cap = cv2.VideoCapture(str(path))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(src_fps / fps))
    writer = None
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            h, w = frame.shape[:2]
            scale = min(1.0, max_edge / max(h, w))
            if scale < 1:
                frame = cv2.resize(frame, (int(w * scale) // 2 * 2, int(h * scale) // 2 * 2), interpolation=cv2.INTER_AREA)
            if writer is None:
                writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), src_fps / step,
                                         (frame.shape[1], frame.shape[0]))
            writer.write(frame)
        i += 1
    cap.release()
    if writer is None:
        raise SystemExit(f"Could not read any frames from {path}")
    writer.release()
    return out


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


def upscale_mask(mask: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Resize a boolean mask to (w, h), smoothing the edge so cutouts aren't jagged."""
    if mask.shape[::-1] == tuple(size):
        return mask
    soft = cv2.resize(mask.astype(np.float32), size, interpolation=cv2.INTER_LINEAR)
    return soft >= 0.5


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fill enclosed gaps in a garment mask.

    SAM often treats a printed graphic (e.g. photos on a tour tee) as a separate object and
    leaves a hole. Real garments almost never have enclosed holes, so anything the
    background can't reach from the image border belongs to the garment.
    """
    m = mask.astype(np.uint8) * 255
    h, w = m.shape
    flood = np.pad(m, 1)  # a 1px empty border guarantees the fill starts outside the garment
    ff_mask = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(flood, ff_mask, (0, 0), 255)
    holes = flood[1:-1, 1:-1] == 0
    return mask | holes


def cutout(frame: Image.Image, mask: np.ndarray, pad: int = 8) -> Image.Image:
    """RGBA crop of just the masked garment (holes filled) on a transparent background."""
    mask = fill_holes(mask)
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


def dominant_color(img: Image.Image) -> str:
    """Median colour of a cutout's opaque pixels as #rrggbb (the garment's real shade)."""
    rgba = np.asarray(img.convert("RGBA"))
    opaque = rgba[rgba[..., 3] > 200][:, :3]
    if len(opaque) == 0:
        return "#808080"
    r, g, b = np.median(opaque, axis=0).astype(int)
    return f"#{r:02x}{g:02x}{b:02x}"


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
