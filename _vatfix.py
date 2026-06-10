import json,time
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
cand=json.load(open('_vatfix_cand.json'))
# only reductions (over-claim), all <=500
red=[c for c in cand if c[7]<0]
print(f"לתיקון (הורדות): {len(red)}")
def findlive(numlabel,date,amt,supkey):
    j=m.post('/expenses/search',{'number':numlabel,'fromDate':'2024-01-01','toDate':'2027-12-31','page':1,'pageSize':50}).json()
    for e in j['items']:
        sn=((e.get('data') or {}).get('supplier') or {}).get('name') or ''
        if str(e.get('date'))[:10]==date and abs((e.get('amount') or 0)-amt)<0.01 and supkey[:6] in sn:
            return e
    return None
from datetime import datetime
def iso(d):  # dd/mm/yyyy -> yyyy-mm-dd
    return datetime.strptime(d,'%d/%m/%Y').strftime('%Y-%m-%d')
log=[]; skipped=[]
for num,dd,dt,sup,tot,curv,correct,diff,direction in red:
    date=iso(dd)
    e=findlive(num,date,tot,sup)
    if not e: skipped.append((num,dd,'לא נמצא live')); continue
    eid=e['id']; raw=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json(); d=raw.get('data') or {}
    live_vat=raw.get('vat'); amt=raw.get('amount')
    new_vat=round(amt-amt/1.18,2)
    # safety: only fix if live vat is the wrong (over) value, and new<live
    if not (live_vat and abs(live_vat-round(0.18*amt,2))<=0.6 and new_vat<live_vat):
        skipped.append((num,dd,f'live_vat={live_vat} לא תואם תבנית')); continue
    if abs(new_vat-live_vat)>500: skipped.append((num,dd,'>500')); continue
    body={k:raw.get(k) for k in ['paymentType','currency','currencyRate','date','reportingDate','number','documentType']}
    body['amount']=amt
    body['vat']=new_vat
    body['amountExcludeVat']=round(amt-new_vat,2)
    body['supplier']=d.get('supplier')
    ac=raw.get('accountingClassification') or {}
    if ac.get('id'): body['accountingClassification']={'id':ac['id']}
    body['description']=d.get('description','')
    body['confirmFromEdit']=True
    r=m.s.put(f"{BASE}/expenses/{eid}",json=body,timeout=60); time.sleep(0.4)
    chk=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    ok = abs((chk.get('vat') or 0)-new_vat)<0.01 and abs((chk.get('amount') or 0)-amt)<0.01
    log.append((num,dd,live_vat,new_vat,chk.get('vat'),'OK' if ok else 'FAIL'))
    print(f"  {num:14} {dd} vat {live_vat}->{new_vat} (amt {amt} שמור) {'OK' if ok else 'FAIL'}")
print(f"\nתוקנו: {len([x for x in log if x[5]=='OK'])}/{len(red)}")
if skipped: print("דולגו:",skipped)
json.dump(log,open('_vatfix_log.json','w'),ensure_ascii=False)
