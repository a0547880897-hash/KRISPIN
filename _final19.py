import time,csv
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
# collision check INT-0002
print("=== INT-0002 (2 הוצאות) ===")
for e in byn[norm('INT-0002')]:
    print(f"  date={str(e.get('date'))[:10]} amt={e.get('amount')} rep={str(e.get('reportingDate'))[:10]}")
ALL=[("5991","2024-07-21","2025-01-01"),("10108463387","2025-01-23","2025-01-01"),
 ("1757466","2025-01-03","2025-01-01"),("70848300","2025-02-26","2025-02-01"),
 ("10508793106","2025-02-23","2025-02-01"),("1099254","2025-02-18","2025-02-01"),
 ("M2501326582","2025-03-28","2025-09-01"),("1044","2025-03-27","2025-09-01"),
 ("70863709","2025-03-26","2025-09-01"),("10908089370","2025-03-23","2025-09-01"),
 ("55316689","2025-03-23","2025-09-01"),("11111","2025-03-06","2025-09-01"),
 ("113997","2025-03-05","2025-09-01"),("M2501800626","2025-04-28","2025-10-01"),
 ("70879808","2025-04-26","2025-10-01"),("10609465031","2025-04-23","2025-10-01"),
 ("2147","2025-04-22","2025-10-01"),("INT-0002","2025-04-06","2025-10-01"),
 ("55354348","2025-04-01","2025-10-01")]
rows=[];bad=0
for num,dt,tgt in ALL:
    cand=[e for e in byn.get(norm(num),[]) if str(e.get('date'))[:10]==dt]
    if not cand:
        rows.append([num,dt,tgt,"NOTFOUND"]);bad+=1;continue
    got=str(cand[0].get('reportingDate'))[:10]
    ok = got==tgt
    if not ok: bad+=1
    rows.append([num,dt,tgt,got,"OK" if ok else "FAIL"])
print(f"\n=== דוח סופי 19 (bad={bad}) ===")
for r in rows: print("  ",r)
print("\nALL OK" if bad==0 else f"\n{bad} BAD")
