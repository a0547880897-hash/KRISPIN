# Morning (Green Invoice) — Expense Drafts Playbook

מסמך זה מסביר **איך** לעבוד עם חשבון ה‑Morning (חשבונית ירוקה / Green Invoice) של המשתמש:
להזין ולתקן **מסמכי הוצאה לא‑מאושרים** (טיוטות). זהו ידע טכני גנרי בלבד —
**כללי העדכון הספציפיים (איזה ספק, איזה מע"מ, איזו קטגוריה) יינתנו בנפרד בכל משימה.**

---

## 0. כללי בטיחות — חובה לקרוא

1. **לעולם אל תאשר מסמך.** רק ממלאים/מעדכנים טיוטות. אישור יוצר רשומת הוצאה (קשה לביטול, משפיע על דיווח מע"מ). **המשתמש מאשר ידנית.**
2. בכל עדכון השאר `confirmFromEdit: false`.
3. גע **רק בטיוטות לא‑מאושרות** (`/expenses/drafts`), ו**רק במסמכים שהמשתמש כיוון אליהם**.
4. אל תיגע ב‑`/expenses` (הוצאות מוקלטות) אלא אם נאמר במפורש.
5. בסיום — ודא שמספר ההוצאות המוקלטות **לא השתנה** (= לא אושר כלום בטעות).
6. שים לב לכפילויות — אותה חשבונית עשויה להופיע גם בטיוטות וגם במוקלטות.

---

## 1. גישה ל‑API

- Base URL: `https://api.greeninvoice.co.il/api/v1`
- משתני סביבה מוגדרים בסביבה: `MORNING_API_KEY`, `MORNING_API_SECRET`
- אימות → טוקן Bearer:

```bash
B=https://api.greeninvoice.co.il/api/v1
TOKEN=$(curl -sS -m25 -X POST $B/account/token -H "Content-Type: application/json" \
  -d "{\"id\":\"$MORNING_API_KEY\",\"secret\":\"$MORNING_API_SECRET\"}" | jq -r '.token')
AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")
```

---

## 2. מושג קריטי: טיוטות לא‑מאושרות מול הוצאות מוקלטות

יש **שני אוספים נפרדים**:

| | `/expenses/drafts` | `/expenses` |
|---|---|---|
| מה זה | סריקות שנקלטו ו**עדיין לא אושרו** ("ממתין לאישור" / "לא מאושר") | הוצאות מוקלטות/גמורות |
| נעבוד על... | **כן — זה היעד** | לא, אלא אם נאמר מפורשות |

- מבנה טיוטה: `{ businessId, id, status, expense:{...}, url, thumbnail }` — ה‑expense **עטוף**.
- ⚠️ הפילטר `draft` ב‑`/expenses/search` הוא **no‑op** (מחזיר הכל) — אל תסתמך עליו.
- ספק בשם **"כללי"** = ה‑OCR של Morning לא זיהה ספק (לרוב גם `amount=null`). צריך **לקרוא את הקובץ הסרוק** ולמלא ידנית.

---

## 3. קריאה / חיפוש טיוטות

```bash
post(){ curl -sS -m25 "${AUTH[@]}" -X POST "$B$1" -d "$2"; }
# סך הכל + עימוד
TOTAL=$(post /expenses/drafts/search '{"pageSize":1}' | jq '.total')
PAGES=$(( (TOTAL+99)/100 ))
for pg in $(seq 1 $PAGES); do post /expenses/drafts/search "{\"pageSize\":100,\"page\":$pg}"; done \
  | jq -c '.items[]? | select(type=="object")' > /tmp/drafts.json
# טיוטה בודדת
curl -sS "${AUTH[@]}" "$B/expenses/drafts/<ID>" | jq .
```

---

## 4. עדכון טיוטה **בלי לאשר** — המנגנון המדויק

`PUT /expenses/drafts/{id}` עם הגוף **עטוף**: `{ "expense": { ... } }`.

כללים שנלמדו בדם (אל תחרוג מהם):
- ❌ גוף **לא‑עטוף** (שדות שטוחים) **מאפס** את הטיוטה לברירות מחדל. תמיד `{expense:{...}}`.
- ❗ `supplier` חייב להיות **אובייקט מלא** (מ‑`GET /suppliers/{id}`). שליחת `{id:...}` בלבד → הספק יוצא `null`.
- `accountingClassification` כ‑`{id, title}`.
- מחק תתי‑אובייקטים לקריאה‑בלבד לפני שליחה: `prediction`, `texts`, `userSession`.
- שמור תמיד `confirmFromEdit:false` ו‑`addRecipient:false` (כדי **לא** לאשר).
- שמר את `fileKey` / `fileHash` (הקובץ הסרוק המצורף).

תבנית עבודה (GET → שינוי → PUT):

```bash
# הבא אובייקט ספק מלא פעם אחת
curl -sS "${AUTH[@]}" "$B/suppliers/<SUPPLIER_ID>" > /tmp/sup.json

curl -sS "${AUTH[@]}" "$B/expenses/drafts/<ID>" > /tmp/d.json
jq --slurpfile sup /tmp/sup.json '
  {expense: (.expense
    | del(.prediction, .texts, .userSession)
    | .documentType = 305          # <- ערכים לדוגמה; הערכים האמיתיים מגיעים מהוראת המשימה
    | .paymentType  = 11
    | .currency = "ILS" | .currencyRate = 1
    | .amount = 0 | .vat = 0
    | .date = "2026-01-01" | .reportingDate = "2026-01-01"
    | .number = "..."
    | .supplier = $sup[0]
    | .accountingClassification = {id:"<CLASS_ID>", title:"<...>"}
    | .confirmFromEdit = false | .addRecipient = false)}' /tmp/d.json > /tmp/body.json

curl -sS -X PUT "${AUTH[@]}" "$B/expenses/drafts/<ID>" -d @/tmp/body.json \
  | jq '{dt:.expense.documentType, pt:.expense.paymentType, amt:.expense.amount, vat:.expense.vat, sup:.expense.supplier.name, status}'
```

---

## 5. קריאת הקבצים הסרוקים (לזיהוי "כללי")

לכל טיוטה יש `.url` (קישור הורדה) ו‑`.thumbnail`.

```bash
URL=$(curl -sS "${AUTH[@]}" "$B/expenses/drafts/<ID>" | jq -r '.url')
curl -sS -L -o /tmp/doc "$URL"; file /tmp/doc       # PDF או JPG
```

- **PDF דיגיטלי** → חלץ טקסט עם PyMuPDF:
  ```bash
  pip install --quiet PyMuPDF        # (pypdf שבור כאן — קריסת rust ב‑cryptography; אין pdftotext)
  python3 -c "import fitz; print('\n'.join(p.get_text() for p in fitz.open('/tmp/doc')))"
  ```
- **תמונה / סריקת‑צילום** (JPG, או PDF שחילוץ הטקסט שלו ריק) → קרא **ויזואלית** עם כלי הקריאה (Read) על הקובץ.
- **כפילויות**: אותה סריקה מועלית לעיתים כמה פעמים — קבץ לפי `md5sum` כדי לא לקרוא פעמיים, ועדכן את כל המזהים הכפולים באותם ערכים.
- **עברית RTL**: טקסט מ‑fitz עלול להתהפך/להסתדר אחרת; חפש שורות גולמיות (grep) במקום regex נוקשה.

---

## 6. ספקים וסיווגי הוצאה

```bash
# חיפוש ספק (מחזיר id + accountingClassificationId)
post /suppliers/search '{"name":"<שם>","pageSize":5}' | jq -c '.items[]|{id,name,acc:.accountingClassificationId}'
# אובייקט ספק מלא (נדרש לעדכון טיוטה)
curl -sS "${AUTH[@]}" "$B/suppliers/<ID>"
# יצירת ספק חדש
curl -sS -X POST "${AUTH[@]}" "$B/suppliers" -d '{"name":"<שם>","taxId":"<ח.פ>"}'
```

טיפ: כדי להתאים קטגוריה לספק קיים, אפשר לראות באיזו `accountingClassification` משתמשות הטיוטות הקיימות שלו (ב‑`/tmp/drafts.json`).

---

## 7. שדות ה‑expense עיקריים (לעיון)

| שדה | משמעות |
|---|---|
| `documentType` | סוג מסמך: 305=חשבונית מס, 320=חשבונית מס/קבלה, 330=זיכוי, 20=אחר |
| `paymentType` | אמצעי תשלום: 3=כרטיס אשראי, 11=אחר (ועוד) |
| `currency` / `currencyRate` | ל‑ILS השער=1; מט"ח דורש שער אמיתי |
| `amount` | ברוטו (כולל מע"מ). בטיוטות יש `amount`+`vat` (אין שדה net נפרד) |
| `vat` | סכום המע"מ |
| `date` / `reportingDate` | תאריך המסמך / תאריך הדיווח (פורמט `YYYY-MM-DD`) |
| `number` | מספר חשבונית |
| `supplier` / `accountingClassification` | אובייקטים (ראה §4) |
| `fileKey` / `fileHash` | הקובץ הסרוק — לשמר |

---

## 8. אימות בסיום

```bash
# 1) הטיוטות עודכנו ועדיין טיוטות (status, מופיעות ב‑drafts)
# 2) ספירת הוצאות מוקלטות לא השתנתה = לא אושר כלום בטעות
post /expenses/search '{"pageSize":1}' | jq '{recorded_total:.total}'
```

תמיד הצג למשתמש סיכום של מה עודכן, ומה דולג/דורש החלטה ידנית.
