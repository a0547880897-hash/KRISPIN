import time,json
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
# pick 1757466 (Jan 2025 target, status 20)
e=byn[norm('1757466')][0]; eid=e['id']
print("ID",eid,"status",e.get('status'))
raw=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
print("=== FULL RAW (top-level keys) ===")
print(sorted(raw.keys()))
print(json.dumps(raw,ensure_ascii=False,indent=1)[:3000])
