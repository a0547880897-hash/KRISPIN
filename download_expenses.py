"""Task 2: download the 304 APPROVED/CLOSED expenses (1.8.2025 - today) from Morning.

Read-only. Saves source file + full expense object for an independent re-scan.
Separate from the drafts task: own folder + own json/index.
"""
import os, csv, json, time, re
import requests
from morning_api import Morning

DOCS = "documents_expenses"
RAW = "expenses_raw.json"
INDEX = "index_expenses.csv"
FROM, TO = "2025-06-01", "2026-06-07"


def sanitize(name, n=40):
    name = (name or "ספק").strip()
    name = re.sub(r'[\\/:*?"<>|\n\r\t]+', "_", name)
    return re.sub(r"\s+", "-", name)[:n].strip("-_") or "ספק"


def ext_from(url, ct):
    if ct:
        ct = ct.lower()
        if "pdf" in ct: return "pdf"
        if "png" in ct: return "png"
        if "jpeg" in ct or "jpg" in ct: return "jpg"
    return "pdf"


def retry(fn, tries=4):
    last = None
    for i in range(tries):
        try: return fn()
        except Exception as e:
            last = e; time.sleep(2 ** i if i else 1)
    raise last


def main():
    os.makedirs(DOCS, exist_ok=True)
    m = Morning(); m.authenticate()
    items, page = [], 1
    while True:
        r = retry(lambda: m.post("/expenses/search", {"page": page, "pageSize": 100, "fromDate": FROM, "toDate": TO}))
        d = r.json(); items += d["items"]
        print(f"  listed page {page}/{d['pages']} total={d['total']}", flush=True)
        if page >= d["pages"]: break
        page += 1; time.sleep(0.15)
    print(f"got {len(items)} expenses", flush=True)

    raw = json.load(open(RAW, encoding="utf-8")) if os.path.exists(RAW) else {}
    rows = []
    for i, it in enumerate(sorted(items, key=lambda x: x.get("date", "")), 1):
        eid = it["id"]; idx = f"{i:04d}"
        raw[eid] = it
        sup = (it.get("supplier") or {}).get("name", "")
        try:
            existing = [f for f in os.listdir(DOCS) if f.startswith(idx + "_" + eid)]
            if existing:
                fname = existing[0]
            else:
                url = it.get("url")
                if not url:
                    g = retry(lambda: m.get("/expenses/" + eid)); url = g.json().get("url")
                rf = retry(lambda: requests.get(url, timeout=90))
                fname = f"{idx}_{eid}_{sanitize(sup)}.{ext_from(url, rf.headers.get('Content-Type'))}"
                open(os.path.join(DOCS, fname), "wb").write(rf.content)
                time.sleep(0.1)
        except Exception as e:
            print(f"  ERR {idx} {eid}: {repr(e)[:120]}", flush=True); fname = ""
        rows.append({"index": idx, "expense_id": eid, "supplier": sup, "filename": fname,
                     "status": it.get("status"), "documentType": it.get("documentType"),
                     "number": it.get("number"), "amount": it.get("amount"), "vat": it.get("vat"),
                     "deductibleVat": it.get("deductibleVat"), "date": it.get("date"),
                     "reportingDate": it.get("reportingDate"), "currency": it.get("currency")})
        if i % 50 == 0 or i == len(items):
            json.dump(raw, open(RAW, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"  [{i}/{len(items)}] saved", flush=True)
    json.dump(raw, open(RAW, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(INDEX, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    nf = sum(1 for r in rows if r["filename"])
    print(f"DONE. {len(rows)} expenses, {nf} files downloaded.", flush=True)


if __name__ == "__main__":
    main()
