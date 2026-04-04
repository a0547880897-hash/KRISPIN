"""Channel 2 — HSV color prefilter.

A cheap gate that answers: "does this rectified strip contain the brand's
dominant colours at all?" If it doesn't we can skip the more expensive
channels for this frame-client pair. It never produces a standalone hit —
it only raises `pass_filter` to let other channels run.
"""

from __future__ import annotations

from typing import Dict, List

import cv2
import numpy as np

from krispin.reference import ClientFingerprint


# Tolerance (in HSV space) for "close enough" colour match.
HSV_TOLERANCE = np.array([15.0, 70.0, 70.0])


def _color_presence(hsv_image: np.ndarray, target_hsv: np.ndarray) -> float:
    """Fraction of pixels in the image that fall within tolerance of target."""
    diff = np.abs(hsv_image.astype(np.float32) - target_hsv.astype(np.float32))
    within = np.all(diff <= HSV_TOLERANCE, axis=-1)
    return float(within.mean())


def color_pass_per_client(
    rectified: np.ndarray,
    fingerprints: List[ClientFingerprint],
    min_fraction: float = 0.01,
) -> Dict[str, float]:
    """For each client, return the max color-presence fraction.

    Clients with no `brand_colors` defined automatically get a score of 1.0
    (they always pass).
    """
    hsv = cv2.cvtColor(rectified, cv2.COLOR_BGR2HSV)
    out: Dict[str, float] = {}
    for fp in fingerprints:
        if not fp.hsv_centroids:
            out[fp.config.client] = 1.0
            continue
        best = 0.0
        for centroid in fp.hsv_centroids:
            target = np.array(centroid, dtype=np.float32)
            best = max(best, _color_presence(hsv, target))
        out[fp.config.client] = best
    return out
