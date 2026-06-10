import time,json
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
from collections import defaultdict
def sup_obj(sid):
    sj=m.get(f'/suppliers/{sid}').json()
    return sj if 'id' in sj else sj.get('supplier',sj)
SUP_TAGAL=sup_obj("c88ae1bd-049e-4971-85fe-b9b836894463")   # קופה קטנה - תגל
SUP_KK=sup_obj("56d7e111-330c-4e61-94a2-2698b99f5415")       # קופה קטנה
CLS_OUT="917c5805-c0d8-48e4-adc7-25d7e7e37fac"  # עבודות חוץ
CLS_KIB="767f8f23-803b-4ca2-9e17-948402dc48a9"  # כיבוד

def wide(name):
    out=[];p=1
    while True:
        j=m.post('/expenses/search',{'supplierName':name,'fromDate':'2024-01-01','toDate':'2027-12-31','page':p,'pageSize':100}).json()
        out+=j['items']
        if p>=j.get('pages',1):break
        p+=1
    return out
def sn(e): return ((e.get('data') or {}).get('supplier') or {}).get('name') or ''

def convert(eid, dt, supplier, clsid, paymentType):
    raw=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    d=raw.get('data') or {}
    body={k:raw.get(k) for k in ['currency','currencyRate','vat','amount','amountExcludeVat','date','reportingDate','number']}
    body['description']=d.get('description','')
    body['documentType']=dt
    body['supplier']=supplier
    body['accountingClassification']={'id':clsid}
    body['paymentType']= paymentType if paymentType is not None else raw.get('paymentType')
    body['pcnClassification']='K'
    r=m.s.put(f"{BASE}/expenses/{eid}",json=body,timeout=60); time.sleep(0.5)
    chk=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    ok = chk.get('documentType')==dt and (chk.get('accountingClassification') or {}).get('id')==clsid and 'קופה' in ((chk.get('data') or {}).get('supplier') or {}).get('name','')
    return r.status_code, ok, (chk.get('data') or {}).get('pcnClassification')

def delete(eid, exp_date, exp_amt):
    raw=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    if str(raw.get('date'))[:10]!=exp_date or raw.get('amount')!=exp_amt:
        return f"SAFETY-MISMATCH date={str(raw.get('date'))[:10]} amt={raw.get('amount')}"
    if raw.get('status')==20:
        m.s.post(f"{BASE}/expenses/{eid}/open",timeout=60); time.sleep(0.4)
    r=m.s.delete(f"{BASE}/expenses/{eid}",timeout=60); time.sleep(0.4)
    return f"del={r.status_code}"

log={'pz_convert':[],'pz_delete':[],'al_convert':[],'al_delete':[]}

# ===== פז =====
pz=[e for e in wide('פז') if 'פז' in sn(e)]
pz20=[e for e in pz if e.get('documentType')==20]
g=defaultdict(list)
for e in pz20: g[(str(e.get('date'))[:10],e.get('amount'))].append(e)
for k,v in sorted(g.items()):
    survivor=v[0]; dels=v[1:]
    sc,ok,pcn=convert(survivor['id'],320,SUP_TAGAL,CLS_OUT,11)
    log['pz_convert'].append((survivor.get('number'),k[0],sc,ok,pcn))
    print(f"פז המרה {survivor.get('number'):16} {k[0]}: {sc} ok={ok} pcn={pcn}")
    for dd in dels:
        res=delete(dd['id'],k[0],k[1])
        log['pz_delete'].append((dd.get('number'),k[0],res))
        print(f"   פז מחיקה {dd.get('number')}: {res}")

# ===== אלוניאל =====
al=[e for e in wide('אלוניאל') if 'אלוניאל' in sn(e)]
g2=defaultdict(list)
for e in al:
    if e.get('documentType') in (20,305,320): g2[(str(e.get('date'))[:10],e.get('amount'))].append(e)
for k,v in sorted(g2.items()):
    dt20s=[e for e in v if e.get('documentType')==20]
    others=[e for e in v if e.get('documentType')!=20]
    if not dt20s:  # standalone already-converted unrelated -> skip
        continue
    survivor=dt20s[0]; dels=dt20s[1:]+others
    sc,ok,pcn=convert(survivor['id'],305,SUP_KK,CLS_KIB,None)  # keep payment
    log['al_convert'].append((survivor.get('number'),k[0],sc,ok,pcn))
    print(f"אל המרה {survivor.get('number'):12} {k[0]}: {sc} ok={ok} pcn={pcn}")
    for dd in dels:
        res=delete(dd['id'],k[0],k[1])
        log['al_delete'].append((dd.get('number'),k[0],res))
        print(f"   אל מחיקה {dd.get('number')}/dt{dd.get('documentType')}: {res}")

json.dump(log,open('_pz_al_log.json','w'),ensure_ascii=False,indent=1)
print("\n=== סיכום ===")
print("פז: המרות",len(log['pz_convert']),"מחיקות",len(log['pz_delete']))
print("אלוניאל: המרות",len(log['al_convert']),"מחיקות",len(log['al_delete']))
print("המרות שנכשלו:",[x for x in log['pz_convert']+log['al_convert'] if not x[3]])
print("מחיקות לא תקינות:",[x for x in log['pz_delete']+log['al_delete'] if 'del=200' not in x[2]])
