import json,time,copy,re,requests,fitz
from morning_api import Morning, BASE
RE=['04','13','14','16','18','19','20','21','22']
GW="https://apigw.greeninvoice.co.il/file-upload/v1/url"
data=json.load(open('b4_data.json'))
def norm(s): return ''.join(c for c in str(s) if c.isdigit())
num2nn={norm(data[nn]['number']):nn for nn in data}
m=Morning();m.authenticate();print('AUTH',flush=True)
def ids():
    o=set();p=1
    while True:
        j=m.post('/expenses/drafts/search',{'page':p,'pageSize':100}).json()
        for it in j['items']:o.add(it['id'])
        if p>=j['pages']:break
        p+=1;time.sleep(0.1)
    return o
before=ids()
for nn in RE:
    r=m.s.get(GW,params={'context':'expense','data':json.dumps({'source':5})},timeout=40).json()
    f={k:(None,v) for k,v in r['fields'].items()}; f['file']=(f'bf_{nn}.pdf',open(f'b4pdf/{nn}.pdf','rb').read(),'application/pdf')
    print(nn,requests.post(r['url'],files=f,timeout=120).status_code,flush=True);time.sleep(1)
print('wait 150s',flush=True);time.sleep(150)
new=[i for i in ids() if i not in before]
print('new drafts:',len(new),flush=True)
def clamp(ds):
    mm=re.search(r"(\d{4})-(\d{2})",str(ds or "")); 
    if not mm:return"2025-11-01"
    f=f"{mm.group(1)}-{mm.group(2)}-01";return f if f>="2025-11-01" else "2025-11-01"
placed={}
for did in new:
    j=m.get('/expenses/drafts/'+did).json(); u=j.get('url')
    if not u:continue
    try:
        b=requests.get(u,timeout=60).content; doc=fitz.open(stream=b,filetype='pdf'); txt=norm(" ".join(p.get_text() for p in doc))
    except:continue
    hit=next((nn for nn in RE if norm(data[nn]['number']) in txt and nn not in placed),None)
    if hit:placed[hit]=did
print('identified by content:',sorted(placed),flush=True)
# write+lock with retry
for rd in range(4):
    m.authenticate();need=[nn for nn in placed if not m.get('/expenses/drafts/'+placed[nn]).json().get('expense',{}).get('amount')]
    if not need and rd>0:break
    for nn in (placed if rd==0 else need):
        v=data[nn];cur=m.get('/expenses/drafts/'+placed[nn]).json();e=copy.deepcopy(cur.get('expense',cur))
        e['supplier']=dict(e.get('supplier') or {});e['supplier']['name']=v['name'][:100]
        if v.get('taxId'):e['supplier']['taxId']=str(v['taxId'])
        e['supplier'].setdefault('country','IL')
        e['number']=str(v['number']);e['date']=v['date'];e['reportingDate']=clamp(v['date'])
        e['amount']=v['amount'];e['vat']=v['vat'];e['currency']='ILS';e['description']=v['note'][:500];e['confirmFromEdit']=True
        m.s.put(f"{BASE}/expenses/drafts/{placed[nn]}",json={'expense':e},timeout=60);time.sleep(0.25)
    time.sleep(25)
json.dump(placed,open('b4_final_map.json','w'))
hold=[nn for nn in placed if m.get('/expenses/drafts/'+placed[nn]).json().get('expense',{}).get('amount')]
print('FINAL held:',sorted(hold),flush=True)
print('still missing:',[nn for nn in RE if nn not in placed],flush=True)
