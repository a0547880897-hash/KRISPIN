import time,copy,json
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

ACTIONS=[
 ("54589216188",None,"delete",None),
 ("02160",None,"delete",None),
 ("55316689","2025-03-01","delete",None),     # kupa-katana duplicate
 ("5991",None,"report","2025-01-01"),
 ("10108463387",None,"report","2025-01-01"),
 ("1757466",None,"report","2025-01-01"),
 ("70848300",None,"report","2025-02-01"),
 ("10508793106",None,"report","2025-02-01"),
 ("1099254",None,"report","2025-02-01"),
 ("M2501326582",None,"report","2025-09-01"),
 ("1044",None,"report","2025-09-01"),
 ("70863709",None,"report","2025-09-01"),
 ("10908089370",None,"report","2025-09-01"),
 ("55316689","2025-03-23","report","2025-09-01"),  # keep (Electra)
 ("11111",None,"report","2025-09-01"),
 ("113997",None,"report","2025-09-01"),
 ("M2501800626",None,"report","2025-10-01"),
 ("70879808",None,"report","2025-10-01"),
 ("10609465031",None,"report","2025-10-01"),
 ("2147",None,"report","2025-10-01"),
 ("INT-0002",None,"report","2025-10-01"),
 ("55354348",None,"report","2025-10-01"),
]
def resolve(num,datef):
    cand=byn.get(norm(num),[])
    if datef: cand=[e for e in cand if str(e.get('date'))[:10]==datef]
    return cand[0] if len(cand)==1 else (cand[0] if cand else None), len(cand)

def open_if(e):
    if e.get('status')==20:
        r=m.s.post(f"{BASE}/expenses/{e['id']}/open",timeout=60)
        time.sleep(0.3); return r.status_code
    return 'open-not-needed'

log=[]
for num,datef,act,newrep in ACTIONS:
    e,n=resolve(num,datef)
    if not e: log.append((num,act,"NOT FOUND")); continue
    eid=e['id']; opened=open_if(e)
    if act=="delete":
        r=m.s.delete(f"{BASE}/expenses/{eid}",timeout=60)
        log.append((num,"delete",f"open={opened} del={r.status_code}"))
    else:
        cur=m.get('/expenses/'+eid).json(); ee=copy.deepcopy(cur.get('expense',cur))
        ee['reportingDate']=newrep
        r=m.s.put(f"{BASE}/expenses/{eid}",json={'expense':ee},timeout=60)
        log.append((num,f"report->{newrep}",f"open={opened} put={r.status_code}"))
    time.sleep(0.4)
for x in log: print(" ",x)
ok=sum(1 for x in log if ('del=2' in x[2] or 'put=200' in x[2] or 'del=200' in x[2]))
print("\nsuccess:",sum(1 for x in log if ('200' in x[2] or 'del=2' in x[2])),"/",len(ACTIONS))
json.dump(log,open('fix3_log.json','w'),ensure_ascii=False)
