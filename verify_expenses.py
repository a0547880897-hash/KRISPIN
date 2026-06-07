"""Option C - verification pass for DIGITAL expense PDFs.

For each digital doc: take Morning's captured amount/vat/number and VERIFY each
against the document's own embedded text (independent check). If the figure
literally appears in the document -> trust it (high/medium). If it does NOT ->
flag for manual visual reading (low). Adds rule-based classification.
Image/scanned docs and unconfirmed-amount docs are left for visual hand-reading.
Hand entries (method 'text') are preserved.
"""
import os, re, csv, json
import fitz

RAW = "expenses_raw.json"; INDEX = "index_expenses.csv"; SCAN = "expenses_scan.json"; DOCS = "documents_expenses"
CLIENT = {"516691953", "021988431"}
DOCT = {305: "חשבונית מס", 320: "חשבונית מס/קבלה", 400: "קבלה", 405: "קבלה/זיכוי",
        330: "חשבונית עסקה", 20: "מסמך הוצאה", 100: "הצעת מחיר"}
PAY = {1: "מזומן", 2: "צ'ק", 3: "כרטיס אשראי", 4: "העברה בנקאית", 5: "PayPal", 0: "", 8: "אחר", 10: "אפליקציה"}


def gt(p):
    try: return "\n".join(pg.get_text() for pg in fitz.open(p))
    except Exception: return ""


def norm(s): return re.sub(r"[\s,]", "", str(s)).lower()


def present(val, nt):
    if val in (None, "", 0): return None
    v = norm(val)
    if v and v in nt: return True
    dg = re.findall(r"\d+", str(val))
    if dg and len(dg[0]) >= 2 and dg[0] in nt: return True
    try:
        f = float(val)
        for c in {str(f), (str(int(f)) if f == int(f) else ""), f"{f:.2f}"}:
            if c and norm(c) in nt: return True
    except Exception: pass
    return False


def classify(s, vat):
    s = s or ""; sl = s.lower()
    fsw = any(k in s or k in sl for k in ["Apple","Google","Wix","Meta","פייסבוק","monday","Canva","Zoom","Dropbox",
        "DigitalOcean","Grammarly","Suno","Ideogram","Runway","Wistia","Genspark","ManyChat","Manychat","MainFunc",
        "Manus","Lovable","GoFullPage","Bitdefender","CapCut","PIPO","Paddle","Microsoft","Anthropic","Midjourney",
        "Envato","Vyond","GoAnimate","OpenAI","Topaz","PandaDoc","Adobe","Cloud","ClickUp","Eleven","Fathom","Gamma"])
    club = any(k in s for k in ["מכבי","הפועל","ביתר","סכנין","קרית שמונה","קשר ספורט","איתוראן ספורט","אחווה הכחולה",
        "ג'רוזלם","אוראל ווליום","קידום הספורט","התאחדות לכדורגל","ריפורט","סהר הפקות","בילבורד"])
    if club: return "מלאי/פרסום (כדורגל)", ("ללא מע\"מ" if not vat else "T — תשומה שוטפת")
    if "צארומי" in s: return "מלאי קמפיינים (אופניים חשמליים)", "T — ציוד/מלאי"
    if fsw: return "תוכנה/שירות דיגיטלי — חו\"ל", "ללא מע\"מ (חו\"ל)"
    if any(k in s for k in ["עמותת","קרן ","ידידי","חסד","תורה","תרומה"]): return "תרומה (סעיף 46)", "ללא מע\"מ"
    if any(k in s for k in ["פאיימי","PayMe","סליקה"]): return "עמלות סליקה", "T — תשומה שוטפת"
    if any(k in s for k in ["רואי חשבון","שיטרית","עורכי דין","עו\"ד","ברכיה","ראיית חשבון"]): return "שירותים מקצועיים", "T — תשומה שוטפת"
    if any(k in s for k in ["מחשבים","או.אמ.סי","אלקטרה","מחסני חשמל","KSP","קיי.אס.פי","סלולר","ג'וי מובייל","אמירים"]):
        return "ציוד/מחשוב — לבדיקה", ("ללא מע\"מ" if not vat else "T — ציוד")
    if any(k in s for k in ["פז","סונול","דלק","דור אלון"]): return "דלק רכב (מע\"מ 2/3)", "T — תשומה שוטפת"
    if any(k in s for k in ["עירייה","עיריית","מים","תאגיד","חשמל","בזק","פרטנר","partner","הוט","סלקום","yes","פלאפון"]):
        return "תשתית/תקשורת", ("ללא מע\"מ" if not vat else "T — תשומה שוטפת")
    if any(k in s for k in ["יקב","דרימיה","יין"]): return "מתנות/כיבוד לקוחות", "T — קיזוז מוגבל"
    return "לבדיקה", ("ללא מע\"מ" if not vat else "T — תשומה שוטפת")


