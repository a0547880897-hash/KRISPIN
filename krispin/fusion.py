"""Fusion + temporal aggregation.

Takes the per-frame hits from every channel and collapses them into a
clean list of `Appearance` objects (one per contiguous window in which a
client's ad was visible). Also decides which candidate windows to send to
the Gemini verifier.

Rules (tuned conservatively — can be relaxed after calibration):
  - A frame is considered a "hit" for client X if:
      (a) the OCR channel fires above threshold, OR
      (b) any two non-OCR channels fire above threshold on the same frame, OR
      (c) a single strong channel fires (confidence >= 0.92)
  - Consecutive hit frames with gaps <= `max_gap_s` are merged into one
    Appearance.
  - Appearances shorter than `min_duration_s` are dropped (likely noise).
  - Appearances with only a single channel in (a) passing and no Gemini
    verification can be flagged for review.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from krispin.config import Appearance, ClientConfig, FrameHit


@dataclass
class FusionConfig:
    max_gap_s: float = 0.6
    min_duration_s: float = 0.4
    strong_confidence: float = 0.92
    pad_for_gemini_s: float = 1.5   # expand each candidate window before verifying


def _merge_by_client(hits: List[FrameHit]) -> Dict[str, List[FrameHit]]:
    by_client: Dict[str, List[FrameHit]] = defaultdict(list)
    for h in hits:
        by_client[h.client].append(h)
    for k in by_client:
        by_client[k].sort(key=lambda x: x.timestamp)
    return by_client


def _frame_passes_fusion(frame_hits: List[FrameHit], strong_conf: float) -> bool:
    """Does this single frame (all channels for one client) qualify as a hit?"""
    if not frame_hits:
        return False
    channels = {h.channel for h in frame_hits}
    # Rule (a): OCR alone is enough (local or gemini, though gemini runs later).
    if "ocr_local" in channels:
        return True
    # Rule (c): any single very strong channel.
    if any(h.confidence >= strong_conf for h in frame_hits):
        return True
    # Rule (b): two or more distinct non-OCR channels.
    non_ocr = channels - {"ocr_local"}
    return len(non_ocr) >= 2


def _group_consecutive(
    hits_by_frame: Dict[int, List[FrameHit]],
    frame_to_ts: Dict[int, float],
    cfg: FusionConfig,
) -> List[Appearance]:
    """Turn a set of per-frame hits (already filtered to "passed fusion") into
    one or more Appearance windows.
    """
    if not hits_by_frame:
        return []

    sorted_frames = sorted(hits_by_frame.keys())
    appearances: List[Appearance] = []

    cur: List[int] = []
    for f in sorted_frames:
        if not cur:
            cur = [f]
            continue
        gap = frame_to_ts[f] - frame_to_ts[cur[-1]]
        if gap <= cfg.max_gap_s:
            cur.append(f)
        else:
            appearances.append(_window_from_frames(cur, hits_by_frame, frame_to_ts, cfg))
            cur = [f]
    if cur:
        appearances.append(_window_from_frames(cur, hits_by_frame, frame_to_ts, cfg))

    return [a for a in appearances if a.duration >= cfg.min_duration_s]


def _window_from_frames(
    frames: List[int],
    hits_by_frame: Dict[int, List[FrameHit]],
    frame_to_ts: Dict[int, float],
    cfg: FusionConfig,
) -> Appearance:
    start = frame_to_ts[frames[0]]
    end = frame_to_ts[frames[-1]]
    all_hits = [h for f in frames for h in hits_by_frame[f]]
    peak = max(h.confidence for h in all_hits)
    channels = sorted({h.channel for h in all_hits})
    client = all_hits[0].client
    return Appearance(
        client=client,
        start_ts=start,
        end_ts=end,
        duration=max(end - start, 1e-3),
        peak_confidence=peak,
        source_channels=channels,
        frame_count=len(frames),
        evidence_frames=frames[:10],
    )


def fuse_hits(
    all_hits: List[FrameHit],
    frame_to_ts: Dict[int, float],
    cfg: FusionConfig = FusionConfig(),
) -> List[Appearance]:
    """Main entry point. Takes every FrameHit from every channel and returns
    the merged list of Appearances, sorted by start time."""
    by_client = _merge_by_client(all_hits)
    results: List[Appearance] = []

    for client, client_hits in by_client.items():
        # Group hits from all channels by frame_idx first.
        per_frame: Dict[int, List[FrameHit]] = defaultdict(list)
        for h in client_hits:
            per_frame[h.frame_idx].append(h)
        # Filter to the frames that actually pass fusion.
        passing = {
            f: hs for f, hs in per_frame.items()
            if _frame_passes_fusion(hs, cfg.strong_confidence)
        }
        results.extend(_group_consecutive(passing, frame_to_ts, cfg))

    results.sort(key=lambda a: (a.start_ts, a.client))
    return results


def build_gemini_candidates(
    appearances: List[Appearance],
    clients: List[ClientConfig],
    cfg: FusionConfig = FusionConfig(),
    only_low_confidence: bool = False,
    low_conf_threshold: float = 0.88,
) -> List[Tuple[ClientConfig, Tuple[float, float]]]:
    """Build the list of (client, (start, end)) windows to send to Gemini.

    If `only_low_confidence` is True we only verify borderline appearances,
    which keeps the Gemini cost minimal. Set it to False during the first
    few production runs to get cross-validation on everything.
    """
    name_to_client = {c.client: c for c in clients}
    out: List[Tuple[ClientConfig, Tuple[float, float]]] = []
    for app in appearances:
        if only_low_confidence and app.peak_confidence >= low_conf_threshold:
            continue
        client = name_to_client.get(app.client)
        if client is None:
            continue
        start = max(0.0, app.start_ts - cfg.pad_for_gemini_s)
        end = app.end_ts + cfg.pad_for_gemini_s
        out.append((client, (start, end)))
    return out
