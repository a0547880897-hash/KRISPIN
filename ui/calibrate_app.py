"""Streamlit UI for one-time LED-strip ROI calibration per stadium.

Run via: `krispin calibrate path/to/match.mp4`

Workflow:
  1. The first frame of the video is loaded.
  2. You draw a polygon around the LED strip (front boards, optionally also
     side boards).
  3. Save as a stadium preset — it becomes available automatically for all
     future matches from the same venue/angle.
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from PIL import Image

from krispin.calibration import save_stadium
from krispin.config import StadiumConfig
from krispin.ingest import read_first_frame

st.set_page_config(page_title="Krispin — Calibration", layout="wide")
st.title("Krispin — Stadium calibration")
st.caption("Draw a polygon around the LED strip in the reference frame, then save.")

video_env = os.environ.get("KRISPIN_CALIBRATION_VIDEO")
stadiums_dir = Path(os.environ.get("KRISPIN_STADIUMS_DIR", "stadiums"))

video_path = st.text_input("Match video path", value=video_env or "")
if not video_path:
    st.info("Point to a match MP4 to begin.")
    st.stop()

video_path = Path(video_path)
if not video_path.exists():
    st.error(f"File not found: {video_path}")
    st.stop()

frame = read_first_frame(video_path)
h, w = frame.shape[:2]
rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
pil = Image.fromarray(rgb)

st.write(f"Frame size: {w} × {h}")

try:
    from streamlit_drawable_canvas import st_canvas
except ImportError:
    st.error(
        "streamlit-drawable-canvas is not installed. Install with "
        "`pip install streamlit-drawable-canvas`."
    )
    st.stop()

max_canvas_w = 1400
scale = min(1.0, max_canvas_w / w)
canvas_w = int(w * scale)
canvas_h = int(h * scale)

st.markdown("**Instructions:** click to add polygon points around the LED strip. "
            "Close the polygon by clicking near the first point.")

canvas_result = st_canvas(
    fill_color="rgba(255, 106, 19, 0.3)",
    stroke_color="#FF6A13",
    stroke_width=3,
    background_image=pil,
    update_streamlit=True,
    height=canvas_h,
    width=canvas_w,
    drawing_mode="polygon",
    key="roi_canvas",
)

stadium_name = st.text_input("Stadium preset name (e.g. haifa_sammy_ofer)")

col1, col2 = st.columns(2)
rectified_w = col1.number_input("Rectified width (px)", min_value=400, max_value=6000, value=2400)
rectified_h = col2.number_input("Rectified height (px)", min_value=40, max_value=600, value=120)

if st.button("Save preset", type="primary"):
    if not stadium_name.strip():
        st.error("Please enter a stadium name.")
        st.stop()
    if canvas_result.json_data is None or not canvas_result.json_data.get("objects"):
        st.error("Draw a polygon first.")
        st.stop()

    polygon_points = []
    for obj in canvas_result.json_data["objects"]:
        if obj.get("type") == "path":
            for seg in obj.get("path", []):
                if len(seg) >= 3:
                    px = seg[-2] / scale
                    py = seg[-1] / scale
                    polygon_points.append((int(px), int(py)))

    if len(polygon_points) < 4:
        st.error("Polygon needs at least 4 points.")
        st.stop()

    stadium = StadiumConfig(
        name=stadium_name.strip(),
        polygon=polygon_points,
        reference_frame_size=(w, h),
        rectified_size=(int(rectified_w), int(rectified_h)),
    )
    path = save_stadium(stadium, stadiums_dir)
    st.success(f"Saved: {path}")
    st.json(stadium.model_dump())
