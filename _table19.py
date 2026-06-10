import time,json,csv
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
# (number, date_match, target_period_label)
TARGET=[
 ("5991","2024-07-21","ינואר 2025"),
 ("10108463387","2025-01-23","ינואר 2025"),
 ("1757466","2025-01-03","ינואר 2025"),
 ("70848300","2025-02-26","פברואר 2025"),
 ("10508793106","2025-02-23","פברואר 2025"),
 ("1099254","2025-02-18","פברואר 2025"),
 ("M2501326582","2025-03-28","ספטמבר 2025"),
 ("1044","2025-03-27","ספטמבר 2025"),
 ("70863709","2025-03-26","ספטמבר 2025"),
 ("10908089370","2025-03-23","ספטמבר 2025"),
 ("55316689","2025-03-23","ספטמבר 2025"),
 ("11111","2025-03-06","ספטמבר 2025"),
 ("113997","2025-03-05","ספטמבר 2025"),
 ("M2501800626","2025-04-28","אוקטובר 2025"),
 ("70879808","2025-04-26","אוקטובר 2025"),
 ("10609465031","2025-04-23","אוקטובר 2025"),
 ("2147","2025-04-22","אוקטובר 2025"),
 ("INT-0002","2025-04-06","אוקטובר 2025"),
 ("55354348","2025-04-01","אוקטובר 2025"),
]
def supname(e):
    raw=m.s.get(f"{BASE}/expenses/{e['id']}",timeout=60).json()
    d=raw.get('data') or {}
    sup=(d.get('supplier') or {})
    return sup.get('name') or raw.get('supplier') or '', raw.get('vat')
rows=[]
for i,(num,dt,tgt) in enumerate(TARGET,1):
    cand=[e for e in byn.get(norm(num),[]) if str(e.get('date'))[:10]==dt]
    e=cand[0] if cand else None
    if not e:
        rows.append([i,num,"לא נמצא","","","","",tgt]); continue
    name,vat=supname(e); time.sleep(0.1)
    rows.append([i,num,name,str(e.get('date'))[:10],e.get('amount'),vat,"נובמבר 2025",tgt])
hdr=["#","מספר מסמך","ספק","תאריך מסמך","סכום כולל","מע\"מ","תקופה נוכחית","תקופת יעד"]
with open('check3_19_table.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f); w.writerow(hdr); w.writerows(rows)
# print markdown
print("| "+" | ".join(hdr)+" |")
print("|"+"|".join(["---"]*len(hdr))+"|")
for r in rows:
    print("| "+" | ".join(str(x) for x in r)+" |")
