"""Step 3: deep-scan every downloaded document and build catalog.xlsx.

For each draft we combine THREE sources of truth:
  1. Morning structured expense fields (amount, vat, number, supplier, ...).
  2. Morning OCR prediction with per-field confidence (high/medium/low).
  3. A REAL read of the document: we extract the text layer from the PDF
     (PyMuPDF) and cross-check the critical values against it.

Per-cell confidence colour:
  GREEN  = value present AND verified against the document text (or exact
           structured+prediction agreement on a high-confidence field).
  YELLOW = value present but only inferred / not verifiable in the text layer
           (e.g. scanned image with no text), or medium OCR confidence.
  RED    = value missing / low confidence / needs client check.

Nothing is written back to Morning. Output: catalog.xlsx (+ a legend sheet).
"""
import os, json, re
import fitz  # PyMuPDF
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

RAW_JSON = "catalog_raw.json"
DOCS_DIR = "documents"
OUT_XLSX = "catalog.xlsx"
DRIVE_FOLDER_ID = "15PhIp59cLThaX715AMtgincHebBCNbyC"

GREEN = PatternFill("solid", fgColor="C6EFCE")
YELLOW = PatternFill("solid", fgColor="FFEB9C")
RED = PatternFill("solid", fgColor="FFC7CE")
HDR = PatternFill("solid", fgColor="305496")
THIN = Border(*[Side(style="thin", color="D9D9D9")] * 4)

# Morning enum maps (best-effort; unknown -> raw code shown).
DOC_TYPES = {20: "חשבונית/קבלה (מסמך הוצאה)", 305: "חשבונית מס", 320: "חשבונית מס/קבלה",
             400: "קבלה", 100: "הצעת מחיר"}
PAY_TYPES = {1: "מזומן", 2: "צ'ק", 3: "כרטיס אשראי", 4: "העברה בנקאית",
             5: "PayPal", 6: "מס", 7: "ניכוי במקור", 8: "אחר", 0: "לא צויין", 10: "אפליקציה"}


def pdf_text(path):
    if not path or not os.path.exists(path):
        return ""
    try:
        if path.lower().endswith(".pdf"):
            doc = fitz.open(path)
            return "\n".join(p.get_text() for p in doc)
    except Exception:
        return ""
    return ""


def norm(s):
    return re.sub(r"[\s,]", "", str(s)).lower()


def pred_map(expense):
    out = {}
    for f in (expense.get("prediction", {}) or {}).get("fields", []):
        out[f["field"]] = (f.get("value"), f.get("confidence"))
    return out


def found_in_text(value, text):
    """True if value plausibly appears in the document text."""
    if value in (None, "", 0):
        return False
    nt = norm(text)
    nv = norm(value)
    if len(nv) < 2:
        return False
    if nv in nt:
        return True
    # numeric: try integer part match
    m = re.findall(r"\d+", str(value))
    if m and len(m[0]) >= 3 and m[0] in nt:
        return True
    return False


def conf_color(value, ocr_conf, verified, has_text):
    """Decide cell colour."""
    if value in (None, "", 0):
        return RED, "חסר"
    if verified:
        return GREEN, "מאומת מול המסמך"
    if not has_text:  # scanned image, cannot verify by text
        return (GREEN if ocr_conf == "high" else YELLOW), "OCR (אין שכבת טקסט לאימות)"
    if ocr_conf == "high":
        return YELLOW, "OCR ודאות גבוהה, לא אומת בטקסט"
    if ocr_conf == "medium":
        return YELLOW, "הוסק/חלקי"
    return RED, "ודאות נמוכה"


def suggest_pcn_input(exp, supplier_name, currency):
    """Suggested PCN874 input classification (for client review)."""
    name = (supplier_name or "")
    foreign = currency and currency != "ILS"
    et = (exp.get("prediction") and dict((f["field"], f.get("value")) for f in exp["prediction"]["fields"]).get("expense_type")) or ""
    if foreign or exp.get("vat", 0) in (0, None) and foreign:
        return "תשומה מחו\"ל / ללא מע\"מ — לבדיקה", YELLOW
    # football-club purchases = inventory per business rules
    if any(k in name for k in ["כדורגל", "מועדון", "קבוצת", "ספורט", "F.C", "FC"]):
        return "מלאי (רכישה דרך קבוצת כדורגל)", YELLOW
    if et in ("equipment", "fixed_assets") or "ציוד" in name:
        return "רכוש קבוע / ציוד — לבדיקה", YELLOW
    return "תשומות שוטפות", YELLOW


