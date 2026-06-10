import json
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
def norm(s): return ''.join(c for c in str(s) if c.isdigit())
import time
exps=[];p=1
while True:
    j=m.post('/expenses/search',{'page':p,'pageSize':100}).json(); exps+=j['items']
    if p>=j['pages']:break
    p+=1
byn={}
for e in exps: byn.setdefault(norm(e.get('number')),[]).append(e)
e=[x for x in byn[norm('1757466')] if str(x.get('date'))[:10]=='2025-01-03'][0]; eid=e['id']
r=m.s.put(f"{BASE}/expenses/{eid}",json={'expense':{'reportingDate':'2025-01-01'}},timeout=60)
j=r.json()
print("PUT response reportingDate =", j.get('reportingDate'))
print("PUT response status =", j.get('status'))
