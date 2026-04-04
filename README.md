# KRISPIN

Automatic detection of LED-board advertisements in football match footage.

Given a 1080p match MP4 and a small per-advertiser reference (just a brand
name + 1 image is enough), Krispin finds every second in which each
advertiser's ad appears on the LED boards, cuts a video clip per appearance,
and produces a per-client PDF report.

## Architecture at a glance

```
video.mp4 ─┬─► Channel 1: PaddleOCR (primary — brand text)
           ├─► Channel 2: HSV color prefilter
           ├─► Channel 3: CLIP tile embeddings
           ├─► Channel 4: ORB keypoint match
           │
           └─► System B: Gemini 2.5 Pro verifier on candidate windows
                        (optional, ~$0.50–2 per match)
                           │
                           ▼
                  Fused appearances →  JSON / CSV / MP4 clips / PDF
```

Detailed design and budget: see the approved plan document.

## One-time setup

```bash
pip install -e .
```

Optional environment variables:

```bash
export GEMINI_API_KEY=...    # enables System B (Gemini verifier)
```

## Typical workflow

1. **Calibrate a stadium (once per venue / camera angle)**

   ```bash
   krispin calibrate path/to/any_match_at_that_venue.mp4
   ```

   A Streamlit page opens. Draw a polygon around the LED strip, name the
   preset (e.g. `haifa_sammy_ofer`), and save. The preset is reused
   automatically for all future matches from that venue.

2. **Add a client (advertiser)**

   Create `clients/<client_name>/client.yaml`:

   ```yaml
   client: JAKO
   brand_text:
     - "JAKO"
     - "עכשיו בישראל"
   brand_colors:
     - "#FF6A13"
   # optional:
   # logo_image: logo.png
   # creative_frames:
   #   - ref_01.png
   # creative_video: ad.mp4
   ```

   Drop any reference assets next to the YAML. Only `brand_text` is
   required — the more you provide, the stronger the detection.

3. **Run detection**

   ```bash
   krispin run path/to/match.mp4
   ```

   Flags:
   - `--stadium haifa_sammy_ofer` force a specific preset (default: auto-detect)
   - `--fps 10` sampling rate (default: 10; lower = faster, less accurate)
   - `--no-clip` disable the CLIP channel
   - `--no-keypoint` disable the ORB channel
   - `--no-gemini` disable the Gemini verifier

   Output lands under `output/<match_stem>/`:
   ```
   output/<match_stem>/
   ├── report.json
   ├── report.csv
   └── <client_name>/
       ├── clip_001.mp4
       ├── clip_002.mp4
       ├── <client_name>_report.pdf
       └── thumbnails/
   ```

4. **(Optional) Review**

   ```bash
   krispin review <match_stem>
   ```

## Project layout

```
krispin/
├── krispin/
│   ├── cli.py              # Typer entrypoint
│   ├── pipeline.py         # End-to-end run_match()
│   ├── ingest.py           # FFmpeg/OpenCV frame sampling
│   ├── calibration.py      # Homography + stadium presets
│   ├── reference.py        # Per-client fingerprints
│   ├── fusion.py           # Temporal aggregation + fusion rules
│   ├── report.py           # JSON / CSV / clips / PDF
│   ├── detectors/
│   │   ├── ocr_local.py    # Channel 1
│   │   ├── color_filter.py # Channel 2
│   │   ├── visual_clip.py  # Channel 3
│   │   └── keypoint.py     # Channel 4
│   └── cloud/
│       └── gemini_verifier.py  # System B
├── ui/
│   ├── calibrate_app.py    # Streamlit ROI drawer
│   └── review_app.py       # Streamlit review UI
├── clients/<name>/client.yaml
├── stadiums/<name>.yaml
└── output/<match_id>/
```
