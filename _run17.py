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
# (number, date, target) — 17 remaining (1757466 & 11111 already done)
ACT=[
 ("5991","2024-07-21","2025-01-01"),
 ("10108463387","2025-01-23","2025-01-01"),
 ("70848300","2025-02-26","2025-02-01"),
 ("10508793106","2025-02-23","2025-02-01"),
 ("1099254","2025-02-18","2025-02-01"),
 ("M2501326582","2025-03-28","2025-09-01"),
 ("1044","2025-03-27","2025-09-01"),
 ("70863709","2025-03-26","2025-09-01"),
 ("10908089370","2025-03-23","2025-09-01"),
 ("55316689","2025-03-23","2025-09-01"),
 ("113997","2025-03-05","2025-09-01"),
 ("M2501800626","2025-04-28","2025-10-01"),
 ("70879808","2025-04-26","2025-10-01"),
 ("10609465031","2025-04-23","2025-10-01"),
 ("2147","2025-04-22","2025-10-01"),
 ("INT-0002","2025-04-06","2025-10-01"),
 ("55354348","2025-04-01","2025-10-01"),
]
def put_rep(e,tgt):
    eid=e['id']
    raw=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    d=raw.get('data') or {}; sup=(d.get('supplier') or {})
    body={'paymentType':d.get('paymentType',-1),'currency':raw.get('currency','ILS'),
     'currencyRate':raw.get('currencyRate',1),'vat':raw.get('vat'),'amount':raw.get('amount'),
     'amountExcludeVat':raw.get('amountExcludeVat'),'date':raw.get('date'),'reportingDate':tgt,
     'documentType':raw.get('documentType'),'number':raw.get('number'),
     'description':d.get('description',''),'supplier':sup,
     'accountingClassificationId':(raw.get('accountingClassification') or {}).get('id')}
    r=m.s.put(f"{BASE}/expenses/{eid}",json=body,timeout=60); time.sleep(0.6)
    chk=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    return r.status_code, str(chk.get('reportingDate'))[:10]
log=[]
for num,dt,tgt in ACT:
    cand=[e for e in byn.get(norm(num),[]) if str(e.get('date'))[:10]==dt]
    if len(cand)!=1:
        log.append((num,dt,tgt,f"AMBIG/NOTFOUND ({len(cand)})")); print("!!",num,dt,len(cand)); continue
    sc,got=put_rep(cand[0],tgt)
    ok="OK" if got==tgt else "FAIL"
    log.append((num,dt,tgt,f"{sc} -> {got} {ok}"))
    print(f"  {num:14} {dt} -> {tgt}: {sc} got={got} {ok}")
json.dump(log,open('_run17_log.json','w'),ensure_ascii=False,indent=1)
okc=sum(1 for x in log if x[3].endswith('OK'))
print(f"\nDONE: {okc}/{len(ACT)} succeeded")
