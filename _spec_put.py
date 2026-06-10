import time,json,copy
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
def norm(s): return ''.join(c for c in str(s) if c.isdigit())
exps=[];p=1
while True:
    j=m.post('/expenses/search',{'page':p,'pageSize':100}).json(); exps+=j['items']
    if p>=j['pages']:break
    p+=1
byn={}
for e in exps: byn.setdefault(norm(e.get('number')),[]).append(e)
e=[x for x in byn[norm('1757466')] if str(x.get('date'))[:10]=='2025-01-03'][0]; eid=e['id']
def rep():
    r=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    return r.get('status'), str(r.get('reportingDate'))[:10]
print("start:",rep())
raw=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
d=raw.get('data') or {}; sup=(d.get('supplier') or {})
TGT='2025-01-01'
# spec-style FLAT body (no 'expense' wrapper)
body={
  'paymentType': d.get('paymentType', -1),
  'currency': raw.get('currency','ILS'),
  'currencyRate': raw.get('currencyRate',1),
  'vat': raw.get('vat'),
  'amount': raw.get('amount'),
  'amountExcludeVat': raw.get('amountExcludeVat'),
  'date': raw.get('date'),
  'reportingDate': TGT,
  'documentType': raw.get('documentType'),
  'number': raw.get('number'),
  'description': d.get('description',''),
  'supplier': sup,
  'accountingClassificationId': (raw.get('accountingClassification') or {}).get('id'),
}
r=m.s.put(f"{BASE}/expenses/{eid}",json=body,timeout=60); time.sleep(0.6)
print("FLAT body PUT:",r.status_code,"-> resp reportingDate:",r.json().get('reportingDate'))
print("readback:",rep())
