import time,json
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
group=byn[norm('11111')]
print("=== כל 4 ההוצאות עם מספר 11111 (לפני) ===")
ids={}
for e in group:
    ids[e['id']]=(str(e.get('date'))[:10],e.get('amount'),str(e.get('reportingDate'))[:10])
    print(f"  date={str(e.get('date'))[:10]} amt={e.get('amount')} rep={str(e.get('reportingDate'))[:10]} id={e['id']}")
# target = date 2025-03-06 (יזמות אונליין 1199)
tgt=[e for e in group if str(e.get('date'))[:10]=='2025-03-06']
assert len(tgt)==1, f"expected 1 target got {len(tgt)}"
e=tgt[0]; eid=e['id']
raw=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
d=raw.get('data') or {}; sup=(d.get('supplier') or {})
body={
 'paymentType': d.get('paymentType',-1),
 'currency': raw.get('currency','ILS'),'currencyRate': raw.get('currencyRate',1),
 'vat': raw.get('vat'),'amount': raw.get('amount'),'amountExcludeVat': raw.get('amountExcludeVat'),
 'date': raw.get('date'),'reportingDate':'2025-09-01','documentType': raw.get('documentType'),
 'number': raw.get('number'),'description': d.get('description',''),'supplier': sup,
 'accountingClassificationId': (raw.get('accountingClassification') or {}).get('id'),
}
r=m.s.put(f"{BASE}/expenses/{eid}",json=body,timeout=60); time.sleep(1)
print("\nPUT ->",r.status_code,"resp reportingDate:",r.json().get('reportingDate'))
# verify all 4 by id
print("\n=== כל 4 ההוצאות עם 11111 (אחרי, GET ישיר לפי id) ===")
for theid,(dt,amt,oldrep) in ids.items():
    rr=m.s.get(f"{BASE}/expenses/{theid}",timeout=60).json()
    flag="  <== שונה" if theid==eid else ""
    print(f"  date={dt} amt={amt} rep_before={oldrep} rep_now={str(rr.get('reportingDate'))[:10]}{flag}")
# full data of target
print("\n=== נתונים מלאים של היעד (יזמות אונליין) ===")
t=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
print(json.dumps({k:t.get(k) for k in ['number','date','reportingDate','amount','vat','amountExcludeVat','currency','documentType','status','active']},ensure_ascii=False,indent=1))
print("supplier:",(t.get('data') or {}).get('supplier',{}).get('name'))
print("classification:",(t.get('accountingClassification') or {}).get('title'))
print("fileKey present:", bool((t.get('data') or {}).get('fileKey')))
