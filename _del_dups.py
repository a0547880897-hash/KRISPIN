import time,datetime
from morning_api import Morning, BASE
m=Morning(); m.authenticate()
def ts(x):
    try: return datetime.datetime.utcfromtimestamp(int(x)).strftime("%Y-%m-%d")
    except: return x
# (id_to_delete, number, expected_rep, expected_created_year)
COPIES=[
 ("48def1c5-1e02-46f4-b910-72bc00e9802a","5991","2025-01-01",2026),
 ("30011167-0c97-49ee-9ffc-26276a94d465","10108463387","2025-01-01",2026),
 ("c2828e04-cbe3-4e2b-8006-eb9a85615da7","10508793106","2025-02-01",2026),
 ("4f4145ad-32be-44c7-af39-69b85acbbcde","10609465031","2025-10-01",2026),
]
for eid,num,rep,yr in COPIES:
    full=m.s.get(f"{BASE}/expenses/{eid}",timeout=60).json()
    cyr=datetime.datetime.utcfromtimestamp(int(full.get('creationDate'))).year
    gotrep=str(full.get('reportingDate'))[:10]; gotnum=str(full.get('number'))
    # SAFETY: confirm this is the 441-copy
    if gotnum!=num or gotrep!=rep or cyr!=yr:
        print(f"  SKIP {num}: mismatch (num={gotnum} rep={gotrep} created={cyr}) — NOT deleting"); continue
    if full.get('status')==20:
        m.s.post(f"{BASE}/expenses/{eid}/open",timeout=60); time.sleep(0.4)
    r=m.s.delete(f"{BASE}/expenses/{eid}",timeout=60); time.sleep(0.4)
    print(f"  {num} (copy, created {ts(full.get('creationDate'))}, rep {gotrep}): DELETE -> {r.status_code}")
print("\n=== אימות: המקור עדיין קיים? ===")
for eid,num in [("b32516c5-0ffd-4a8d-9d49-6d3536ff71d6","5991"),
                ("2a1063de-8bd5-41b8-a8e2-2b9220e6768f","10108463387"),
                ("38fa090e-8ab3-4ada-ba3e-54d8f1b3f5e5","10508793106"),
                ("f5a8787c-90e2-4ae2-9fbc-45f2d024b3ac","10609465031")]:
    r=m.s.get(f"{BASE}/expenses/{eid}",timeout=60)
    j=r.json() if r.status_code==200 else {}
    print(f"  {num} מקור: HTTP{r.status_code} rep={str(j.get('reportingDate'))[:10]} amt={j.get('amount')} active={j.get('active')}")
