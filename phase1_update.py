"""Phase 1 — LIVE update of all pending expense drafts in Morning.

Read-modify-write: for each draft we GET the current expense object, overlay only
the corrected fields (so fileKey/fileHash/supplier.id/documentType/paymentType are
preserved), and PUT it back nested as {"expense": {...}}.  Status is left at 10
(pending approval) — we NEVER approve and NEVER delete (except fully-confirmed
exact duplicates, with --delete-dups).

Field rules (per client):
  * VAT: Israeli tax invoice -> vat = amount*18/118; foreign / no-VAT doc -> 0.
         Trigger = VAT was detected (override vat>0, else Morning vat>0), gated by
         ILS currency + non-foreign supplier + not a donation/no-VAT class.
  * reportingDate: first-of-month(document date), clamped to >= 2025-11-01.
  * accountingClassification.vat (deduction %): 100 default; FUEL & ELECTRICITY 25.
  * supplier name+taxId, number, date, amount: from verified catalog/overrides.

Usage:
  python3 phase1_update.py            # dry-run, writes phase1_plan.json
  python3 phase1_update.py --apply [--limit N] [--delete-dups]
"""
import sys, json, time, re
from morning_api import Morning, BASE

LIVE = "drafts_live.json"
RAW = "catalog_raw.json"
OV = "manual_overrides.json"
PLAN = "phase1_plan.json"
LOG = "phase1_log.json"

# never touch these
SKIP = {
    "20cefe06-1e7e-4ee4-80ff-6723586b3d3f",  # junk draft I created by mistake
    "42770546-f0bd-4edf-b444-8fc6de92f14c",  # Elbruz refund, 0 GBP
    "4e33949a-4181-4895-b0a5-226d57ac61a0",  # credit/refund -99 USD (זיכוי)
}

FOREIGN = ["Meta","פייסבוק","Facebook","Amazon","Zoom","Cleverbridge","Topaz","JUST EAT","Paddle",
    "Lemon","Google","Apple","Wix","Anthropic","Midjourney","Suno","Envato","Vyond","GoAnimate",
    "monday","Renderforest","Elbruz","Ideogram","Runway","Wistia","Genspark","ManyChat","Manychat",
    "MainFunc","Manus","Lovable","GoFullPage","Bitdefender","CapCut","PIPO","Grammarly","PandaDoc",
    "Canva","DigitalOcean","OpenAI","Adobe","Dropbox","Microsoft","PYROGSS","GLAMOUROSA","Levski",
    "EA ","Electronic Arts","Steam","PlayStation","Spotify","Netflix","Telegram","Booking"]

# Fuel stations (vehicle fuel -> 25% VAT deduction). Avoid ambiguous bare words.
FUEL = ["פז חברת נפט","פז ","סונול","דלק ","דלקן","דור אלון","delek","sonol","paz","ten דלק"]
# Electricity UTILITY suppliers only (consumption -> 25%). NOT electrical-goods
# importers/retailers (יבואן/מחסני/מוצרי חשמל) which are normal 100% purchases.
ELEC = ["חברת חשמל","אלקטרה פאוור","סופר פאוור"]
ELEC_NOT = ["יבואן","מחסני","מוצרי","צארומי","STARK"]

OV_KEYMAP = {"sup":"sup","tax":"tax","num":"num","date":"date","amt":"amount","vat":"vat","cur":"cur"}


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


def resolve(it, raw, ov):
    """Final corrected values for one live draft."""
    e = it.get("expense", {}) or {}
    sup = e.get("supplier", {}) or {}
    o = ov.get(it["id"], {})
    rraw = raw.get(it["id"], {})
    rexp = rraw.get("expense", {}) if rraw else {}
    # prediction date (for non-overridden docs)
    pred_date = None
    for f in (rexp.get("prediction", {}) or {}).get("fields", []):
        if f.get("field") == "date":
            pred_date = f.get("value")

    name = o["sup"][0] if "sup" in o else sup.get("name", "")
    taxId = o["tax"][0] if "tax" in o else (sup.get("taxId") or "")
    number = o["num"][0] if "num" in o else (e.get("number") or "")
    date = o["date"][0] if "date" in o else (pred_date or (e.get("reportingDate") or "")[:10])
    amount = fnum(o["amt"][0]) if "amt" in o else fnum(e.get("amount"))
    currency = o["cur"][0] if "cur" in o else (e.get("currency") or "ILS")
    vat_orig = fnum(o["vat"][0]) if "vat" in o else fnum(e.get("vat"))
    cls = o.get("cls", "")
    dtype = e.get("documentType")

    # --- VAT determination ---
    # Overrides are authoritative: if I verified vat (incl. 0 for Eilat/exempt),
    # trust its sign. Otherwise a Hebrew-vendor tax invoice (חשבונית מס) carries
    # VAT even when Morning recorded 0; ambiguous docs stay 0 (claim less).
    is_hebrew = bool(re.search(r"[֐-׿]", name or ""))
    has_vat = True
    if currency != "ILS":
        has_vat = False
    elif any(k in (name or "") for k in FOREIGN):
        has_vat = False
    elif dtype in (405,):  # donation receipt
        has_vat = False
    elif "ללא מע" in cls or "לא נכלל" in cls or "חו\"ל" in cls:
        has_vat = False
    elif "vat" in o:                       # verified override -> trust its sign
        has_vat = (vat_orig or 0) > 0
    elif (vat_orig or 0) > 0:              # Morning detected VAT
        has_vat = True
    elif dtype in (300, 305, 320) and is_hebrew:  # Hebrew tax invoice w/o vat -> add 18%
        has_vat = True
    else:
        has_vat = False
    vat = round(amount * 18 / 118, 2) if (has_vat and amount) else 0

    # --- deduction % ---
    nm = name or ""
    is_fuel = any(k in nm for k in FUEL)
    is_elec = any(k in nm for k in ELEC) and not any(x in nm for x in ELEC_NOT)
    deduct = 25 if (has_vat and (is_fuel or is_elec)) else 100

    return {
        "id": it["id"], "name": name, "taxId": str(taxId or ""), "number": str(number or ""),
        "date": (date or "")[:10], "reportingDate": clamp_reporting(date or e.get("reportingDate")),
        "amount": amount, "vat": vat, "vat_orig": vat_orig, "currency": currency,
        "deduct": deduct, "dtype": dtype, "overridden": bool(o),
    }


