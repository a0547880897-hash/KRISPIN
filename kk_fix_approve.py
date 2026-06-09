"""Fix + approve all 68 קופה קטנה (תגל/סוזן) drafts.
Fix: complete the accountingClassification object (was stored as {id,title} only),
clamp reportingDate (>=2025-11-01). Then POST /expenses/drafts/{id}/approve.
Records full details of each approved expense for the summary.
"""
import json,time,copy,re
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
cmap={c['id']:c for c in m.get('/accounting/classifications').json()}
def keepcls(c):
    return {k:c[k] for k in ('id','irsCode','title','code','key','income','vat','mixed') if k in c}
def clamp(ds):
    mm=re.search(r"(\d{4})-(\d{2})",str(ds or ""))
    if not mm: return "2025-11-01"
    fom=f"{mm.group(1)}-{mm.group(2)}-01"; return fom if fom>="2025-11-01" else "2025-11-01"

ids=json.load(open('kk_targets.json'))
# already approved earlier
DONE_ID='7ea1500a-7c30-44ba-9859-7b7a5b6811a4'
DONE_EXP='4f4145ad-32be-44c7-af39-69b85acbbcde'
results=[]; fails=[]
# include the already-approved one in results
e0=m.get('/expenses/'+DONE_EXP).json(); ee0=e0.get('expense',e0)
results.append({'supplier':(ee0.get('supplier',{}) or {}).get('name'),'number':ee0.get('number'),'date':str(ee0.get('date'))[:10],
                'reportingDate':str(ee0.get('reportingDate'))[:10],'amount':ee0.get('amount'),'vat':ee0.get('vat'),
                'classification':(ee0.get('accountingClassification',{}) or {}).get('title'),'expId':DONE_EXP})

todo=[i for i in ids if i!=DONE_ID]
print(f"to fix+approve: {len(todo)} (1 already done)",flush=True)
for n,did in enumerate(todo,1):
    try:
        cur=m.get('/expenses/drafts/'+did).json()
        if cur.get('status') is None and 'expense' not in cur:
            fails.append({'id':did,'why':'gone'}); continue
        e=copy.deepcopy(cur.get('expense',cur))
        ac=e.get('accountingClassification') or {}
        cid=ac.get('id')
        if cid in cmap: e['accountingClassification']=keepcls(cmap[cid])
        if e.get('date'): e['reportingDate']=clamp(e['date'])
        e['confirmFromEdit']=True
        r=m.s.put(f"{BASE}/expenses/drafts/{did}",json={'expense':e},timeout=60)
        if r.status_code>=300:
            fails.append({'id':did,'step':'fix','code':r.status_code,'body':r.text[:120]}); continue
        time.sleep(0.2)
        ap=m.s.post(f"{BASE}/expenses/drafts/{did}/approve",json={},timeout=60)
        if ap.status_code>=300:
            fails.append({'id':did,'step':'approve','code':ap.status_code,'body':ap.text[:150]}); continue
        ex=ap.json(); ex=ex.get('expense',ex)
        results.append({'supplier':(ex.get('supplier',{}) or {}).get('name'),'number':ex.get('number'),'date':str(ex.get('date'))[:10],
                        'reportingDate':str(ex.get('reportingDate'))[:10],'amount':ex.get('amount'),'vat':ex.get('vat'),
                        'classification':(ex.get('accountingClassification',{}) or {}).get('title'),'expId':ex.get('id')})
    except Exception as ce:
        fails.append({'id':did,'err':str(ce)})
    if n%15==0: print(f"  {n}/{len(todo)} ok={len(results)-1} fail={len(fails)}",flush=True)
    time.sleep(0.3)
json.dump({'results':results,'fails':fails},open('kk_results.json','w'),ensure_ascii=False,indent=1)
print(f"\nDONE approved={len(results)} (incl 1 prior) fails={len(fails)}",flush=True)
if fails[:5]: print("sample fails:",json.dumps(fails[:5],ensure_ascii=False),flush=True)
