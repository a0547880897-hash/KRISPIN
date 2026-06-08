"""Batch2: upload 18 new invoice PDFs (b2pdf/NN.pdf) to Morning as expense drafts,
then match each upload to its created draft by MD5 hash. Never approves.

Flow:
 1. Snapshot existing draft IDs.
 2. For each NN: GET presigned S3 url, POST multipart -> draft created async (~30s).
 3. Poll draft list until >=18 new drafts appear (or timeout).
 4. Download each NEW draft's file, md5 it, match to b2_local_md5.json -> b2_map.json
"""
import json, time, hashlib, glob, os, requests
from morning_api import Morning

LOCAL_MD5 = json.load(open("b2_local_md5.json"))
NN_LIST = sorted(LOCAL_MD5.keys())
GW = "https://apigw.greeninvoice.co.il/file-upload/v1/url"


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


def upload_one(m, nn):
    r = m.s.get(GW, params={"context": "expense", "data": json.dumps({"source": 5})}, timeout=40)
    r.raise_for_status()
    d = r.json()
    files = {k: (None, v) for k, v in d["fields"].items()}
    files["file"] = (f"b2_{nn}.pdf", open(f"b2pdf/{nn}.pdf", "rb").read(), "application/pdf")
    up = requests.post(d["url"], files=files, timeout=120)
    return up.status_code


def md5_of_draft_file(m, did):
    full = m.get("/expenses/drafts/" + did).json()
    url = full.get("url")
    if not url:
        return None
    fr = requests.get(url, timeout=60)
    if fr.status_code != 200:
        return None
    return hashlib.md5(fr.content).hexdigest()


def main():
    m = Morning(); m.authenticate()
    print("AUTH OK", flush=True)

    before = list_draft_ids(m)
    json.dump(list(before.keys()), open("b2_before_ids.json", "w"))
    print(f"existing drafts before upload: {len(before)}", flush=True)

    # upload all 18
    for nn in NN_LIST:
        code = upload_one(m, nn)
        print(f"  uploaded {nn}: S3 status {code}", flush=True)
        time.sleep(1.0)
    print("all 18 posted to S3. waiting for drafts to materialize...", flush=True)

    # poll for new drafts
    new_ids = []
    for attempt in range(20):
        time.sleep(15)
        m.authenticate()  # refresh token if needed
        now = list_draft_ids(m)
        new_ids = [i for i in now if i not in before]
        print(f"  poll {attempt+1}: {len(new_ids)} new drafts", flush=True)
        if len(new_ids) >= len(NN_LIST):
            break

    json.dump(new_ids, open("b2_new_ids.json", "w"))
    print(f"new drafts found: {len(new_ids)}", flush=True)

    # match by hash
    md5_to_nn = {v: k for k, v in LOCAL_MD5.items()}
    mapping = {}
    unmatched_drafts = []
    for did in new_ids:
        h = md5_of_draft_file(m, did)
        if h in md5_to_nn:
            mapping[md5_to_nn[h]] = did
        else:
            unmatched_drafts.append({"id": did, "md5": h})
        time.sleep(0.2)

    json.dump(mapping, open("b2_map.json", "w"), indent=1)
    print(f"matched {len(mapping)}/{len(NN_LIST)} invoices to drafts", flush=True)
    missing = [nn for nn in NN_LIST if nn not in mapping]
    if missing:
        print("UNMATCHED invoices:", missing, flush=True)
        json.dump(unmatched_drafts, open("b2_unmatched.json", "w"), indent=1)


if __name__ == "__main__":
    main()
