"""Write the client-specified fields into each קופה קטנה - תגל electricity draft.

Per client instruction, every one of these 15 drafts is booked as:
  supplier             = קופה קטנה - תגל   (id c88ae1bd-... ; PCN: ספק קופה קטנה)
  payment method       = אחר               (paymentType 11)
  accounting class.    = חשמל              (id 53defdfe-...)
  number/date/amount/vat = read from the invoice
  reportingDate        = first-of-issue-month, clamped >= 2025-11-01
                         (invoices before Nov-2025 report as Nov-2025)

Read-modify-write per draft: preserves fileKey/fileHash/status (stays 10 = pending,
NEVER approved) and everything not explicitly set. Never approves, never deletes.

  python3 kk_chashmal_write.py            # dry-run (prints the plan)
  python3 kk_chashmal_write.py --apply
"""
import sys, json, time, copy
from morning_api import Morning, BASE

DATA = {r["nn"]: r for r in json.load(open("kk_chashmal_data.json", encoding="utf-8"))}
MAP = json.load(open("kk_chashmal_map.json", encoding="utf-8"))

SUP_ID = "c88ae1bd-049e-4971-85fe-b9b836894463"
SUP_NAME = "קופה קטנה - תגל"
PAYMENT_OTHER = 11           # אחר (verified: 34/38 of this supplier's expenses use 11)
DOCTYPE = 320                # חשבונית מס/קבלה ("קבלה/חשבונית מס")
CLS = {"id": "53defdfe-b554-4390-be74-88a6c95b6062", "title": "חשמל",
       "irsCode": 3590, "code": "3500", "key": "3590",
       "income": 100, "vat": 100, "mixed": 50}


def main():
    apply = "--apply" in sys.argv
    m = Morning(); m.authenticate()
    print("AUTH OK | mode =", "APPLY" if apply else "DRY-RUN", flush=True)
    log = {"ok": [], "fail": []}
    for nn in sorted(MAP):
        did = MAP[nn]
        v = DATA[nn]
        try:
            cur = m.get(f"/expenses/drafts/{did}").json()
            e = copy.deepcopy(cur.get("expense", cur))
            e["supplier"] = {"id": SUP_ID, "name": SUP_NAME, "country": "IL", "taxId": ""}
            e["documentType"] = DOCTYPE
            e["paymentType"] = PAYMENT_OTHER
            e["accountingClassification"] = dict(CLS)
            e["number"] = str(v["number"])
            e["date"] = v["date"]
            e["reportingDate"] = v["reportingDate"]
            e["amount"] = v["amount"]
            e["vat"] = v["vat"]
            e["currency"] = "ILS"
            if not apply:
                print(f"  [{nn}] {did[:8]} num={e['number']:>11} date={e['date']} "
                      f"rep={e['reportingDate']} amt={e['amount']:>8} vat={e['vat']:>7} "
                      f"pay={e['paymentType']} cls=חשמל sup={SUP_NAME}")
                continue
            r = m.s.put(f"{BASE}/expenses/drafts/{did}", json={"expense": e}, timeout=60)
            if r.status_code < 300:
                log["ok"].append(nn)
                print(f"  [{nn}] OK {did}", flush=True)
            else:
                log["fail"].append({"nn": nn, "id": did, "code": r.status_code, "body": r.text[:200]})
                print(f"  [{nn}] FAIL {r.status_code} {r.text[:160]}", flush=True)
        except Exception as ex:
            log["fail"].append({"nn": nn, "id": did, "err": str(ex)})
            print(f"  [{nn}] ERR {ex}", flush=True)
        time.sleep(0.35)
    if apply:
        json.dump(log, open("kk_chashmal_write_log.json", "w"), ensure_ascii=False, indent=1)
        print(f"\nDONE ok={len(log['ok'])} fail={len(log['fail'])}")
        if log["fail"]:
            print("FAILS:", json.dumps(log["fail"], ensure_ascii=False)[:600])
    else:
        missing = [r for r in DATA if r not in MAP]
        if missing:
            print("\n*** WARNING: these invoices have no mapped draft yet:", missing)
        print(f"\nDRY-RUN: would update {len(MAP)} drafts. Re-run with --apply.")


if __name__ == "__main__":
    main()
