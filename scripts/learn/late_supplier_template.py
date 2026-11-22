"""The Late Supplier's worksheet: learn/files/hubricon-late-supplier.xlsx.

Three sheets, the course's lessons 5 and 6 in a file a reader keeps:
  Orders     three dates per order; days late is worked out for every row
  Scorecard  per supplier: orders, share on time, average days late, the worst 1 in 10, the latest
  Reorder    the reorder point and the last day to order, from the worst-1-in-10 figure

Example rows are invented and say so. Formulas work in Excel and Google Sheets.

    python3 scripts/learn/late_supplier_template.py
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.formula import ArrayFormula

OUT = Path(__file__).resolve().parents[2] / "learn" / "files" / "hubricon-late-supplier.xlsx"
INK, INK3, BLUE, PANEL, RULE = "0A0E17", "636B7A", "0B5FFF", "F5F6F8", "E4E7EC"
FONT = "Inter"
ROWS = 500  # order rows the formulas cover

h1 = Font(name=FONT, size=16, bold=True, color=INK)
k = Font(name=FONT, size=9, bold=True, color=INK3)
body = Font(name=FONT, size=11, color=INK)
note = Font(name=FONT, size=10, color=INK3)
bold = Font(name=FONT, size=11, bold=True, color=INK)
leak = Font(name=FONT, size=11, bold=True, color=BLUE)
panel = PatternFill("solid", fgColor=PANEL)
under = Border(bottom=Side(style="thin", color=INK))
hair = Border(bottom=Side(style="thin", color=RULE))


def head(ws, title, lines):
    ws["A1"] = title
    ws["A1"].font = h1
    for i, t in enumerate(lines):
        c = ws.cell(row=2 + i, column=1, value=t)
        c.font = note
    ws.sheet_view.showGridLines = False


wb = Workbook()

# ---------------------------------------------------------------- Orders ----
o = wb.active
o.title = "Orders"
head(o, "Your orders", [
    "One row per order. Type over the example rows (they are invented), or paste your own below them.",
    "Days late = actual ready date minus promised ready date. A minus number means early.",
])
cols = ["Supplier", "Order date", "Promised ready date", "Actual ready date", "Days late"]
for j, c in enumerate(cols, start=1):
    cell = o.cell(row=5, column=j, value=c.upper())
    cell.font = k
    cell.border = under
widths = [28, 16, 20, 18, 12]
for j, w in enumerate(widths, start=1):
    o.column_dimensions[chr(64 + j)].width = w
example = [
    ("Example supplier A", 0, 30, 41), ("Example supplier A", 35, 65, 64), ("Example supplier A", 70, 100, 118),
    ("Example supplier A", 120, 150, 149), ("Example supplier B", 10, 40, 40), ("Example supplier B", 60, 90, 93),
]
start = date(2026, 1, 5)
for i in range(ROWS):
    r = 6 + i
    if i < len(example):
        s, a, b, c = example[i]
        o.cell(row=r, column=1, value=s)
        o.cell(row=r, column=2, value=start + timedelta(days=a))
        o.cell(row=r, column=3, value=start + timedelta(days=b))
        o.cell(row=r, column=4, value=start + timedelta(days=c))
    for j in (2, 3, 4):
        o.cell(row=r, column=j).number_format = "yyyy-mm-dd"
    o.cell(row=r, column=5, value=f'=IF(OR(C{r}="",D{r}=""),"",D{r}-C{r})')
    o.cell(row=r, column=5).number_format = '0;"−"0;0'
    for j in range(1, 6):
        o.cell(row=r, column=j).font = body
        o.cell(row=r, column=j).border = hair
o.freeze_panes = "A6"
last = 6 + ROWS - 1
SUP, LATE = f"Orders!$A$6:$A${last}", f"Orders!$E$6:$E${last}"

# ------------------------------------------------------------- Scorecard ----
s = wb.create_sheet("Scorecard")
head(s, "Your suppliers, scored", [
    "Type each supplier's name exactly as it appears on Orders. Everything else fills in.",
    "Track one number: the worst 1 in 10. It is the lateness nine orders in ten come in under, and what your extra stock has to cover.",
    "With fewer than 10 orders it is mostly the single worst order: a starting point that sharpens with every order.",
])
cols = ["Supplier", "Orders", "On time", "Average days late", "Worst 1 in 10, days late", "Latest ever"]
for j, c in enumerate(cols, start=1):
    cell = s.cell(row=6, column=j, value=c.upper())
    cell.font = k
    cell.border = under
for j, w in enumerate([28, 10, 10, 18, 24, 12], start=1):
    s.column_dimensions[chr(64 + j)].width = w
names = ["Example supplier A", "Example supplier B"] + [""] * 8
for i, n in enumerate(names):
    r = 7 + i
    s.cell(row=r, column=1, value=n or None).font = bold
    s.cell(row=r, column=1).fill = panel
    s.cell(row=r, column=2, value=f'=IF(A{r}="","",COUNTIFS({SUP},A{r},{LATE},"<>"))')
    s.cell(row=r, column=3, value=f'=IF(OR(A{r}="",B{r}=0),"",COUNTIFS({SUP},A{r},{LATE},"<=0")/B{r})')
    s.cell(row=r, column=3).number_format = "0%"
    s.cell(row=r, column=4, value=f'=IF(OR(A{r}="",B{r}=0),"",AVERAGEIFS({LATE},{SUP},A{r}))')
    s.cell(row=r, column=4).number_format = "0.0"
    s[f"E{r}"] = ArrayFormula(f"E{r}", f'=IF(OR(A{r}="",B{r}=0),"",PERCENTILE(IF(({SUP}=A{r})*ISNUMBER({LATE}),{LATE}),0.9))')
    s.cell(row=r, column=5).number_format = "0"
    s[f"F{r}"] = ArrayFormula(f"F{r}", f'=IF(OR(A{r}="",B{r}=0),"",MAX(IF(({SUP}=A{r})*ISNUMBER({LATE}),{LATE})))')
    for j in range(2, 7):
        s.cell(row=r, column=j).font = leak if j == 5 else body
    for j in range(1, 7):
        s.cell(row=r, column=j).border = hair

# --------------------------------------------------------------- Reorder ----
ro = wb.create_sheet("Reorder")
head(ro, "When your next order goes out", [
    "Fill in the shaded cells for one product. Order when stock on hand and on the way falls to the reorder point.",
    "It assumes you sell at the same pace until the order lands. Arithmetic on your numbers, not a forecast.",
])
ro.column_dimensions["A"].width = 52
ro.column_dimensions["B"].width = 16
ro.column_dimensions["C"].width = 60
rows = [
    ("Units you sell a day", 40, "Your last 30 days of sales, divided by 30"),
    ("Units on hand and on the way", 4000, "Everything you own that hasn't sold yet"),
    ("Promised production days", 30, "Order date to promised ready date"),
    ("Worst 1 in 10, days late", "=IFERROR(Scorecard!E7,12)", "From the Scorecard; type a number to override"),
    ("Shipping, door to door, days", 35, "Ready at the supplier to sellable at your warehouse"),
]
for i, (label, v, hint) in enumerate(rows):
    r = 5 + i
    ro.cell(row=r, column=1, value=label).font = body
    c = ro.cell(row=r, column=2, value=v)
    c.font = bold
    c.fill = panel
    ro.cell(row=r, column=3, value=hint).font = note
    for j in (1, 2, 3):
        ro.cell(row=r, column=j).border = hair
outs = [
    ("Reorder point, units", "=B5*(B7+B8+B9)", "0", "A day's sales × (promised + worst 1 in 10 late + shipping)"),
    ("Days until the shelf is empty", "=IF(B5=0,\"\",B6/B5)", "0", "On hand and on the way ÷ a day's sales"),
    ("Last day to order, counting from today", "=IF(B5=0,\"\",B12-(B7+B8+B9))", "0", "A minus number means it's already late: order now"),
    ("Order by this date", "=IF(B5=0,\"\",TODAY()+B13)", "yyyy-mm-dd", "Put it in your calendar"),
    ("If you trusted the promise, you'd order on day", "=IF(B5=0,\"\",B12-(B7+B9))", "0", "The difference is the cover lateness needs"),
]
for i, (label, f, fmt, hint) in enumerate(outs):
    r = 11 + i
    ro.cell(row=r, column=1, value=label).font = bold
    c = ro.cell(row=r, column=2, value=f)
    c.font = leak if i in (0, 2) else bold
    c.number_format = fmt
    ro.cell(row=r, column=3, value=hint).font = note
    for j in (1, 2, 3):
        ro.cell(row=r, column=j).border = hair

for ws in wb.worksheets:
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="center", wrap_text=False)

wb.properties.creator = "Hubricon"
wb.properties.title = "The Late Supplier: worksheet"
OUT.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT)
print(OUT)
