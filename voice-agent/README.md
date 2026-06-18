# סוכן מכירות קולי — בנק יהב

שרת Node.js שמחבר שיחות טלפון נכנסות מ‑Twilio אל OpenAI Realtime API, מנהל שיחת
מכירה טבעית בעברית בשם בנק יהב, ובסוף השיחה שולח סיכום **במייל** מחשבון Gmail.

## ⚠️ אבטחה — לקרוא לפני הכל

המפתחות שהופיעו בקובץ המידע (Twilio Auth Token, OpenAI API Key, סיסמת שרת)
**נחשפו בצ'אט ולכן יש לבטל אותם ולהנפיק חדשים לפני שימוש.** אף מפתח אמיתי לא נשמר
בקוד או ב‑`.env` שבריפו — יש למלא אותם ידנית ב‑`.env` המקומי (שנמצא ב‑`.gitignore`
ולעולם לא עולה ל‑git).

## ארכיטקטורה

```
מחייג → מספר Twilio → Twilio Media Stream (WebSocket) → server.js
      → OpenAI Realtime API (WebSocket, speech-to-speech) → חזרה ל‑Twilio → המחייג
בסיום: server.js בונה סיכום (GPT) → שולח מייל מ‑Gmail
```

| קובץ | תפקיד |
|------|--------|
| `server.js` | Express + WebSocket server, מגיש TwiML |
| `twilioHandler.js` | מטפל בחיבור ה‑Media Stream של Twilio, מגשר ל‑OpenAI |
| `openaiRealtime.js` | חיבור והגדרת ה‑session מול OpenAI Realtime |
| `conversation.js` | תרבות השיחה: barge-in, VAD, פתיחה חד‑פעמית, איסוף תמליל |
| `persona.js` | פרסונת סוכן המכירות (instructions) |
| `knowledgeBase.js` | מאגר המידע הרשמי של בנק יהב (המקור היחיד לציטוט) |
| `summary.js` | בניית סיכום מהתמליל |
| `gmail.js` | שליחת המייל |

## התקנה והרצה

```bash
cd voice-agent
npm install
cp .env.example .env     # מלא את הערכים האמיתיים
npm run check            # בדיקת תקינות תחביר
npm start
```

## חשיפה פומבית (חובה)

Twilio Media Streams דורש כתובת `wss://` פומבית ומאובטחת (לא localhost).
בפיתוח השתמש ב‑ngrok וכוון את `PUBLIC_HOSTNAME` ל‑host שהתקבל:

```bash
ngrok http 3340
# PUBLIC_HOSTNAME=abcd-1-2-3-4.ngrok-free.app
```

הגדר ב‑Twilio את ה‑Voice webhook של המספר ל‑`POST https://<host>/voice/webhook`.

## חיבור Gmail

שליחת מייל מ‑Gmail דורשת הרשאה. הדרך הפשוטה: **App Password** (דורש 2FA בחשבון):
https://myaccount.google.com/apppasswords — והזן ל‑`GMAIL_APP_PASSWORD`.
אם לא מוגדר — הסיכום יודפס ללוג במקום להישלח (השיחה לא תיפול).

## נקודות לאימות בזמן פריסה (spec §12)

1. **שם המודל** של Realtime מתעדכן — `OPENAI_REALTIME_MODEL` (beta: `gpt-4o-realtime-preview`, GA: `gpt-realtime`).
2. **שמות אירועי ה‑WebSocket** של OpenAI Realtime — ודא מול התיעוד הנוכחי.
3. **פורמט האודיו** של Twilio — base64 mu‑law (`g711_ulaw`) בשני הכיוונים.
4. **מבנה הודעות Twilio** — `start` / `media` / `stop` והשדה `streamSid`.

## כוונון תרבות השיחה (spec §7)

הערכים נמצאים ב‑`openaiRealtime.js` (`turn_detection`):
- נשימות קוטעות → העלה `threshold` ל‑0.7.
- הסוכן קוטע אותך → העלה `silence_duration_ms` ל‑900.
- מילים ראשונות נחתכות → העלה `prefix_padding_ms` ל‑400.
