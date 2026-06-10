import csv,re
rows=list(csv.DictReader(open('expenses_audit.csv',encoding='utf-8-sig')))
VAT='מע"מ'
def f(x):
    try: return float(str(x).replace(',',''))
    except: return None
def dmonth(s):
    m=re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})',str(s)); return (int(m.group(3)),int(m.group(2))) if m else None
def rmonth(s):
    m=re.match(r'(\d{1,2})/(\d{4})',str(s)); return (int(m.group(2)),int(m.group(1))) if m else None
def mi(ym): return ym[0]*12+ym[1] if ym else None
VALID_TAX={'חשבונית מס','חשבונית מס / קבלה'}
from collections import Counter

print("===== בדיקה 1: יחס מע\"מ חורג מ-18% (מסמכים עם מע\"מ>0) =====")
out1=[]
for r in rows:
    vat=f(r[VAT]); net=f(r['סכום לא כולל מע״מ'])
    if vat and vat>0 and net and net>0:
        exp=round(net*0.18,2); ratio=vat/net*100
        if abs(vat-exp)>max(0.10,net*0.01):
            out1.append((r['מספר המסמך'],r['ספק'][:20],r['סוג המסמך'][:14],net,vat,round(ratio,1)))
print("חריגים:",len(out1))
for x in sorted(out1,key=lambda z:-abs(z[5]-18))[:30]:
    print("  מס'%s | %-20s | %-14s | נטו %s מעמ %s = %s%%"%x)

print("\n===== בדיקה 2: קבלה/חשבון-חיוב עם מע\"מ (לא חשבונית מס) =====")
out2=[r for r in rows if r['סוג המסמך'] not in VALID_TAX and (f(r[VAT]) or 0)>0]
print("סהכ:",len(out2),"| פילוח:",dict(Counter(r['סוג המסמך'] for r in out2)))
print("סכום מעמ בשורות אלה:",round(sum(f(r[VAT]) or 0 for r in out2),2))
for x in sorted(out2,key=lambda r:-(f(r[VAT]) or 0))[:25]:
    print("  מס'%s | %-22s | %-18s | מעמ %s | %s"%(x['מספר המסמך'],x['ספק'][:22],x['סוג המסמך'][:18],x[VAT],x['תאריך המסמך']))

print("\n===== בדיקה 3: פער מעל 6 חודשים בין תאריך מסמך לדיווח =====")
out3=[]
for r in rows:
    dm=dmonth(r['תאריך המסמך']); rm=rmonth(r['חודש דיווח'])
    if dm and rm:
        gap=mi(rm)-mi(dm)
        if gap>6: out3.append((r['מספר המסמך'],r['ספק'][:20],r['תאריך המסמך'],r['חודש דיווח'],gap,f(r[VAT]) or 0))
print("חריגים (>6 חודשים):",len(out3),"| מעמ בסיכון:",round(sum(x[4-1+1] for x in out3) and sum(x[5] for x in out3),2))
for x in sorted(out3,key=lambda z:-z[4])[:25]:
    print("  מס'%s | %-20s | מסמך %s -> דיווח %s = %s חוד' | מעמ %s"%x)

print("\n===== בדיקה 4: דיווח מוקדם מתאריך המסמך (לא תקין) =====")
out4=[]
for r in rows:
    dm=dmonth(r['תאריך המסמך']); rm=rmonth(r['חודש דיווח'])
    if dm and rm and mi(rm)<mi(dm):
        out4.append((r['מספר המסמך'],r['ספק'][:20],r['תאריך המסמך'],r['חודש דיווח'],mi(dm)-mi(rm),f(r[VAT]) or 0))
print("חריגים:",len(out4))
for x in sorted(out4,key=lambda z:-z[4]):
    print("  מס'%s | %-20s | מסמך %s -> דיווח %s (מוקדם ב-%s חוד') | מעמ %s"%x)
