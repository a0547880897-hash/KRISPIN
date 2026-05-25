#!/bin/bash
# macOS — לחיצה כפולה על הקובץ הזה כדי להפעיל
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ צריך להתקין Python קודם — הורד מ: https://www.python.org/downloads/"
  echo "אחרי ההתקנה, לחץ שוב פעמיים על הקובץ הזה."
  read -n 1 -s -r -p "לחץ על מקש כלשהו לסגירה…"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "📦 מתקין (פעם אחת בלבד, ייקח דקה)…"
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip >/dev/null
  ./.venv/bin/pip install -r requirements.txt
fi

echo "🚀 מריץ… הדפדפן ייפתח אוטומטית על http://127.0.0.1:8000"
echo "(להשאיר את החלון הזה פתוח כל עוד אתה מוריד. לעצירה: Ctrl+C)"
./.venv/bin/python app.py
