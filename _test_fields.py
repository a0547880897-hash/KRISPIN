import time,json
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
# supplier object for קופה קטנה - תגל
SUP_TAGAL_ID="c88ae1bd-049e-4971-85fe-b9b836894463"
sj=m.get(f'/suppliers/{SUP_TAGAL_ID}').json()
sup=sj if 'id' in sj else sj.get('supplier',sj)
print("supplier:",sup.get('name'),"taxId=",repr(sup.get('taxId')))
# target: recent פז 60309901663000 (2026-05-15, not filed)
j=m.post('/expenses/search',{'number':'60309901663000','fromDate':'2024-01-01','toDate':'2027-12-31'}).json()
e=j['items'][0]; eid=e['id']
raw=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
print("BEFORE: dt=",raw.get('documentType'),"sup=",((raw.get('data') or {}).get('supplier') or {}).get('name'),
      "class=",(raw.get('accountingClassification') or {}).get('title'),"pay=",(raw.get('data') or {}).get('paymentType'),
      "amt=",raw.get('amount'),"rep=",str(raw.get('reportingDate'))[:10])
body={
 'paymentType':11,
 'currency':raw.get('currency','ILS'),'currencyRate':raw.get('currencyRate',1),
 'vat':raw.get('vat'),'amount':raw.get('amount'),'amountExcludeVat':raw.get('amountExcludeVat'),
 'date':raw.get('date'),'reportingDate':raw.get('reportingDate'),
 'documentType':320,
 'number':raw.get('number'),'description':(raw.get('data') or {}).get('description',''),
 'supplier':sup,
 'accountingClassificationId':'917c5805-c0d8-48e4-adc7-25d7e7e37fac',
}
r=m.s.put(f"{BASE}/expenses/{eid}",json=body,timeout=60); time.sleep(1)
print("PUT:",r.status_code)
chk=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
print("AFTER:  dt=",chk.get('documentType'),"sup=",((chk.get('data') or {}).get('supplier') or {}).get('name'),
      "class=",(chk.get('accountingClassification') or {}).get('title'),"pay=",(chk.get('data') or {}).get('paymentType'),
      "amt=",chk.get('amount'),"vat=",chk.get('vat'),"rep=",str(chk.get('reportingDate'))[:10])
