#!/bin/bash
# יוצר אפליקציה ניתנת ללחיצה "YouTube Downloader.app" על שולחן העבודה (macOS)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Desktop/YouTube Downloader.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>YouTube Downloader</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundleIdentifier</key><string>local.youtube.downloader</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0</string>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/launcher" <<LAUNCH
#!/bin/bash
open "$ROOT/start.command"
LAUNCH
chmod +x "$APP/Contents/MacOS/launcher"

# המרת ה-PNG ל-icns בעזרת כלים מובנים של macOS
TMP="$(mktemp -d)/icon.iconset"
mkdir -p "$TMP"
for sz in 16 32 64 128 256 512; do
  sips -z $sz $sz "$ROOT/assets/icon.png" --out "$TMP/icon_${sz}x${sz}.png" >/dev/null
  d=$((sz*2))
  sips -z $d $d "$ROOT/assets/icon.png" --out "$TMP/icon_${sz}x${sz}@2x.png" >/dev/null
done
iconutil -c icns "$TMP" -o "$APP/Contents/Resources/icon.icns"

echo "✅ נוצרה אפליקציה על שולחן העבודה: YouTube Downloader"
