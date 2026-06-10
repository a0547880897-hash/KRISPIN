import time,json
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
NOTE="זיכוי חוז תגל"
def find(num,date,amt,supkey):
    j=m.post('/expenses/search',{'number':num,'fromDate':'2024-01-01','toDate':'2027-12-31','page':1,'pageSize':50}).json()
    for e in j['items']:
        sn=((e.get('data') or {}).get('supplier') or {}).get('name') or ''
        if str(e.get('date'))[:10]==date and e.get('amount')==amt and supkey in sn:
            return e
    return None
def convert(e, dt, set_pay=None):
    eid=e['id']; raw=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json(); d=raw.get('data') or {}
    body={k:raw.get(k) for k in ['currency','currencyRate','vat','amount','amountExcludeVat','date','reportingDate','number']}
    body['paymentType']= set_pay if set_pay is not None else raw.get('paymentType')
    body['documentType']=dt
    body['supplier']=d.get('supplier')
    ac=raw.get('accountingClassification') or {}
    if ac.get('id'): body['accountingClassification']={'id':ac['id']}
    body['description']=d.get('description','')
    body['remarks']=NOTE
    body['confirmFromEdit']=True
    r=m.s.put(f"{BASE}/expenses/{eid}",json=body,timeout=60); time.sleep(0.6)
    chk=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    rem=(chk.get('data') or {}).get('remarks')
    return r.status_code, chk.get('documentType'), rem, (chk.get('accountingClassification') or {}).get('title')

log=[]
# ליבנה (3): dt320, pay11(אחר), note, keep cls/supplier
LIB=[('5310001641','2026-01-07',290),('5310004834','2026-01-07',1195),('5310001202000034000','2026-01-07',250)]
for num,date,amt in LIB:
    e=find(num,date,amt,'ליבנה')
    if not e: print("!! ליבנה לא נמצא",num); continue
    sc,dt,rem,cls=convert(e,320,set_pay=11)
    log.append(('ליבנה',num,sc,dt,rem,cls)); print(f"ליבנה {num}: {sc} dt={dt} cls={cls} note={rem}")
# אלוף ספורט: dt305, note, keep rest
e=find('303-268916','2025-11-20',152.8,'אלוף ספורט')
if e: 
    sc,dt,rem,cls=convert(e,305); log.append(('אלוף',sc,dt,rem)); print(f"אלוף ספורט: {sc} dt={dt} cls={cls} note={rem}")
# ישרוטל: dt305, note, keep rest
e=find('51-135216','2025-11-10',540,'ישרוטל')
if e:
    sc,dt,rem,cls=convert(e,305); log.append(('ישרוטל',sc,dt,rem)); print(f"ישרוטל: {sc} dt={dt} cls={cls} note={rem}")
# deletes (verify date+amt+supplier)
print("--- מחיקות ---")
for num,date,amt,supkey in [('0000000','2026-02-16',3000,'תגל קריספין'),('0000000','2026-02-15',6555,'גרוזלם')]:
    e=find(num,date,amt, supkey if supkey!='גרוזלם' else "ג'רוזלם")
    if not e: print(f"!! לא נמצא למחיקה: {supkey} {amt}"); continue
    eid=e['id']
    if e.get('status')==20: m.s.post(f"{BASE}/expenses/{eid}/open",timeout=60); time.sleep(0.4)
    r=m.s.delete(f"{BASE}/expenses/{eid}",timeout=60); time.sleep(0.4)
    print(f"מחיקה {supkey} ₪{amt} ({date}): del={r.status_code}")
json.dump(log,open('_batch2_log.json','w'),ensure_ascii=False)
