"""Build per-client reference fingerprints from `client.yaml` assets.

Each client may provide any combination of:
  - brand_text tokens (required)
  - brand_colors
  - a logo PNG/JPG
  - 1..N creative frames
  - the full creative video

We turn whatever is provided into detector-specific fingerprints:
  - `text_tokens`     : list of lowercase tokens for OCR fuzzy match
  - `hsv_centroids`   : list of HSV triples for the color prefilter
  - `clip_embedding`  : averaged CLIP embedding of all reference images
  - `orb_features`    : (keypoints, descriptors) from the logo image

Modules that need only a subset of fingerprints consume just those fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from krispin.config import ClientConfig


@dataclass
class ClientFingerprint:
    config: ClientConfig
    text_tokens: List[str] = field(default_factory=list)
    hsv_centroids: List[Tuple[float, float, float]] = field(default_factory=list)
    reference_images: List[np.ndarray] = field(default_factory=list)  # BGR
    clip_embedding: Optional[np.ndarray] = None    # shape (D,), L2-normalized
    orb_descriptors: Optional[np.ndarray] = None   # shape (N, 32)
    orb_keypoints: Optional[list] = None           # list[cv2.KeyPoint]


def _hex_to_hsv(hex_color: str) -> Tuple[float, float, float]:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    bgr = np.uint8([[[b, g, r]]])
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0, 0]
    return float(hsv[0]), float(hsv[1]), float(hsv[2])


def _load_image(path: Path) -> Optional[np.ndarray]:
    if path is None or not Path(path).exists():
        return None
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    return img


def _extract_video_keyframes(video_path: Path, max_frames: int = 8) -> List[np.ndarray]:
    """Pull up to `max_frames` evenly-spaced frames from a short reference ad."""
    if not Path(video_path).exists():
        return []
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            return []
        stride = max(1, total // max_frames)
        frames: List[np.ndarray] = []
        for i in range(0, total, stride):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, frame = cap.read()
            if ok:
                frames.append(frame)
            if len(frames) >= max_frames:
                break
        return frames
    finally:
        cap.release()


def build_fingerprint(
    cfg: ClientConfig,
    clip_model=None,
    clip_preprocess=None,
    device: str = "cpu",
) -> ClientFingerprint:
    """Compute all reference signals for one client.

    `clip_model` and `clip_preprocess` are optional — if not passed, the
    CLIP embedding field is left None and the CLIP channel is skipped for
    this client. Same for ORB: if no logo image is given, ORB is skipped.
    """
    fp = ClientFingerprint(config=cfg)

    # --- text tokens (normalised lowercase for fuzzy matching) ---
    fp.text_tokens = [t.strip().lower() for t in cfg.brand_text if t.strip()]

    # --- HSV centroids from hex colors ---
    fp.hsv_centroids = [_hex_to_hsv(c) for c in cfg.brand_colors]

    # --- gather all reference images (frames + logo + video keyframes) ---
    images: List[np.ndarray] = []
    for frame_path in cfg.creative_frames:
        img = _load_image(frame_path)
        if img is not None:
            images.append(img)
    logo = _load_image(cfg.logo_image) if cfg.logo_image else None
    if logo is not None:
        images.append(logo)
    if cfg.creative_video is not None:
        images.extend(_extract_video_keyframes(cfg.creative_video))
    fp.reference_images = images

    # --- CLIP embedding (average across all reference images) ---
    if clip_model is not None and clip_preprocess is not None and images:
        import torch
        from PIL import Image

        tensors = []
        for img in images:
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            tensors.append(clip_preprocess(pil))
        batch = torch.stack(tensors).to(device)
        with torch.no_grad():
            feats = clip_model.encode_image(batch)
            feats = feats / feats.norm(dim=-1, keepdim=True)
            mean = feats.mean(dim=0)
            mean = mean / mean.norm()
        fp.clip_embedding = mean.cpu().numpy().astype(np.float32)

    # --- ORB features for logo / highest-res reference image ---
    if logo is not None or images:
        src = logo if logo is not None else images[0]
        gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        orb = cv2.ORB_create(nfeatures=500)
        kps, desc = orb.detectAndCompute(gray, None)
        if desc is not None and len(kps) > 0:
            fp.orb_keypoints = kps
            fp.orb_descriptors = desc

    return fp


def build_all_fingerprints(
    clients: List[ClientConfig],
    use_clip: bool = True,
) -> Tuple[List[ClientFingerprint], dict]:
    """Build fingerprints for every client. Loads CLIP once if requested.

    Returns `(fingerprints, ctx)` where `ctx` contains the loaded CLIP model
    so other detectors can reuse it without a second load.
    """
    ctx: dict = {}
    clip_model = None
    clip_preprocess = None
    device = "cpu"

    if use_clip:
        try:
            import torch
            import open_clip

            device = "cuda" if torch.cuda.is_available() else (
                "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu"
            )
            clip_model, _, clip_preprocess = open_clip.create_model_and_transforms(
                "ViT-L-14", pretrained="openai"
            )
            clip_model = clip_model.to(device).eval()
            ctx["clip_model"] = clip_model
            ctx["clip_preprocess"] = clip_preprocess
            ctx["clip_device"] = device
        except Exception as exc:
            # CLIP unavailable — continue without it. OCR channel alone is
            # already strong for text-heavy ads.
            ctx["clip_error"] = str(exc)

    fingerprints = [
        build_fingerprint(c, clip_model=clip_model, clip_preprocess=clip_preprocess, device=device)
        for c in clients
    ]
    return fingerprints, ctx
