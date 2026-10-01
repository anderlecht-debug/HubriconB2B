"""The Fee Staircase template: the course's spreadsheet, built from the engine's own cards.

    uv run --no-project --with openpyxl python scripts/learn/fee_staircase_template.py

Writes learn/files/hubricon-fee-staircase.xlsx. Every fee in it is read from
ratecard.json (the table the engine exports, which lib/fees.js prices with) and
every storage figure from engine/src/hubricon_engine/models/fee_schedule.py, so
the template a reader downloads and the engine that priced the case study run
the same card. The formulas are the arithmetic of lib/fees.js written out in
cells; scripts/learn/verify_fee_staircase.py recalculates a copy in LibreOffice
and holds it to the golden cases that pin lib/fees.js to the Python.

openpyxl writes formulas without values. Recalculate before publishing, so a
reader who opens the file in a viewer that does not calculate still sees the
numbers: the verify script does that for the published file too (--publish).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "learn" / "files" / "hubricon-fee-staircase.xlsx"
COURSE_URL = "https://www.hubricon.com/learn/fee-staircase"

# lib/fees.js: the thresholds the engine's detectors use. Hubricon's, not Amazon's.
MAX_SHAVEABLE_OZ = 2.0
MIN_PER_UNIT_USD = 0.08
MAX_ENVELOPE_OVERAGE = 1.35
MIN_DIM_WEIGHT_RATIO = 1.3
UNITS_LOW, UNITS_HIGH = 0.5, 1.5
# scripts/case-study.mjs: the stated assumptions of the case study.
LANDED_COST_SHARE = 0.25
COST_DRIFT = 0.10
# engine/src/hubricon_engine/models/fee_schedule.py, EFFECTIVE 2026-01-15.
STORAGE_EFFECTIVE = "2026-01-15"
STORAGE = {"offpeak": 0.78, "peak": 2.40}
AGED = [(181, 210, 0.50), (211, 240, 1.00), (241, 270, 1.50), (271, 300, 5.45),
        (301, 330, 5.70), (331, 365, 5.90), (366, None, 6.90)]
AGED_MIN_366 = 0.15

N_MONTHS = 10000
CATALOGUE_ROWS = 500
EDGE_NAMES = ["Largest", "Weight", "Price", "Size tier", "Box"]

# The example a reader overwrites. Invented, and labelled so on every sheet.
EXAMPLE = {"name": "Example (invented): a 12.6 oz kitchen item", "price": 14.99, "category": "Home & Kitchen",
           "weight": 12.6, "sides": (9, 6, 3), "bsr": 2400}
EXAMPLE_AGES = [1800, 240, 160, 120, 60, 0, 0, 0]
EXAMPLE_SOLD_30 = 900

# -- look ------------------------------------------------------------------------
ARIAL = "Arial"
F_BODY = Font(name=ARIAL, size=10)
F_BOLD = Font(name=ARIAL, size=10, bold=True)
F_TITLE = Font(name=ARIAL, size=16, bold=True)
F_H = Font(name=ARIAL, size=11, bold=True)
F_NOTE = Font(name=ARIAL, size=9, color="595959")
F_INPUT = Font(name=ARIAL, size=10, color="0000FF")
F_LINK = Font(name=ARIAL, size=10, color="008000")
F_URL = Font(name=ARIAL, size=10, color="0B5FFF", underline="single")
FILL_INPUT = PatternFill("solid", fgColor="FFFF00")
FILL_HEAD = PatternFill("solid", fgColor="F2F2F2")
RULE = Border(bottom=Side(style="thin", color="BFBFBF"))
WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")

USD2 = '$#,##0.00;($#,##0.00);"-"'
USD4 = '$#,##0.0000;($#,##0.0000);"-"'
USD0 = '$#,##0;($#,##0);"-"'
OZ = '0.00'
PCT = '0.0%;(0.0%);"-"'
INT = '#,##0'


def load():
    rc = json.loads((ROOT / "ratecard.json").read_text())
    return rc


def put(ws, ref, value, font=F_BODY, fmt=None, fill=None, align=None, comment=None):
    c = ws[ref]
    c.value = value
    c.font = font
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    if align:
        c.alignment = align
    if comment:
        c.comment = Comment(comment, "Hubricon")
    return c


def inp(ws, ref, value, fmt=None, comment=None):
    return put(ws, ref, value, F_INPUT, fmt, FILL_INPUT, comment=comment)


def name(wb, nm, ref):
    wb.defined_names[nm] = DefinedName(nm, attr_text=ref)


def head_row(ws, row, labels, start_col=1):
    for i, label in enumerate(labels):
        c = ws.cell(row=row, column=start_col + i, value=label)
        c.font = F_BOLD
        c.fill = FILL_HEAD
        c.alignment = Alignment(wrap_text=True, vertical="bottom")
        c.border = RULE


# -- the arithmetic of lib/fees.js, as formulas ---------------------------------------

def fee_f(tier, w, band, card):
    """fees.fulfilmentFee: the card's tread for this tier, weight and price band, plus the surcharge.
    `card` is 0 for non-peak, 1 for peak: the six fee columns are three price bands per card."""
    col = f"{card * 3}+{band}"
    ss = f"INDEX(SS_FEES,SUMPRODUCT(--(SS_EDGES<{w}))+1,{col})"
    ls = (f"IF({w}<=OVER3_FROM,INDEX(LS_FEES,SUMPRODUCT(--(LS_EDGES<{w}))+1,{col}),"
          f"INDEX(OVER3_BASE,1,{col})+OVER3_PER4*CEILING(({w}-OVER3_FROM)/4,1))")
    return (f'IF(OR({w}="",{band}="",{tier}=""),"",IF({tier}="Small standard",IF({w}>SS_MAX,"",ROUND({ss}*(1+FUEL),4)),'
            f'IF({tier}="Large standard",IF({w}>LS_MAX,"",ROUND({ls}*(1+FUEL),4)),"")))')


def edge_below_f(tier, w):
    """fees.bandEdgeBelow: the heaviest band edge this weight is above, within its tier."""
    ss = f'IF(SUMPRODUCT(--(SS_EDGES<{w}))=0,"",INDEX(SS_EDGES,SUMPRODUCT(--(SS_EDGES<{w}))))'
    ls = (f'IF({w}>OVER3_FROM,OVER3_FROM+4*(CEILING(({w}-OVER3_FROM)/4,1)-1),'
          f'IF(SUMPRODUCT(--(LS_EDGES<{w}))=0,"",INDEX(LS_EDGES,SUMPRODUCT(--(LS_EDGES<{w})))))')
    return f'IF({w}="","",IF({tier}="Small standard",{ss},IF({tier}="Large standard",{ls},"")))'


def tier_f(bw, l, m, s):
    """fees.sizeTier on the billable weight. No dimensions, no tier: a tier is never guessed."""
    return (f'IF(OR({bw}="",{l}=""),"",IF(AND({bw}<=SS_MAX,{l}<=SS_L,{m}<=SS_M,{s}<=SS_S),"Small standard",'
            f'IF(AND({bw}<=LS_MAX,{l}<=LS_L,{m}<=LS_M,{s}<=LS_S),"Large standard","Oversize")))')


def units_f(bsr, cat):
    """fees.estimateUnits: the power-law rank curve, scaled for the category."""
    return (f'IF(OR({bsr}="",{bsr}<1),"",ROUND(IFERROR(INDEX(CAT_SCALE,MATCH({cat},CATS,0)),UC_DEFAULT)*'
            f'IF({bsr}>=UC_KNEE,10^(UC_A-UC_B*LOG10({bsr})),10^(UC_A-UC_B*LOG10(UC_KNEE))*(UC_KNEE/{bsr})^UC_HEXP),1))')


def band_f(price):
    return f'IF({price}="","",IF({price}<BAND_LO,1,IF({price}<=BAND_HI,2,3)))'


def referral_rate_f(price, cat, override=None):
    base = f'IFERROR(INDEX(CAT_REF,MATCH({cat},CATS,0)),REF_DEFAULT)'
    if override:
        base = f'IF({override}<>"",{override},{base})'
    return f'IF({price}="","",{base})'


# -- sheets ---------------------------------------------------------------------------

def rate_card(wb, rc):
    ws = wb.create_sheet("Rate card")
    fba = rc["fba"]
    np_, pk = fba["cards"]["non_peak"], fba["cards"]["peak"]
    ws.column_dimensions["A"].width = 44
    for col in "BCDEFG":
        ws.column_dimensions[col].width = 14
    ws.column_dimensions["H"].width = 70
    put(ws, "A1", "Rate card: Amazon's published US fees, 2026", F_TITLE)
    put(ws, "A2", f"As Hubricon's engine loads them (ratecard.json, generated {rc['generated']}). Amazon reprices about once a year: "
                  "check the live schedule in Seller Central before you act on a number.", F_NOTE)
    put(ws, "A3", "Source: " + np_["source"] + f" ({np_['effective']} to {np_['through']}) and " + pk["source"]
        + f" ({pk['effective']} to {pk['through']}); sellercentral.amazon.com, Fulfillment by Amazon fees, US. "
          "Cross-checked by the engine against two published reproductions of the same card.", F_NOTE)

    r = 5
    put(ws, f"A{r}", "Constants", F_H)
    rows = [
        ("Fuel and logistics surcharge, on every fulfilment fee", fba["fuel_surcharge"], PCT, "FUEL", f"In force since {fba['fuel_surcharge_from']}, no end date."),
        ("Price band edge: under this is the low-price band ($)", fba["price_band_edges"][0], USD2, "BAND_LO", "Under $10, $10 to $50 (inclusive), over $50: three columns on every card."),
        ("Price band edge: over this is the top band ($)", fba["price_band_edges"][1], USD2, "BAND_HI", None),
        ("Small standard: heaviest (oz)", fba["small_standard_max_oz"], OZ, "SS_MAX", None),
        ("Small standard: longest side (in)", fba["small_standard_envelope_in"][0], OZ, "SS_L", "The sides are sorted longest first before they are compared."),
        ("Small standard: median side (in)", fba["small_standard_envelope_in"][1], OZ, "SS_M", None),
        ("Small standard: shortest side (in)", fba["small_standard_envelope_in"][2], OZ, "SS_S", None),
        ("Large standard: heaviest (oz)", fba["large_standard_max_oz"], OZ, "LS_MAX", "20 lb."),
        ("Large standard: longest side (in)", fba["large_standard_envelope_in"][0], OZ, "LS_L", None),
        ("Large standard: median side (in)", fba["large_standard_envelope_in"][1], OZ, "LS_M", None),
        ("Large standard: shortest side (in)", fba["large_standard_envelope_in"][2], OZ, "LS_S", None),
        ("Dimensional weight divisor (cubic inches per lb)", fba["dim_divisor"], "0", "DIM_DIV", "Amazon bills the greater of the unit's weight and its dimensional weight."),
        ("Dimensional weight applies from (cubic inches)", fba["dim_weight_min_cuft"] * 1728, INT, "DIM_MIN_CUIN", "One cubic foot. Under it the engine bills real weight, as the ground carriers do."),
        ("Large standard: table ends at (oz)", np_["large_standard"][-1][0], OZ, "OVER3_FROM", "3 lb. Above it: a base fee plus a step per 4 oz."),
        ("Over 3 lb: per 4 oz above 3 lb ($)", np_["over_3lb_per_4oz"], USD2, "OVER3_PER4", None),
        ("Referral fee: minimum per unit ($)", fba["referral_min_usd"], USD2, "REF_MIN", None),
        ("Referral fee: rate where the category is not listed", fba["referral_default"], PCT, "REF_DEFAULT", "Several categories charge a lower rate on low-priced items. Check your category's published rate and type it on One listing if it differs."),
        ("Holiday peak card: first day", date.fromisoformat(pk["effective"]), "yyyy-mm-dd", "PEAK_FROM", None),
        ("Holiday peak card: last day", date.fromisoformat(pk["through"]), "yyyy-mm-dd", "PEAK_TO", None),
        ("Months a year on the peak card", 3, "0", "PEAK_MONTHS", "October 15 to January 14 is three months. A year is nine months on the non-peak card and three on peak."),
    ]
    r += 1
    head_row(ws, r, ["What", "Value", "", "", "", "", "", "Note"])
    for label, value, fmt, nm, note in rows:
        r += 1
        put(ws, f"A{r}", label)
        put(ws, f"B{r}", value, fmt=fmt)
        if note:
            put(ws, f"H{r}", note, F_NOTE)
        name(wb, nm, f"'Rate card'!$B${r}")

    r += 2
    put(ws, f"A{r}", "Hubricon's thresholds (ours, not Amazon's: the same ones the engine uses)", F_H)
    r += 1
    head_row(ws, r, ["What", "Value", "", "", "", "", "", "Why"])
    for label, value, fmt, nm, note in [
        ("A weight edge counts if the unit is this close above it (oz)", MAX_SHAVEABLE_OZ, OZ, "MAX_SHAVE", "Further over than this is a redesign, not a shave."),
        ("Smallest gap worth a move ($ per unit)", MIN_PER_UNIT_USD, USD2, "MIN_UNIT", "Under eight cents a unit, the change costs more attention than it pays."),
        ("A size-tier edge counts if one side is at most this far over", MAX_ENVELOPE_OVERAGE, '0.00"x"', "MAX_ENV", "1.35 means up to 35% over the small-standard limit on that one side."),
        ("Dimensional weight counts if it is at least this times the real weight", MIN_DIM_WEIGHT_RATIO, '0.00"x"', "MIN_DIM_RATIO", None),
        ("Volume range: low end, times the rank estimate", UNITS_LOW, '0.00"x"', "U_LOW", "The rank curve is wrong by a factor of two either way, so a monthly figure is always a range."),
        ("Volume range: high end, times the rank estimate", UNITS_HIGH, '0.00"x"', "U_HIGH", None),
        ("Volume doubt for the simulation (sigma of a lognormal)", "=LN(2)/1.645", "0.0000", "SIGMA", "Puts the 5th and 95th percentiles at half and double the estimate."),
        ("Landed cost when you have not typed one (share of price)", LANDED_COST_SHARE, PCT, "LANDED_SHARE", "The case study's stated assumption. Type your own cost; it is always better."),
    ]:
        r += 1
        put(ws, f"A{r}", label)
        put(ws, f"B{r}", value, fmt=fmt)
        if note:
            put(ws, f"H{r}", note, F_NOTE)
        name(wb, nm, f"'Rate card'!$B${r}")

    def fee_table(r, title, rows_np, rows_pk, edges_name, fees_name):
        put(ws, f"A{r}", title, F_H)
        r += 1
        head_row(ws, r, ["Up to (oz)", "Non-peak: under $10", "Non-peak: $10 to $50", "Non-peak: over $50",
                         "Peak: under $10", "Peak: $10 to $50", "Peak: over $50", "Note"])
        first = r + 1
        for (edge, np_fees), (_, pk_fees) in zip(rows_np, rows_pk):
            r += 1
            put(ws, f"A{r}", edge, fmt=OZ)
            for i, v in enumerate(list(np_fees) + list(pk_fees)):
                put(ws, f"{get_column_letter(2 + i)}{r}", v, fmt=USD2)
        put(ws, f"H{first}", "Before the fuel and logistics surcharge. A unit pays the first row whose edge it does not exceed.", F_NOTE)
        name(wb, edges_name, f"'Rate card'!$A${first}:$A${r}")
        name(wb, fees_name, f"'Rate card'!$B${first}:$G${r}")
        return r

    r += 2
    r = fee_table(r, "Small standard: fulfilment fee per unit ($)", np_["small_standard"], pk["small_standard"], "SS_EDGES", "SS_FEES")
    r += 2
    r = fee_table(r, "Large standard: fulfilment fee per unit ($)", np_["large_standard"], pk["large_standard"], "LS_EDGES", "LS_FEES")
    r += 1
    put(ws, f"A{r}", "Over 3 lb: base, before the per-4-oz steps")
    for i, v in enumerate(list(np_["over_3lb_base"]) + list(pk["over_3lb_base"])):
        put(ws, f"{get_column_letter(2 + i)}{r}", v, fmt=USD2)
    name(wb, "OVER3_BASE", f"'Rate card'!$B${r}:$G${r}")

    r += 2
    put(ws, f"A{r}", f"Storage and the aged-inventory surcharge, standard size (in force {STORAGE_EFFECTIVE})", F_H)
    r += 1
    head_row(ws, r, ["What", "$ per cubic foot a month", "", "", "", "", "", "Note"])
    r += 1
    put(ws, f"A{r}", "Monthly storage, January to September")
    put(ws, f"B{r}", STORAGE["offpeak"], fmt=USD2)
    name(wb, "STOR_OFF", f"'Rate card'!$B${r}")
    r += 1
    put(ws, f"A{r}", "Monthly storage, October to December")
    put(ws, f"B{r}", STORAGE["peak"], fmt=USD2)
    name(wb, "STOR_PEAK", f"'Rate card'!$B${r}")
    r += 1
    head_row(ws, r, ["Aged-inventory surcharge: age from (days)", "to (days)", "$ per cubic foot a month", "", "", "", "", "Note"])
    first = r + 1
    for lo, hi, rate in AGED:
        r += 1
        put(ws, f"A{r}", lo, fmt=INT)
        put(ws, f"B{r}", hi if hi is not None else "and over", fmt=INT)
        put(ws, f"C{r}", rate, fmt=USD2)
    put(ws, f"H{first + 3}", "Day 271: the step from $1.50 to $5.45, about 3.6 times. Amazon takes the snapshot on the 15th of each month.", F_NOTE)
    name(wb, "AGED_RATES", f"'Rate card'!$C${first}:$C${r}")
    r += 1
    put(ws, f"A{r}", "366 days and over: or this much per unit, whichever is greater ($)")
    put(ws, f"B{r}", AGED_MIN_366, fmt=USD2)
    name(wb, "AGED_MIN", f"'Rate card'!$B${r}")
    r += 1
    put(ws, f"A{r}", "Source: engine/src/hubricon_engine/models/fee_schedule.py, Amazon's US schedule in force 2026-01-15.", F_NOTE)

    r += 2
    put(ws, f"A{r}", "Categories: referral rate and the rank curve's scale", F_H)
    r += 1
    head_row(ws, r, ["Category", "Referral rate", "Volume scale", "", "", "", "", "Note"])
    refs, scales = fba["referral_by_category"], rc["units_curve"]["category_scale"]
    cats = sorted(set(refs) | set(scales))
    first = r + 1
    for cat in cats:
        r += 1
        put(ws, f"A{r}", cat.title())
        put(ws, f"B{r}", refs.get(cat, fba["referral_default"]), fmt=PCT)
        put(ws, f"C{r}", scales.get(cat, rc["units_curve"]["default_scale"]), fmt="0.00")
        missing = [w for w, src in (("referral rate", refs), ("volume scale", scales)) if cat not in src]
        if missing:
            put(ws, f"H{r}", "Default " + " and ".join(missing) + ": the engine holds no category-specific figure.", F_NOTE)
    name(wb, "CATS", f"'Rate card'!$A${first}:$A${r}")
    name(wb, "CAT_REF", f"'Rate card'!$B${first}:$B${r}")
    name(wb, "CAT_SCALE", f"'Rate card'!$C${first}:$C${r}")

    r += 2
    uc = rc["units_curve"]
    put(ws, f"A{r}", "The rank curve: monthly units from a top-level Best Sellers Rank", F_H)
    put(ws, f"H{r}", uc["note"].capitalize() + ".", F_NOTE)
    r += 1
    head_row(ws, r, ["What", "Value", "", "", "", "", "", "Note"])
    for label, value, nm, note in [
        ("a: units = scale × 10^(a − b × log10(rank))", uc["a"], "UC_A", "A power law fitted by the engine (harvest/amazon.py)."),
        ("b", uc["b"], "UC_B", None),
        ("Head of the curve starts above this rank", uc["head_knee"], "UC_KNEE", "Above it (ranks 1 to 999) the curve flattens: knee units × (knee ÷ rank)^exponent."),
        ("Head exponent", uc["head_exp"], "UC_HEXP", None),
        ("Scale where the category is not listed", uc["default_scale"], "UC_DEFAULT", None),
    ]:
        r += 1
        put(ws, f"A{r}", label)
        put(ws, f"B{r}", value)
        if note:
            put(ws, f"H{r}", note, F_NOTE)
        name(wb, nm, f"'Rate card'!$B${r}")

    r += 2
    put(ws, f"A{r}", "Lists", F_H)
    r += 1
    first = r
    for nm in EDGE_NAMES:
        put(ws, f"A{r}", nm)
        r += 1
    name(wb, "EDGE_NAMES", f"'Rate card'!$A${first}:$A${r - 1}")
    put(ws, f"A{r}", "Jan–Sep")
    put(ws, f"A{r + 1}", "Oct–Dec")
    name(wb, "SEASONS", f"'Rate card'!$A${r}:$A${r + 1}")
    ws.freeze_panes = "B5"
    return ws


def one_listing(wb):
    ws = wb.create_sheet("One listing")
    ws.column_dimensions["A"].width = 50
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 16
    ws.column_dimensions["F"].width = 70
    put(ws, "A1", "One listing on Amazon's fee staircase", F_TITLE)
    put(ws, "A2", "Type the five public numbers in the yellow cells (lesson 2). Everything else is arithmetic off Amazon's published 2026 cards on the Rate card sheet.", F_NOTE)
    put(ws, "A3", "Estimates from published cards, not Amazon's bill. For your own SKUs, the Fee Preview report is the ground truth.", F_NOTE)

    put(ws, "A4", "Your listing", F_H)
    head_row(ws, 4, ["Your listing", "Value", "", "", "", "Where to find it"])
    ex = EXAMPLE
    inputs = [
        (5, "Listing", ex["name"], None, "Anything you will recognise. The example row is invented: overwrite it."),
        (6, "Price ($)", ex["price"], USD2, "The buy box price on the product page."),
        (7, "Category", ex["category"], None, "The top-level category the Best Sellers Rank is quoted in. Pick from the list, or type one: an unlisted category uses the default referral rate and volume scale."),
        (8, "Item weight (oz)", ex["weight"], OZ, "Product information, \"Item Weight\". Pounds × 16. It is a floor: Amazon bills the packed unit."),
        (9, "Side 1 (in)", ex["sides"][0], OZ, "Product information, \"Product Dimensions\" or \"Package Dimensions\". Any order: they are sorted below."),
        (10, "Side 2 (in)", ex["sides"][1], OZ, None),
        (11, "Side 3 (in)", ex["sides"][2], OZ, None),
        (12, "Best Sellers Rank, top-level category", ex["bsr"], INT, "Product information, the first rank listed (not the sub-category rank)."),
        (13, "Your own units a month (optional)", None, INT, "Your listing? Business Reports gives the real number. Typed here, it replaces the rank estimate."),
        (14, "Landed cost per unit ($, optional)", None, USD2, "Unit cost plus freight to Amazon plus packaging. Blank: 25% of the price, an assumption."),
        (15, "Referral rate (optional)", None, PCT, "Blank: the category's rate on the Rate card. Type your category's published rate if it differs."),
    ]
    for row, label, value, fmt, note in inputs:
        put(ws, f"A{row}", label)
        inp(ws, f"B{row}", value, fmt)
        if note:
            put(ws, f"F{row}", note, F_NOTE, align=WRAP)
    dv = DataValidation(type="list", formula1="CATS", allow_blank=True, showErrorMessage=False)
    ws.add_data_validation(dv)
    dv.add("B7")

    head_row(ws, 17, ["What Amazon sees", "Value", "", "", "", "How"])
    rows = [
        (18, "Longest side (in)", '=IF(COUNT(B9:B11)<3,"",ROUND(LARGE(B9:B11,1),2))', OZ, None),
        (19, "Median side (in)", '=IF(COUNT(B9:B11)<3,"",ROUND(LARGE(B9:B11,2),2))', OZ, None),
        (20, "Shortest side (in)", '=IF(COUNT(B9:B11)<3,"",ROUND(SMALL(B9:B11,1),2))', OZ, None),
        (21, "Cubic inches", '=IF(B18="","",B18*B19*B20)', '#,##0.0', None),
        (22, "Dimensional weight (oz)", '=IF(B21="","",IF(B21<DIM_MIN_CUIN,"",ROUND(B21/DIM_DIV*16,2)))', OZ, "Cubic inches ÷ 139, in pounds, × 16. Blank under a cubic foot: there, real weight is billed."),
        (23, "Billable weight (oz)", '=IF(B8="","",IF(B22="",B8,MAX(B8,B22)))', OZ, "The greater of the item weight and the dimensional weight."),
        (24, "Size tier", "=" + tier_f("B23", "B18", "B19", "B20"), None, "Small standard: 15 × 12 × 0.75 in and 16 oz. Large standard: 18 × 14 × 8 in and 20 lb. Larger is oversize, outside this course."),
        (25, "Price band", '=IF(B26="","",CHOOSE(B26,"Under $10","$10 to $50","Over $50"))', None, None),
        (26, "Price band, as a column number", "=" + band_f("B6"), "0", "1, 2 or 3: which column of the card this price pays."),
        (27, "Referral rate", "=" + referral_rate_f("B6", "B7", "B15"), PCT, None),
        (28, "Referral fee per unit ($)", '=IF(B6="","",ROUND(MAX(B6*B27,REF_MIN),2))', USD2, "The greater of price × rate and $0.30."),
    ]
    for row, label, f, fmt, note in rows:
        put(ws, f"A{row}", label)
        put(ws, f"B{row}", f, fmt=fmt)
        if note:
            put(ws, f"F{row}", note, F_NOTE, align=WRAP)

    head_row(ws, 30, ["On each card", "Non-peak (Jan 15 to Oct 14, 2026)", "Holiday peak (Oct 15, 2026 to Jan 14, 2027)", "", "", "How"])
    put(ws, "A31", "Fulfilment fee per unit, with the surcharge ($)")
    put(ws, "B31", "=" + fee_f("$B$24", "$B$23", "$B$26", 0), fmt=USD4)
    put(ws, "C31", "=" + fee_f("$B$24", "$B$23", "$B$26", 1), fmt=USD4)
    put(ws, "F31", "The card's row for this tier and weight, the column for this price, × 1.035.", F_NOTE, align=WRAP)
    put(ws, "A32", "You keep, after Amazon's two fees ($)")
    for col in "BC":
        put(ws, f"{col}32", f'=IF({col}31="","",ROUND($B$6-$B$28-{col}31,2))', fmt=USD2)
    put(ws, "A33", "Amazon's share of the price")
    for col in "BC":
        put(ws, f"{col}33", f'=IF({col}32="","",($B$6-{col}32)/$B$6)', fmt=PCT)

    # Edge 1: the weight band
    head_row(ws, 35, ["Edge 1: the weight band", "Non-peak", "Peak", "", "", "How"])
    put(ws, "A36", "Band edge below this weight (oz)")
    put(ws, "B36", "=" + edge_below_f("$B$24", "$B$23"), fmt=OZ)
    put(ws, "F36", "The heaviest edge on the card this unit is above. Blank in the lightest band.", F_NOTE, align=WRAP)
    put(ws, "A37", "Ounces over it")
    put(ws, "B37", '=IF(B36="","",ROUND($B$23-B36,3))', fmt='0.000')
    put(ws, "A38", "Fee at the edge ($)")
    put(ws, "A39", "Step per unit ($)")
    put(ws, "A40", "Verdict")
    put(ws, "A41", "Counts per unit ($)")
    for col, card, fee in (("B", 0, "B31"), ("C", 1, "C31")):
        put(ws, f"{col}38", "=" + fee_f("$B$24", "$B$36", "$B$26", card), fmt=USD4)
        put(ws, f"{col}39", f'=IF(OR({col}38="",{fee}=""),"",ROUND({fee}-{col}38,4))', fmt=USD4)
        put(ws, f"{col}40", f'=IF($B$24="","Enter price, weight and all three sides",IF($B$36="","No cheaper band below this weight",IF($B$37>MAX_SHAVE,"More than 2 oz over: a redesign, not a shave",IF({col}39<MIN_UNIT,"Under 8 cents a unit: leave it","Worth a look"))))', align=WRAP)
        put(ws, f"{col}41", f'=IF({col}40="Worth a look",{col}39,0)', fmt=USD4)
    put(ws, "F39", "What one cheaper band would save on every unit, on this card.", F_NOTE, align=WRAP)

    # Edge 2: the price band
    head_row(ws, 43, ["Edge 2: the price band", "Non-peak", "Peak", "", "", "How"])
    put(ws, "A44", "Price edge below this price ($)")
    put(ws, "B44", '=IF(OR($B$26="",$B$26=1),"",IF($B$26=2,BAND_LO,BAND_HI))', fmt=USD2)
    put(ws, "A45", "One cent under it ($)")
    put(ws, "B45", '=IF(B44="","",B44-0.01)', fmt=USD2)
    put(ws, "A46", "Fee one price band down ($)")
    put(ws, "A47", "Fee jump per unit ($)")
    put(ws, "A48", "Price given up, net of referral, per unit ($)")
    put(ws, "A49", "Net per unit at the lower price ($)")
    put(ws, "A50", "Break-even price: above this, staying up pays ($)")
    put(ws, "A51", "Verdict")
    put(ws, "A52", "Counts per unit ($)")
    for col, card, fee in (("B", 0, "B31"), ("C", 1, "C31")):
        put(ws, f"{col}46", f'=IF($B$44="","",' + fee_f("$B$24", "$B$23", "($B$26-1)", card) + ")", fmt=USD4)
        put(ws, f"{col}47", f'=IF(OR({col}46="",{fee}=""),"",ROUND({fee}-{col}46,4))', fmt=USD4)
        put(ws, f"{col}48", f'=IF($B$44="","",($B$6-$B$45)*(1-$B$27))', fmt=USD4)
        put(ws, f"{col}49", f'=IF(OR({col}47="",{col}48=""),"",ROUND({col}47-{col}48,4))', fmt=USD4)
        put(ws, f"{col}50", f'=IF({col}47="","",ROUND($B$45+{col}47/(1-$B$27),2))', fmt=USD2)
        put(ws, f"{col}51", f'=IF($B$6="","Enter a price",IF($B$44="","Under $10 already: no price edge below",IF(OR({col}49="",{col}49<=MIN_UNIT),"Dropping under the edge costs more than it saves","Worth a look")))', align=WRAP)
        put(ws, f"{col}52", f'=IF({col}51="Worth a look",{col}49,0)', fmt=USD4)
    put(ws, "F48", "(Price − one cent under the edge) × (1 − referral rate): what you give up, after the referral fee you also stop paying on it.", F_NOTE, align=WRAP)
    put(ws, "F50", "One cent under the edge, plus the fee jump grossed up for referral. Volume is assumed to hold at the lower price.", F_NOTE, align=WRAP)

    # Edge 3: the size tier
    head_row(ws, 54, ["Edge 3: the size tier", "Non-peak", "Peak", "", "", "How"])
    put(ws, "A55", "Sides over the small-standard envelope")
    put(ws, "B55", '=IF($B$18="","",($B$18>SS_L)+($B$19>SS_M)+($B$20>SS_S))', fmt="0")
    put(ws, "A56", "Which side")
    put(ws, "B56", '=IF(B55<>1,"",IF($B$18>SS_L,"Longest",IF($B$19>SS_M,"Median","Shortest")))')
    put(ws, "A57", "How far over its limit (× the limit)")
    put(ws, "B57", '=IF(B55<>1,"",MAX($B$18/SS_L,$B$19/SS_M,$B$20/SS_S))', fmt='0.00"x"')
    put(ws, "A58", "Small-standard fee at this weight ($)")
    put(ws, "A59", "Gap per unit ($)")
    put(ws, "A60", "Verdict")
    put(ws, "A61", "Counts per unit ($)")
    for col, card, fee in (("B", 0, "B31"), ("C", 1, "C31")):
        put(ws, f"{col}58", f'=IF(OR($B$24<>"Large standard",$B$23>SS_MAX),"",' + fee_f('"Small standard"', "$B$23", "$B$26", card) + ")", fmt=USD4)
        put(ws, f"{col}59", f'=IF(OR({col}58="",{fee}=""),"",ROUND({fee}-{col}58,4))', fmt=USD4)
        put(ws, f"{col}60", f'=IF($B$24<>"Large standard","Not large standard: no tier edge to step under",IF($B$23>SS_MAX,"Over 16 oz: small standard is out of reach",IF($B$55<>1,"More than one side over: not a trim",IF($B$57>MAX_ENV,"That side is more than 35% over: not a trim",IF({col}59<MIN_UNIT,"Under 8 cents a unit: leave it","Worth a look")))))', align=WRAP)
        put(ws, f"{col}61", f'=IF({col}60="Worth a look",{col}59,0)', fmt=USD4)

    # Edge 4: the box
    head_row(ws, 63, ["Edge 4: the box (dimensional weight)", "Non-peak", "Peak", "", "", "How"])
    put(ws, "A64", "Dimensional weight ÷ item weight")
    put(ws, "B64", '=IF(OR($B$22="",$B$8=""),"",$B$22/$B$8)', fmt='0.00"x"')
    put(ws, "A65", "Fee on the item weight alone ($)")
    put(ws, "A66", "Gap per unit ($)")
    put(ws, "A67", "Verdict")
    put(ws, "A68", "Counts per unit ($)")
    for col, card, fee in (("B", 0, "B31"), ("C", 1, "C31")):
        put(ws, f"{col}65", f'=IF($B$64="","",' + fee_f("$B$24", "$B$8", "$B$26", card) + ")", fmt=USD4)
        put(ws, f"{col}66", f'=IF(OR({col}65="",{fee}=""),"",ROUND({fee}-{col}65,4))', fmt=USD4)
        put(ws, f"{col}67", f'=IF($B$22="","Under a cubic foot: billed on real weight",IF($B$64<MIN_DIM_RATIO,"The box is within 30% of the real weight: leave it",IF({col}66<MIN_UNIT,"Under 8 cents a unit: leave it","Worth a look")))', align=WRAP)
        put(ws, f"{col}68", f'=IF({col}67="Worth a look",{col}66,0)', fmt=USD4)

    # Volume
    head_row(ws, 70, ["Volume, from the rank", "Value", "", "", "", "How"])
    put(ws, "A71", "Category volume scale")
    put(ws, "B71", '=IF($B$7="",UC_DEFAULT,IFERROR(INDEX(CAT_SCALE,MATCH($B$7,CATS,0)),UC_DEFAULT))', fmt="0.00")
    put(ws, "A72", "Estimated units a month, from the rank")
    put(ws, "B72", "=" + units_f("$B$12", "$B$7"), fmt=INT)
    put(ws, "F72", "An estimate, wrong by a factor of two either way. Never use it as a point.", F_NOTE, align=WRAP)
    put(ws, "A73", "Units a month used below")
    put(ws, "B73", '=IF($B$13<>"",$B$13,B72)', fmt=INT)
    put(ws, "A74", "Range: low")
    put(ws, "B74", '=IF(B73="","",B73*IF($B$13<>"",1,U_LOW))', fmt=INT)
    put(ws, "A75", "Range: high")
    put(ws, "B75", '=IF(B73="","",B73*IF($B$13<>"",1,U_HIGH))', fmt=INT)
    put(ws, "F74", "Half to one and a half times the estimate, as the engine brackets it. Your own units are a number, not a range.", F_NOTE, align=WRAP)

    # What it is worth
    head_row(ws, 77, ["What each edge is worth", "Per unit, non-peak", "Per unit, peak", "A year, low", "A year, high", "How"])
    worth = [(78, "Largest single edge", None), (79, "Weight", 41), (80, "Price", 52), (81, "Size tier", 61), (82, "Box", 68)]
    for row, label, src in worth:
        put(ws, f"A{row}", label)
        if src:
            put(ws, f"B{row}", f"=B{src}", fmt=USD4)
            put(ws, f"C{row}", f"=C{src}", fmt=USD4)
        else:
            put(ws, f"B{row}", "=MAX(B79:B82)", fmt=USD4)
            put(ws, f"C{row}", "=INDEX(C79:C82,MATCH(B78,B79:B82,0))", fmt=USD4)
        for col, rng in (("D", "$B$74"), ("E", "$B$75")):
            put(ws, f"{col}{row}", f'=IF({rng}="","",ROUND({rng}*((12-PEAK_MONTHS)*B{row}+PEAK_MONTHS*C{row}),0))', fmt=USD0)
    put(ws, "F78", "Edges overlap (a lighter unit can also drop a tier), so they are never added together: the largest single one is the finding.", F_NOTE, align=WRAP)
    put(ws, "F79", "A year is nine months on the non-peak card and three on peak. Volume is assumed to hold.", F_NOTE, align=WRAP)

    # Unit economics
    head_row(ws, 84, ["The unit, with your cost", "Non-peak", "Peak", "", "", "How"])
    put(ws, "A85", "Landed cost per unit used ($)")
    put(ws, "B85", '=IF($B$14<>"",$B$14,IF($B$6="","",ROUND($B$6*LANDED_SHARE,2)))', fmt=USD2)
    put(ws, "D85", '=IF($B$14<>"","yours","assumed: 25% of price")', F_NOTE)
    put(ws, "A86", "Contribution per unit, before ads, storage and returns ($)")
    put(ws, "A87", "Break-even ad cost of sale (ACoS)")
    put(ws, "A88", "Price floor: below this, every sale loses money ($)")
    for col in "BC":
        put(ws, f"{col}86", f'=IF(OR({col}32="",$B$85=""),"",ROUND({col}32-$B$85,2))', fmt=USD2)
        put(ws, f"{col}87", f'=IF({col}86="","",{col}86/$B$6)', fmt=PCT)
        put(ws, f"{col}88", f'=IF(OR({col}31="",$B$85=""),"",ROUND(($B$85+{col}31)/(1-$B$27),2))', fmt=USD2)
    put(ws, "F87", "Ads break even on profit, not revenue: spend more than this share of the price on ads and the sale loses money.", F_NOTE, align=WRAP)

    # Is the change worth making? (lesson 4)
    head_row(ws, 90, ["Is the change worth making?", "Value", "", "", "", "How"])
    put(ws, "A91", "The edge the change would take you under")
    inp(ws, "B91", "Weight")
    dv2 = DataValidation(type="list", formula1="EDGE_NAMES", allow_blank=False)
    ws.add_data_validation(dv2)
    dv2.add("B91")
    put(ws, "A92", "What the change costs you, once ($)")
    inp(ws, "B92", 1500, USD0)
    put(ws, "F92", "Example (invented): a packaging redesign and one new print run. Type your own quote.", F_NOTE, align=WRAP)
    put(ws, "A93", "That edge over a year: low, high ($)")
    put(ws, "B93", "=INDEX(D78:D82,MATCH($B$91,EDGE_NAMES,0))", fmt=USD0)
    put(ws, "C93", "=INDEX(E78:E82,MATCH($B$91,EDGE_NAMES,0))", fmt=USD0)
    put(ws, "A94", "Months to pay it back: at the low end, at the high end")
    put(ws, "B94", '=IF(OR($B$92="",N(B93)=0),"",ROUND($B$92/(B93/12),1))', fmt="0.0")
    put(ws, "C94", '=IF(OR($B$92="",N(C93)=0),"",ROUND($B$92/(C93/12),1))', fmt="0.0")
    put(ws, "A95", "Verdict")
    put(ws, "B95", '=IF($B$92="","Type what the change costs",IF(N(C93)=0,"This edge is worth nothing here: leave it",IF(B94<=12,"Pays back inside a year even at the low end",IF(C94<=12,"Pays back inside a year only if volume is at the high end","More than a year even at the high end: probably leave it"))))')
    put(ws, "F94", "The one-time cost ÷ a month of the edge. Plan on the low end.", F_NOTE, align=WRAP)
    ws.freeze_panes = "B5"
    return ws


def catalogue(wb):
    ws = wb.create_sheet("Catalogue")
    put(ws, "A1", "Every SKU at once, ranked by what its largest edge is worth", F_TITLE)
    put(ws, "A2", "Paste one SKU per row into the yellow columns (lesson 8). For your own SKUs, the Fee Preview report has Amazon's own measured sides, weight and fee.", F_NOTE)
    put(ws, "A3", "Columns M onward are formulas. Ranges, because the rank curve is wrong by a factor of two either way; your own units make it a number.", F_NOTE)
    put(ws, "AH4", "Working: every step of the arithmetic, shown", F_H)
    headers = [
        "SKU", "Product", "Price ($)", "Category", "Weight (oz)", "or weight (lb)", "Side 1 (in)", "Side 2 (in)", "Side 3 (in)",
        "Sales rank", "Your units a month (optional)", "Amazon's fee per unit, Fee Preview (optional)",
        "Size tier", "Billable weight (oz)", "Fee, non-peak ($)", "Fee, peak ($)", "Amazon's fee minus this sheet's ($)",
        "Edge below (oz)", "Over by (oz)",
        "Weight edge, non-peak ($/unit)", "Price edge, non-peak ($/unit)", "Size tier, non-peak ($/unit)", "Box, non-peak ($/unit)",
        "Weight edge, peak ($/unit)", "Price edge, peak ($/unit)", "Size tier, peak ($/unit)", "Box, peak ($/unit)",
        "Largest edge", "Units a month used", "A year at stake, low ($)", "A year at stake, high ($)", "Rank (by the low end)", "",
        "Weight used (oz)", "Longest (in)", "Median (in)", "Shortest (in)", "Dimensional weight (oz)", "Price band (1-3)",
        "Referral rate", "Fee at edge, non-peak", "Fee at edge, peak", "Fee a price band down, non-peak", "Fee a price band down, peak",
        "Price given up, net of referral", "Sides over small standard", "Over side ÷ its limit", "Small-standard fee, non-peak",
        "Small-standard fee, peak", "Fee on item weight, non-peak", "Fee on item weight, peak", "Units from rank",
    ]
    hr = 6
    head_row(ws, hr, headers)
    widths = [12, 26, 9, 18, 9, 9, 8, 8, 8, 10, 11, 13, 15, 10, 10, 10, 11, 9, 9, 11, 11, 11, 11, 11, 11, 11, 11, 12, 10, 12, 12, 9, 3,
              9, 8, 8, 8, 10, 8, 8, 10, 10, 11, 11, 11, 10, 10, 11, 11, 11, 11, 10]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[hr].height = 54

    first, last = hr + 1, hr + CATALOGUE_ROWS
    dv = DataValidation(type="list", formula1="CATS", allow_blank=True, showErrorMessage=False)
    ws.add_data_validation(dv)
    dv.add(f"D{first}:D{last}")
    for r in range(first, last + 1):
        R = lambda c: f"{c}{r}"  # noqa: E731
        f = {
            "M": tier_f("N", "AI", "AJ", "AK"),
            "N": '=IF(AH="","",IF(AL="",AH,MAX(AH,AL)))',
            "O": fee_f("M", "N", "AM", 0),
            "P": fee_f("M", "N", "AM", 1),
            "Q": '=IF(OR(L="",O=""),"",ROUND(L-IF(AND(TODAY()>=PEAK_FROM,TODAY()<=PEAK_TO),P,O),2))',
            "R": edge_below_f("M", "N"),
            "S": '=IF(R="","",ROUND(N-R,3))',
            "T": '=IF(OR(R="",O="",AO=""),"",IF(S>MAX_SHAVE,"",IF(ROUND(O-AO,4)<MIN_UNIT,"",ROUND(O-AO,4))))',
            "X": '=IF(OR(R="",P="",AP=""),"",IF(S>MAX_SHAVE,"",IF(ROUND(P-AP,4)<MIN_UNIT,"",ROUND(P-AP,4))))',
            "U": '=IF(OR(AQ="",O=""),"",IF(ROUND(ROUND(O-AQ,4)-AS,4)<=MIN_UNIT,"",ROUND(ROUND(O-AQ,4)-AS,4)))',
            "Y": '=IF(OR(AR="",P=""),"",IF(ROUND(ROUND(P-AR,4)-AS,4)<=MIN_UNIT,"",ROUND(ROUND(P-AR,4)-AS,4)))',
            "V": '=IF(OR(AV="",O=""),"",IF(AND(AT=1,AU<=MAX_ENV),IF(ROUND(O-AV,4)<MIN_UNIT,"",ROUND(O-AV,4)),""))',
            "Z": '=IF(OR(AW="",P=""),"",IF(AND(AT=1,AU<=MAX_ENV),IF(ROUND(P-AW,4)<MIN_UNIT,"",ROUND(P-AW,4)),""))',
            "W": '=IF(OR(AX="",O=""),"",IF(AL>=AH*MIN_DIM_RATIO,IF(ROUND(O-AX,4)<MIN_UNIT,"",ROUND(O-AX,4)),""))',
            "AA": '=IF(OR(AY="",P=""),"",IF(AL>=AH*MIN_DIM_RATIO,IF(ROUND(P-AY,4)<MIN_UNIT,"",ROUND(P-AY,4)),""))',
            "AB": '=IF(COUNT(T:W)=0,"",CHOOSE(MATCH(MAX(T:W),T:W,0),"Weight","Price","Size tier","Box"))',
            "AC": '=IF(K<>"",K,AZ)',
            "AD": '=IF(OR(AB="",AC=""),"",ROUND(AC*IF(K<>"",1,U_LOW)*((12-PEAK_MONTHS)*MAX(T:W)+PEAK_MONTHS*N(INDEX(X:AA,MATCH(MAX(T:W),T:W,0)))),0))',
            "AE": '=IF(OR(AB="",AC=""),"",ROUND(AC*IF(K<>"",1,U_HIGH)*((12-PEAK_MONTHS)*MAX(T:W)+PEAK_MONTHS*N(INDEX(X:AA,MATCH(MAX(T:W),T:W,0)))),0))',
            "AF": f'=IF(AD="","",RANK(AD,$AD${first}:$AD${last}))',
            "AH": '=IF(E<>"",E,IF(F<>"",ROUND(F*16,3),""))',
            "AI": '=IF(COUNT(G:I)<3,"",ROUND(LARGE(G:I,1),2))',
            "AJ": '=IF(COUNT(G:I)<3,"",ROUND(LARGE(G:I,2),2))',
            "AK": '=IF(COUNT(G:I)<3,"",ROUND(SMALL(G:I,1),2))',
            "AL": '=IF(AI="","",IF(AI*AJ*AK<DIM_MIN_CUIN,"",ROUND(AI*AJ*AK/DIM_DIV*16,2)))',
            "AM": band_f("C"),
            "AN": referral_rate_f("C", "D"),
            "AO": fee_f("M", "R", "AM", 0),
            "AP": fee_f("M", "R", "AM", 1),
            "AQ": '=IF(OR(AM="",AM=1),"",' + fee_f("M", "N", "(AM-1)", 0) + ")",
            "AR": '=IF(OR(AM="",AM=1),"",' + fee_f("M", "N", "(AM-1)", 1) + ")",
            "AS": '=IF(OR(AM="",AM=1),"",(C-(IF(AM=2,BAND_LO,BAND_HI)-0.01))*(1-AN))',
            "AT": '=IF(AI="","",(AI>SS_L)+(AJ>SS_M)+(AK>SS_S))',
            "AU": '=IF(OR(AT="",AT<>1),"",MAX(AI/SS_L,AJ/SS_M,AK/SS_S))',
            "AV": '=IF(OR(M<>"Large standard",N="",N>SS_MAX),"",' + fee_f('"Small standard"', "N", "AM", 0) + ")",
            "AW": '=IF(OR(M<>"Large standard",N="",N>SS_MAX),"",' + fee_f('"Small standard"', "N", "AM", 1) + ")",
            "AX": '=IF(OR(AL="",AH=""),"",' + fee_f("M", "AH", "AM", 0) + ")",
            "AY": '=IF(OR(AL="",AH=""),"",' + fee_f("M", "AH", "AM", 1) + ")",
            "AZ": units_f("J", "D"),
        }
        fmts = {"N": OZ, "O": USD4, "P": USD4, "Q": USD2, "R": OZ, "S": '0.000', "AC": INT, "AD": USD0, "AE": USD0, "AF": "0",
                "AH": OZ, "AI": OZ, "AJ": OZ, "AK": OZ, "AL": OZ, "AM": "0", "AN": PCT, "AS": USD4, "AT": "0", "AU": '0.00"x"', "AZ": INT}
        for col in ["T", "U", "V", "W", "X", "Y", "Z", "AA", "AO", "AP", "AQ", "AR", "AV", "AW", "AX", "AY"]:
            fmts[col] = USD4
        for col, formula in f.items():
            formula = formula if formula.startswith("=") else "=" + formula
            put(ws, R(col), _rowify(formula, r), fmt=fmts.get(col))
        for col in "ABCDEFGHIJKL":
            ws[R(col)].fill = FILL_INPUT
            ws[R(col)].font = F_INPUT
        ws[R("C")].number_format = USD2
        ws[R("L")].number_format = USD2
    ex = EXAMPLE
    for col, v in zip("ABCDEFGHIJ", ["EX-001", ex["name"], ex["price"], ex["category"], ex["weight"], None, *ex["sides"], ex["bsr"]]):
        ws[f"{col}{first}"].value = v
    ws.freeze_panes = f"C{first}"
    ws.auto_filter.ref = f"A{hr}:AF{last}"
    return ws


import re as _re

_COL_TOKEN = _re.compile(r"(?<![A-Za-z_$'!])\b([A-Z]{1,2})(?::([A-Z]{1,2}))?\b(?![\d(_A-Za-z])")
_NAMED = {"SS_MAX", "SS_L", "SS_M", "SS_S", "LS_MAX", "LS_L", "LS_M", "LS_S"}


def _rowify(formula: str, r: int) -> str:
    """Catalogue formulas are written with bare column letters (O, T:W); this pins them to row r.
    Quoted strings and defined names are left alone."""
    out, i = [], 0
    for part in _re.split(r'("[^"]*")', formula):
        if part.startswith('"'):
            out.append(part)
            continue
        def sub(m):
            a, b = m.group(1), m.group(2)
            if b:
                return f"{a}{r}:{b}{r}"
            return f"{a}{r}"
        out.append(_COL_TOKEN.sub(sub, part))
    return "".join(out)


def simulation(wb):
    ws = wb.create_sheet("Ten thousand months")
    ws.column_dimensions["A"].width = 44
    for col, w in zip("BCDEFGHI", [16, 16, 14, 14, 14, 16, 18, 4]):
        ws.column_dimensions[col].width = w
    ws.column_dimensions["J"].width = 34
    ws.column_dimensions["K"].width = 16
    put(ws, "A1", "Ten thousand months: the edge, sized as a range", F_TITLE)
    put(ws, "A2", "Lesson 6. Every number here comes from One listing. Recalculate (F9 in Excel, Ctrl+Shift+F9 in LibreOffice) and ten thousand new months are drawn.", F_NOTE)
    put(ws, "A3", "Excludes advertising, storage and returns, as the case study does. After January 14, 2027 the 2026 non-peak card is assumed to hold: Amazon's 2027 schedule is not published yet.", F_NOTE)

    head_row(ws, 4, ["Inputs", "Non-peak", "Peak", "", "", "", "", "", "", "Result", "Value"])
    put(ws, "A5", "Which edge to size")
    inp(ws, "B5", "Largest")
    dv = DataValidation(type="list", formula1="EDGE_NAMES", allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B5")
    put(ws, "A6", "First month")
    inp(ws, "B6", date(2026, 10, 1), "mmm yyyy")
    put(ws, "A7", "Price ($)")
    put(ws, "B7", "='One listing'!B6", F_LINK, USD2)
    put(ws, "A8", "Referral fee per unit ($)")
    put(ws, "B8", "='One listing'!B28", F_LINK, USD2)
    put(ws, "A9", "Fulfilment fee per unit ($)")
    put(ws, "B9", "='One listing'!B31", F_LINK, USD4)
    put(ws, "C9", "='One listing'!C31", F_LINK, USD4)
    put(ws, "A10", "Landed cost per unit ($)")
    put(ws, "B10", "='One listing'!B85", F_LINK, USD2)
    put(ws, "A11", "Units a month, the centre of the draw")
    put(ws, "B11", "='One listing'!B73", F_LINK, INT)
    put(ws, "A12", "Volume doubt (sigma)")
    inp(ws, "B12", "=SIGMA", "0.0000", comment="ln 2 ÷ 1.645: half and double the estimate at the 5th and 95th percentiles. "
                                                 "If you typed your own units on One listing, your doubt is smaller: type a lower number.")
    put(ws, "A13", "The edge, per unit ($)")
    put(ws, "B13", "=INDEX('One listing'!B78:B82,MATCH($B$5,EDGE_NAMES,0))", F_LINK, USD4)
    put(ws, "C13", "=INDEX('One listing'!C78:C82,MATCH($B$5,EDGE_NAMES,0))", F_LINK, USD4)
    put(ws, "A14", "Landed cost drift, either way, each month")
    inp(ws, "B14", COST_DRIFT, PCT, comment="Freight and exchange rates move. The case study drifts cost ±10% a month.")

    head_row(ws, 16, ["Month", "Days", "Days on the peak card", "Share on peak", "Fee that month ($)", "Edge that month ($ per unit)"])
    for i in range(12):
        r = 17 + i
        put(ws, f"A{r}", f"=DATE(YEAR($B$6),MONTH($B$6)+{i},1)", fmt="mmm yyyy")
        put(ws, f"B{r}", f"=DATE(YEAR($B$6),MONTH($B$6)+{i + 1},1)-A{r}", fmt="0")
        put(ws, f"C{r}", f"=MAX(0,MIN(A{r}+B{r},PEAK_TO+1)-MAX(A{r},PEAK_FROM))", fmt="0")
        put(ws, f"D{r}", f"=C{r}/B{r}", fmt=PCT)
        put(ws, f"E{r}", f'=IF($B$9="","",$B$9*(1-D{r})+$C$9*D{r})', fmt=USD4)
        put(ws, f"F{r}", f'=IF($B$13="","",$B$13*(1-D{r})+$C$13*D{r})', fmt=USD4)
    put(ws, "A30", "The edge over the year, per unit ($)", F_BOLD)
    put(ws, "F30", "=SUM(F17:F28)", F_BOLD, USD4)

    first, last = 35, 34 + N_MONTHS
    rng = lambda c: f"{c}{first}:{c}{last}"  # noqa: E731
    results = [
        (5, "Months simulated", f"=COUNT({rng('G')})", INT),
        (6, "The edge over a year: P10 ($)", f'=IF(COUNT({rng("H")})=0,"",PERCENTILE({rng("H")},0.1))', USD0),
        (7, "The edge over a year: median ($)", f'=IF(COUNT({rng("H")})=0,"",PERCENTILE({rng("H")},0.5))', USD0),
        (8, "The edge over a year: P90 ($)", f'=IF(COUNT({rng("H")})=0,"",PERCENTILE({rng("H")},0.9))', USD0),
        (10, "Profit in a month: P10 ($)", f'=IF(COUNT({rng("G")})=0,"",PERCENTILE({rng("G")},0.1))', USD0),
        (11, "Profit in a month: median ($)", f'=IF(COUNT({rng("G")})=0,"",PERCENTILE({rng("G")},0.5))', USD0),
        (12, "Profit in a month: P90 ($)", f'=IF(COUNT({rng("G")})=0,"",PERCENTILE({rng("G")},0.9))', USD0),
        (13, "Share of months at a loss", f'=IF(COUNT({rng("G")})=0,"",COUNTIF({rng("G")},"<0")/COUNT({rng("G")}))', PCT),
    ]
    for row, label, f, fmt in results:
        put(ws, f"J{row}", label)
        put(ws, f"K{row}", f, F_BOLD, fmt)
    put(ws, "J14", "P10: one year in ten comes in under it. P90: one in ten over it. Quote the range, rounded down.", F_NOTE, align=WRAP)

    head_row(ws, 34, ["Month no.", "Calendar month (1 = first)", "Volume draw (z)", "Units a month this year",
                      "Landed cost this month ($)", "Fee this month ($)", "Profit this month ($)", "The edge over this year ($)"])
    for k in range(N_MONTHS):
        r = first + k
        ws.cell(row=r, column=1, value=k + 1).font = F_BODY
        ws.cell(row=r, column=2, value=k % 12 + 1).font = F_BODY
        put(ws, f"C{r}", "=NORMSINV(MAX(RAND(),1E-12))", fmt="0.000")
        put(ws, f"D{r}", f'=IF($B$11="","",$B$11*EXP($B$12*C{r}))', fmt=INT)
        put(ws, f"E{r}", f'=IF($B$10="","",$B$10*(1-$B$14+2*$B$14*RAND()))', fmt=USD2)
        put(ws, f"F{r}", f"=INDEX($E$17:$E$28,B{r})", fmt=USD4)
        put(ws, f"G{r}", f'=IF(OR(D{r}="",E{r}="",F{r}=""),"",D{r}*($B$7-$B$8-F{r}-E{r}))', fmt=USD0)
        put(ws, f"H{r}", f'=IF(D{r}="","",D{r}*$F$30)', fmt=USD0)
    put(ws, "A32", "Each row is one month. Its volume is one year's level, drawn once from the rank estimate's range; its cost drifts on its own; its fee is that calendar month's blend of the two cards.", F_NOTE)
    ws.freeze_panes = "A35"
    return ws


def cliff(wb):
    ws = wb.create_sheet("The 271-day cliff")
    ws.column_dimensions["A"].width = 40
    for col, w in zip("BCDEFGH", [12, 12, 16, 16, 16, 18, 18]):
        ws.column_dimensions[col].width = w
    ws.column_dimensions["I"].width = 60
    put(ws, "A1", "The 271-day cliff: what aging stock costs to keep", F_TITLE)
    put(ws, "A2", "Lesson 7. Needs your own export: Reports, Fulfillment, Manage Inventory Health (Inventory Age). Public pages cannot see this one.", F_NOTE)
    put(ws, "A3", "Where the report carries Amazon's own estimated surcharge columns, those are Amazon's number: prefer them to this sheet.", F_NOTE)

    head_row(ws, 4, ["Inputs", "Value", "", "", "", "", "", "", "Where to find it"])
    put(ws, "A5", "Cubic feet per unit, from One listing")
    put(ws, "B5", "=IF('One listing'!B21=\"\",\"\",ROUND('One listing'!B21/1728,4))", F_LINK, "0.0000")
    put(ws, "A6", "Or your own cubic feet per unit (optional)")
    inp(ws, "B6", None, "0.0000")
    put(ws, "I6", "Fee Preview gives Amazon's measured sides: longest × median × shortest ÷ 1,728.", F_NOTE)
    put(ws, "A7", "Cubic feet per unit used")
    put(ws, "B7", '=IF(B6<>"",B6,B5)', fmt="0.0000")
    put(ws, "A8", "Storage season")
    inp(ws, "B8", "Jan–Sep")
    dv = DataValidation(type="list", formula1="SEASONS", allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B8")
    put(ws, "A9", "Units sold in the last 30 days")
    inp(ws, "B9", EXAMPLE_SOLD_30, INT)
    put(ws, "I9", "The same report: units shipped, last 30 days.", F_NOTE)

    head_row(ws, 11, ["Age band", "From (days)", "To (days)", "Units on hand", "Storage ($/cu ft)", "Surcharge ($/cu ft)",
                      "Per unit a month ($)", "This band a month ($)", "Note"])
    bands = [(0, 180, None)] + AGED
    for i, (lo, hi, rate) in enumerate(bands):
        r = 12 + i
        put(ws, f"A{r}", f"{lo} to {hi} days" if hi else f"{lo} days and over")
        put(ws, f"B{r}", lo, fmt=INT)
        put(ws, f"C{r}", hi if hi else "", fmt=INT)
        inp(ws, f"D{r}", EXAMPLE_AGES[i], INT)
        put(ws, f"E{r}", '=IF($B$8="Oct–Dec",STOR_PEAK,STOR_OFF)', fmt=USD2)
        put(ws, f"F{r}", 0 if rate is None else f"=INDEX(AGED_RATES,{i})", fmt=USD2)
        if hi is None:
            g = f'=IF($B$7="","",ROUND($B$7*E{r}+MAX($B$7*F{r},AGED_MIN),4))'
        else:
            g = f'=IF($B$7="","",ROUND($B$7*(E{r}+F{r}),4))'
        put(ws, f"G{r}", g, fmt=USD4)
        put(ws, f"H{r}", f'=IF(OR(G{r}="",D{r}=""),"",ROUND(D{r}*G{r},2))', fmt=USD2)
    put(ws, "I16", "The cliff: from here the surcharge is $5.45, not $1.50.", F_NOTE)
    put(ws, "I19", "Over 365 days: $6.90 a cubic foot or $0.15 a unit, whichever is greater.", F_NOTE)
    put(ws, "A21", "Total", F_BOLD)
    put(ws, "D21", "=SUM(D12:D19)", F_BOLD, INT)
    put(ws, "H21", "=SUM(H12:H19)", F_BOLD, USD2)

    head_row(ws, 23, ["The cliff, in your numbers", "Value", "", "", "", "", "", "", "How"])
    put(ws, "A24", "Next month, if none of the 241 to 270 day units sell, they cost more by ($)")
    put(ws, "B24", '=IF($B$7="","",ROUND(D15*$B$7*(INDEX(AGED_RATES,4)-INDEX(AGED_RATES,3)),2))', fmt=USD2)
    put(ws, "I24", "Units about to cross × cubic feet × ($5.45 − $1.50). A month from now they are 271 to 300 days old.", F_NOTE)
    put(ws, "A25", "A unit's storage a month at 270 days, then at 271 ($)")
    put(ws, "B25", "=G15", fmt=USD4)
    put(ws, "C25", "=G16", fmt=USD4)
    put(ws, "A26", "Days of cover at the current pace")
    put(ws, "B26", '=IF(OR(B9="",B9=0),"",ROUND(D21/(B9/30),0))', fmt=INT)
    put(ws, "A27", "Verdict")
    put(ws, "B27", '=IF(B26="","Enter units sold",IF(B26>270,"Over 270 days of cover: at this pace, units cross the cliff before they sell","Under 271 days of cover: the newest units sell before they age into it"))')
    put(ws, "I26", "Units on hand ÷ units sold a day. Amazon ages stock first in, first out.", F_NOTE)
    ws.freeze_panes = "A5"
    return ws


def start_here(wb, rc):
    ws = wb.active
    ws.title = "Start here"
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 96
    put(ws, "B2", "The Fee Staircase", F_TITLE)
    put(ws, "B3", "The template for the free Hubricon course of the same name.", F_BODY)
    c = put(ws, "C3", COURSE_URL, F_URL)
    c.hyperlink = COURSE_URL
    rows = [
        ("What it does", "Puts any Amazon listing on the fee staircase from five public numbers: the size tier, the price band, the four edges a unit can sit just past, what each is worth a unit and a year, and the range a simulation puts around it."),
        ("Yellow cells", "Yours to type in. Blue text is something you typed."),
        ("Black", "Formulas. Every one is visible: click any cell to see the arithmetic."),
        ("Green", "Pulled from another sheet."),
        ("", ""),
        ("1. One listing", "Type the five public numbers for one listing (lessons 2 to 5). Start with the example to see how it reads, then overwrite it."),
        ("2. Ten thousand months", "Puts a range on what the edge is worth a year (lesson 6)."),
        ("3. The 271-day cliff", "Prices aging stock from your own Inventory Age export (lesson 7)."),
        ("4. Catalogue", "Paste every SKU and rank them by what their largest edge is worth (lesson 8)."),
        ("5. Rate card", "Amazon's 2026 cards and every constant the formulas use, with sources. Nothing is hidden."),
        ("", ""),
        ("The cards", f"Amazon's US FBA fulfilment fees for 2026: non-peak (Jan 15 to Oct 14) and holiday peak (Oct 15, 2026 to Jan 14, 2027), with the 3.5% fuel and logistics surcharge. Storage and the aged-inventory surcharge as in force from Jan 15, 2026. Loaded {rc['generated']}."),
        ("What it is", "Arithmetic off published cards, and estimates where it says so. It is not Amazon's bill. For your own SKUs, the Fee Preview report in Seller Central is the ground truth: compare it on the Catalogue sheet."),
        ("When it goes stale", "Amazon reprices about once a year. When it does, check the Rate card sheet against the new schedule, or download the template again."),
        ("The example rows", "Invented, to show how a filled sheet reads. Not a client, not a real listing."),
        ("", ""),
        ("Made by", "Hubricon, which runs this arithmetic on whole catalogues every week, and is paid only in months it earns more than its fee. Free to use and share with the name left on."),
    ]
    for i, (k, v) in enumerate(rows):
        r = 5 + i
        put(ws, f"B{r}", k, F_BOLD, align=TOP)
        put(ws, f"C{r}", v, F_BODY, align=WRAP)
    ws["B6"].fill = FILL_INPUT
    ws["B6"].font = Font(name=ARIAL, size=10, bold=True, color="0000FF")
    ws["B8"].font = Font(name=ARIAL, size=10, bold=True, color="008000")
    ws.sheet_view.showGridLines = False
    return ws


def build(path: Path = OUT, catalogue_rows: list[dict] | None = None) -> Path:
    rc = load()
    wb = Workbook()
    start_here(wb, rc)
    one_listing(wb)
    simulation(wb)
    cliff(wb)
    cat = catalogue(wb)
    rate_card(wb, rc)
    # The order a reader meets them in.
    wb._sheets = [wb["Start here"], wb["One listing"], wb["Ten thousand months"], wb["The 271-day cliff"], wb["Catalogue"], wb["Rate card"]]
    if catalogue_rows:
        for i, row in enumerate(catalogue_rows):
            for col, v in row.items():
                cat[f"{col}{7 + i}"].value = v
    wb.active = 0
    wb.properties.creator = "Hubricon"
    wb.properties.title = "The Fee Staircase: template"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


if __name__ == "__main__":
    out = build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
    print(f"wrote {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
