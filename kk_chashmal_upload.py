"""Upload each split קופה קטנה - תגל invoice PDF to Morning as an expense DRAFT,
then match each upload back to its created draft by MD5 hash.

Mirrors the proven b2/b3/b4 flow:
 1. Snapshot existing draft IDs.
 2. For each invoice: GET presigned upload url, POST multipart -> draft created async.
 3. Poll the draft list until the new drafts materialize.
 4. Download each NEW draft's file, md5 it, match to kk_chashmal_data.json.
Never approves, never deletes. Writes kk_chashmal_map.json (nn -> draft_id).
"""
import json, time, hashlib, requests
from morning_api import Morning

DATA = json.load(open("kk_chashmal_data.json", encoding="utf-8"))
BY_MD5 = {r["md5"]: r["nn"] for r in DATA}
GW = "https://apigw.greeninvoice.co.il/file-upload/v1/url"
OUTDIR = "kk_chashmal"


def list_draft_ids(m):
    ids, page = {}, 1
    while True:
        j = m.post("/expenses/drafts/search", {"page": page, "pageSize": 100}).json()
        for it in j["items"]:
            ids[it["id"]] = it.get("creationDate", 0)
        if page >= j["pages"]:
            break
        page += 1
        time.sleep(0.15)
    return ids


def upload_one(m, rec):
    m._ensure()
    r = m.s.get(GW, params={"context": "expense", "data": json.dumps({"source": 5})}, timeout=40)
    r.raise_for_status()
    d = r.json()
    files = {k: (None, v) for k, v in d["fields"].items()}
    files["file"] = (rec["file"], open(f"{OUTDIR}/{rec['file']}", "rb").read(), "application/pdf")
    up = requests.post(d["url"], files=files, timeout=120)
    return up.status_code


def md5_of_draft_file(m, did):
    full = m.get("/expenses/drafts/" + did).json()
    url = full.get("url")
    if not url:
        return None
    fr = requests.get(url, timeout=60)
    return hashlib.md5(fr.content).hexdigest() if fr.status_code == 200 else None


def main():
    m = Morning(); m.authenticate()
    print("AUTH OK", flush=True)

    before = list_draft_ids(m)
    json.dump(list(before.keys()), open("kk_chashmal_before.json", "w"))
    print(f"existing drafts before upload: {len(before)}", flush=True)

    for rec in DATA:
        code = upload_one(m, rec)
        print(f"  uploaded {rec['nn']} ({rec['number']}): S3 status {code}", flush=True)
        time.sleep(1.0)
    print(f"all {len(DATA)} posted. waiting for drafts to materialize...", flush=True)

    new_ids = []
    for attempt in range(24):
        time.sleep(15)
        m.authenticate()
        now = list_draft_ids(m)
        new_ids = [i for i in now if i not in before]
        print(f"  poll {attempt+1}: {len(new_ids)} new drafts", flush=True)
        if len(new_ids) >= len(DATA):
            break
    json.dump(new_ids, open("kk_chashmal_new.json", "w"))

    mapping = {}
    unmatched = []
    for did in new_ids:
        h = md5_of_draft_file(m, did)
        if h in BY_MD5:
            mapping[BY_MD5[h]] = did
        else:
            unmatched.append({"id": did, "md5": h})
        time.sleep(0.2)

    json.dump(mapping, open("kk_chashmal_map.json", "w"), ensure_ascii=False, indent=1)
    print(f"matched {len(mapping)}/{len(DATA)} invoices to drafts", flush=True)
    missing = [r["nn"] for r in DATA if r["nn"] not in mapping]
    if missing:
        print("UNMATCHED invoices:", missing, flush=True)
        json.dump(unmatched, open("kk_chashmal_unmatched.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
