#!/usr/bin/env bash
# Linux — הרצה בפקודה אחת
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ צריך Python 3. התקן עם: sudo apt install -y python3 python3-venv"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "📦 מתקין (פעם אחת בלבד)…"
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip >/dev/null
  ./.venv/bin/pip install -r requirements.txt
fi

echo "🚀 מריץ… הדפדפן ייפתח אוטומטית על http://127.0.0.1:8000"
exec ./.venv/bin/python app.py