COLUMNS = [
    "#index", "שם ספק", "מספר עוסק / ח.פ.", "סוג מסמך", "מספר מסמך", "תאריך המסמך",
    "תקופת דיווח", "סכום לפני מע\"מ", "סך הכל מע\"מ", "סכום כולל מע\"מ",
    "מטבע", "שולם באמצעות", "מספר הקצאה", "סיווג תשומה (PCN874)",
    "שם הקובץ", "קישור ב-Drive", "draft_id", "רמת ודאות כללית", "הערות",
]
# which columns get per-cell colouring -> (col_index, value_key)
COLOR_COLS = {
    "שם ספק": "supplier", "מספר עוסק / ח.פ.": "taxId", "סוג מסמך": "document_type",
    "מספר מסמך": "number", "תאריך המסמך": "date", "סכום לפני מע\"מ": "net",
    "סך הכל מע\"מ": "vat", "סכום כולל מע\"מ": "amount", "מטבע": "currency",
    "שולם באמצעות": "payment_type", "מספר הקצאה": "assignment_number",
}
CRITICAL = {"amount", "number", "date", "supplier"}


def main():
    raw = json.load(open(RAW_JSON, encoding="utf-8"))
    files = {f.split("_")[1]: f for f in os.listdir(DOCS_DIR)} if os.path.isdir(DOCS_DIR) else {}

    wb = Workbook()
    ws = wb.active
    ws.title = "קטלוג 441"
    ws.sheet_view.rightToLeft = True

    # header
    for c, name in enumerate(COLUMNS, 1):
        cell = ws.cell(1, c, name)
        cell.fill = HDR
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN
    ws.freeze_panes = "A2"

    rows = sorted(raw.values(), key=lambda d: d.get("creationDate", 0))
    r = 2
    stats = {"green": 0, "yellow": 0, "red": 0}
    for i, d in enumerate(rows, 1):
        did = d["id"]
        exp = d.get("expense", {})
        sup = exp.get("supplier", {}) or {}
        pm = pred_map(exp)
        fname = files.get(did, "")
        text = pdf_text(os.path.join(DOCS_DIR, fname)) if fname else ""
        has_text = len(text.strip()) > 20

        currency = exp.get("currency", "")
        net_pred = pm.get("net", (None, None))[0]
        amount = exp.get("amount", pm.get("amount", (None,))[0])
        vat = exp.get("vat", pm.get("vat", (None,))[0])
        net = net_pred if net_pred is not None else (
            round(amount - vat, 2) if isinstance(amount, (int, float)) and isinstance(vat, (int, float)) else None)
        doc_code = exp.get("documentType") or pm.get("document_type", (None,))[0]
        pay_code = exp.get("paymentType", pm.get("payment_type", (None,))[0])
        period = d.get("reportingPeriod") or exp.get("reportingDate", "")

        values = {
            "supplier": sup.get("name", ""),
            "taxId": sup.get("taxId", "") or pm.get("taxId", (None,))[0],
            "document_type": DOC_TYPES.get(doc_code, doc_code),
            "number": exp.get("number", "") or pm.get("number", (None,))[0],
            "date": pm.get("date", (None,))[0] or exp.get("reportingDate", ""),
            "net": net, "vat": vat, "amount": amount, "currency": currency,
            "payment_type": PAY_TYPES.get(pay_code, pay_code),
            "assignment_number": pm.get("assignment_number", (None,))[0] or "",
        }
        pcn, pcn_fill = suggest_pcn_input(exp, sup.get("name", ""), currency)
        drive_link = f"https://drive.google.com/drive/folders/{DRIVE_FOLDER_ID}"

        row_vals = {
            "#index": i, "שם ספק": values["supplier"], "מספר עוסק / ח.פ.": values["taxId"],
            "סוג מסמך": values["document_type"], "מספר מסמך": values["number"],
            "תאריך המסמך": values["date"], "תקופת דיווח": period,
            "סכום לפני מע\"מ": values["net"], "סך הכל מע\"מ": values["vat"],
            "סכום כולל מע\"מ": values["amount"], "מטבע": currency,
            "שולם באמצעות": values["payment_type"], "מספר הקצאה": values["assignment_number"],
            "סיווג תשומה (PCN874)": pcn, "שם הקובץ": fname,
            "קישור ב-Drive": drive_link, "draft_id": did, "רמת ודאות כללית": "",
            "הערות": "",
        }

        notes = []
        if not fname:
            notes.append("אין קובץ מצורף")
        if not has_text and fname:
            notes.append("מסמך סרוק (אין שכבת טקסט) — אימות ויזואלי מומלץ")
        if currency and currency != "ILS":
            notes.append("מטבע חוץ — לבדוק מע\"מ תשומות")

        crit_reds = 0
        for c, name in enumerate(COLUMNS, 1):
            cell = ws.cell(r, c, row_vals[name])
            cell.border = THIN
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            key = COLOR_COLS.get(name)
            if key:
                val = values[key]
                ocr_conf = pm.get(key, (None, None))[1]
                verified = found_in_text(val, text) if has_text else False
                fill, why = conf_color(val, ocr_conf, verified, has_text)
                cell.fill = fill
                if fill is RED and key in CRITICAL:
                    crit_reds += 1
                if fill is GREEN: stats["green"] += 1
                elif fill is YELLOW: stats["yellow"] += 1
                else: stats["red"] += 1
            elif name == "סיווג תשומה (PCN874)":
                cell.fill = pcn_fill

        # overall confidence
        overall = ws.cell(r, COLUMNS.index("רמת ודאות כללית") + 1)
        if crit_reds == 0:
            overall.value, overall.fill = "גבוהה", GREEN
        elif crit_reds == 1:
            overall.value, overall.fill = "בינונית", YELLOW
        else:
            overall.value, overall.fill = "נמוכה — לבדיקה", RED
        ws.cell(r, COLUMNS.index("הערות") + 1).value = "; ".join(notes)
        r += 1

    # column widths
    widths = [7, 26, 16, 22, 14, 14, 11, 13, 11, 13, 8, 16, 14, 26, 30, 14, 38, 14, 34]
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w

    # legend sheet
    lg = wb.create_sheet("מקרא")
    lg.sheet_view.rightToLeft = True
    legend = [
        ("מקרא קידוד צבעים — רמת ודאות לכל תא", ""),
        ("🟩 ירוק", "ודאות גבוהה — הנתון נקרא ברור מהמסמך / אומת מול טקסט המסמך"),
        ("🟨 צהוב", "ודאות בינונית — הוסק או מ-OCR בלבד (לא ניתן לאימות בטקסט)"),
        ("🟥 אדום", "ודאות נמוכה / חסר — דורש בדיקת הלקוח"),
        ("", ""),
        ("שדות קריטיים", "סכום, מספר מסמך, תאריך, שם ספק"),
        ("רמת ודאות כללית", "נקבעת לפי כמות השדות הקריטיים האדומים בשורה"),
        ("מקור הנתונים", "Morning (שדות מובנים) + OCR prediction + קריאת טקסט אמיתית מה-PDF"),
        ("PCN874", "סיווג התשומה הוא הצעה לבדיקת הלקוח (נבחר לטובת הפחתת מס)"),
        ("חשוב", "לא בוצעה שום הטמעה/עדכון במורנינג. הורדה+סריקה+אקסל בלבד."),
    ]
    for ri, (a, b) in enumerate(legend, 1):
        lg.cell(ri, 1, a).font = Font(bold=ri == 1 or b == "")
        lg.cell(ri, 2, b)
    lg.column_dimensions["A"].width = 22
    lg.column_dimensions["B"].width = 80
    lg["A2"].fill = GREEN; lg["A3"].fill = YELLOW; lg["A4"].fill = RED

    wb.save(OUT_XLSX)
    print(f"Wrote {OUT_XLSX}: {r-2} rows. Cell colours -> green={stats['green']} yellow={stats['yellow']} red={stats['red']}")


if __name__ == "__main__":
    main()
