"""Write the full visual scan (scan_full.json) back to all pending drafts in Morning.

Read-modify-write per draft (preserves fileKey/hash/supplier.id; status stays 10).
Fills supplier name+taxId, number, date, reportingDate (clamped >=2025-11), amount,
vat, currency, accountingClassification.vat (deduction %: 25 for fuel/electricity).
Never approves. Skips the junk draft and credit notes (זיכוי) per client rule.
"""
import sys, json, time, re, copy
from morning_api import Morning, BASE

SCAN = "scan_full.json"
LOG = "full_update_log.json"
SKIP = {"20cefe06-1e7e-4ee4-80ff-6723586b3d3f"}  # junk draft


def clamp(date_str):
    m = re.search(r"(\d{4})-(\d{2})", str(date_str or ""))
    if not m:
        return "2025-11-01"
    fom = f"{m.group(1)}-{m.group(2)}-01"
    return fom if fom >= "2025-11-01" else "2025-11-01"


def deduct_pct(v):
    blob = f"{v.get('cls','')} {v.get('supplier','')} {v.get('note','')}"
    if "חשמל" in blob or "25%" in blob or any(k in blob for k in ["פז ","סונול","דלק ","דור אלון","דלקן"]):
        return 25
    return 100


def main():
    apply = "--apply" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else None
    full = json.load(open(SCAN, encoding="utf-8"))
    items = [(k, v) for k, v in full.items() if k not in SKIP and v.get("scanned") != "skip"]
    # do not enter credit notes (zikui)
    items = [(k, v) for k, v in items if "זיכוי" not in (v.get("cls","")+v.get("note",""))]
    if limit:
        items = items[:limit]
    print(f"to update: {len(items)} (credits & junk skipped)")
    if not apply:
        for k, v in items[:6]:
            print(" ", (v.get("supplier") or "")[:22], "| num", str(v.get("number"))[:14],
                  "| amt", v.get("amount"), "| vat", v.get("vat"), "| date", v.get("date"),
                  "| ded", deduct_pct(v))
        return
    m = Morning(); m.authenticate()
    log = {"ok": [], "fail": []}
    for i, (did, v) in enumerate(items, 1):
        try:
            cur = m.get(f"/expenses/drafts/{did}").json()
            e = copy.deepcopy(cur.get("expense", cur) if "expense" in cur else cur)
            e.setdefault("supplier", {}); e["supplier"] = dict(e["supplier"])
            if v.get("supplier"):
                e["supplier"]["name"] = v["supplier"][:100]
            if v.get("taxId"):
                e["supplier"]["taxId"] = str(v["taxId"])
            e["supplier"].setdefault("country", "IL")
            if v.get("number"):
                e["number"] = str(v["number"])[:50]
            if v.get("date"):
                e["date"] = v["date"]
                e["reportingDate"] = clamp(v["date"])
            if v.get("amount") is not None:
                e["amount"] = v["amount"]
                e["vat"] = v.get("vat") or 0
            if v.get("currency"):
                e["currency"] = v["currency"]
            ac = dict(e.get("accountingClassification") or {})
            if ac:
                ac["vat"] = deduct_pct(v); e["accountingClassification"] = ac
            r = m.s.put(f"{BASE}/expenses/drafts/{did}", json={"expense": e}, timeout=60)
            (log["ok"] if r.status_code < 300 else log["fail"]).append(
                did if r.status_code < 300 else {"id": did, "code": r.status_code, "body": r.text[:150]})
        except Exception as ex:
            log["fail"].append({"id": did, "err": str(ex)})
        if i % 25 == 0:
            print(f"  {i}/{len(items)} ok={len(log['ok'])} fail={len(log['fail'])}")
        time.sleep(0.32)
    json.dump(log, open(LOG, "w"), ensure_ascii=False, indent=1)
    print(f"DONE ok={len(log['ok'])} fail={len(log['fail'])}")
    if log["fail"][:3]:
        print("sample fails:", log["fail"][:3])


if __name__ == "__main__":
    main()
