#!/usr/bin/env python3
"""Assemble all per-email JSON files into a single self-contained index.html.

Reads site/data/emails/*.json (each written by the mail-gathering agents),
de-duplicates by internetMessageId, sorts chronologically, classifies each
message as sent/received relative to the mailbox owner, and injects the data
into index.template.html -> index.html.
"""
import json
import glob
import os
import re
import html

HERE = os.path.dirname(os.path.abspath(__file__))
EMAILS_DIR = os.path.join(HERE, "data", "emails")
TEMPLATE = os.path.join(HERE, "index.template.html")
OUT = os.path.join(HERE, "index.html")

OWNER = "hen@ak-adv.co.il"
TARGETS = {"yossi@shilansky.co.il", "yossi@yossidror.co.il"}


def addr(x):
    return (x or "").strip().lower()


def in_scope(msg):
    """Keep only messages where one of the target addresses is sender or recipient."""
    people = []
    f = msg.get("from") or {}
    people.append(addr(f.get("address")))
    for key in ("to", "cc", "bcc"):
        for r in (msg.get(key) or []):
            people.append(addr(r.get("address")))
    return any(p in TARGETS for p in people)


def main():
    files = glob.glob(os.path.join(EMAILS_DIR, "*.json"))
    by_id = {}
    skipped = 0
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as fh:
                msg = json.load(fh)
        except Exception as e:
            print("WARN could not parse", fp, e)
            continue
        mid = msg.get("internetMessageId") or os.path.basename(fp)
        # de-dup: prefer the record that actually has a body
        if mid in by_id and len(by_id[mid].get("bodyHtml") or "") >= len(msg.get("bodyHtml") or ""):
            continue
        by_id[mid] = msg

    msgs = []
    for mid, msg in by_id.items():
        if not in_scope(msg):
            skipped += 1
            continue
        f = msg.get("from") or {}
        direction = "sent" if addr(f.get("address")) == OWNER else "received"
        date = msg.get("sentDateTime") or msg.get("receivedDateTime") or ""
        atts = [a for a in (msg.get("attachments") or [])]
        real_atts = [a for a in atts if not a.get("isInline")]
        msgs.append({
            "id": mid,
            "subject": (msg.get("subject") or "(ללא נושא)").strip(),
            "from": f,
            "to": msg.get("to") or [],
            "cc": msg.get("cc") or [],
            "date": date,
            "direction": direction,
            "bodyHtml": msg.get("bodyHtml") or ("<pre>" + html.escape(msg.get("bodyPreview") or "") + "</pre>"),
            "attachments": atts,
            "realAttachmentCount": len(real_atts),
            "webLink": msg.get("webLink") or "",
        })

    msgs.sort(key=lambda m: m["date"])

    with open(TEMPLATE, encoding="utf-8") as fh:
        tpl = fh.read()

    payload = json.dumps(msgs, ensure_ascii=False)
    out = tpl.replace("/*__DATA__*/", payload)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(out)

    sent = sum(1 for m in msgs if m["direction"] == "sent")
    recv = sum(1 for m in msgs if m["direction"] == "received")
    att = sum(m["realAttachmentCount"] for m in msgs)
    print(f"files={len(files)} unique={len(by_id)} in_scope={len(msgs)} skipped_out_of_scope={skipped}")
    print(f"sent={sent} received={recv} real_attachments={att}")
    if msgs:
        print("range:", msgs[0]["date"], "->", msgs[-1]["date"])


if __name__ == "__main__":
    main()
