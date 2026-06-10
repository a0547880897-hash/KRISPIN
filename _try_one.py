import time,json,copy
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
def norm(s): return ''.join(c for c in str(s) if c.isdigit())
exps=[];p=1
while True:
    j=m.post('/expenses/search',{'page':p,'pageSize':100}).json(); exps+=j['items']
    if p>=j['pages']:break
    p+=1;time.sleep(0.03)
byn={}
for e in exps: byn.setdefault(norm(e.get('number')),[]).append(e)
e=[x for x in byn[norm('1757466')] if str(x.get('date'))[:10]=='2025-01-03'][0]; eid=e['id']
def rep():
    r=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    return r.get('status'), str(r.get('reportingDate'))[:10]
print("start:",rep())
TGT='2025-01-01'

# A) minimal partial: only reportingDate
r=m.s.put(f"{BASE}/expenses/{eid}",json={'expense':{'reportingDate':TGT}},timeout=60); time.sleep(0.6)
print("A minimal {reportingDate}:",r.status_code, rep(), r.text[:160])

# B) draft-style reconstructed minimal fields (supplier+classification as ids)
raw=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
d=raw.get('data') or {}; sup=(d.get('supplier') or {})
body={'expense':{
  'reportingDate':TGT,
  'date':raw.get('date'),
  'number':raw.get('number'),
  'amount':raw.get('amount'),
  'vat':raw.get('vat'),
  'currency':raw.get('currency'),
  'documentType':raw.get('documentType'),
  'paymentType':d.get('paymentType') or 11,
  'accountingClassificationId':(raw.get('accountingClassification') or {}).get('id'),
  'supplierId':sup.get('id'),
}}
r=m.s.put(f"{BASE}/expenses/{eid}",json=body,timeout=60); time.sleep(0.6)
print("B draft-style ids:",r.status_code, rep(), r.text[:160])

# C) open first (status->30), then minimal partial
ro=m.s.post(f"{BASE}/expenses/{eid}/open",timeout=60); time.sleep(0.5)
print("  open:",ro.status_code, rep())
r=m.s.put(f"{BASE}/expenses/{eid}",json={'expense':{'reportingDate':TGT}},timeout=60); time.sleep(0.6)
print("C open+minimal:",r.status_code, rep(), r.text[:160])

# restore status to 20 if needed (do NOT change rep)
st,rd=rep()
if st==30:
    m.s.post(f"{BASE}/expenses/{eid}/close",timeout=60); time.sleep(0.3)
    print("restored:",rep())
