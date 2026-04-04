"""Reporting — turn a `MatchReport` into deliverables:
  - JSON  (machine-readable, for programmatic use)
  - CSV   (human-readable, one row per Appearance)
  - Clips (FFmpeg-cut MP4s, one per Appearance, with padding)
  - PDF   (one report per client with thumbnails and timestamps)

All artefacts land under `output/<match_id>/`.
"""

from __future__ import annotations

import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import cv2

from krispin.config import Appearance, MatchReport


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# JSON / CSV
# ---------------------------------------------------------------------------

def write_json(report: MatchReport, out_dir: Path) -> Path:
    out_dir = _ensure_dir(out_dir)
    path = out_dir / "report.json"
    payload = {
        "match_id": report.match_id,
        "video_path": report.video_path,
        "stadium": report.stadium,
        "duration_seconds": report.duration_seconds,
        "fps_sampled": report.fps_sampled,
        "per_client_summary": report.per_client_summary(),
        "appearances": [a.model_dump() for a in report.appearances],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_csv(report: MatchReport, out_dir: Path) -> Path:
    out_dir = _ensure_dir(out_dir)
    path = out_dir / "report.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "client", "appearance_idx", "start_ts", "end_ts", "duration_s",
            "peak_confidence", "source_channels", "gemini_verified",
        ])
        per_client_counter: Dict[str, int] = defaultdict(int)
        for app in report.appearances:
            per_client_counter[app.client] += 1
            writer.writerow([
                app.client,
                per_client_counter[app.client],
                f"{app.start_ts:.3f}",
                f"{app.end_ts:.3f}",
                f"{app.duration:.3f}",
                f"{app.peak_confidence:.3f}",
                "|".join(app.source_channels),
                app.gemini_verified,
            ])
    return path


# ---------------------------------------------------------------------------
# Clip cutting
# ---------------------------------------------------------------------------

def cut_clips(
    report: MatchReport,
    out_dir: Path,
    pad_before: float = 2.0,
    pad_after: float = 2.0,
) -> Dict[str, List[Path]]:
    """Cut one MP4 per Appearance, grouped into per-client subfolders."""
    video_path = Path(report.video_path)
    by_client: Dict[str, List[Path]] = defaultdict(list)
    per_client_counter: Dict[str, int] = defaultdict(int)

    for app in report.appearances:
        per_client_counter[app.client] += 1
        idx = per_client_counter[app.client]
        client_dir = _ensure_dir(out_dir / app.client)
        clip_path = client_dir / f"clip_{idx:03d}.mp4"

        start = max(0.0, app.start_ts - pad_before)
        duration = (app.end_ts - app.start_ts) + pad_before + pad_after
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}",
            "-i", str(video_path),
            "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            str(clip_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            by_client[app.client].append(clip_path)
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    return by_client


# ---------------------------------------------------------------------------
# Thumbnails
# ---------------------------------------------------------------------------

def extract_thumbnails(
    report: MatchReport,
    out_dir: Path,
) -> Dict[str, List[Path]]:
    """Save one JPEG thumbnail per Appearance (frame at the midpoint)."""
    video_path = Path(report.video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {}
    try:
        by_client: Dict[str, List[Path]] = defaultdict(list)
        per_client_counter: Dict[str, int] = defaultdict(int)
        for app in report.appearances:
            per_client_counter[app.client] += 1
            idx = per_client_counter[app.client]
            mid_s = (app.start_ts + app.end_ts) / 2.0
            cap.set(cv2.CAP_PROP_POS_MSEC, mid_s * 1000.0)
            ok, frame = cap.read()
            if not ok:
                continue
            thumb_dir = _ensure_dir(out_dir / app.client / "thumbnails")
            thumb_path = thumb_dir / f"thumb_{idx:03d}.jpg"
            cv2.imwrite(str(thumb_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            by_client[app.client].append(thumb_path)
        return by_client
    finally:
        cap.release()


# ---------------------------------------------------------------------------
# Per-client PDF
# ---------------------------------------------------------------------------

def _fmt_ts(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    return f"{int(m):02d}:{s:05.2f}"


def write_client_pdfs(
    report: MatchReport,
    out_dir: Path,
    thumbnails: Dict[str, List[Path]],
) -> Dict[str, Path]:
    """Create a PDF summary per client using ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas
    except ImportError:
        return {}

    by_client: Dict[str, List[Appearance]] = defaultdict(list)
    for app in report.appearances:
        by_client[app.client].append(app)

    out_paths: Dict[str, Path] = {}
    for client, apps in by_client.items():
        pdf_dir = _ensure_dir(out_dir / client)
        pdf_path = pdf_dir / f"{client}_report.pdf"
        c = canvas.Canvas(str(pdf_path), pagesize=A4)
        w, h = A4

        c.setFont("Helvetica-Bold", 18)
        c.drawString(2 * cm, h - 2 * cm, f"Krispin Report — {client}")
        c.setFont("Helvetica", 10)
        c.drawString(2 * cm, h - 2.7 * cm, f"Match: {report.match_id}")
        c.drawString(2 * cm, h - 3.2 * cm, f"Stadium: {report.stadium}")
        total_s = sum(a.duration for a in apps)
        c.drawString(2 * cm, h - 3.7 * cm,
                     f"Appearances: {len(apps)}   Total on-screen: {total_s:.1f}s")

        y = h - 5 * cm
        thumbs = thumbnails.get(client, [])
        for idx, app in enumerate(apps):
            if y < 4 * cm:
                c.showPage()
                y = h - 2 * cm
                c.setFont("Helvetica-Bold", 12)
                c.drawString(2 * cm, y, f"{client} (cont.)")
                y -= 0.8 * cm

            c.setFont("Helvetica-Bold", 11)
            c.drawString(2 * cm, y, f"#{idx + 1}  {_fmt_ts(app.start_ts)} → {_fmt_ts(app.end_ts)}")
            c.setFont("Helvetica", 9)
            c.drawString(2 * cm, y - 0.4 * cm,
                         f"duration: {app.duration:.2f}s   confidence: {app.peak_confidence:.2f}"
                         f"   channels: {'/'.join(app.source_channels)}")

            if idx < len(thumbs):
                try:
                    c.drawImage(str(thumbs[idx]), 11 * cm, y - 2.2 * cm,
                                width=8 * cm, height=2.5 * cm, preserveAspectRatio=True)
                except Exception:
                    pass
            y -= 3 * cm

        c.save()
        out_paths[client] = pdf_path

    return out_paths


# ---------------------------------------------------------------------------
# One-shot orchestration
# ---------------------------------------------------------------------------

def write_full_report(report: MatchReport, out_root: Path) -> dict:
    """Produce every artefact under `out_root/<match_id>/` and return their paths."""
    out_dir = _ensure_dir(Path(out_root) / report.match_id)
    json_path = write_json(report, out_dir)
    csv_path = write_csv(report, out_dir)
    clips = cut_clips(report, out_dir)
    thumbnails = extract_thumbnails(report, out_dir)
    pdfs = write_client_pdfs(report, out_dir, thumbnails)
    return {
        "json": json_path,
        "csv": csv_path,
        "clips": clips,
        "thumbnails": thumbnails,
        "pdfs": pdfs,
        "out_dir": out_dir,
    }
