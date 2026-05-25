#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# בדיקת ffmpeg (נדרש למיזוג וידאו+אודיו)
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "⚠️  ffmpeg לא מותקן — נדרש למיזוג האיכויות הגבוהות."
  echo "    Ubuntu/Debian:  sudo apt install -y ffmpeg"
  echo "    macOS (brew):   brew install ffmpeg"
  echo "    Windows:        winget install Gyan.FFmpeg"
  echo ""
fi

# יצירת סביבה וירטואלית והתקנת תלויות
if [ ! -d ".venv" ]; then
  echo "📦 יוצר סביבה וירטואלית ומתקין תלויות…"
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip >/dev/null
  ./.venv/bin/pip install -r requirements.txt
fi

echo "🚀 מריץ את האפליקציה על http://127.0.0.1:8000"
exec ./.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
