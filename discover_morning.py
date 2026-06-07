"""Discovery: authenticate to Morning and locate the expense-drafts endpoint.

Run this FIRST in a session that has network access to api.greeninvoice.co.il.
It authenticates, then probes several candidate endpoints for the
"pending approval" expense drafts, printing status + a sample so we can
lock the exact endpoint and field names before bulk download.
"""
import json
from morning_api import Morning

m = Morning()
info = m.authenticate()
print("AUTH OK. token expires:", info.get("expires"))
print("=" * 60)

# Candidate endpoints to probe. Morning groups: expenses, expense drafts.
# We try GET and POST(search) shapes. The real one returns paged results.
search_body = {"page": 1, "pageSize": 5}
candidates = [
    ("POST", "/expenses/drafts/search", search_body),
    ("POST", "/expense_drafts/search", search_body),
    ("POST", "/expenses/search", {**search_body, "status": [0]}),
    ("POST", "/expenses/search", search_body),
    ("GET", "/expenses/drafts", None),
    ("GET", "/expense_drafts", None),
    ("POST", "/expenses/drafts", search_body),
]

for method, path, body in candidates:
    try:
        r = m.post(path, body) if method == "POST" else m.get(path)
        snippet = r.text[:400].replace("\n", " ")
        print(f"[{r.status_code}] {method} {path} :: {snippet}")
        if r.status_code == 200:
            try:
                data = r.json()
                total = data.get("total") if isinstance(data, dict) else None
                print(f"      -> total={total} keys={list(data)[:8] if isinstance(data, dict) else type(data)}")
            except Exception:
                pass
    except Exception as e:
        print(f"[ERR] {method} {path} :: {repr(e)[:160]}")
    print("-" * 60)

print("\nNext: pick the endpoint that returns ~441 pending drafts, then build download_drafts.py")
