"""Channel 3 — CLIP tile-based visual matching.

We split the rectified LED strip into `n_tiles` horizontal tiles, compute a
CLIP embedding per tile, and compare each tile against each client's mean
reference embedding. A frame matches a client if the max tile similarity is
above threshold.

Tile-level (rather than whole-strip) matching handles partial occlusion —
if a player stands in front of 3 out of 10 tiles the remaining 7 still carry
the brand signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np

from krispin.config import FrameHit
from krispin.reference import ClientFingerprint


@dataclass
class ClipDetector:
    n_tiles: int = 10
    similarity_threshold: float = 0.78  # cosine, tuned on a few matches
    model: object = None
    preprocess: object = None
    device: str = "cpu"

    def _split_tiles(self, rectified: np.ndarray) -> List[np.ndarray]:
        h, w = rectified.shape[:2]
        tile_w = w // self.n_tiles
        tiles = []
        for i in range(self.n_tiles):
            x0 = i * tile_w
            x1 = w if i == self.n_tiles - 1 else (i + 1) * tile_w
            tiles.append(rectified[:, x0:x1])
        return tiles

    def _embed_batch(self, bgr_images: List[np.ndarray]) -> Optional[np.ndarray]:
        if self.model is None or self.preprocess is None or not bgr_images:
            return None
        import torch
        from PIL import Image

        tensors = []
        for img in bgr_images:
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            tensors.append(self.preprocess(pil))
        batch = torch.stack(tensors).to(self.device)
        with torch.no_grad():
            feats = self.model.encode_image(batch)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.cpu().numpy().astype(np.float32)

    def detect(
        self,
        rectified: np.ndarray,
        fingerprints: List[ClientFingerprint],
        frame_idx: int,
        timestamp: float,
    ) -> List[FrameHit]:
        if self.model is None:
            return []

        tiles = self._split_tiles(rectified)
        tile_embs = self._embed_batch(tiles)  # (n_tiles, D)
        if tile_embs is None:
            return []

        hits: List[FrameHit] = []
        for fp in fingerprints:
            if fp.clip_embedding is None:
                continue
            sims = tile_embs @ fp.clip_embedding  # cosine since both L2-normed
            max_sim = float(sims.max())
            if max_sim >= self.similarity_threshold:
                hits.append(
                    FrameHit(
                        client=fp.config.client,
                        frame_idx=frame_idx,
                        timestamp=timestamp,
                        channel="clip",
                        confidence=max_sim,
                        details={"best_tile": int(sims.argmax())},
                    )
                )
        return hits
