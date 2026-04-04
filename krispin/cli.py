"""Krispin command-line interface.

Commands:
  krispin run <video.mp4>       Run detection on a match and write the report.
  krispin calibrate <video.mp4> Launch the Streamlit ROI calibration UI.
  krispin review <match_id>     Launch the Streamlit review UI.
  krispin list-stadiums         Print saved stadium presets.
  krispin list-clients          Print clients found under ./clients/.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from krispin.calibration import list_stadiums
from krispin.config import load_all_clients
from krispin.pipeline import RunConfig, run_match
from krispin.report import write_full_report

app = typer.Typer(add_completion=False, no_args_is_help=True)

REPO_ROOT = Path.cwd()
DEFAULT_CLIENTS_DIR = REPO_ROOT / "clients"
DEFAULT_STADIUMS_DIR = REPO_ROOT / "stadiums"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"


@app.command()
def run(
    video: Path = typer.Argument(..., exists=True, help="Path to the match MP4 file."),
    stadium: Optional[str] = typer.Option(None, help="Stadium preset name. Auto-detected if omitted."),
    fps: float = typer.Option(10.0, help="Frames per second to sample."),
    clients_dir: Path = typer.Option(DEFAULT_CLIENTS_DIR, help="Directory containing per-client YAML files."),
    stadiums_dir: Path = typer.Option(DEFAULT_STADIUMS_DIR, help="Directory containing stadium presets."),
    output_dir: Path = typer.Option(DEFAULT_OUTPUT_DIR, help="Where to write reports, clips, PDFs."),
    no_clip: bool = typer.Option(False, help="Disable the CLIP visual channel."),
    no_keypoint: bool = typer.Option(False, help="Disable the ORB keypoint channel."),
    no_gemini: bool = typer.Option(False, help="Disable the Gemini verifier (System B)."),
) -> None:
    """Run the full detection pipeline on a match video."""
    cfg = RunConfig(
        video_path=video,
        clients_dir=clients_dir,
        stadiums_dir=stadiums_dir,
        stadium_name=stadium,
        target_fps=fps,
        use_clip=not no_clip,
        use_keypoint=not no_keypoint,
        use_gemini=not no_gemini,
    )
    typer.secho(f"Running Krispin on {video}", fg=typer.colors.CYAN, bold=True)
    report = run_match(cfg)
    artefacts = write_full_report(report, output_dir)

    typer.secho("\nDone.", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  Appearances found : {len(report.appearances)}")
    typer.echo(f"  Report folder     : {artefacts['out_dir']}")
    summary = report.per_client_summary()
    for client, info in summary.items():
        typer.echo(f"  - {client:<20} {info['count']} appearances   {info['total_seconds']:.1f}s total")


@app.command("list-stadiums")
def list_stadiums_cmd(
    stadiums_dir: Path = typer.Option(DEFAULT_STADIUMS_DIR),
) -> None:
    presets = list_stadiums(stadiums_dir)
    if not presets:
        typer.secho(f"No stadium presets under {stadiums_dir}", fg=typer.colors.YELLOW)
        return
    for p in presets:
        typer.echo(f"  {p.name:<30} ref={p.reference_frame_size}  rect={p.rectified_size}")


@app.command("list-clients")
def list_clients_cmd(
    clients_dir: Path = typer.Option(DEFAULT_CLIENTS_DIR),
) -> None:
    clients = load_all_clients(clients_dir)
    if not clients:
        typer.secho(f"No client.yaml files under {clients_dir}", fg=typer.colors.YELLOW)
        return
    for c in clients:
        typer.echo(f"  {c.client:<20} tokens={c.brand_text}")


@app.command()
def calibrate(
    video: Optional[Path] = typer.Argument(None, exists=True, help="Frame source for calibration."),
) -> None:
    """Launch the Streamlit calibration UI.

    You will draw a polygon around the LED strip once per stadium; the preset
    is saved under `stadiums/<name>.yaml` and reused automatically afterwards.
    """
    ui_path = REPO_ROOT / "ui" / "calibrate_app.py"
    env = os.environ.copy()
    if video is not None:
        env["KRISPIN_CALIBRATION_VIDEO"] = str(video.resolve())
    env["KRISPIN_STADIUMS_DIR"] = str(DEFAULT_STADIUMS_DIR.resolve())
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(ui_path)], env=env)


@app.command()
def review(
    match_id: str = typer.Argument(..., help="Match ID (the MP4 stem)."),
    output_dir: Path = typer.Option(DEFAULT_OUTPUT_DIR),
) -> None:
    """Launch the Streamlit review UI for an already-processed match."""
    ui_path = REPO_ROOT / "ui" / "review_app.py"
    env = os.environ.copy()
    env["KRISPIN_REVIEW_MATCH_DIR"] = str((output_dir / match_id).resolve())
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(ui_path)], env=env)


if __name__ == "__main__":
    app()
