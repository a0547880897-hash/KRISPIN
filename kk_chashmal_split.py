"""Split the קופה קטנה - תגל electricity-bills PDF (one invoice per page) into
single-page PDFs and extract each invoice's fields (number, issue date, net, vat,
total). Cross-checks parsed figures against a hand-verified table so a parsing
slip can never reach Morning. Writes kk_chashmal_data.json + per-page PDFs.

Nothing here touches Morning.
"""
import json, re, hashlib, os, sys
import fitz  # pymupdf

SRC = sys.argv[1] if len(sys.argv) > 1 else "kk_chashmal/source.pdf"
OUTDIR = "kk_chashmal"
DATA = "kk_chashmal_data.json"

# Hand-verified from a careful read of every page (critical fields).
# number -> (issue_date YYYY-MM-DD, net, vat, total)
EXPECT = {
    "55316689": ("2025-03-01", 1457.37, 262.33, 1719.70),
    "55354348": ("2025-04-01", 857.41, 154.33, 1011.74),
    "55391287": ("2025-05-01", 369.61, 66.53, 436.14),
    "55476465": ("2025-06-01", 566.36, 101.94, 668.30),
    "55509435": ("2025-07-01", 807.71, 145.39, 953.10),
    "55527759": ("2025-08-01", 1123.60, 202.25, 1325.85),
    "55592029": ("2025-09-01", 1155.83, 208.05, 1363.88),
    "55657777": ("2025-10-01", 897.63, 161.57, 1059.20),
    "55682525": ("2025-11-01", 588.78, 105.98, 694.76),
    "55742101": ("2025-12-01", 470.16, 84.63, 554.79),
    "55819948": ("2026-01-01", 988.58, 177.94, 1166.52),
    "55850038": ("2026-02-01", 1511.03, 271.99, 1783.02),
    "55907226": ("2026-03-01", 735.17, 132.33, 867.50),
    "55998899": ("2026-04-01", 739.62, 133.13, 872.75),
    "553059110": ("2026-05-01", 712.95, 128.33, 841.28),
}


def num(s):
    return round(float(s.replace(",", "")), 2)


def clamp_reporting(date_str):
    m = re.match(r"(\d{4})-(\d{2})", date_str)
    fom = f"{m.group(1)}-{m.group(2)}-01"
    return fom if fom >= "2025-11-01" else "2025-11-01"


def parse_page(t):
    inv = re.search(r"(?:Create|Append)Pdf(\d+)END", t)
    dt = re.search(r"(\d{2})/(\d{2})/(\d{4})\s*:תאריך עריכת", t)
    net = re.search(r'סה"כ ללא מע"מ([\d,]+\.\d{2})', t)
    vat = re.search(r'([\d,]+\.\d{2})סה"כ מע"מ', t)
    tot = re.search(r'([\d,]+\.\d{2})סה"כ כולל מע"מ', t)
    issue = f"{dt.group(3)}-{dt.group(2)}-{dt.group(1)}" if dt else None
    return {
        "number": inv.group(1) if inv else None,
        "issue_date": issue,
        "net": num(net.group(1)) if net else None,
        "vat": num(vat.group(1)) if vat else None,
        "total": num(tot.group(1)) if tot else None,
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    doc = fitz.open(SRC)
    records = []
    problems = []
    for i in range(doc.page_count):
        page = doc[i]
        p = parse_page(page.get_text())
        nn = f"{i+1:02d}"
        number = p["number"]
        exp = EXPECT.get(number)
        # cross-check critical fields against the verified table
        if not exp:
            problems.append(f"page {nn}: invoice {number} not in verified table")
        else:
            edate, enet, evat, etot = exp
            for label, got, want in (("issue_date", p["issue_date"], edate),
                                     ("net", p["net"], enet),
                                     ("vat", p["vat"], evat),
                                     ("total", p["total"], etot)):
                if got != want:
                    problems.append(f"page {nn} ({number}): {label} parsed={got} expected={want}")
        # sanity: net + vat == total
        if p["net"] is not None and p["vat"] is not None and p["total"] is not None:
            if abs(p["net"] + p["vat"] - p["total"]) > 0.02:
                problems.append(f"page {nn} ({number}): net+vat != total ({p['net']}+{p['vat']}!={p['total']})")

        # write single-page PDF
        ym = p["issue_date"][:7] if p["issue_date"] else "unknown"
        fname = f"kk_{nn}_{number}_{ym}.pdf"
        fpath = os.path.join(OUTDIR, fname)
        one = fitz.open()
        one.insert_pdf(doc, from_page=i, to_page=i)
        one.save(fpath)
        one.close()
        md5 = hashlib.md5(open(fpath, "rb").read()).hexdigest()

        records.append({
            "nn": nn,
            "number": number,
            "date": p["issue_date"],
            "reportingDate": clamp_reporting(p["issue_date"]),
            "net": p["net"],
            "vat": p["vat"],
            "amount": p["total"],
            "currency": "ILS",
            "file": fname,
            "md5": md5,
        })
    doc.close()

    json.dump(records, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"split {len(records)} pages -> {OUTDIR}/  | data -> {DATA}")
    print(f"{'NN':>2} {'invoice':>11} {'date':>10} {'reporting':>10} {'net':>9} {'vat':>8} {'total':>9}")
    for r in records:
        print(f"{r['nn']:>2} {r['number']:>11} {r['date']:>10} {r['reportingDate']:>10} "
              f"{r['net']:>9} {r['vat']:>8} {r['amount']:>9}")
    print(f"\ntotal incl VAT = {round(sum(r['amount'] for r in records),2)} | "
          f"total VAT = {round(sum(r['vat'] for r in records),2)}")
    if problems:
        print("\n*** CROSS-CHECK PROBLEMS — do NOT upload until resolved ***")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("\nCROSS-CHECK OK: every parsed figure matches the verified table.")


if __name__ == "__main__":
    main()