def sig(p):
    t = re.sub(r"\D", "", p["taxId"] or "")
    n = re.sub(r"\W", "", p["number"] or "").lower()
    if n and len(n) >= 5 and p["name"] and p["name"] != "כללי" and p["amount"]:
        return f"{n}|{round(p['amount'],2)}|{(p['name'] or '')[:14]}"
    return None


def build_body(m, did, p):
    """GET fresh draft, overlay corrected fields, return nested body."""
    cur = m.get(f"/expenses/drafts/{did}").json()
    e = cur.get("expense", cur) if "expense" in cur else cur
    e = dict(e)
    e.setdefault("supplier", {})
    e["supplier"] = dict(e["supplier"])
    e["supplier"]["name"] = p["name"]
    if p["taxId"]:
        e["supplier"]["taxId"] = p["taxId"]
    e["supplier"].setdefault("country", "IL")
    if p["number"]:
        e["number"] = p["number"]
    if p["date"]:
        e["date"] = p["date"]
    e["reportingDate"] = p["reportingDate"]
    if p["amount"] is not None:
        e["amount"] = p["amount"]
    e["vat"] = p["vat"]
    e["currency"] = p["currency"]
    ac = dict(e.get("accountingClassification") or {})
    if ac:
        ac["vat"] = p["deduct"]
        e["accountingClassification"] = ac
    return {"expense": e}


def main():
    apply = "--apply" in sys.argv
    deldups = "--delete-dups" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    live = json.load(open(LIVE, encoding="utf-8"))
    raw = json.load(open(RAW, encoding="utf-8"))
    ovall = json.load(open(OV, encoding="utf-8"))
    ov = {k: v for k, v in ovall.items() if not k.startswith("_")}

    plans = []
    for it in live:
        if it["id"] in SKIP:
            continue
        plans.append(resolve(it, raw, ov))

    # duplicate detection (strict)
    by_sig = {}
    for p in plans:
        s = sig(p)
        if s:
            by_sig.setdefault(s, []).append(p)
    dups = {s: ps for s, ps in by_sig.items() if len(ps) > 1}
    # keep earliest creationDate -> need creationDate; map id->creation
    cdate = {it["id"]: it.get("creationDate", 0) for it in live}
    to_delete = []
    for s, ps in dups.items():
        ps_sorted = sorted(ps, key=lambda p: cdate.get(p["id"], 0))
        for extra in ps_sorted[1:]:
            to_delete.append({"sig": s, "id": extra["id"], "name": extra["name"],
                              "number": extra["number"], "amount": extra["amount"],
                              "kept": ps_sorted[0]["id"]})

    vat_fixed = sum(1 for p in plans if (p["vat_orig"] or 0) != p["vat"])
    json.dump({"plans": plans, "dups": to_delete}, open(PLAN, "w"), ensure_ascii=False, indent=1)
    print(f"plans={len(plans)} | vat recomputed/changed={vat_fixed} | "
          f"deduct25={sum(1 for p in plans if p['deduct']==25)} | "
          f"exact-dup-groups={len(dups)} | drafts-to-delete={len(to_delete)}")
    if not apply:
        print("DRY-RUN. wrote", PLAN, "- sample:")
        for p in plans[:5]:
            print(" ", p["name"][:24], "| num", p["number"][:14], "| amt", p["amount"],
                  "| vat", p["vat"], "(was", p["vat_orig"], ")| rep", p["reportingDate"], "| ded", p["deduct"])
        if to_delete:
            print("DUP delete candidates:")
            for d in to_delete:
                print("  DEL", d["id"], d["name"][:20], d["number"], d["amount"], "(keep", d["kept"], ")")
        return

    m = Morning(); m.authenticate()
    log = {"ok": [], "fail": [], "deleted": [], "deldfail": []}
    todo = plans[:limit] if limit else plans
    for i, p in enumerate(todo, 1):
        try:
            body = build_body(m, p["id"], p)
            r = m.s.put(f"{BASE}/expenses/drafts/{p['id']}", json=body, timeout=60)
            if r.status_code < 300:
                log["ok"].append(p["id"])
            else:
                log["fail"].append({"id": p["id"], "code": r.status_code, "body": r.text[:200]})
        except Exception as ex:
            log["fail"].append({"id": p["id"], "err": str(ex)})
        if i % 25 == 0:
            print(f"  {i}/{len(todo)} ok={len(log['ok'])} fail={len(log['fail'])}")
        time.sleep(0.35)
    if deldups:
        for d in to_delete:
            try:
                r = m.s.delete(f"{BASE}/expenses/drafts/{d['id']}", timeout=60)
                (log["deleted"] if r.status_code < 300 else log["deldfail"]).append(
                    {**d, "code": r.status_code})
            except Exception as ex:
                log["deldfail"].append({**d, "err": str(ex)})
            time.sleep(0.35)
    json.dump(log, open(LOG, "w"), ensure_ascii=False, indent=1)
    print(f"APPLIED ok={len(log['ok'])} fail={len(log['fail'])} "
          f"deleted={len(log['deleted'])} deldfail={len(log['deldfail'])}")


if __name__ == "__main__":
    main()
