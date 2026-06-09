"""Batch3 upload: upload 26 new invoice PDFs (b3pdf/NN.pdf, EXCLUDING doc 20 which is
already in Morning) as expense drafts, then match each to its draft by MD5 hash.
Never approves. Mirrors b2_upload.py.
"""
import json, time, hashlib, glob, os, requests
from morning_api import Morning

EXCLUDE = {"20"}  # already exists in Morning (rent receipt #42 / 2760 / 2025-11-28)
GW = "https://apigw.greeninvoice.co.il/file-upload/v1/url"
NN_LIST = [f"{i:02d}" for i in range(1, 28) if f"{i:02d}" not in EXCLUDE]


def local_md5():
    h = {}
    for nn in NN_LIST:
        h[nn] = hashlib.md5(open(f"b3pdf/{nn}.pdf", "rb").read()).hexdigest()
    return h


def list_draft_ids(m):
    ids, page = {}, 1
    while True:
        j = m.post("/expenses/drafts/search", {"page": page, "pageSize": 100}).json()
        for it in j["items"]:
            ids[it["id"]] = it.get("creationDate", 0)
        if page >= j["pages"]:
            break
        page += 1; time.sleep(0.12)
    return ids


def upload_one(m, nn):
    r = m.s.get(GW, params={"context": "expense", "data": json.dumps({"source": 5})}, timeout=40)
    r.raise_for_status(); d = r.json()
    files = {k: (None, v) for k, v in d["fields"].items()}
    files["file"] = (f"b3_{nn}.pdf", open(f"b3pdf/{nn}.pdf", "rb").read(), "application/pdf")
    return requests.post(d["url"], files=files, timeout=120).status_code


def md5_of_draft(m, did):
    full = m.get("/expenses/drafts/" + did).json()
    url = full.get("url")
    if not url:
        return None
    fr = requests.get(url, timeout=60)
    return hashlib.md5(fr.content).hexdigest() if fr.status_code == 200 else None


def main():
    LM = local_md5(); json.dump(LM, open("b3_local_md5.json", "w"), indent=1)
    m = Morning(); m.authenticate(); print("AUTH OK", flush=True)
    before = list_draft_ids(m)
    print(f"drafts before: {len(before)} | uploading {len(NN_LIST)} (excl {sorted(EXCLUDE)})", flush=True)
    for nn in NN_LIST:
        print(f"  upload {nn}: {upload_one(m, nn)}", flush=True); time.sleep(1.0)
    print("posted. polling...", flush=True)
    new_ids = []
    for a in range(24):
        time.sleep(15); m.authenticate()
        now = list_draft_ids(m)
        new_ids = [i for i in now if i not in before]
        print(f"  poll {a+1}: {len(new_ids)} new", flush=True)
        if len(new_ids) >= len(NN_LIST):
            break
    m2n = {v: k for k, v in LM.items()}
    mp, un = {}, []
    for did in new_ids:
        h = md5_of_draft(m, did)
        (mp.__setitem__(m2n[h], did) if h in m2n else un.append({"id": did, "md5": h}))
        time.sleep(0.15)
    json.dump(mp, open("b3_map.json", "w"), indent=1)
    print(f"matched {len(mp)}/{len(NN_LIST)}", flush=True)
    miss = [nn for nn in NN_LIST if nn not in mp]
    if miss:
        print("UNMATCHED:", miss, flush=True)
        json.dump(un, open("b3_unmatched.json", "w"), indent=1)


if __name__ == "__main__":
    main()
