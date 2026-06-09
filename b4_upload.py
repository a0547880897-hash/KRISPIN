"""Batch4: upload only the NEW invoices (b4_dedup.json) to Morning as expense drafts,
match each to its draft by MD5 hash. Never approves. Multi-page invoices kept together.
"""
import json, time, hashlib, requests
from morning_api import Morning
GW="https://apigw.greeninvoice.co.il/file-upload/v1/url"
NEW=json.load(open('b4_dedup.json'))['new']
def lm():
    return {nn:hashlib.md5(open(f'b4pdf/{nn}.pdf','rb').read()).hexdigest() for nn in NEW}
def ids(m):
    o={};p=1
    while True:
        j=m.post('/expenses/drafts/search',{'page':p,'pageSize':100}).json()
        for it in j['items']: o[it['id']]=1
        if p>=j['pages']:break
        p+=1;time.sleep(0.1)
    return o
def up(m,nn):
    r=m.s.get(GW,params={'context':'expense','data':json.dumps({'source':5})},timeout=40).json()
    f={k:(None,v) for k,v in r['fields'].items()}
    f['file']=(f'b4_{nn}.pdf',open(f'b4pdf/{nn}.pdf','rb').read(),'application/pdf')
    return requests.post(r['url'],files=f,timeout=120).status_code
def md5d(m,did):
    u=m.get('/expenses/drafts/'+did).json().get('url')
    if not u:return None
    fr=requests.get(u,timeout=60)
    return hashlib.md5(fr.content).hexdigest() if fr.status_code==200 else None
def main():
    LM=lm(); m=Morning();m.authenticate();print('AUTH OK',flush=True)
    before=ids(m); print(f'before={len(before)} uploading {len(NEW)} NEW: {NEW}',flush=True)
    for nn in NEW: print(f'  up {nn}:{up(m,nn)}',flush=True); time.sleep(1.0)
    print('polling...',flush=True); new=[]
    for a in range(24):
        time.sleep(15);m.authenticate();now=ids(m);new=[i for i in now if i not in before]
        print(f'  poll{a+1}:{len(new)}',flush=True)
        if len(new)>=len(NEW):break
    m2n={v:k for k,v in LM.items()};mp={};un=[]
    for did in new:
        h=md5d(m,did)
        (mp.__setitem__(m2n[h],did) if h in m2n else un.append(did));time.sleep(0.15)
    json.dump(mp,open('b4_map.json','w'),indent=1)
    print(f'matched {len(mp)}/{len(NEW)}',flush=True)
    miss=[nn for nn in NEW if nn not in mp]
    if miss:print('UNMATCHED',miss,flush=True)
main()
