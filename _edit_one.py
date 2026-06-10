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

# STEP 1: open to manual-open (status 30)
r=m.s.post(f"{BASE}/expenses/{eid}/open",timeout=60); time.sleep(0.5)
print("after open:",r.status_code, rep()[:2])

# STEP 2: PUT full object with reportingDate AND data.reportingDate, confirmFromEdit
st,rd,raw=rep()
ee=copy.deepcopy(raw)
ee['reportingDate']='2025-01-01'
if isinstance(ee.get('data'),dict):
    ee['data']['reportingDate']='2025-01-01'
ee['confirmFromEdit']=True
r=m.s.put(f"{BASE}/expenses/{eid}",json={'expense':ee},timeout=60); time.sleep(0.6)
print("after PUT(rep+data+confirmFromEdit):",r.status_code, rep()[:2])

# STEP 3: try PUT again without confirm, plain
st,rd,raw=rep()
ee=copy.deepcopy(raw); ee['reportingDate']='2025-01-01'
r=m.s.put(f"{BASE}/expenses/{eid}",json={'expense':ee},timeout=60); time.sleep(0.6)
print("after PUT(plain status30):",r.status_code, rep()[:2])

# restore: close back to 20 if we left it at 30
st,_,_=rep()
if st==30:
    rc=m.s.post(f"{BASE}/expenses/{eid}/close",timeout=60); time.sleep(0.3)
    print("restored close:",rc.status_code, rep()[:2])
