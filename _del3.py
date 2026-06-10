import time
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
TARGETS=[("54589216188",None),("02160",None),("55316689","2025-03-01")]
for num,datef in TARGETS:
    cand=byn.get(norm(num),[])
    if datef: cand=[e for e in cand if str(e.get('date'))[:10]==datef]
    if not cand:
        print(f"{num}: כבר לא קיים (נמחק)"); continue
    for e in cand:
        eid=e['id']
        if e.get('status')==20:
            m.s.post(f"{BASE}/expenses/{eid}/open",timeout=60); time.sleep(0.4)
        r=m.s.delete(f"{BASE}/expenses/{eid}",timeout=60); time.sleep(0.4)
        print(f"{num} date={str(e.get('date'))[:10]} amt={e.get('amount')}: delete -> {r.status_code}")
