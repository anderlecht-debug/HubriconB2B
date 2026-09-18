"""The Reimbursement Playbook spreadsheet: the lead magnet that lives on a
seller's hard drive with Hubricon's name on it.

Every window, approval assumption and reason code is copied from
`hubricon_engine.models.recovery` so the template and the engine can never
disagree; `tests/test_template_parity.py` proves it. Demo rows come from the
Tarnhollow catalogue and say so.
"""

from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from hubricon_engine.models import recovery

from . import facts as F
from .demo import DEMO_DIR, TODAY
from .state import CONTENT_DIR

OUT = CONTENT_DIR.parent / "learn" / "reimbursement-playbook-template.xlsx"
NAVY = "050A1F"; AMBER = "FFC000"; GREY = "EEF0F5"

WINDOWS = [
    ("warehouse_eligible_after_days", recovery.WAREHOUSE_ELIGIBLE_AFTER_DAYS, "Days after a warehouse loss or damage before you may file"),
    ("warehouse_deadline_days", recovery.WAREHOUSE_DEADLINE_DAYS, "Days after a warehouse loss or damage until the window shuts"),
    ("refund_min_age_days", recovery.REFUND_MIN_AGE_DAYS, "A refund younger than this is not a claim yet"),
    ("refund_eligible_after_days", recovery.REFUND_ELIGIBLE_AFTER_DAYS, "Days after a refund before a no-return claim may be filed"),
    ("refund_deadline_days", recovery.REFUND_DEADLINE_DAYS, "Days after a refund until the no-return window shuts"),
    ("damaged_return_deadline_days", recovery.DAMAGED_RETURN_DEADLINE_DAYS, "Days after a damaged return until the window shuts"),
    ("expiring_within_days", recovery.EXPIRING_WITHIN_DAYS, "A claim this close to its deadline is called expiring"),
    ("found_match_window_days", recovery.FOUND_MATCH_WINDOW_DAYS, "A 'found' adjustment inside this many days offsets a loss"),
    ("reimbursement_match_window_days", recovery.REIMBURSEMENT_MATCH_WINDOW_DAYS, "A paid reimbursement inside this many days offsets a loss"),
    ("no_cost_value_fraction", recovery.NO_COST_VALUE_FRACTION_OF_PRICE, "Value fallback when no landed cost is on file, as a share of price"),
]
TYPES = ["warehouse_lost", "warehouse_damaged", "carrier_damaged", "transit_lost", "refund_no_return", "damaged_return", "reimbursement_reversal"]


def _head(ws, row, values, fill=NAVY, color="FFFFFF"):
    for i, v in enumerate(values, start=1):
        c = ws.cell(row=row, column=i, value=v)
        c.font = Font(bold=True, color=color); c.fill = PatternFill("solid", fgColor=fill)
        c.alignment = Alignment(vertical="center", wrap_text=True)


