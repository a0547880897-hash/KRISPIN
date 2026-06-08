"""Phase 2 — LIVE update of APPROVED expenses (Oct 2025 .. Apr 2026).

Independent, document-based values come from expenses_scan.json (my visual /
document reads) plus phase2_supplement.json (the few not previously covered).
We do read-modify-write on PUT /expenses/{id} (flat body), correcting:
  * VAT: 18% for Israeli tax invoices, 0 for foreign/no-VAT (trusts the scanned
    vat sign: scan vat>0 -> recompute 18%, scan vat==0 -> 0).
  * reportingDate: first-of-month(doc date), clamped to >= 2025-11-01.
  * accountingClassification.vat (deduction %): 100 default; fuel/electricity 25.
  * amount/number/date from the scan.
Status is preserved (closed expenses stay closed). Nothing is approved/deleted.

Processed newest->oldest in batches (default 50):
  python3 phase2_update.py            # dry-run
  python3 phase2_update.py --apply [--batch 50] [--offset 0]
"""
import sys, json, time, re, copy
from morning_api import Morning, BASE

RAW = "expenses_raw.json"
SCAN = "expenses_scan.json"
SUP = "phase2_supplement.json"
LOG = "phase2_log.json"
PLAN = "phase2_plan.json"

FOREIGN = ["Meta","פייסבוק","Facebook","Amazon","Zoom","Cleverbridge","Topaz","JUST EAT","Paddle",
    "Lemon","Google","Apple","Wix","Anthropic","Midjourney","Suno","Envato","Vyond","GoAnimate",
    "monday","Renderforest","Elbruz","Ideogram","Runway","Wistia","Genspark","ManyChat","Manychat",
    "MainFunc","Manus","Lovable","GoFullPage","Bitdefender","CapCut","PIPO","Grammarly","PandaDoc",
    "Canva","DigitalOcean","OpenAI","Adobe","Dropbox","Microsoft","PYROGSS","GLAMOUROSA","Levski",
    "EA ","Electronic Arts","Steam","PlayStation","Spotify","Netflix","Telegram","Booking","x.ai","Grok","xAI"]
FUEL = ["פז חברת נפט","פז ","סונול","דלק ","דלקן","דור אלון","delek","sonol","paz"]
ELEC = ["חברת חשמל","אלקטרה פאוור","סופר פאוור"]
ELEC_NOT = ["יבואן","מחסני","מוצרי","צארומי","STARK"]


def fnum(v):
    try:
        return round(float(v), 2)
    except Exception:
        return None


def clamp_reporting(date_str):
    m = re.search(r"(\d{4})-(\d{2})", str(date_str or ""))
    if not m:
        return "2025-11-01"
    fom = f"{m.group(1)}-{m.group(2)}-01"
    return fom if fom >= "2025-11-01" else "2025-11-01"


def resolve(eid, s, live_dt):
    name = s.get("supplier") or ""
    amount = fnum(s.get("amount"))
    currency = s.get("currency") or "ILS"
    vat_scan = fnum(s.get("vat"))
    pcn = s.get("pcn") or ""
    date = str(s.get("date") or "")[:10]
    is_hebrew = bool(re.search(r"[֐-׿]", name))

    has_vat = True
    if currency != "ILS":
        has_vat = False
    elif any(k in name for k in FOREIGN):
        has_vat = False
    elif "ללא מע" in pcn or "לא נכלל" in pcn or "חו\"ל" in pcn or "נדרשת חשבונית" in pcn:
        has_vat = False
    elif (vat_scan or 0) > 0:
        has_vat = True
    elif live_dt in (300, 305, 320) and is_hebrew and (vat_scan or 0) == 0:
        # Hebrew tax invoice scanned without explicit vat -> still carries VAT
        has_vat = True
    else:
        has_vat = False
    vat = round(amount * 18 / 118, 2) if (has_vat and amount) else 0

    is_fuel = any(k in name for k in FUEL)
    is_elec = any(k in name for k in ELEC) and not any(x in name for x in ELEC_NOT)
    deduct = 25 if (has_vat and (is_fuel or is_elec)) else 100

    return {"id": eid, "name": name, "number": str(s.get("number") or ""), "date": date,
            "reportingDate": clamp_reporting(date), "amount": amount, "vat": vat,
            "vat_scan": vat_scan, "currency": currency, "deduct": deduct,
            "method": s.get("method"), "doubt": s.get("doubt", "")}


