import time,json
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
# all expenses
exps=[];p=1
while True:
    j=m.post('/expenses/search',{'page':p,'pageSize':100}).json(); exps+=j['items']
    if p>=j['pages']:break
    p+=1
print("total expenses in default search:",len(exps))
# map documentType counts + supplier name access
# search items may lack supplierName; fetch supplier via GET is costly. First inspect a sample item keys
print("sample item keys:",sorted(exps[0].keys()))
# print docType distribution
from collections import Counter
dt=Counter(e.get('documentType') for e in exps)
print("documentType distribution:",dict(dt))
