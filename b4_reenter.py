import json,time,hashlib,requests
from morning_api import Morning
GW="https://apigw.greeninvoice.co.il/file-upload/v1/url"
RE=['03','04','13','14','15','16','18','19','20','21','22']
def ids(m):
    o={};p=1
    while True:
        j=m.post('/expenses/drafts/search',{'page':p,'pageSize':100}).json()
        for it in j['items']: o[it['id']]=1
        if p>=j['pages']:break
        p+=1;time.sleep(0.1)
    return o
m=Morning();m.authenticate();print('AUTH OK',flush=True)
before=set(ids(m))
for nn in RE:
    r=m.s.get(GW,params={'context':'expense','data':json.dumps({'source':5})},timeout=40).json()
    f={k:(None,v) for k,v in r['fields'].items()}
    f['file']=(f'b4re_{nn}.pdf',open(f'b4pdf/{nn}.pdf','rb').read(),'application/pdf')
    print(nn,requests.post(r['url'],files=f,timeout=120).status_code,flush=True);time.sleep(1)
print('uploaded; waiting 150s for Morning to process...',flush=True)
time.sleep(150)
now=set(ids(m)); new=[i for i in now if i not in before]
json.dump(new,open('b4re_newids.json','w'))
print('new drafts after settle:',len(new),flush=True)
