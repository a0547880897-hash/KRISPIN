"""Step 2: download ALL Morning expense drafts (pending approval) locally.

Read-only against Morning (search + get + file download). NEVER creates,
updates, deletes, or confirms anything. Saves:
  documents/NNNN_<draft_id>_<supplier>.<ext>   original supplier file
  catalog_raw.json                              full draft objects (for scanning)
  index.csv                                      index, draft_id, supplier, filename, ...

Resumable: re-running skips drafts whose file already exists. Throttled + retries.

The accidental empty draft created by the buggy discovery probe is EXCLUDED.
"""
import os, csv, json, time, re, sys
import requests
from morning_api import Morning

# Junk draft accidentally created by discover_morning.py's POST /expenses/drafts probe.
EXCLUDE_IDS = {"20cefe06-1e7e-4ee4-80ff-6723586b3d3f"}

DOCS_DIR = "documents"
RAW_JSON = "catalog_raw.json"
INDEX_CSV = "index.csv"
PAGE_SIZE = 50


def sanitize(name, maxlen=40):
    name = (name or "ספק-לא-ידוע").strip()
    name = re.sub(r"[\\/:*?\"<>|\n\r\t]+", "_", name)
    name = re.sub(r"\s+", "-", name)
    return name[:maxlen].strip("-_") or "ספק"


def ext_from(fileKey, content_type):
    if fileKey and "." in fileKey:
        e = fileKey.rsplit(".", 1)[-1].lower()
        if 1 <= len(e) <= 5:
            return e
    ct = (content_type or "").lower()
    if "pdf" in ct: return "pdf"
    if "png" in ct: return "png"
    if "jpeg" in ct or "jpg" in ct: return "jpg"
    return "bin"


def retry(fn, tries=4, base=2):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(base * (2 ** i) if i else 1)
    raise last


def list_all_drafts(m):
    out, page = [], 1
    while True:
        r = retry(lambda: m.post("/expenses/drafts/search", {"page": page, "pageSize": PAGE_SIZE}))
        r.raise_for_status()
        d = r.json()
        out.extend(d["items"])
        total, pages = d["total"], d["pages"]
        print(f"  listed page {page}/{pages} (total={total})", flush=True)
        if page >= pages:
            break
        page += 1
        time.sleep(0.15)
    return out, total


def main():
    os.makedirs(DOCS_DIR, exist_ok=True)
    m = Morning(); m.authenticate()
    print("AUTH OK", flush=True)

    items, total = list_all_drafts(m)
    items = [it for it in items if it["id"] not in EXCLUDE_IDS]
    print(f"Total reported by API: {total}. After excluding junk: {len(items)} drafts to process.", flush=True)

    raw = {}
    if os.path.exists(RAW_JSON):
        raw = json.load(open(RAW_JSON, encoding="utf-8"))

    index_rows = []
    for i, it in enumerate(sorted(items, key=lambda x: x.get("creationDate", 0)), start=1):
        did = it["id"]
        idx = f"{i:04d}"
        try:
            full = raw.get(did)
            if not full or "url" not in full:
                r = retry(lambda: m.get("/expenses/drafts/" + did))
                r.raise_for_status()
                full = r.json()
                raw[did] = full
                time.sleep(0.12)

            supplier = (full.get("expense", {}).get("supplier", {}) or {}).get("name", "")
            url = full.get("url")
            fileKey = full.get("expense", {}).get("fileKey")

            # find existing file for this draft (resume)
            existing = [f for f in os.listdir(DOCS_DIR) if f.startswith(idx + "_" + did)]
            if existing:
                fname = existing[0]
            elif url:
                rf = retry(lambda: requests.get(url, timeout=90))
                ext = ext_from(fileKey, rf.headers.get("Content-Type"))
                fname = f"{idx}_{did}_{sanitize(supplier)}.{ext}"
                with open(os.path.join(DOCS_DIR, fname), "wb") as fh:
                    fh.write(rf.content)
                time.sleep(0.12)
            else:
                fname = ""  # no file attached

            exp = full.get("expense", {})
            index_rows.append({
                "index": idx,
                "draft_id": did,
                "supplier": supplier,
                "filename": fname,
                "fileKey": fileKey or "",
                "currency": exp.get("currency", ""),
                "amount": exp.get("amount", ""),
                "vat": exp.get("vat", ""),
                "documentType": exp.get("documentType", ""),
                "number": exp.get("number", ""),
                "reportingDate": exp.get("reportingDate", ""),
                "has_file": bool(fname),
            })
            if i % 25 == 0 or i == len(items):
                json.dump(raw, open(RAW_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                print(f"  [{i}/{len(items)}] saved progress (last supplier: {supplier[:30]})", flush=True)
        except Exception as e:
            print(f"  ERROR on {idx} {did}: {repr(e)[:160]}", flush=True)
            index_rows.append({"index": idx, "draft_id": did, "supplier": "", "filename": "",
                               "fileKey": "", "currency": "", "amount": "", "vat": "",
                               "documentType": "", "number": "", "reportingDate": "", "has_file": False})

    json.dump(raw, open(RAW_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(INDEX_CSV, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(index_rows[0].keys()))
        w.writeheader(); w.writerows(index_rows)

    n_files = sum(1 for r in index_rows if r["has_file"])
    print(f"\nDONE. {len(index_rows)} drafts, {n_files} files downloaded, {len(index_rows)-n_files} without file.", flush=True)


if __name__ == "__main__":
    main()
