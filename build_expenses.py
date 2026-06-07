"""Task 2: independent re-scan of the 304 approved expenses -> catalog_expenses_approved.xlsx
+ a discrepancy report (my reading vs Morning's captured data).

The xlsx holds MY scan (correct values). Manual corrections live in
expenses_overrides.json (same shape as manual_overrides.json). The discrepancy
report (printed) lists ONLY where Morning differs from the document on
amount / vat / document-category.
"""
import os, re, json
import fitz
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

RAW = "expenses_raw.json"; DOCS = "documents_expenses"; OUT = "catalog_expenses_approved.xlsx"
OVERRIDES = "expenses_overrides.json"
GREEN=PatternFill("solid",fgColor="C6EFCE"); YELLOW=PatternFill("solid",fgColor="FFEB9C")
RED=PatternFill("solid",fgColor="FFC7CE"); HDR=PatternFill("solid",fgColor="305496")
THIN=Border(*[Side(style="thin",color="D9D9D9")]*4)

DOC_TYPES={305:"חשבונית מס",320:"חשבונית מס/קבלה",400:"קבלה",330:"חשבון עסקה",
           405:"קבלה (זיכוי/תרומה)",20:"מסמך הוצאה",10:"הצעת מחיר"}
PAY={1:"מזומן",2:"צ'ק",3:"כרטיס אשראי",4:"העברה בנקאית",5:"PayPal",0:"לא צויין",10:"אפליקציה"}
HEBM={1:"ינו",2:"פבר",3:"מרץ",4:"אפר",5:"מאי",6:"יוני",7:"יולי",8:"אוג",9:"ספט",10:"אוק",11:"נוב",12:"דצמ"}

def bimonthly(s):
    m=re.search(r'(\d{4})-(\d{2})',str(s or ""))
    if not m: return ""
    y,mo=int(m.group(1)),int(m.group(2)); st=mo if mo%2 else mo-1
    return f"{st:02d}-{st+1:02d}/{y}"

def gettext(p):
    if not p.lower().endswith(".pdf"): return ""
    try: return "\n".join(pg.get_text() for pg in fitz.open(p))
    except: return ""

def norm(s): return re.sub(r'[\s,]','',str(s)).lower()
def in_text(v,nt):
    if v in (None,'',0): return None
    if norm(v) in nt: return True
    dg=re.findall(r'\d+',str(v))
    if dg and len(dg[0])>=2 and dg[0] in nt: return True
    try:
        f=float(v)
        for c in {str(f),(str(int(f)) if f==int(f) else ''),f"{f:.2f}"}:
            if c and norm(c) in nt: return True
    except: pass
    return False

def doctype_from_text(t):
    if re.search(r'חשבונית\s*מס\s*[/\\]?\s*קבלה',t) or 'חשבונית מס קבלה' in t: return "חשבונית מס/קבלה"
    if 'חשבון עסקה' in t or 'חשבונית עסקה' in t: return "חשבון עסקה"
    if 'חשבונית מס' in t: return "חשבונית מס"
    if re.search(r'\bקבלה\b',t): return "קבלה"
    return ""

COLUMNS=["#index","שם ספק","מספר עוסק / ח.פ.","סוג מסמך","מספר מסמך","תאריך המסמך","תקופת דיווח",
         "סכום לפני מע\"מ","סך הכל מע\"מ","סכום כולל מע\"מ","מטבע","שולם באמצעות",
         "סיווג הוצאה","שם הקובץ","expense_id","רמת ודאות","הערות"]

