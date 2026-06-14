import json, re, glob, os, sys

OUT_DIR = "/home/user/KRISPIN/site/data/emails"

def slug(mid):
    return "m_" + re.sub(r'[^A-Za-z0-9]', '', mid or "")

def conv(raw):
    sender = raw.get("sender") or {}
    out = {
        "internetMessageId": raw.get("internetMessageId"),
        "subject": raw.get("subject"),
        "from": {"name": sender.get("name"), "address": sender.get("address")},
        "to": [{"name": r.get("name"), "address": r.get("address")} for r in (raw.get("toRecipients") or [])],
        "cc": [{"name": r.get("name"), "address": r.get("address")} for r in (raw.get("ccRecipients") or [])],
        "bcc": [{"name": r.get("name"), "address": r.get("address")} for r in (raw.get("bccRecipients") or [])],
        "sentDateTime": raw.get("sentDateTime"),
        "receivedDateTime": raw.get("receivedDateTime"),
        "bodyContentType": "html",
        "bodyHtml": (raw.get("body") or {}).get("content"),
        "bodyPreview": raw.get("bodyPreview"),
        "hasAttachments": raw.get("hasAttachments"),
        "attachments": [{"name": a.get("name"), "contentType": a.get("contentType"),
                         "size": a.get("size"), "isInline": a.get("isInline")}
                        for a in (raw.get("attachments") or [])],
        "webLink": raw.get("webLink"),
    }
    return out

for f in sorted(glob.glob(os.path.join(OUT_DIR, "_raw_*.json"))):
    with open(f, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = conv(raw)
    fn = os.path.join(OUT_DIR, slug(out["internetMessageId"]) + ".json")
    with open(fn, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    print(f"{out['sentDateTime']} | {out['subject']} | bodyHtml={len(out['bodyHtml'])} | {fn}")
