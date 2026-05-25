# הורדת סרטוני יוטיוב

אפליקציית ווב פשוטה: מדביקים לינק של סרטון יוטיוב → מורידים אותו למחשב באיכות המקסימלית.

## הדרך הכי פשוטה (ללא ידע טכני)

צריך רק **Python** מותקן (פעם אחת). אם אין — מורידים מ-https://www.python.org/downloads/
(בחלונות חשוב לסמן בהתקנה "Add Python to PATH").

אחר כך:

- **Windows:** לחיצה כפולה על `start.bat`
- **macOS:** לחיצה כפולה על `start.command`
- **Linux:** מריצים `./run.sh`

זהו. בפעם הראשונה זה מתקין הכל לבד (כולל ffmpeg, אוטומטית), ואז הדפדפן נפתח על
`http://127.0.0.1:8000`. בכל פעם הבאה זה פשוט נפתח מיד.

> אין צורך להתקין ffmpeg ידנית — הוא מגיע אוטומטית עם ההתקנה.

## קיצור דרך עם אייקון על שולחן העבודה (לחיצה אחת)

כדי לפתוח את האפליקציה בלחיצה אחת עם אייקון, מריצים פעם אחת את המתקין:

- **Windows:** קליק ימני על `tools/install_shortcut_windows.ps1` → "Run with PowerShell"
- **macOS:** `bash tools/install_shortcut_macos.sh` (יוצר `YouTube Downloader.app` על שולחן העבודה)
- **Linux:** `./tools/install_shortcut_linux.sh`

מעכשיו פשוט לוחצים על האייקון "YouTube Downloader".

## ל-Claude Code: סקיל + הורדה משורת הפקודה

הפרויקט כולל **סקיל מובנה ל-Claude Code** בתיקייה
`.claude/skills/youtube-downloader/` — כך שאפשר פשוט לבקש מ-Claude Code
"תוריד לי את הסרטון הזה <לינק>" והוא יטפל בהכל. כדי להתקין אותו גלובלית,
מעתיקים את התיקייה ל-`~/.claude/skills/`.

הורדה ישירה משורת הפקודה (נשמר ל-`~/Downloads`):

```bash
python tools/download.py "<URL>"                 # MP4 באיכות מקסימלית
python tools/download.py "<URL>" --quality 1080  # רזולוציה ספציפית
python tools/download.py "<URL>" --audio         # MP3 בלבד
```

## שימוש

1. מדביקים לינק של סרטון יוטיוב ולוחצים **בדוק**.
2. בוחרים איכות (ברירת מחדל: **מקסימלית**) או **אודיו בלבד (MP3)**.
3. לוחצים **הורד** — פס התקדמות מציג מהירות וזמן שנותר, והקובץ יורד אוטומטית.

## איך זה עובד

מבוסס על **yt-dlp** (מוריד) + **ffmpeg** (ממזג), עם backend ב-FastAPI ו-frontend בעברית.
יוטיוב מגיש באיכויות הגבוהות (1080p/4K) את הווידאו והאודיו כשני זרמים נפרדים;
האפליקציה מורידה את שניהם (`bv*+ba/b`) וממזגת ל-MP4 יחיד.

## מבנה

```
app.py                       # שרת FastAPI שעוטף את yt-dlp
static/index.html            # הממשק (עברית, RTL)
tools/download.py            # הורדה משורת הפקודה
tools/install_shortcut_*     # יצירת קיצור דרך עם אייקון לכל מערכת
assets/icon.*                # אייקון האפליקציה
.claude/skills/...           # סקיל מובנה ל-Claude Code
requirements.txt             # תלויות Python (כולל ffmpeg דרך imageio-ffmpeg)
start.bat / start.command    # הפעלה בלחיצה כפולה — Windows / macOS
run.sh                       # הפעלה — Linux
```

## הערה משפטית

הורד רק תוכן שמותר לך להוריד (תוכן שלך, רישיון Creative Commons, או בהרשאת הבעלים).
השימוש באחריותך בלבד.
