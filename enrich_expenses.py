"""Complete the expenses scan into a reviewable by-month sheet.

For each of the ~449 expenses:
 - keep my parsed figures where the parser found them cleanly (method text-parsed/high);
 - where the parser could not read the RTL amount, FILL from Morning's captured
   figure but FLAG it "לאימות ויזואלי" (transparent, for the client's review);
 - docs with no extractable text (images) / no file -> placeholder flagged for
   visual reading.
Adds rule-based expense_type + PCN classification (client's business logic).
Doc-type code -> Hebrew. Nothing here touches Morning.
"""
import os, json, csv, re

RAW = "expenses_raw.json"; INDEX = "index_expenses.csv"; SCAN = "expenses_scan.json"; DOCS = "documents_expenses"
DOCT = {305: "חשבונית מס", 320: "חשבונית מס/קבלה", 400: "קבלה", 405: "קבלה/זיכוי",
        330: "חשבונית עסקה", 20: "מסמך הוצאה", 100: "הצעת מחיר"}
PAY = {1: "מזומן", 2: "צ'ק", 3: "כרטיס אשראי", 4: "העברה בנקאית", 5: "PayPal", 0: "", 8: "אחר", 10: "אפליקציה"}

def classify(sup, cur, vat):
    s = sup or ""
    sl = s.lower()
    foreign_sw = any(k in s or k in sl for k in ["Apple","Google","Wix","Meta","פייסבוק","monday","Canva","Zoom",
        "Dropbox","DigitalOcean","Grammarly","Suno","Ideogram","Runway","Wistia","Genspark","ManyChat","Manychat",
        "MainFunc","Manus","Lovable","GoFullPage","Bitdefender","CapCut","PIPO","Paddle","Microsoft","Anthropic",
        "Midjourney","Envato","Vyond","GoAnimate","OpenAI","Topaz","PandaDoc","Adobe","Gett","Cloud","Suno"])
    clubs = any(k in s for k in ["מכבי","הפועל","ביתר","סכנין","קרית שמונה","קשר ספורט","איתוראן ספורט","אחווה הכחולה",
        "ג'רוזלם","אוראל ווליום","קידום הספורט","התאחדות לכדורגל","ריפורט","סהר הפקות","בילבורד"])
    if clubs:
        return "מלאי/פרסום (כדורגל ליגת העל)", ("ללא מע\"מ" if not vat else "T — תשומה שוטפת")
    if "צארומי" in s:
        return "מלאי קמפיינים (אופניים חשמליים - מתנות הגרלה)", "T — ציוד/מלאי"
    if foreign_sw:
        return "תוכנה/שירות דיגיטלי — חו\"ל", "ללא מע\"מ (שירות חו\"ל)"
    if any(k in s for k in ["עמותת","תרומה","קרן ","ידידי","חסד","תורה"]):
        return "תרומה (סעיף 46)", "ללא מע\"מ"
    if any(k in s for k in ["פאיימי","PayMe","סליקה","ויזה כאל","ישראכרט","לאומי קארד"]):
        return "עמלות סליקה/שירותי תשלום", "T — תשומה שוטפת"
    if any(k in s for k in ["מחשבים","אלקטרה","מחסני חשמל","KSP","קיי.אס.פי","סלולר","ג'וי מובייל","הכל בכיף","אמירים"]):
        return "ציוד/רכוש קבוע — לבדיקה", ("ללא מע\"מ" if not vat else "T — ציוד")
    if any(k in s for k in ["דלק","פז","סונול","דור אלון","ten","ילו"]):
        return "דלק רכב (מע\"מ 2/3)", "T — תשומה שוטפת"
    if any(k in s for k in ["עירייה","עיריית","ארנונה","מים","תאגיד","חשמל","בזק","פרטנר","partner","הוט","סלקום","yes"]):
        return "תשומות שוטפות (משק/תשתית)", ("ללא מע\"מ" if not vat else "T — תשומה שוטפת")
    if any(k in s for k in ["עורכי דין","עו\"ד","ברכיה","רואי חשבון","שיטרית","ראיית חשבון"]):
        return "שירותים מקצועיים (משפטי/הנהח\"ש)", "T — תשומה שוטפת"
    if any(k in s for k in ["יקב","דרימיה","יין"]):
        return "מתנות/כיבוד לקוחות", "T — קיזוז מוגבל"
    return "לבדיקה", ("ללא מע\"מ" if not vat else "T — תשומה שוטפת")

def fnum(v):
    try: return round(float(v), 2)
    except Exception: return None

def main():
    raw = json.load(open(RAW, encoding="utf-8"))
    scan = json.load(open(SCAN, encoding="utf-8")) if os.path.exists(SCAN) else {}
    files = {f.split("_")[1]: f for f in os.listdir(DOCS)} if os.path.isdir(DOCS) else {}
    rows = list(csv.DictReader(open(INDEX, encoding="utf-8-sig")))
    for r in rows:
        eid = r["expense_id"]; m = raw.get(eid, {})
        sup = (m.get("supplier") or {}).get("name", "") or r.get("supplier", "")
        cur = m.get("currency", "ILS")
        e = scan.get(eid)
        if e and not str(e.get("_meta", "")):
            pass
        if e is None:
            # image / no-file -> placeholder for visual reading
            has = bool(files.get(eid))
            e = {"supplier": sup, "taxId": (m.get("supplier") or {}).get("taxId", ""),
                 "doc_type": DOCT.get(m.get("documentType"), str(m.get("documentType", ""))),
                 "number": m.get("number", ""), "date": (m.get("date") or "")[:10],
                 "net": fnum(m.get("amountExcludeVat")), "vat": fnum(m.get("vat")), "amount": fnum(m.get("amount")),
                 "currency": cur, "payment": PAY.get(m.get("paymentType"), ""),
                 "method": "image-לקריאה-ויזואלית" if has else "ללא-קובץ",
                 "confidence": "low",
                 "doubt": "מסמך סרוק/תמונה — ממתין לקריאה ויזואלית ידנית" if has else "אין קובץ מצורף — נתונים ממורנינג בלבד"}
        # fill missing figures from Morning, flagged
        if e.get("amount") is None and m.get("amount") is not None:
            e["amount"] = fnum(m.get("amount")); e["vat"] = fnum(m.get("vat")); e["net"] = fnum(m.get("amountExcludeVat"))
            e["confidence"] = "low"
            e["doubt"] = (e.get("doubt") or "") + " | סכום מולא ממורנינג — לאמת ויזואלית"
        # doc type from Morning if I don't have one
        if not e.get("doc_type"):
            e["doc_type"] = DOCT.get(m.get("documentType"), str(m.get("documentType", "")))
        if not e.get("payment"):
            e["payment"] = PAY.get(m.get("paymentType"), "")
        # classification if empty
        if not e.get("expense_type"):
            et, pcn = classify(sup, cur, e.get("vat"))
            e["expense_type"] = et; e["pcn"] = pcn
        if not e.get("supplier"):
            e["supplier"] = sup
        scan[eid] = e
    json.dump(scan, open(SCAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = len([k for k in scan if not k.startswith("_")])
    flagged = sum(1 for k, v in scan.items() if not k.startswith("_") and "לאמת" in (v.get("doubt") or "") or "ויזואלית" in (v.get("doubt") or ""))
    print(f"enriched. total rows: {tot} | flagged for visual verify: {flagged}")

if __name__ == "__main__":
    main()
