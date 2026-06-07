"""Package the PCN invoices into a self-contained folder tree + linked Excel.

Reads PCN_FINAL.xlsx, copies each invoice's source file into
  מסמכי_PCN/<bi-monthly period>/<NN>_<supplier>.<ext>
naming it by a running index NN, and writes a fresh Excel where every row has a
clickable hyperlink ("צפייה במסמך") to its file (relative path) plus the index.
Everything is zipped so the links work after extraction (and can be dragged to Drive).
"""
import os, re, shutil, zipfile
from openpyxl import load_workbook, Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

SRC = {"טיוטה": "documents", "מאושר": "documents_expenses"}
PKG = "/tmp/pcn_pkg"
DOCDIR = "מסמכי_PCN"
HDR = PatternFill("solid", fgColor="305496"); SUB = PatternFill("solid", fgColor="DDEBF7")
GREEN = PatternFill("solid", fgColor="C6EFCE"); YELLOW = PatternFill("solid", fgColor="FFEB9C")
RED = PatternFill("solid", fgColor="FFC7CE"); THIN = Border(*[Side(style="thin", color="D9D9D9")]*4)
CF = {"🟩": GREEN, "🟨": YELLOW, "🟥": RED}


def san(s, n=22):
    s = re.sub(r'[\\/:*?"<>|\n\r\t.]+', "_", str(s or "ספק"))
    return re.sub(r"\s+", "-", s)[:n].strip("-_") or "ספק"


def main():
    if os.path.exists(PKG):
        shutil.rmtree(PKG)
    os.makedirs(os.path.join(PKG, DOCDIR))
    ws = load_workbook("PCN_FINAL.xlsx")["חשבוניות לקיזוז"]
    head = [c.value for c in ws[1]]
    col = {n: i for i, n in enumerate(head)}
    out = Workbook(); o = out.active; o.title = "חשבוניות לקיזוז"; o.sheet_view.rightToLeft = True
    NEW = ["#מסמך", "צפייה במסמך"] + head
    for c, name in enumerate(NEW, 1):
        cell = o.cell(1, c, name); cell.fill = HDR; cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); cell.border = THIN
    o.freeze_panes = "A2"
    r = 2; idx = 0; copied = 0; missing = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        src = row[col["מקור"]]
        if src not in SRC:  # period sub-header row
            o.cell(r, 1, src).font = Font(bold=True)
            for c in range(1, len(NEW)+1): o.cell(r, c).fill = SUB
            r += 1; continue
        idx += 1
        period = str(row[col["תקופה"]] or "ללא").replace("/", "_")
        sup = row[col["שם ספק"]]
        fname = row[col["קובץ"]]
        link = ""
        if fname:
            srcpath = os.path.join(SRC[src], fname)
            ext = fname.rsplit(".", 1)[-1] if "." in fname else "pdf"
            newname = f"{idx:03d}_{san(sup)}.{ext}"
            pdir = os.path.join(PKG, DOCDIR, period)
            os.makedirs(pdir, exist_ok=True)
            if os.path.exists(srcpath):
                shutil.copy(srcpath, os.path.join(pdir, newname)); copied += 1
                link = f"{DOCDIR}/{period}/{newname}"
            else:
                missing += 1
        vals = [idx, "פתח מסמך ↗" if link else "אין קובץ"] + list(row)
        for c, v in enumerate(vals, 1):
            cell = o.cell(r, c, v); cell.border = THIN
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if c == 2 and link:
                cell.hyperlink = link; cell.font = Font(color="0563C1", underline="single", bold=True)
            if NEW[c-1] == "ודאות" and v in CF: cell.fill = CF[v]
            if NEW[c-1] == "סטטוס" and v: cell.fill = RED
        r += 1
    widths = [7, 14, 12, 11, 10, 24, 13, 16, 15, 11, 12, 14, 18, 18, 7, 18, 30, 26]
    for c, w in enumerate(widths, 1):
        o.column_dimensions[get_column_letter(c)].width = w
    out.save(os.path.join(PKG, "PCN_FINAL_עם_קישורים.xlsx"))
    # zip
    zpath = "/tmp/PCN_חבילה_מלאה.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(PKG):
            for f in files:
                fp = os.path.join(root, f)
                z.write(fp, os.path.relpath(fp, PKG))
    print(f"copied {copied} files, missing {missing}, rows {idx}")
    print("zip:", zpath, round(os.path.getsize(zpath)/1e6, 1), "MB")


if __name__ == "__main__":
    main()
