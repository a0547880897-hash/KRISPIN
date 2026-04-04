"""System B — Gemini 2.5 Pro verifier on candidate windows.

Rather than paying per-minute for a whole-match video API, we let System A
(the self-hosted detectors) propose a short list of candidate windows —
small 3–10 s clips where at least one channel fires — and send *only those*
to Gemini for verification. Gemini returns yes/no + a tight timestamp.

This gives us a strong second opinion at ~$0.02–0.05 per call, so a typical
match with ~30–50 candidate windows costs about $0.50–2 in total.

Requires `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in the environment. If not
set, the verifier degrades gracefully to a no-op and System A still runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from krispin.config import ClientConfig


@dataclass
class GeminiVerdict:
    confirmed: bool
    start_ts: Optional[float]
    end_ts: Optional[float]
    confidence: float
    explanation: str


def _cut_clip(video_path: Path, start_s: float, end_s: float, out_path: Path) -> bool:
    """Use ffmpeg to cut a short clip from the source video."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{max(0.0, start_s):.3f}",
        "-i", str(video_path),
        "-t", f"{max(0.1, end_s - start_s):.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-an",
        str(out_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path.exists() and out_path.stat().st_size > 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _build_prompt(client: ClientConfig, abs_start: float, abs_end: float) -> str:
    tokens = " / ".join(client.brand_text)
    return (
        "You are verifying advertisements that appear on the LED perimeter boards "
        "of a football pitch. Look ONLY at the LED boards around the pitch, not "
        "at player shirts or the scoreboard overlay.\n\n"
        f"Advertiser name: {client.client}\n"
        f"Brand text to look for (any language): {tokens}\n\n"
        "Task: Did this short clip contain the advertiser's LED ad at any point? "
        "If yes, report the start and end timestamps within the clip (in seconds, "
        "float) when the ad is clearly visible. Be strict — only confirm if the "
        "brand text or logo is actually legible on the LED strip.\n\n"
        "Respond ONLY with compact JSON in this exact shape:\n"
        '{"confirmed": true|false, "start_s": <float or null>, "end_s": <float or null>, '
        '"confidence": <0.0-1.0>, "explanation": "<one short sentence>"}'
    )


class GeminiVerifier:
    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.model_name = model_name
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return
        try:
            from google import genai
            self._client = genai.Client(api_key=api_key)
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def verify_window(
        self,
        video_path: Path,
        client: ClientConfig,
        window: Tuple[float, float],
    ) -> Optional[GeminiVerdict]:
        """Send a single candidate window to Gemini.

        Returns None if the verifier is unavailable or the call fails.
        """
        if not self._available:
            return None

        start_s, end_s = window
        with tempfile.TemporaryDirectory() as tmp:
            clip_path = Path(tmp) / "clip.mp4"
            if not _cut_clip(video_path, start_s, end_s, clip_path):
                return None
            try:
                uploaded = self._client.files.upload(file=str(clip_path))
                prompt = _build_prompt(client, start_s, end_s)
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=[uploaded, prompt],
                )
                text = (response.text or "").strip()
            except Exception as exc:
                return GeminiVerdict(
                    confirmed=False,
                    start_ts=None,
                    end_ts=None,
                    confidence=0.0,
                    explanation=f"gemini error: {exc}",
                )

            # Strip markdown fences if present.
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:]
                text = text.strip()

            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return GeminiVerdict(
                    confirmed=False,
                    start_ts=None,
                    end_ts=None,
                    confidence=0.0,
                    explanation=f"invalid JSON: {text[:120]}",
                )

            confirmed = bool(data.get("confirmed", False))
            s = data.get("start_s")
            e = data.get("end_s")
            return GeminiVerdict(
                confirmed=confirmed,
                start_ts=(start_s + float(s)) if s is not None else None,
                end_ts=(start_s + float(e)) if e is not None else None,
                confidence=float(data.get("confidence", 0.0)),
                explanation=str(data.get("explanation", ""))[:500],
            )

    def verify_batch(
        self,
        video_path: Path,
        candidates: List[Tuple[ClientConfig, Tuple[float, float]]],
    ) -> List[Optional[GeminiVerdict]]:
        return [self.verify_window(video_path, c, w) for c, w in candidates]
