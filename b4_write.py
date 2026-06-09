"""Write batch2 visual-scan data (b4_data.json) into the 18 new drafts (b4_map.json).

Read-modify-write per draft: preserves fileKey/fileHash/status (stays 10, NOT approved)
and accountingClassification. Sets supplier name+taxId, number, date, reportingDate
(clamped >= 2025-11-01), amount, vat, currency, paymentType (if given), description (note).
Never approves, never deletes.
"""
import sys, json, time, re, copy
from morning_api import Morning, BASE

SCAN = json.load(open("b4_data.json", encoding="utf-8"))
MAP = json.load(open("b4_map.json"))


def clamp(date_str):
    m = re.search(r"(\d{4})-(\d{2})", str(date_str or ""))
    if not m:
        return "2025-11-01"
    fom = f"{m.group(1)}-{m.group(2)}-01"
    return fom if fom >= "2025-11-01" else "2025-11-01"


def main():
    apply = "--apply" in sys.argv
    m = Morning(); m.authenticate()
    print("AUTH OK", flush=True)
    log = {"ok": [], "fail": []}
    for nn in sorted(SCAN):
        if nn not in MAP:
            continue
        did = MAP[nn]
        v = SCAN[nn]
        try:
            cur = m.get(f"/expenses/drafts/{did}").json()
            e = copy.deepcopy(cur.get("expense", cur))
            e["supplier"] = dict(e.get("supplier") or {})
            e["supplier"]["name"] = v["name"][:100]
            if v.get("taxId"):
                e["supplier"]["taxId"] = str(v["taxId"])
            e["supplier"].setdefault("country", "IL")
            e["number"] = str(v["number"])[:50]
            e["date"] = v["date"]
            e["reportingDate"] = clamp(v["date"])
            e["amount"] = v["amount"]
            e["vat"] = v.get("vat") or 0
            e["currency"] = v.get("currency", "ILS")
            if v.get("paymentType") is not None:
                e["paymentType"] = v["paymentType"]
            if v.get("note"):
                e["description"] = v["note"][:1000]
            if not apply:
                print(f"  [{nn}] {v['name'][:24]:24} tax={e['supplier'].get('taxId'):>10} "
                      f"num={e['number']:>12} date={e['date']} amt={e['amount']} vat={e['vat']} "
                      f"rep={e['reportingDate']}")
                continue
            r = m.s.put(f"{BASE}/expenses/drafts/{did}", json={"expense": e}, timeout=60)
            if r.status_code < 300:
                log["ok"].append(nn)
                print(f"  [{nn}] OK", flush=True)
            else:
                log["fail"].append({"nn": nn, "code": r.status_code, "body": r.text[:200]})
                print(f"  [{nn}] FAIL {r.status_code} {r.text[:120]}", flush=True)
        except Exception as ex:
            log["fail"].append({"nn": nn, "err": str(ex)})
            print(f"  [{nn}] ERR {ex}", flush=True)
        time.sleep(0.35)
    if apply:
        json.dump(log, open("b4_write_log.json", "w"), ensure_ascii=False, indent=1)
        print(f"DONE ok={len(log['ok'])} fail={len(log['fail'])}")


if __name__ == "__main__":
    main()