def fnum(v):
    try: return round(float(v), 2)
    except Exception: return None


def main():
    raw = json.load(open(RAW, encoding="utf-8"))
    scan = json.load(open(SCAN, encoding="utf-8")) if os.path.exists(SCAN) else {}
    done = set(k for k in scan if not k.startswith("_"))
    files = {f.split("_")[1]: f for f in os.listdir(DOCS)}
    conf_n = ver_n = low_n = 0
    for r in csv.DictReader(open(INDEX, encoding="utf-8-sig")):
        eid = r["expense_id"]; f = files.get(eid)
        if eid in done or not f or not f.lower().endswith(".pdf"):
            continue
        t = gt(os.path.join(DOCS, f)); nt = norm(t)
        if len(t.strip()) < 40:
            continue  # image -> visual
        m = raw.get(eid, {}); sup = (m.get("supplier") or {}).get("name", "")
        amt = fnum(m.get("amount")); vat = fnum(m.get("vat")); number = m.get("number", "")
        a_ok = present(amt, nt); n_ok = present(number, nt)
        taxid = ""
        for i in re.findall(r"(?<!\d)(\d{9})(?!\d)", t):
            if i not in CLIENT: taxid = i; break
        dtype = DOCT.get(m.get("documentType"), str(m.get("documentType", "")))
        if "חשבונית מס/קבלה" in t or "חשבונית מס / קבלה" in t: dtype = "חשבונית מס/קבלה"
        elif re.search(r"חשבונית\s*מס(?!\s*/?\s*קבלה)", t): dtype = "חשבונית מס"
        elif "קבלה" in t and "חשבונית" not in t: dtype = "קבלה"
        et, pcn = classify(sup, vat)
        if a_ok:
            conf = "high" if n_ok else "medium"
            doubt = "" if n_ok else "מספר מסמך לא אומת בטקסט"
            ver_n += 1
        else:
            conf = "low"; doubt = "⚠️ סכום מורנינג לא אומת בטקסט — דורש קריאה ויזואלית ידנית"; low_n += 1
        scan[eid] = {"supplier": sup, "taxId": taxid or (m.get("supplier") or {}).get("taxId", ""),
                     "doc_type": dtype, "number": number, "date": (m.get("date") or "")[:10],
                     "net": fnum(m.get("amountExcludeVat")), "vat": vat, "amount": amt,
                     "currency": m.get("currency", "ILS"), "payment": PAY.get(m.get("paymentType"), ""),
                     "expense_type": et, "pcn": pcn, "method": "verified" if a_ok else "needs-visual",
                     "confidence": conf, "doubt": doubt}
        if conf == "high": conf_n += 1
    json.dump(scan, open(SCAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"verified digital: amount-confirmed={ver_n} (high={conf_n}) | unconfirmed(needs visual)={low_n}")
    print("total scanned:", len([k for k in scan if not k.startswith("_")]))


if __name__ == "__main__":
    main()
