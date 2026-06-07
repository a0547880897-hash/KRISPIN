"""Parse authoritative text of digital expense PDFs -> draft scan entries.

Pulls EXACT figures (total / vat / net), document number, date, currency, and a
supplier-tax-id (9 digits, excluding the client's own 516691953) straight from
the document's embedded text. Classification + doubts are added by rules and
then reviewed. Image/scanned docs are skipped here (read visually instead).
"""
import os, re, csv, json
import fitz

DOCS = "documents_expenses"; INDEX = "index_expenses.csv"; OUT = "expenses_scan.json"
CLIENT = {"516691953", "021988431"}  # client's own ids - never the supplier

def gt(p):
    try: return "\n".join(pg.get_text() for pg in fitz.open(p))
    except Exception: return ""

def num(s):
    try: return round(float(s.replace(",", "")), 2)
    except Exception: return None

NUMTOK = re.compile(r'[\d,]+\.\d{2}|\d{1,3}(?:,\d{3})+|\d+\.\d{2}')

def near_number(t, label_pats, window=30):
    """Find the monetary number closest to any label occurrence (either side)."""
    best = None
    for lp in label_pats:
        for m in re.finditer(lp, t):
            s, e = m.start(), m.end()
            seg = t[max(0, s - window):e + window]
            cands = NUMTOK.findall(seg)
            cands = [num(c) for c in cands if num(c) is not None]
            if cands:
                # prefer the largest plausible amount in window
                best = max([c for c in cands] + ([best] if best else []))
    return best

def find_total(t):
    # explicit adjacent first
    for p in [r'Amount\s+(?:paid|due)[^\d]{0,8}\$?\s*([\d,]+\.\d{2})', r'Total[^\d]{0,8}\$?\s*([\d,]+\.\d{2})']:
        m = re.findall(p, t)
        if m: return num(m[-1])
    return near_number(t, [r'סה"?כ\s*לתשלום', r'כ"?סה\s*לתשלום', r'סה"?כ\s*כולל\s*מע"?מ',
                           r'לתשלום\s*כ"?סה', r'סך\s*הכול', r'Amount\s+(?:paid|due)', r'Total'])

def find_vat(t):
    for p in [r'VAT\s*1[78]%?[^\d]{0,8}\$?\s*([\d,]+\.\d{2})']:
        m = re.findall(p, t)
        if m: return num(m[-1])
    return near_number(t, [r'מע"?מ\s*1[78]', r'1[78]\.00%', r'מע"?מ\b', r'VAT'], window=22)

def find_number(t):
    for p in [r'חשבונית\s*מס(?:\s*/?\s*קבלה)?\s*(?:מרכזת\s*)?([A-Za-z]{0,3}\d[\w\-/]{2,})',
              r'Invoice\s*number\s*([A-Za-z0-9][\w\-]{3,})', r'Tax\s*Invoice\s*/?\s*Receipt\s*(\d{3,})',
              r'קבלה(?:\s*על\s*תרומה)?\s*(?:מספר\s*)?(\d{3,})']:
        m = re.search(p, t)
        if m: return m.group(1).strip()
    return ""

def find_date(t):
    m = re.search(r'(\d{2})/(\d{2})/(\d{2,4})', t)
    if m:
        d, mo, y = m.groups(); y = y if len(y) == 4 else "20" + y
        return f"{y}-{mo}-{d}"
    months = {"January":"01","February":"02","March":"03","April":"04","May":"05","June":"06",
              "July":"07","August":"08","September":"09","October":"10","November":"11","December":"12"}
    m = re.search(r'([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})', t)
    if m and m.group(1) in months:
        return f"{m.group(3)}-{months[m.group(1)]}-{int(m.group(2)):02d}"
    return ""

def find_taxid(t):
    ids = re.findall(r'(?<!\d)(\d{9})(?!\d)', t)
    for i in ids:
        if i not in CLIENT: return i
    return ""

def main():
    files = {f.split("_")[1]: f for f in os.listdir(DOCS)}
    scan = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    done = set(k for k in scan if not k.startswith("_"))
    n = 0
    for r in csv.DictReader(open(INDEX, encoding="utf-8-sig")):
        eid = r["expense_id"]; f = files.get(eid)
        if not f or not f.lower().endswith(".pdf") or eid in done:
            continue
        t = gt(os.path.join(DOCS, f))
        if len(t.strip()) < 40:
            continue  # image/scanned -> visual
        total = find_total(t); vat = find_vat(t)
        usd = ("USD" in t or "$" in t) and ("₪" not in t.split("$")[0][-40:] if "$" in t else "USD" in t)
        cur = "USD" if (re.search(r'\$\s*\d', t) or "USD" in t) and "ILS" not in t[:200] else "ILS"
        net = round(total - vat, 2) if (total is not None and vat) else (total if total is not None else None)
        conf = "high" if (total is not None and (vat is not None or "$" in t)) else "low"
        scan[eid] = {
            "supplier": (r.get("supplier") or "").strip(), "taxId": find_taxid(t),
            "doc_type": "", "number": find_number(t), "date": find_date(t) or (r.get("date") or "")[:10],
            "net": net, "vat": vat if vat is not None else (0 if cur == "USD" else None),
            "amount": total, "currency": cur, "payment": "", "expense_type": "", "pcn": "",
            "method": "text-parsed", "confidence": conf,
            "doubt": "" if conf == "high" else "פרסור אוטומטי לא מצא סכום/מע\"מ ברור — לאמת מול המסמך"
        }
        n += 1
    json.dump(scan, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"parsed {n} digital docs. total scanned now: {len([k for k in scan if not k.startswith('_')])}")

if __name__ == "__main__":
    main()
