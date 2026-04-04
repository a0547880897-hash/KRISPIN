"""Video ingestion — turn an MP4 into a stream of (timestamp, frame) pairs.

We sample at a configurable FPS (default 10) using FFmpeg via OpenCV's
VideoCapture, which is simpler and cross-platform than piping raw frames.
For a 90-minute 1080p match at 10 FPS that's ~54 000 frames — readable in a
single pass on a T4 GPU in ~20–40 minutes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np


@dataclass
class SampledFrame:
    idx: int           # 0-based index into the sampled stream (not source stream)
    timestamp: float   # Seconds from the start of the video
    image: np.ndarray  # BGR, shape (H, W, 3)


def get_video_info(video_path: Path) -> dict:
    """Return basic metadata: fps, frame_count, width, height, duration_s."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = frame_count / fps if fps > 0 else 0.0
        return {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration_s": duration,
        }
    finally:
        cap.release()


def iter_frames(
    video_path: Path,
    target_fps: float = 10.0,
    start_s: float = 0.0,
    end_s: Optional[float] = None,
) -> Iterator[SampledFrame]:
    """Yield frames from `video_path` at ~`target_fps`.

    We read every source frame and keep one every `stride` frames, where
    `stride = round(src_fps / target_fps)`. This is robust to variable-frame-
    rate videos because we also emit the real PTS via `CAP_PROP_POS_MSEC`.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    try:
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        stride = max(1, round(src_fps / target_fps))

        if start_s > 0:
            cap.set(cv2.CAP_PROP_POS_MSEC, start_s * 1000.0)

        emitted = 0
        src_idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if end_s is not None and ts > end_s:
                break

            if src_idx % stride == 0:
                yield SampledFrame(idx=emitted, timestamp=ts, image=frame)
                emitted += 1
            src_idx += 1
    finally:
        cap.release()


def read_first_frame(video_path: Path) -> np.ndarray:
    """Read the first frame — used for one-off calibration UIs."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")
    try:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f"Could not read any frame from {video_path}")
        return frame
    finally:
        cap.release()
