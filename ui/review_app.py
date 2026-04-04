"""Streamlit UI for reviewing / approving detections on a processed match.

Run via: `krispin review <match_id>`

Shows every Appearance with its thumbnail, timestamps, confidence, and the
channels that contributed. You can approve or reject each one; decisions are
saved back into `reviewed.json` alongside the original report.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Krispin — Review", layout="wide")
st.title("Krispin — Detection review")

match_dir_env = os.environ.get("KRISPIN_REVIEW_MATCH_DIR")
match_dir = Path(st.text_input("Match output folder", value=match_dir_env or ""))

if not match_dir or not match_dir.exists():
    st.info("Point to a processed match output folder.")
    st.stop()

report_path = match_dir / "report.json"
if not report_path.exists():
    st.error(f"No report.json in {match_dir}")
    st.stop()

report = json.loads(report_path.read_text(encoding="utf-8"))

st.caption(f"Match: **{report['match_id']}**   Stadium: **{report['stadium']}**")
st.caption(f"Total appearances: **{len(report['appearances'])}**")

summary = report.get("per_client_summary", {})
if summary:
    st.subheader("Per-client summary")
    for client, info in summary.items():
        st.write(f"• **{client}** — {info['count']} appearances, {info['total_seconds']:.1f}s total")

st.divider()

reviewed_path = match_dir / "reviewed.json"
if reviewed_path.exists():
    decisions = json.loads(reviewed_path.read_text(encoding="utf-8"))
else:
    decisions = {}

for idx, app in enumerate(report["appearances"]):
    key = f"{app['client']}_{idx}"
    with st.container(border=True):
        cols = st.columns([2, 3])
        thumb = match_dir / app["client"] / "thumbnails" / f"thumb_{idx + 1:03d}.jpg"
        if thumb.exists():
            cols[0].image(str(thumb), use_container_width=True)

        cols[1].markdown(f"**{app['client']}** — appearance #{idx + 1}")
        cols[1].write(
            f"⏱ {app['start_ts']:.2f}s → {app['end_ts']:.2f}s   "
            f"({app['duration']:.2f}s)"
        )
        cols[1].write(f"confidence: {app['peak_confidence']:.2f}")
        cols[1].write(f"channels: {'/'.join(app['source_channels'])}")
        if app.get("gemini_verified"):
            cols[1].success("✔ Gemini verified")
        if app.get("gemini_explanation"):
            cols[1].caption(app["gemini_explanation"])

        current = decisions.get(key, "pending")
        choice = cols[1].radio(
            "Decision",
            ["pending", "approved", "rejected"],
            index=["pending", "approved", "rejected"].index(current),
            key=f"radio_{key}",
            horizontal=True,
        )
        decisions[key] = choice

if st.button("Save review decisions", type="primary"):
    reviewed_path.write_text(json.dumps(decisions, indent=2, ensure_ascii=False), encoding="utf-8")
    st.success(f"Saved to {reviewed_path}")
