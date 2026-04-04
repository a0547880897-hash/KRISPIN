"""End-to-end pipeline wiring the ingest → detect → fuse → verify → report stages.

This module is deliberately procedural so it can be read top-to-bottom by
someone tracing what the system does. The Typer CLI calls into `run_match`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from tqdm import tqdm

from krispin.calibration import (
    auto_detect_stadium,
    compute_homography,
    load_stadium,
    rectify_strip,
)
from krispin.cloud.gemini_verifier import GeminiVerifier
from krispin.config import (
    Appearance,
    ClientConfig,
    FrameHit,
    MatchReport,
    StadiumConfig,
)
from krispin.detectors.color_filter import color_pass_per_client
from krispin.detectors.keypoint import KeypointDetector
from krispin.detectors.ocr_local import OcrLocal
from krispin.detectors.visual_clip import ClipDetector
from krispin.fusion import FusionConfig, build_gemini_candidates, fuse_hits
from krispin.ingest import get_video_info, iter_frames, read_first_frame
from krispin.reference import build_all_fingerprints
from krispin.config import load_all_clients


@dataclass
class RunConfig:
    video_path: Path
    clients_dir: Path
    stadiums_dir: Path
    stadium_name: Optional[str] = None
    target_fps: float = 10.0
    use_clip: bool = True
    use_keypoint: bool = True
    use_gemini: bool = True
    color_min_fraction: float = 0.005  # loose — just a prefilter


def run_match(cfg: RunConfig) -> MatchReport:
    # 1. Load clients and build fingerprints (loads CLIP once).
    clients: List[ClientConfig] = load_all_clients(cfg.clients_dir)
    if not clients:
        raise RuntimeError(f"No clients found under {cfg.clients_dir}")
    fingerprints, ctx = build_all_fingerprints(clients, use_clip=cfg.use_clip)

    # 2. Resolve stadium preset.
    if cfg.stadium_name:
        stadium = load_stadium(cfg.stadiums_dir, cfg.stadium_name)
    else:
        first = read_first_frame(cfg.video_path)
        stadium = auto_detect_stadium(first, cfg.stadiums_dir)
        if stadium is None:
            raise RuntimeError(
                f"No stadium preset found in {cfg.stadiums_dir}. "
                "Run `krispin calibrate` first (or pass --stadium)."
            )

    info = get_video_info(cfg.video_path)
    frame_size = (info["width"], info["height"])
    H = compute_homography(stadium, frame_size)

    # 3. Instantiate detectors.
    ocr = OcrLocal()
    clip_det = ClipDetector(
        model=ctx.get("clip_model"),
        preprocess=ctx.get("clip_preprocess"),
        device=ctx.get("clip_device", "cpu"),
    ) if cfg.use_clip else None
    kp_det = KeypointDetector() if cfg.use_keypoint else None

    # 4. Stream frames through the detectors.
    all_hits: List[FrameHit] = []
    frame_to_ts: dict = {}
    total_expected = int((info["duration_s"] or 0) * cfg.target_fps)
    pbar = tqdm(
        iter_frames(cfg.video_path, target_fps=cfg.target_fps),
        total=total_expected or None,
        desc="Scanning frames",
        unit="frame",
    )
    for sample in pbar:
        strip = rectify_strip(sample.image, H, stadium.rectified_size)
        frame_to_ts[sample.idx] = sample.timestamp

        # Cheap color prefilter — skip expensive detectors on clients whose
        # colors are not present at all in the current strip.
        color_scores = color_pass_per_client(strip, fingerprints, min_fraction=cfg.color_min_fraction)
        active_fps = [fp for fp in fingerprints if color_scores.get(fp.config.client, 1.0) >= cfg.color_min_fraction]
        if not active_fps:
            continue

        all_hits.extend(ocr.detect(strip, active_fps, sample.idx, sample.timestamp))
        if clip_det is not None:
            all_hits.extend(clip_det.detect(strip, active_fps, sample.idx, sample.timestamp))
        if kp_det is not None:
            all_hits.extend(kp_det.detect(strip, active_fps, sample.idx, sample.timestamp))

    # 5. Fuse per-frame hits into Appearances.
    fusion_cfg = FusionConfig()
    appearances: List[Appearance] = fuse_hits(all_hits, frame_to_ts, fusion_cfg)

    # 6. Optional Gemini verification of candidate windows.
    if cfg.use_gemini:
        verifier = GeminiVerifier()
        if verifier.available:
            candidates = build_gemini_candidates(appearances, clients, fusion_cfg)
            verdicts = verifier.verify_batch(cfg.video_path, candidates)
            for app, verdict in zip(appearances, verdicts):
                if verdict is None:
                    continue
                app.gemini_verified = verdict.confirmed
                app.gemini_explanation = verdict.explanation
                if verdict.confirmed:
                    app.source_channels = sorted(set(app.source_channels) | {"gemini"})
                    app.peak_confidence = max(app.peak_confidence, verdict.confidence)
            # Drop appearances that Gemini explicitly refuted AND have only
            # one supporting local channel.
            appearances = [
                a for a in appearances
                if not (a.gemini_explanation and not a.gemini_verified and len(a.source_channels) <= 1)
            ]

    return MatchReport(
        match_id=Path(cfg.video_path).stem,
        video_path=str(cfg.video_path),
        stadium=stadium.name,
        duration_seconds=info["duration_s"],
        fps_sampled=cfg.target_fps,
        appearances=appearances,
    )