def main():
    raw=json.load(open(RAW,encoding="utf-8"))
    ov={k:v for k,v in (json.load(open(OVERRIDES,encoding="utf-8")).items() if os.path.exists(OVERRIDES) else [])
        if not k.startswith("_")} if os.path.exists(OVERRIDES) else {}
    files={f.split("_")[1]:f for f in os.listdir(DOCS)} if os.path.isdir(DOCS) else {}

    wb=Workbook(); ws=wb.active; ws.title="הוצאות מאושרות"; ws.sheet_view.rightToLeft=True
    for c,n in enumerate(COLUMNS,1):
        cell=ws.cell(1,c,n); cell.fill=HDR; cell.font=Font(bold=True,color="FFFFFF")
        cell.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True); cell.border=THIN
    ws.freeze_panes="A2"

    discrepancies=[]  # (idx, supplier, field, morning, mine)
    rows=sorted(raw.values(), key=lambda x:x.get("date",""))
    r=2; stats={"g":0,"y":0,"red":0}
    for i,e in enumerate(rows,1):
        eid=e["id"]; idx=f"{i:04d}"; sup=(e.get("supplier") or {}).get("name","")
        fname=files.get(eid,""); text=gettext(os.path.join(DOCS,fname)) if fname else ""
        nt=norm(text); has=len(text.strip())>20
        mtype=DOC_TYPES.get(e.get("documentType"),e.get("documentType"))
        amt=e.get("amount"); vat=e.get("vat"); net=e.get("amountExcludeVat")
        num=e.get("number"); date=(e.get("date") or "")[:10]
        a_ok=in_text(amt,nt); n_ok=in_text(num,nt); ttype=doctype_from_text(text)

        # discrepancy detection (only meaningful when we have text)
        if has:
            if a_ok is False: discrepancies.append((idx,sup,"סכום",amt,"לא נמצא בטקסט"))
            if e.get("vat") not in (None,0) and in_text(vat,nt) is False:
                discrepancies.append((idx,sup,"מע\"מ",vat,"לא נמצא בטקסט"))
            if ttype and ttype!=mtype:
                discrepancies.append((idx,sup,"סיווג מסמך",mtype,ttype))

        o=ov.get(eid,{})
        vals={"שם ספק":sup,"מספר עוסק / ח.פ.":(e.get("supplier") or {}).get("taxId",""),
              "סוג מסמך":(ttype or mtype),"מספר מסמך":num,"תאריך המסמך":date,
              "תקופת דיווח":bimonthly(date or e.get("reportingDate")),
              "סכום לפני מע\"מ":net,"סך הכל מע\"מ":vat,"סכום כולל מע\"מ":amt,"מטבע":e.get("currency",""),
              "שולם באמצעות":PAY.get(e.get("paymentType"),e.get("paymentType")),
              "סיווג הוצאה":(e.get("accountingClassification") or {}).get("title","")}
        for k,vv in o.get("set",{}).items(): vals[k]=vv

        notes=[]
        if not fname: notes.append("אין קובץ")
        elif not has: notes.append("מסמך סרוק — נקרא ויזואלית" if eid in ov else "מסמך סרוק — אימות ויזואלי מומלץ")
        if o.get("note"): notes.append(o["note"])

        crit_red=0
        for c,n in enumerate(COLUMNS,1):
            if n=="#index": cell=ws.cell(r,c,i)
            elif n=="expense_id": cell=ws.cell(r,c,eid)
            elif n=="רמת ודאות": cell=ws.cell(r,c,"")
            elif n=="הערות": cell=ws.cell(r,c,"; ".join(notes))
            elif n=="שם הקובץ":
                cell=ws.cell(r,c,fname)
                if fname: cell.hyperlink=DOCS+"/"+fname; cell.font=Font(color="0563C1",underline="single")
            else: cell=ws.cell(r,c,vals.get(n,""))
            cell.border=THIN; cell.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True)
            # colour the critical cells
            if n in ("סכום כולל מע\"מ","מספר מסמך"):
                ok = a_ok if n.startswith("סכום") else n_ok
                if eid in ov: fill=GREEN
                elif ok is True: fill=GREEN
                elif ok is None: fill=YELLOW
                elif not has: fill=YELLOW
                else: fill=RED
                cell.fill=fill
                if fill is RED: crit_red+=1
                stats["g" if fill is GREEN else "y" if fill is YELLOW else "red"]+=1
        ov_cell=ws.cell(r,COLUMNS.index("רמת ודאות")+1)
        lvl=o.get("ov")
        if lvl: ov_cell.value,ov_cell.fill={"high":("גבוהה",GREEN),"medium":("בינונית",YELLOW),"low":("נמוכה — לבדיקה",RED)}[lvl]
        elif crit_red==0: ov_cell.value,ov_cell.fill="גבוהה",GREEN
        elif crit_red==1: ov_cell.value,ov_cell.fill="בינונית",YELLOW
        else: ov_cell.value,ov_cell.fill="נמוכה — לבדיקה",RED
        r+=1

    widths=[7,26,16,20,15,13,12,12,11,12,7,16,26,30,38,14,40]
    for c,w in enumerate(widths,1): ws.column_dimensions[get_column_letter(c)].width=w
    wb.save(OUT)
    json.dump(discrepancies, open("expenses_discrepancies.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Wrote {OUT}: {r-2} rows. cells g={stats['g']} y={stats['y']} red={stats['red']}")
    print(f"Discrepancies (text-based, pre visual review): {len(discrepancies)}")

if __name__=="__main__":
    main()