def _widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def build(out: Path = OUT) -> Path:
    data = F.load_data()
    rec = recovery.run(data, today=TODAY)
    values = recovery.unit_values(data)
    wb = Workbook()

    ws = wb.active; ws.title = "Read me"
    lines = [
        "The Reimbursement Playbook — working template (Hubricon)",
        "",
        "What this is: one sheet per Amazon report, a Claims sheet that dates and values every claim, and a filing log.",
        "Every window and approval assumption on the Windows sheet is the same constant Hubricon's engine runs; change a cell there and every claim recalculates.",
        "",
        "How to use it:",
        "1. Windows: set 'As of' to today (it is =TODAY() by default).",
        "2. COGS: paste your landed cost per SKU (unit cost + inbound freight + packaging). Claims are valued at landed cost; Amazon reimburses at manufacturing cost.",
        "3. Ledger / Returns / Reimbursements / Refunds: paste the raw exports. The helper columns on the right classify each row.",
        "4. Claims: one row per loss you are filing. Type, SKU, event date and units are yours; everything else is a formula.",
        "5. Filing log: the case id, the date filed, what Amazon paid, and whether it paid in cash or in kind.",
        "",
        "The rows already here are demo data from a fictional catalogue (Tarnhollow). Delete them before you paste your own.",
        "Inbound-shipment shortages are not in this playbook: they need the shipment reconciliation export.",
        "",
        "Free training and the written playbook: https://www.hubricon.com/learn/reimbursement-playbook",
    ]
    for i, t in enumerate(lines, start=1):
        c = ws.cell(row=i, column=1, value=t)
        if i == 1:
            c.font = Font(bold=True, size=14)
    _widths(ws, [120])

    ws = wb.create_sheet("Windows")
    _head(ws, 1, ["Setting", "Value", "What it means", "Source"])
    ws.cell(row=2, column=1, value="as_of"); ws.cell(row=2, column=2, value="=TODAY()"); ws.cell(row=2, column=3, value="The date every claim is judged against; the demo rows were judged as of " + TODAY.isoformat())
    ws.cell(row=2, column=4, value="you")
    for r, (name, val, meaning) in enumerate(WINDOWS, start=3):
        ws.cell(row=r, column=1, value=name); ws.cell(row=r, column=2, value=val); ws.cell(row=r, column=3, value=meaning)
        ws.cell(row=r, column=4, value="hubricon_engine.models.recovery")
    r0 = 3 + len(WINDOWS) + 1
    _head(ws, r0, ["Claim type", "P(approve)", "What it means", "Source"])
    for i, t in enumerate(TYPES, start=r0 + 1):
        ws.cell(row=i, column=1, value=t); ws.cell(row=i, column=2, value=recovery.P_APPROVE[t])
        ws.cell(row=i, column=3, value="Stated assumption used for expected value; Amazon's own unreconciled counts approve more often")
        ws.cell(row=i, column=4, value="hubricon_engine.models.recovery.P_APPROVE")
    r1 = r0 + len(TYPES) + 2
    _head(ws, r1, ["Claim type", "Eligible after (days)", "Deadline (days)", "Counted from"])
    windows_by_type = {
        "warehouse_lost": (recovery.WAREHOUSE_ELIGIBLE_AFTER_DAYS, recovery.WAREHOUSE_DEADLINE_DAYS, "the adjustment date"),
        "warehouse_damaged": (recovery.WAREHOUSE_ELIGIBLE_AFTER_DAYS, recovery.WAREHOUSE_DEADLINE_DAYS, "the adjustment date"),
        "carrier_damaged": (recovery.WAREHOUSE_ELIGIBLE_AFTER_DAYS, recovery.WAREHOUSE_DEADLINE_DAYS, "the adjustment date"),
        "transit_lost": (recovery.WAREHOUSE_ELIGIBLE_AFTER_DAYS, recovery.WAREHOUSE_DEADLINE_DAYS, "the adjustment date"),
        "refund_no_return": (recovery.REFUND_ELIGIBLE_AFTER_DAYS, recovery.REFUND_DEADLINE_DAYS, "the refund date"),
        "damaged_return": (0, recovery.DAMAGED_RETURN_DEADLINE_DAYS, "the return date"),
        "reimbursement_reversal": (0, recovery.WAREHOUSE_DEADLINE_DAYS, "the reversal date"),
    }
    for i, t in enumerate(TYPES, start=r1 + 1):
        e, dl, frm = windows_by_type[t]
        ws.cell(row=i, column=1, value=t); ws.cell(row=i, column=2, value=e); ws.cell(row=i, column=3, value=dl); ws.cell(row=i, column=4, value=frm)
    ws.cell(row=r1 + len(TYPES) + 2, column=1, value="TYPE_TABLE_ROW").font = Font(color="999999")
    ws.cell(row=r1 + len(TYPES) + 2, column=2, value=r1 + 1)
    _widths(ws, [34, 14, 90, 44])
    type_first, type_last = r1 + 1, r1 + len(TYPES)
    p_first, p_last = r0 + 1, r0 + len(TYPES)

    ws = wb.create_sheet("Reason codes")
    _head(ws, 1, ["Ledger reason", "Class", "Claimable?"])
    for i, (code, cls) in enumerate(sorted(recovery.REASON_CODES.items()), start=2):
        ws.cell(row=i, column=1, value=code); ws.cell(row=i, column=2, value=cls)
        ws.cell(row=i, column=3, value="yes" if cls in recovery.REIMBURSABLE else "no")
    _widths(ws, [16, 24, 12])

    ws = wb.create_sheet("COGS")
    _head(ws, 1, ["sku", "product_name", "unit_cost_usd", "inbound_freight_per_unit_usd", "packaging_per_unit_usd", "other_cost_per_unit_usd", "landed_cost (formula)"])
    for i, r in enumerate(sorted(data["cogs_inputs"], key=lambda x: x["sku"]), start=2):
        for j, k in enumerate(("sku", "product_name", "unit_cost_usd", "inbound_freight_per_unit_usd", "packaging_per_unit_usd", "other_cost_per_unit_usd"), start=1):
            ws.cell(row=i, column=j, value=r.get(k))
        ws.cell(row=i, column=7, value=f"=SUM(C{i}:F{i})")
    cogs_last = 1 + len(data["cogs_inputs"])
    _widths(ws, [18, 30, 14, 26, 22, 22, 20])

    ws = wb.create_sheet("Ledger")
    cols = ["Date", "FNSKU", "ASIN", "MSKU", "Title", "Event Type", "Reference ID", "Quantity", "Fulfillment Center", "Disposition", "Reason", "Country", "Reconciled Quantity", "Unreconciled Quantity"]
    _head(ws, 1, cols + ["Class (helper)", "Claimable (helper)", "Units lost (helper)"])
    for i, r in enumerate(sorted(data["inventory_ledger"], key=lambda x: x.get("event_date") or ""), start=2):
        vals = [r.get("event_date"), r.get("fnsku"), r.get("asin"), r.get("sku"), r.get("title"), r.get("event_type"), r.get("reference_id"), r.get("quantity"),
                r.get("fulfillment_center"), r.get("disposition"), r.get("reason"), r.get("country"), r.get("reconciled_qty"), r.get("unreconciled_qty")]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=i, column=j, value=v)
        ws.cell(row=i, column=15, value=f'=IFERROR(VLOOKUP(K{i},\'Reason codes\'!$A$2:$B$40,2,FALSE),"")')
        ws.cell(row=i, column=16, value=f'=IF(AND(ISNUMBER(SEARCH("adjust",F{i})),OR(O{i}="warehouse_lost",O{i}="warehouse_damaged",O{i}="carrier_damaged",O{i}="transit_lost")),"yes","no")')
        ws.cell(row=i, column=17, value=f'=IF(P{i}="yes",IF(N{i}<>"",N{i},MAX(0,-H{i})),0)')
    _widths(ws, [12, 12, 14, 18, 28, 12, 14, 10, 10, 14, 8, 8, 10, 12, 20, 12, 12])

    ws = wb.create_sheet("Returns")
    cols = ["return-date", "order-id", "sku", "asin", "fnsku", "product-name", "quantity", "fulfillment-center-id", "detailed-disposition", "reason", "status"]
    _head(ws, 1, cols + ["Claimable (helper)"])
    for i, r in enumerate(sorted(data["fba_returns"], key=lambda x: x.get("return_date") or ""), start=2):
        vals = [r.get("return_date"), r.get("order_id"), r.get("sku"), r.get("asin"), r.get("fnsku"), r.get("product_name"), r.get("quantity"),
                r.get("fulfillment_center_id"), r.get("detailed_disposition"), r.get("reason"), r.get("status")]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=i, column=j, value=v)
        ws.cell(row=i, column=12, value=f'=IF(AND(OR(I{i}="DAMAGED",I{i}="CARRIER_DAMAGED"),ISERROR(SEARCH("reimburs",K{i}))),"yes","no")')
    _widths(ws, [22, 22, 18, 14, 12, 28, 9, 12, 20, 20, 26, 12])

    ws = wb.create_sheet("Reimbursements")
    cols = ["approval-date", "reimbursement-id", "case-id", "amazon-order-id", "reason", "sku", "fnsku", "asin", "amount-per-unit", "amount-total", "quantity-reimbursed-cash", "quantity-reimbursed-inventory", "quantity-reimbursed-total", "original-reimbursement-type"]
    _head(ws, 1, cols + ["Cash share (helper)"])
    for i, r in enumerate(sorted(data["fba_reimbursements"], key=lambda x: x.get("approval_date") or ""), start=2):
        vals = [r.get("approval_date"), r.get("reimbursement_id"), r.get("case_id"), r.get("amazon_order_id"), r.get("reason"), r.get("sku"), r.get("fnsku"), r.get("asin"),
                r.get("amount_per_unit"), r.get("amount_total"), r.get("quantity_reimbursed_cash"), r.get("quantity_reimbursed_inventory"), r.get("quantity_reimbursed_total"), r.get("original_reimbursement_type")]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=i, column=j, value=v)
        ws.cell(row=i, column=15, value=f'=IF(M{i}>0,IF(K{i}<>"",K{i},M{i})/M{i},0)')
    _widths(ws, [14, 14, 14, 22, 20, 18, 12, 14, 12, 12, 10, 10, 10, 18, 12])

    ws = wb.create_sheet("Refunds")
    _head(ws, 1, ["date/time", "type", "order id", "sku", "quantity", "product sales", "total", "Age in days (helper)", "Units returned (helper)", "Short (helper)"])
    refunds = [t for t in data["settlement_transactions"] if (t.get("txn_type") or "").lower() == "refund"]
    for i, t in enumerate(sorted(refunds, key=lambda x: x.get("txn_datetime") or ""), start=2):
        vals = [t.get("txn_datetime"), t.get("txn_type"), t.get("order_id"), t.get("sku"), t.get("quantity"), t.get("product_sales"), t.get("total")]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=i, column=j, value=v)
        ws.cell(row=i, column=8, value=f"=IFERROR(Windows!$B$2-DATEVALUE(LEFT(A{i},10)),\"\")")
        ws.cell(row=i, column=9, value=f"=SUMIFS(Returns!$G:$G,Returns!$B:$B,C{i})")
        ws.cell(row=i, column=10, value=f"=MAX(0,ABS(E{i})-I{i})")
    _widths(ws, [22, 10, 22, 18, 9, 12, 12, 14, 14, 10])

    ws = wb.create_sheet("Claims")
    _head(ws, 1, ["Claim type", "SKU", "Event date", "Units", "Order id (refunds)", "Unit value", "Value", "Eligible from", "Deadline", "Days left",
                  "Status", "P(approve)", "Expected value", "Value basis"])
    claims = [c for c in rec["claims"]]
    for i, c in enumerate(claims, start=2):
        ws.cell(row=i, column=1, value=c["claim_type"]); ws.cell(row=i, column=2, value=c["sku"])
        ws.cell(row=i, column=3, value=date.fromisoformat(c["event_date"])); ws.cell(row=i, column=3).number_format = "yyyy-mm-dd"
        ws.cell(row=i, column=4, value=c["units"]); ws.cell(row=i, column=5, value=c.get("order_id"))
        if c["claim_type"] in ("refund_no_return", "reimbursement_reversal"):
            ws.cell(row=i, column=6, value=c["unit_value"])
        else:
            ws.cell(row=i, column=6, value=f"=IFERROR(VLOOKUP(B{i},COGS!$A$2:$G${cogs_last},7,FALSE),\"\")")
        ws.cell(row=i, column=7, value=f"=IF(F{i}=\"\",\"\",D{i}*F{i})")
        ws.cell(row=i, column=8, value=f"=C{i}+VLOOKUP(A{i},Windows!$A${type_first}:$C${type_last},2,FALSE)"); ws.cell(row=i, column=8).number_format = "yyyy-mm-dd"
        ws.cell(row=i, column=9, value=f"=C{i}+VLOOKUP(A{i},Windows!$A${type_first}:$C${type_last},3,FALSE)"); ws.cell(row=i, column=9).number_format = "yyyy-mm-dd"
        ws.cell(row=i, column=10, value=f"=I{i}-Windows!$B$2")
        ws.cell(row=i, column=11, value=f"=IF(Windows!$B$2>I{i},\"expired\",IF(Windows!$B$2<H{i},\"not_yet_eligible\",IF(J{i}<=Windows!$B${3 + [w[0] for w in WINDOWS].index('expiring_within_days')},\"expiring\",\"open\")))")
        ws.cell(row=i, column=12, value=f"=VLOOKUP(A{i},Windows!$A${p_first}:$B${p_last},2,FALSE)")
        ws.cell(row=i, column=13, value=f"=IF(G{i}=\"\",\"\",G{i}*L{i})")
        ws.cell(row=i, column=14, value=c["value_basis"])
    ws.cell(row=len(claims) + 3, column=1, value="Demo rows above are Tarnhollow demo data, judged as of " + TODAY.isoformat() + ". Delete them and add your own.").font = Font(italic=True, color="666666")
    _widths(ws, [22, 18, 12, 8, 22, 11, 11, 12, 12, 9, 16, 10, 14, 60])

    ws = wb.create_sheet("Filing log")
    _head(ws, 1, ["Claim row", "SKU", "Case id", "Filed on", "Amazon's answer", "Paid in cash", "Replaced in inventory (units)", "Paid on", "Notes"])
    _widths(ws, [10, 18, 16, 12, 18, 12, 24, 12, 40])

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
