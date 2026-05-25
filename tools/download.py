#!/usr/bin/env python3
"""הורדת סרטון יוטיוב משורת הפקודה לתיקיית ההורדות.

שימוש:
    python tools/download.py <URL>
    python tools/download.py <URL> --quality 1080
    python tools/download.py <URL> --audio
"""
import argparse
import shutil
import sys
from pathlib import Path

import yt_dlp


def resolve_ffmpeg():
    if shutil.which("ffmpeg"):
        return None
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def build_format(quality: str, audio: bool) -> str:
    if audio:
        return "ba/b"
    if quality == "best":
        return "bv*+ba/b"
    return f"bv*[height<={quality}]+ba/b[height<={quality}]/b"


def main():
    ap = argparse.ArgumentParser(description="הורדת סרטון יוטיוב באיכות מקסימלית")
    ap.add_argument("url", help="קישור הסרטון")
    ap.add_argument(
        "--quality",
        default="best",
        help="best (ברירת מחדל) או גובה: 2160 / 1440 / 1080 / 720 / 480",
    )
    ap.add_argument("--audio", action="store_true", help="אודיו בלבד (MP3)")
    ap.add_argument(
        "--out",
        default=str(Path.home() / "Downloads"),
        help="תיקיית יעד (ברירת מחדל: ~/Downloads)",
    )
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    opts = {
        "format": build_format(args.quality, args.audio),
        "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "merge_output_format": "mp4",
    }
    ff = resolve_ffmpeg()
    if ff:
        opts["ffmpeg_location"] = ff
    if args.audio:
        opts.pop("merge_output_format", None)
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}
        ]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([args.url])
    except Exception as e:  # noqa: BLE001
        print(f"\n❌ ההורדה נכשלה: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n✅ נשמר בתיקייה: {out_dir}")


if __name__ == "__main__":
    main()
