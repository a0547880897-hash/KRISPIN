"""Channel 4 — ORB keypoint matching against the client logo image.

Good for ads that are mostly graphic (logos with little text). ORB is fast,
runs on CPU, and is robust to mild scale/perspective changes.

We match descriptors from the rectified strip against each client's ORB
descriptors, then apply Lowe's ratio test. A frame is a hit for client X if
the number of good matches clears a minimum.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

from krispin.config import FrameHit
from krispin.reference import ClientFingerprint


@dataclass
class KeypointDetector:
    min_good_matches: int = 12
    ratio_test: float = 0.75
    _orb: object = None
    _matcher: object = None

    def _lazy_init(self) -> None:
        if self._orb is None:
            self._orb = cv2.ORB_create(nfeatures=1000)
            self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def detect(
        self,
        rectified: np.ndarray,
        fingerprints: List[ClientFingerprint],
        frame_idx: int,
        timestamp: float,
    ) -> List[FrameHit]:
        self._lazy_init()

        gray = cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY)
        _, frame_desc = self._orb.detectAndCompute(gray, None)
        if frame_desc is None or len(frame_desc) < 2:
            return []

        hits: List[FrameHit] = []
        for fp in fingerprints:
            if fp.orb_descriptors is None or len(fp.orb_descriptors) < 2:
                continue
            try:
                knn = self._matcher.knnMatch(fp.orb_descriptors, frame_desc, k=2)
            except cv2.error:
                continue
            good = [m for pair in knn if len(pair) == 2
                    for m, n in [pair]
                    if m.distance < self.ratio_test * n.distance]
            if len(good) >= self.min_good_matches:
                # Normalise to 0..1 by capping at 3x the minimum.
                conf = min(1.0, len(good) / (3 * self.min_good_matches))
                hits.append(
                    FrameHit(
                        client=fp.config.client,
                        frame_idx=frame_idx,
                        timestamp=timestamp,
                        channel="keypoint",
                        confidence=conf,
                        details={"good_matches": len(good)},
                    )
                )
        return hits
