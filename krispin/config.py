"""Configuration models for clients, stadiums, and run results.

All user-facing YAML files map to these Pydantic models. The goal is that the
PM (non-developer) only ever edits `clients/<name>/client.yaml` and the rest is
handled automatically.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Client (advertiser) schema
# ---------------------------------------------------------------------------

class KeyVisualRegion(BaseModel):
    """Optional sub-region of the reference image that carries the brand signal.

    Coordinates are normalised 0..1 relative to the reference image.
    """

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)


class ClientConfig(BaseModel):
    """A single advertiser the system should look for in a match video."""

    client: str                                   # Human name, e.g. "JAKO"
    brand_text: List[str]                         # Required: brand tokens (heb+eng)
    brand_colors: List[str] = Field(default_factory=list)   # Hex like "#FF6A13"
    logo_image: Optional[Path] = None             # PNG/JPG of the logo
    creative_frames: List[Path] = Field(default_factory=list)  # 1+ reference frames
    creative_video: Optional[Path] = None         # Ad as sent to media (optional)
    key_visual_region: Optional[KeyVisualRegion] = None

    @field_validator("brand_text")
    @classmethod
    def _at_least_one_token(cls, v: List[str]) -> List[str]:
        tokens = [t.strip() for t in v if t and t.strip()]
        if not tokens:
            raise ValueError("brand_text must contain at least one non-empty token")
        return tokens

    @classmethod
    def load(cls, path: Path) -> "ClientConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        cfg = cls.model_validate(data)
        # Resolve relative asset paths against the YAML's directory.
        base = Path(path).parent
        if cfg.logo_image is not None:
            cfg.logo_image = (base / cfg.logo_image).resolve()
        cfg.creative_frames = [(base / p).resolve() for p in cfg.creative_frames]
        if cfg.creative_video is not None:
            cfg.creative_video = (base / cfg.creative_video).resolve()
        return cfg


def load_all_clients(clients_dir: Path) -> List[ClientConfig]:
    """Load every `client.yaml` found under `clients_dir/*/`."""
    clients: List[ClientConfig] = []
    for yaml_path in sorted(Path(clients_dir).glob("*/client.yaml")):
        clients.append(ClientConfig.load(yaml_path))
    return clients


# ---------------------------------------------------------------------------
# Stadium (ROI calibration) schema
# ---------------------------------------------------------------------------

class StadiumConfig(BaseModel):
    """Calibration data for a specific stadium / camera angle.

    `polygon` is a list of (x, y) points (ints, pixel coords) enclosing the
    LED strip in a reference frame. `reference_frame_size` is the (w, h) of
    that reference frame so the polygon can be re-scaled if the source has a
    different resolution.

    `rectified_size` is the output size of the flattened strip (width, height).
    """

    name: str
    polygon: List[Tuple[int, int]]
    reference_frame_size: Tuple[int, int]
    rectified_size: Tuple[int, int] = (2400, 120)

    def save(self, path: Path) -> None:
        Path(path).write_text(
            yaml.safe_dump(self.model_dump(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "StadiumConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)


# ---------------------------------------------------------------------------
# Detection result schema
# ---------------------------------------------------------------------------

class FrameHit(BaseModel):
    """A single per-frame detection from one channel."""

    client: str
    frame_idx: int
    timestamp: float                 # Seconds into the match video
    channel: str                     # "ocr_local", "clip", "keypoint", "color", "gemini"
    confidence: float                # 0.0 – 1.0
    details: dict = Field(default_factory=dict)


class Appearance(BaseModel):
    """A contiguous window in which a client's ad was visible."""

    client: str
    start_ts: float
    end_ts: float
    duration: float
    peak_confidence: float
    source_channels: List[str]
    frame_count: int
    evidence_frames: List[int] = Field(default_factory=list)
    gemini_verified: bool = False
    gemini_explanation: Optional[str] = None


class MatchReport(BaseModel):
    """Top-level report for a processed match."""

    match_id: str
    video_path: str
    stadium: str
    duration_seconds: float
    fps_sampled: float
    appearances: List[Appearance]

    def per_client_summary(self) -> dict:
        out: dict = {}
        for app in self.appearances:
            bucket = out.setdefault(
                app.client,
                {"count": 0, "total_seconds": 0.0, "timestamps": []},
            )
            bucket["count"] += 1
            bucket["total_seconds"] += app.duration
            bucket["timestamps"].append(
                {"start": app.start_ts, "end": app.end_ts, "duration": app.duration}
            )
        return out
