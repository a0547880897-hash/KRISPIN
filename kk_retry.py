import json,time,copy,re
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
cmap={c['id']:c for c in m.get('/accounting/classifications').json()}
def keepcls(c): return {k:c[k] for k in ('id','irsCode','title','code','key','income','vat','mixed') if k in c}
def clamp(ds):
    mm=re.search(r"(\d{4})-(\d{2})",str(ds or "")); 
    if not mm: return "2025-11-01"
    f=f"{mm.group(1)}-{mm.group(2)}-01"; return f if f>="2025-11-01" else "2025-11-01"
def dateonly(ds):
    mm=re.search(r"(\d{4}-\d{2}-\d{2})",str(ds or "")); return mm.group(1) if mm else ds

prev=json.load(open('kk_results.json'))
results=prev['results']; fails=prev['fails']
retry_ids=[f['id'] for f in fails if 'id' in f]
print("retrying:",len(retry_ids),flush=True)
newfails=[]
for n,did in enumerate(retry_ids,1):
    try:
        cur=m.get('/expenses/drafts/'+did).json()
        e=copy.deepcopy(cur.get('expense',cur))
        if not e.get('amount'): newfails.append({'id':did,'why':'gone/empty'}); continue
        ac=e.get('accountingClassification') or {}
        if ac.get('id') in cmap: e['accountingClassification']=keepcls(cmap[ac['id']])
        e['date']=dateonly(e.get('date'))           # <-- normalize date
        e['reportingDate']=dateonly(clamp(e.get('date')))
        e['confirmFromEdit']=True
        r=m.s.put(f"{BASE}/expenses/drafts/{did}",json={'expense':e},timeout=60)
        if r.status_code>=300: newfails.append({'id':did,'step':'fix','code':r.status_code,'body':r.text[:120]}); continue
        time.sleep(0.2)
        ap=m.s.post(f"{BASE}/expenses/drafts/{did}/approve",json={},timeout=60)
        if ap.status_code>=300: newfails.append({'id':did,'step':'approve','code':ap.status_code,'body':ap.text[:150]}); continue
        ex=ap.json(); ex=ex.get('expense',ex)
        results.append({'supplier':(ex.get('supplier',{}) or {}).get('name'),'number':ex.get('number'),'date':str(ex.get('date'))[:10],
                        'reportingDate':str(ex.get('reportingDate'))[:10],'amount':ex.get('amount'),'vat':ex.get('vat'),
                        'classification':(ex.get('accountingClassification',{}) or {}).get('title'),'expId':ex.get('id')})
    except Exception as ce: newfails.append({'id':did,'err':str(ce)})
    if n%15==0: print(f"  {n}/{len(retry_ids)} approved_total={len(results)} fail={len(newfails)}",flush=True)
    time.sleep(0.3)
json.dump({'results':results,'fails':newfails},open('kk_results.json','w'),ensure_ascii=False,indent=1)
print(f"\nTOTAL approved={len(results)} remaining_fails={len(newfails)}",flush=True)
if newfails[:5]: print("sample:",json.dumps(newfails[:5],ensure_ascii=False),flush=True)
