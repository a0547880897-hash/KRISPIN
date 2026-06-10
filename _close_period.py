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
e=[x for x in byn[norm('1757466')] if str(x.get('date'))[:10]=='2025-01-03'][0]; eid=e['id']
def rep():
    r=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    return r.get('status'), str(r.get('reportingDate'))[:10]
print("start:",rep())
TGT='2025-01-01'
# open -> status 30
print("open:", m.s.post(f"{BASE}/expenses/{eid}/open",timeout=60).status_code); time.sleep(0.5)
print(" now:",rep())
# try close with various period body keys
for body in [{'reportingDate':TGT},{'reportDate':TGT},{'period':TGT},{'date':TGT},{'reportingDate':TGT,'expense':{'reportingDate':TGT}}]:
    r=m.s.post(f"{BASE}/expenses/{eid}/close",json=body,timeout=60); time.sleep(0.5)
    st,rd=rep()
    print(f"close {list(body.keys())}: {r.status_code} -> status={st} rep={rd}")
    if st==30: continue
    # reopen for next test
    if rd!='2025-11-01':
        print("   *** CHANGED! ***"); break
    m.s.post(f"{BASE}/expenses/{eid}/open",timeout=60); time.sleep(0.4)
# ensure final status 20
st,rd=rep()
if st==30: m.s.post(f"{BASE}/expenses/{eid}/close",timeout=60); time.sleep(0.3)
print("FINAL:",rep())
