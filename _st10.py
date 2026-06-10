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
e=[x for x in byn[norm('113997')] if str(x.get('date'))[:10]=='2025-03-05'][0]; eid=e['id']
def rep():
    r=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    return r.get('status'), str(r.get('reportingDate'))[:10]
print("start (113997, expect st10):",rep())
TGT='2025-09-01'
for label,body in [("minimal",{'expense':{'reportingDate':TGT}})]:
    r=m.s.put(f"{BASE}/expenses/{eid}",json=body,timeout=60); time.sleep(0.6)
    print(f"PUT {label}: {r.status_code} -> {rep()}")
    print("   resp reportingDate:", r.json().get('reportingDate'))
