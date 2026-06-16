#!/usr/bin/env python3
"""Assemble per-email JSON files into a single self-contained legal-review app.

For each message it computes:
  - direction (sent/received) relative to the mailbox owner
  - a normalised subject used as the conversation-thread key
  - the "new" body (quoted reply history stripped) plus the full original body
  - an in-reply-to reference (the previous message in the same thread)
  - a YYYY-MM month bucket
and injects everything into app.template.html -> index.html.
"""
import json, glob, os, re, html

HERE = os.path.dirname(os.path.abspath(__file__))
EMAILS_DIR = os.path.join(HERE, "data", "emails")
TEMPLATE = os.path.join(HERE, "app.template.html")
OUT = os.path.join(HERE, "index.html")

OWNER = "hen@ak-adv.co.il"
TARGETS = {"yossi@shilansky.co.il", "yossi@yossidror.co.il"}


def addr(x):
    return (x or "").strip().lower()


def in_scope(msg):
    people = [addr((msg.get("from") or {}).get("address"))]
    for key in ("to", "cc", "bcc"):
        for r in (msg.get(key) or []):
            people.append(addr(r.get("address")))
    return any(p in TARGETS for p in people)


def norm_subject(s):
    s = s or ""
    s = re.sub(r"[‎‏‪-‮⁦-⁩]", "", s)  # bidi marks
    # strip leading RE:/FW:/FWD: (Hebrew mail keeps English prefixes), repeatedly
    while True:
        s2 = re.sub(r"^\s*(re|fw|fwd|תגובה|הועבר)\s*:\s*", "", s, flags=re.IGNORECASE)
        if s2 == s:
            break
        s = s2
    return re.sub(r"\s+", " ", s).strip().lower()


def dequote(body):
    """Return (new_body_html, was_cut). Cuts at the first quoted-reply boundary."""
    if not body:
        return body, False
    low = body.lower()
    idxs = []
    for pat in ['id="appendonsend"', 'border-top:solid #e1e1e1', '<hr',
                '<b>from:', '<b>מאת:', 'from:</b>', 'מאת:</b>',
                '<b>from</b>', '<b>מאת</b>']:
        i = low.find(pat)
        if i != -1:
            idxs.append(i)
    m = re.search(r"_{20,}", body)
    if m:
        idxs.append(m.start())
    idxs = [i for i in idxs if i > 40]
    if not idxs:
        return body, False
    cut = min(idxs)
    back = body.rfind("<", 0, cut)   # trim to the start of the boundary tag
    if back > 40:
        cut = back
    return body[:cut], True


def main():
    by_id = {}
    for fp in glob.glob(os.path.join(EMAILS_DIR, "*.json")):
        try:
            with open(fp, encoding="utf-8") as fh:
                msg = json.load(fh)
        except Exception as e:
            print("WARN bad json", fp, e)
            continue
        mid = msg.get("internetMessageId") or os.path.basename(fp)
        if mid in by_id:
            cur = by_id[mid]
            cs = (1 if (cur.get("from") or {}).get("address") else 0, len(cur.get("bodyHtml") or ""))
            ns = (1 if (msg.get("from") or {}).get("address") else 0, len(msg.get("bodyHtml") or ""))
            if ns <= cs:
                continue
        by_id[mid] = msg

    msgs = []
    for mid, msg in by_id.items():
        if not in_scope(msg):
            continue
        f = msg.get("from") or {}
        direction = "sent" if addr(f.get("address")) == OWNER else "received"
        date = msg.get("sentDateTime") or msg.get("receivedDateTime") or ""
        full = msg.get("bodyHtml") or ("<pre>" + html.escape(msg.get("bodyPreview") or "") + "</pre>")
        new, cut = dequote(full)
        atts = msg.get("attachments") or []
        msgs.append({
            "id": mid,
            "subject": (msg.get("subject") or "(ללא נושא)").strip(),
            "subjectBase": norm_subject(msg.get("subject")),
            "from": {"name": f.get("name") or "", "address": f.get("address") or ""},
            "to": [{"name": r.get("name") or "", "address": r.get("address") or ""} for r in (msg.get("to") or [])],
            "cc": [{"name": r.get("name") or "", "address": r.get("address") or ""} for r in (msg.get("cc") or [])],
            "date": date,
            "month": date[:7],
            "direction": direction,
            "bodyNew": new,
            "bodyFull": full,
            "wasCut": cut,
            "attachments": [{"name": a.get("name"), "contentType": a.get("contentType"),
                             "size": a.get("size"), "isInline": a.get("isInline")} for a in atts],
            "webLink": msg.get("webLink") or "",
        })

    msgs.sort(key=lambda m: m["date"])

    # thread ids by first-appearance of normalised subject + in-reply-to (prev in thread)
    thread_ids, order = {}, []
    for m in msgs:
        k = m["subjectBase"]
        if k not in thread_ids:
            thread_ids[k] = len(thread_ids) + 1
            order.append(k)
        m["threadId"] = thread_ids[k]
    last_in_thread = {}
    for m in msgs:
        prev = last_in_thread.get(m["threadId"])
        if prev:
            m["inReplyTo"] = {"from": prev["from"], "date": prev["date"], "direction": prev["direction"]}
        else:
            m["inReplyTo"] = None
        last_in_thread[m["threadId"]] = m

    with open(TEMPLATE, encoding="utf-8") as fh:
        tpl = fh.read()
    payload = json.dumps(msgs, ensure_ascii=False).replace("</", "<\\/")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(tpl.replace("/*__DATA__*/", payload))

    sent = sum(1 for m in msgs if m["direction"] == "sent")
    print(f"in_scope={len(msgs)} sent={sent} received={len(msgs)-sent} threads={len(thread_ids)} "
          f"dequoted={sum(1 for m in msgs if m['wasCut'])}")
    print("range:", msgs[0]["date"], "->", msgs[-1]["date"])


if __name__ == "__main__":
    main()