def main():
    apply = "--apply" in sys.argv
    batch = int(sys.argv[sys.argv.index("--batch") + 1]) if "--batch" in sys.argv else 50
    offset = int(sys.argv[sys.argv.index("--offset") + 1]) if "--offset" in sys.argv else 0

    raw = json.load(open(RAW, encoding="utf-8"))
    items = {e["id"]: e for e in (raw if isinstance(raw, list) else list(raw.values()))}
    scan = json.load(open(SCAN, encoding="utf-8"))
    sup = json.load(open(SUP, encoding="utf-8"))
    scan = {**scan, **sup}

    scope = [e for e in items.values() if "2025-10" <= str(e.get("date") or "")[:7] <= "2026-04"]
    scope.sort(key=lambda e: str(e.get("date") or ""), reverse=True)  # newest first

    plans = []
    for e in scope:
        s = scan.get(e["id"])
        if not s:
            plans.append({"id": e["id"], "name": "(no scan)", "skip": True})
            continue
        p = resolve(e["id"], s, e.get("documentType"))
        plans.append(p)
    json.dump(plans, open(PLAN, "w"), ensure_ascii=False, indent=1)

    vat_fixed = sum(1 for p in plans if not p.get("skip") and (p["vat_scan"] or 0) != p["vat"])
    print(f"scope={len(scope)} | planned={sum(1 for p in plans if not p.get('skip'))} | "
          f"vat changed={vat_fixed} | deduct25={sum(1 for p in plans if p.get('deduct')==25)} | "
          f"no-scan={sum(1 for p in plans if p.get('skip'))}")
    sel = [p for p in plans if not p.get("skip")][offset:offset + batch] if apply else plans[:6]
    if not apply:
        for p in plans[:8]:
            if p.get("skip"):
                print("  SKIP", p["id"][:8]); continue
            print(f"  {p['name'][:22]:22} num {str(p['number'])[:12]:12} amt {p['amount']} "
                  f"vat {p['vat']} (scan {p['vat_scan']}) rep {p['reportingDate']} ded {p['deduct']}")
        print(f"-- to apply use --apply (batch={batch}); newest->oldest --")
        return

    m = Morning(); m.authenticate()
    log = {"ok": [], "fail": []}
    print(f"applying offset={offset} batch={batch} ({len(sel)} docs)")
    for i, p in enumerate(sel, 1):
        try:
            e = m.get(f"/expenses/{p['id']}").json()
            body = copy.deepcopy(e.get("expense", e) if "expense" in e else e)
            if p["amount"] is not None:
                body["amount"] = p["amount"]
            if p["number"]:
                body["number"] = p["number"]
            if p["date"]:
                body["date"] = p["date"]
            body["reportingDate"] = p["reportingDate"]
            body["vat"] = p["vat"]
            body["currency"] = p["currency"]
            ac = dict(body.get("accountingClassification") or {})
            if ac:
                ac["vat"] = p["deduct"]
                body["accountingClassification"] = ac
            r = m.s.put(f"{BASE}/expenses/{p['id']}", json=body, timeout=60)
            (log["ok"] if r.status_code < 300 else log["fail"]).append(
                p["id"] if r.status_code < 300 else {"id": p["id"], "code": r.status_code, "body": r.text[:160]})
        except Exception as ex:
            log["fail"].append({"id": p["id"], "err": str(ex)})
        if i % 10 == 0:
            print(f"  {i}/{len(sel)} ok={len(log['ok'])} fail={len(log['fail'])}")
        time.sleep(0.35)
    # merge log across batches
    try:
        old = json.load(open(LOG))
    except Exception:
        old = {"ok": [], "fail": []}
    old["ok"] += log["ok"]; old["fail"] += log["fail"]
    json.dump(old, open(LOG, "w"), ensure_ascii=False, indent=1)
    print(f"BATCH done ok={len(log['ok'])} fail={len(log['fail'])} | total ok={len(old['ok'])} fail={len(old['fail'])}")


if __name__ == "__main__":
    main()
