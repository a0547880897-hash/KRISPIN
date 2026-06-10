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
e=byn[norm('1757466')][0]; eid=e['id']
def rep():
    r=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    return r.get('status'), str(r.get('reportingDate'))[:10], r
print("start:",rep()[:2])
def setrep(d):
    st,rd,raw=rep(); ee=copy.deepcopy(raw); ee['reportingDate']=d
    r=m.s.put(f"{BASE}/expenses/{eid}",json={'expense':ee},timeout=60); time.sleep(0.6)
    return r.status_code, rep()[:2]
for tgt in ['2025-12-01','2026-01-01','2025-09-01','2025-01-01','2025-11-01']:
    print(f"set {tgt}:", setrep(tgt))
print("FINAL:",rep()[:2])
