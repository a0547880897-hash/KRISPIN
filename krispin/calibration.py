"""ROI calibration — map the LED-strip polygon in the camera view to a
flat rectangular strip that's easy to run OCR / matching on.

Flow:
  1. User (once per stadium) draws a polygon around the front LED band in a
     reference frame via the Streamlit UI (`ui/calibrate_app.py`).
  2. That polygon + reference frame size is saved to `stadiums/<name>.yaml`.
  3. At detection time, for each sampled frame we compute a homography from
     the polygon to a flat rectangle (default 2400x120) and warp the LED
     strip into that flat rectangle.

The camera in our use case is high and far with only gentle on-axis panning,
so the polygon barely shifts between frames. We still allow an optional small
phase-correlation refinement for robustness but it's not critical.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from krispin.config import StadiumConfig


def order_polygon_clockwise(points: List[Tuple[int, int]]) -> np.ndarray:
    """Return a 4-point polygon ordered TL, TR, BR, BL.

    If the user gave more than 4 points we take the convex hull's bounding
    quadrilateral via `cv2.minAreaRect`.
    """
    pts = np.asarray(points, dtype=np.float32)
    if len(pts) > 4:
        rect = cv2.minAreaRect(pts)
        box = cv2.boxPoints(rect)
        pts = box

    # Order: TL, TR, BR, BL by sum / diff trick.
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(s)]  # TL
    ordered[2] = pts[np.argmax(s)]  # BR
    ordered[1] = pts[np.argmin(d)]  # TR
    ordered[3] = pts[np.argmax(d)]  # BL
    return ordered


def compute_homography(stadium: StadiumConfig, frame_size: Tuple[int, int]) -> np.ndarray:
    """Compute the homography that maps the LED polygon in the source frame
    to a flat (rectified_w x rectified_h) rectangle.

    `frame_size` is (width, height) of the *current* frame. If it differs
    from `stadium.reference_frame_size`, we scale the polygon accordingly.
    """
    ref_w, ref_h = stadium.reference_frame_size
    cur_w, cur_h = frame_size
    sx, sy = cur_w / ref_w, cur_h / ref_h

    src = order_polygon_clockwise(stadium.polygon).copy()
    src[:, 0] *= sx
    src[:, 1] *= sy

    rw, rh = stadium.rectified_size
    dst = np.array([[0, 0], [rw, 0], [rw, rh], [0, rh]], dtype=np.float32)
    H, _ = cv2.findHomography(src, dst)
    return H


def rectify_strip(frame: np.ndarray, H: np.ndarray, rectified_size: Tuple[int, int]) -> np.ndarray:
    """Warp the input frame so the LED strip becomes a flat rectangle."""
    rw, rh = rectified_size
    return cv2.warpPerspective(frame, H, (rw, rh))


# ---------------------------------------------------------------------------
# Stadium preset management
# ---------------------------------------------------------------------------

def save_stadium(stadium: StadiumConfig, stadiums_dir: Path) -> Path:
    stadiums_dir = Path(stadiums_dir)
    stadiums_dir.mkdir(parents=True, exist_ok=True)
    path = stadiums_dir / f"{stadium.name}.yaml"
    stadium.save(path)
    return path


def load_stadium(stadiums_dir: Path, name: str) -> StadiumConfig:
    return StadiumConfig.load(Path(stadiums_dir) / f"{name}.yaml")


def list_stadiums(stadiums_dir: Path) -> List[StadiumConfig]:
    out: List[StadiumConfig] = []
    for p in sorted(Path(stadiums_dir).glob("*.yaml")):
        out.append(StadiumConfig.load(p))
    return out


def auto_detect_stadium(
    first_frame: np.ndarray,
    stadiums_dir: Path,
) -> Optional[StadiumConfig]:
    """Pick the stadium preset whose reference frame size and aspect ratio
    best matches `first_frame`. This is a minimal v1 heuristic — we can later
    swap it for ORB feature matching against saved reference snapshots.
    """
    presets = list_stadiums(stadiums_dir)
    if not presets:
        return None
    h, w = first_frame.shape[:2]
    best: Optional[StadiumConfig] = None
    best_score = -1.0
    for preset in presets:
        pw, ph = preset.reference_frame_size
        aspect_diff = abs((w / h) - (pw / ph))
        res_diff = abs(w - pw) / max(pw, 1)
        score = -(aspect_diff + res_diff)
        if score > best_score:
            best = preset
            best_score = score
    return best
