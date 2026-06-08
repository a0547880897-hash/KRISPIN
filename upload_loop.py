from morning_api import Morning
import json, requests, time, os
m=Morning(); m.authenticate()
UP='https://apigw.greeninvoice.co.il/file-upload/v1/url'
mapping={"01":"d149384b-184e-4929-842c-9d1b5d8528b5"}  # invoice 1 already uploaded
known=set(json.load(open('draft_ids_before.json')))|set(mapping.values())
def all_ids():
    ids=[]; page=1
    while True:
        j=m.post('/expenses/drafts/search',{'page':page,'pageSize':100}).json(); ids+=[it['id'] for it in j['items']]
        if page*100>=j['total']: break
        page+=1
    return ids
def log(s):
    open('upload_progress.log','a').write(s+'\n')
for n in range(2,28):
    nn=f'{n:02d}'
    try:
        r=m.s.get(UP, params={'context':'expense','data':json.dumps({'source':5})}, timeout=40).json()
        files={k:(None,v) for k,v in r['fields'].items()}
        files['file']=(f'invoice{nn}.pdf', open(f'invpdf/{nn}.pdf','rb').read(), 'application/pdf')
        up=requests.post(r['url'], files=files, timeout=120)
        if up.status_code>=300: log(f'{nn} S3FAIL {up.status_code}'); continue
        found=None
        for _ in range(18):
            time.sleep(5)
            new=set(all_ids())-known
            if new: found=list(new)[0]; break
        if found:
            mapping[nn]=found; known.add(found); log(f'{nn} -> {found}')
        else:
            log(f'{nn} NO_DRAFT_APPEARED')
        json.dump(mapping,open('upload_map.json','w'))
    except Exception as e:
        log(f'{nn} ERR {e}')
json.dump(mapping,open('upload_map.json','w'))
log(f'DONE mapped={len(mapping)}')
