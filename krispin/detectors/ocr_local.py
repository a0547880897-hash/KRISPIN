"""Channel 1 — Local OCR via PaddleOCR.

This is the PRIMARY channel. Per the user's feedback the most important
signal is the brand name / on-board text. We run PaddleOCR on the rectified
LED strip once per sampled frame, then fuzzy-match each detected line against
every client's `brand_text` tokens.

PaddleOCR supports Arabic-script (RTL) reasonably well; for Hebrew it works
but the strongest signal comes from Latin brand names (e.g. "JAKO") which it
nails. We configure it to run with `lang='en'` for strong Latin, plus a second
pass with `lang='ar'` which covers Hebrew-ish characters surprisingly well.

The detector is lazy-loaded — first call constructs the model (slow), later
calls reuse it (fast).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from rapidfuzz import fuzz

from krispin.config import FrameHit
from krispin.reference import ClientFingerprint


@dataclass
class OcrLocal:
    """Stateful wrapper holding the PaddleOCR model(s)."""

    min_score: float = 0.6           # PaddleOCR line confidence minimum
    fuzzy_threshold: int = 85        # rapidfuzz partial_ratio min (0..100)
    _ocr_en: object = None
    _ocr_he: object = None           # fallback for non-Latin lines

    def _lazy_init(self) -> None:
        if self._ocr_en is not None:
            return
        from paddleocr import PaddleOCR  # local import to keep CLI imports fast

        self._ocr_en = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        # PaddleOCR does not ship an explicit Hebrew model; 'arabic' covers
        # Hebrew characters well enough for brand-name matching.
        try:
            self._ocr_he = PaddleOCR(use_angle_cls=True, lang="arabic", show_log=False)
        except Exception:
            self._ocr_he = None

    def _run_paddle(self, model, image: np.ndarray) -> List[tuple]:
        """Normalise PaddleOCR output to [(text, score, bbox), ...]."""
        if model is None:
            return []
        try:
            raw = model.ocr(image, cls=True)
        except Exception:
            return []
        if not raw:
            return []
        first = raw[0]
        if first is None:
            return []
        out = []
        for line in first:
            try:
                bbox = line[0]
                text = line[1][0]
                score = float(line[1][1])
                out.append((text, score, bbox))
            except (IndexError, TypeError, ValueError):
                continue
        return out

    def detect(
        self,
        rectified: np.ndarray,
        fingerprints: List[ClientFingerprint],
        frame_idx: int,
        timestamp: float,
    ) -> List[FrameHit]:
        self._lazy_init()

        lines = self._run_paddle(self._ocr_en, rectified)
        if self._ocr_he is not None:
            lines += self._run_paddle(self._ocr_he, rectified)

        # Filter by OCR confidence.
        texts = [t for t, s, _ in lines if s >= self.min_score and t and t.strip()]
        if not texts:
            return []

        joined = " ".join(texts).lower()

        hits: List[FrameHit] = []
        for fp in fingerprints:
            best_score = 0.0
            matched_token: Optional[str] = None
            for token in fp.text_tokens:
                score = fuzz.partial_ratio(token, joined)
                if score > best_score:
                    best_score = score
                    matched_token = token
            if best_score >= self.fuzzy_threshold:
                hits.append(
                    FrameHit(
                        client=fp.config.client,
                        frame_idx=frame_idx,
                        timestamp=timestamp,
                        channel="ocr_local",
                        confidence=best_score / 100.0,
                        details={
                            "matched_token": matched_token,
                            "seen_text": joined[:200],
                        },
                    )
                )
        return hits
