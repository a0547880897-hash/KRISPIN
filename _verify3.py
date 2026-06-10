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

CHECK=[
 ("54589216188",None,"deleted?"),
 ("02160",None,"deleted?"),
 ("55316689","2025-03-01","deleted-dup?"),
 ("5991",None,"2025-01"),
 ("10108463387",None,"2025-01"),
 ("1757466",None,"2025-01"),
 ("70848300",None,"2025-02"),
 ("10508793106",None,"2025-02"),
 ("1099254",None,"2025-02"),
 ("M2501326582",None,"2025-09"),
 ("1044",None,"2025-09"),
 ("70863709",None,"2025-09"),
 ("10908089370",None,"2025-09"),
 ("55316689","2025-03-23","2025-09-keep"),
 ("11111",None,"2025-09"),
 ("113997",None,"2025-09"),
 ("M2501800626",None,"2025-10"),
 ("70879808",None,"2025-10"),
 ("10609465031",None,"2025-10"),
 ("2147",None,"2025-10"),
 ("INT-0002",None,"2025-10"),
 ("55354348",None,"2025-10"),
]
for num,datef,want in CHECK:
    cand=byn.get(norm(num),[])
    if datef: cand=[e for e in cand if str(e.get('date'))[:10]==datef]
    if not cand:
        print(f"{num:16} GONE (want {want})"); continue
    for e in cand:
        print(f"{num:16} st={e.get('status')} date={str(e.get('date'))[:10]} rep={str(e.get('reportingDate'))[:10]} amt={e.get('amount')} sup={(e.get('supplierName') or '')[:18]} want={want}")
