#!/bin/bash
# יוצר קיצור דרך "YouTube Downloader" על שולחן העבודה ובתפריט (Linux)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

make_desktop() {
  cat <<DESKTOP
[Desktop Entry]
Type=Application
Name=YouTube Downloader
Comment=הורדת סרטוני יוטיוב באיכות מקסימלית
Exec=$ROOT/run.sh
Icon=$ROOT/assets/icon.png
Terminal=true
Categories=AudioVideo;Utility;
DESKTOP
}

APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
make_desktop > "$APPS_DIR/youtube-downloader.desktop"
chmod +x "$APPS_DIR/youtube-downloader.desktop"

DESK="$HOME/Desktop"
[ -d "$DESK" ] || DESK="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESK" ]; then
  make_desktop > "$DESK/youtube-downloader.desktop"
  chmod +x "$DESK/youtube-downloader.desktop"
  gio set "$DESK/youtube-downloader.desktop" metadata::trusted true 2>/dev/null || true
fi

echo "✅ נוצר קיצור דרך: YouTube Downloader (שולחן העבודה + תפריט היישומים)"
