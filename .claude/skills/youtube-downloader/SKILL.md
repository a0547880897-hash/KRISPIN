---
name: youtube-downloader
description: Download a YouTube (or other site) video/audio to the user's computer at maximum quality. Use whenever the user shares a YouTube link and wants to download/save it, asks to "download this video", "save this as MP3", "get the audio", or wants to open the YouTube downloader app/UI.
---

# YouTube Downloader

A local app + CLI that downloads YouTube videos at maximum quality (merges the
best video+audio into MP4, or extracts MP3). Built on `yt-dlp` + `ffmpeg`
(ffmpeg ships automatically via the `imageio-ffmpeg` Python package — no manual
install needed).

## Step 1 — Find the project directory

Read the absolute project path from `project_path.txt` located next to this
SKILL.md file. If that file is missing, search common locations
(`~/krispin`, `~/Desktop/krispin`, `~/Downloads/krispin`, `~/KRISPIN`) for a
folder containing `app.py` and `tools/download.py`. Call it `PROJECT_DIR`.

If it cannot be found, the project is not installed yet — clone it:
`git clone https://github.com/a0547880897-hash/krispin` and checkout branch
`claude/keen-dirac-Oal54`, then continue.

## Step 2 — Ensure dependencies (first run only)

If `PROJECT_DIR/.venv` does not exist, create it and install:

```bash
cd "PROJECT_DIR"
python3 -m venv .venv            # on Windows: python -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

(Windows venv python is `.venv\Scripts\python`.)

## Step 3 — Do what the user asked

**Download a specific link (preferred — fast, no UI):**

```bash
cd "PROJECT_DIR"
./.venv/bin/python tools/download.py "<URL>"                 # max-quality MP4
./.venv/bin/python tools/download.py "<URL>" --quality 1080  # specific height
./.venv/bin/python tools/download.py "<URL>" --audio         # MP3 audio only
```

The file is saved to the user's `~/Downloads` folder by default (override with
`--out "<folder>"`). Report the saved path back to the user.

**Open the graphical app (when the user wants the web UI):**

- macOS: `open "PROJECT_DIR/start.command"`
- Windows: start `PROJECT_DIR\start.bat`
- Linux: `"PROJECT_DIR/run.sh"`

This launches a local server and opens `http://127.0.0.1:8000` in the browser.

## Notes

- Quality values: `best` (default), `2160`, `1440`, `1080`, `720`, `480`.
- If a download fails with a YouTube extraction error, update the downloader:
  `./.venv/bin/pip install -U yt-dlp` and retry.
- Only download content the user is allowed to download.
