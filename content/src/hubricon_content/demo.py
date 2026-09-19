"""Tarnhollow: the demo catalogue every video and lesson runs on.

Twenty-four private-label SKUs, twelve monthly periods, roughly three million
dollars a year, seed 42. Written as the same Amazon export layouts the engine's
own fixtures use, so every figure on screen comes out of the engine's parsers
and models exactly as a client's would. Nothing here is a real brand, and every
surface that shows a Tarnhollow number says "demo data".

The generator is deterministic: the same seed writes byte-identical files, and
`tests/test_demo_determinism.py` pins their hashes so a silent change to the
demo can never change a published number unnoticed.
"""

import calendar
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from .state import CONTENT_DIR

DEMO_DIR = CONTENT_DIR / "demo" / "tarnhollow"
SEED = 42
BRAND = "Tarnhollow"
TODAY = date(2026, 9, 1)           # the pinned "as of" date every run uses
PERIODS = [(2025, 9), (2025, 10), (2025, 11), (2025, 12), (2026, 1), (2026, 2), (2026, 3),
           (2026, 4), (2026, 5), (2026, 6), (2026, 7), (2026, 8)]
SEASON = [0.92, 1.00, 1.28, 1.42, 0.86, 0.84, 0.94, 1.00, 1.04, 1.02, 1.06, 1.08]
CLIENT = {"name": BRAND, "cash_on_hand": 262000.0, "monthly_fixed_costs": 31500.0, "channel": "amazon"}

# name, base price, unit cost, freight, packaging, lead days, base monthly units, elasticity, size tier, cubic ft
SKUS = [
    ("Cast Iron Skillet 10in",      34.99, 9.40, 2.10, 0.60, 55, 620, -1.30, "large",    0.41),
    ("Cast Iron Skillet 12in",      44.99, 12.80, 2.60, 0.70, 55, 410, -1.20, "large",    0.55),
    ("Enamel Dutch Oven 5qt",       79.99, 24.50, 4.20, 1.10, 60, 260, -1.05, "large",    0.92),
    ("Carbon Steel Wok",            49.99, 13.20, 2.30, 0.60, 50, 300, -1.45, "large",    0.62),
    ("Bamboo Cutting Board L",      27.99, 6.10, 1.40, 0.40, 40, 540, -1.80, "standard", 0.28),
    ("Bamboo Cutting Board M",      19.99, 4.20, 1.00, 0.30, 40, 720, -2.05, "standard", 0.18),
    ("Walnut Serving Tray",         38.99, 10.90, 1.70, 0.50, 45, 190, -1.25, "standard", 0.30),
    ("Chef Knife 8in",              59.99, 14.60, 1.10, 0.90, 45, 450, -0.95, "standard", 0.09),
    ("Paring Knife 3.5in",          18.99, 3.90, 0.50, 0.40, 45, 610, -1.60, "standard", 0.04),
    ("Bread Knife 10in",            29.99, 6.80, 0.70, 0.50, 45, 280, -1.35, "standard", 0.07),
    ("Knife Sharpener Whetstone",   24.99, 5.20, 0.90, 0.40, 35, 380, -1.90, "standard", 0.06),
    ("Stainless Mixing Bowls 5pc",  36.99, 9.10, 2.40, 0.80, 50, 330, -1.50, "large",    0.70),
    ("Silicone Spatula Set",        14.99, 2.60, 0.40, 0.30, 30, 900, -2.20, "standard", 0.05),
    ("Measuring Cups Steel",        21.99, 4.70, 0.70, 0.40, 35, 470, -1.70, "standard", 0.08),
    ("Salt Cellar Acacia",          16.99, 3.30, 0.50, 0.30, 35, 350, -1.85, "standard", 0.05),
    ("Pepper Mill Walnut",          32.99, 8.20, 0.90, 0.50, 45, 260, -1.15, "standard", 0.06),
    ("French Press 34oz",           29.99, 7.10, 1.30, 0.60, 40, 390, -1.40, "standard", 0.22),
    ("Pour Over Kettle Gooseneck",  42.99, 11.40, 1.60, 0.70, 45, 240, -1.10, "standard", 0.24),
    ("Coffee Canister Airtight",    22.99, 5.00, 0.80, 0.40, 35, 430, -1.75, "standard", 0.10),
    ("Tea Infuser Mug",             17.99, 3.80, 0.60, 0.30, 35, 380, -1.95, "standard", 0.08),
    ("Apron Waxed Canvas",          39.99, 9.60, 0.60, 0.40, 40, 210, -1.20, "standard", 0.07),
    ("Oven Mitts Aramid Pair",      19.99, 4.10, 0.40, 0.30, 35, 520, -1.65, "standard", 0.06),
    ("Trivet Cork Set",             12.99, 2.10, 0.30, 0.20, 30, 610, -2.30, "standard", 0.04),
    ("Kitchen Towels Linen 4pk",    24.99, 5.50, 0.50, 0.30, 35, 340, -1.55, "standard", 0.05),
]

FEE_FBA = {"standard": 4.35, "large": 7.10}
REFERRAL = 0.15
STORAGE_PER_CUFT = {"offpeak": 0.78, "peak": 2.40}
CAMPAIGNS = ["Skillets - Exact", "Skillets - Broad", "Knives - Exact", "Knives - Broad",
             "Boards - Exact", "Coffee - Exact", "Coffee - Broad", "Catalog - Auto"]
CAMPAIGN_SKUS = {0: [0, 1, 2, 3], 1: [0, 1, 2, 3], 2: [7, 8, 9, 10], 3: [7, 8, 9, 10],
                 4: [4, 5, 6], 5: [16, 17, 18, 19], 6: [16, 17, 18, 19], 7: list(range(24))}
FCS = ["ONT8", "PHX7", "MDW2", "LAX9", "DFW6"]


def _sku_code(i: int, name: str) -> str:
    words = [w for w in name.replace("-", " ").split() if w.isalpha()]
    return f"TH-{''.join(w[:3].upper() for w in words[:2])}-{i + 1:02d}"


def _asin(i: int) -> str:
    return f"B0TH{i + 1:03d}KX"


def _fnsku(i: int) -> str:
    return f"X0TH{i + 1:04d}"


def _month_bounds(y: int, m: int) -> tuple[date, date]:
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def _money(v: float) -> str:
    return f"${v:,.2f}"


def _int(v) -> str:
    return f"{int(round(v)):,}"


def _write(path: Path, header: list[str], rows: list[list], preamble: list[str] | None = None) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        if preamble:
            for line in preamble:
                fh.write(line + "\n")
        w = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def _price_path(rng: np.random.Generator, base: float, i: int) -> list[float]:
    """Three to four distinct prices over the year, so the elasticity fit has
    real price variation (the engine needs a coefficient of variation of two
    percent or more) — the way a brand that tests prices actually looks."""
    steps = [0.0, rng.choice([-0.08, -0.05, 0.05, 0.08, 0.10]), rng.choice([-0.04, 0.04, 0.06]),
             rng.choice([0.0, 0.03, -0.03])]
    cut1, cut2, cut3 = sorted(rng.choice(range(2, 11), size=3, replace=False))
    prices = []
    for m in range(12):
        k = 0 if m < cut1 else 1 if m < cut2 else 2 if m < cut3 else 3
        p = base * (1 + steps[k])
        prices.append(round(p - 0.01 if (p * 100) % 100 == 0 else p, 2))
    return prices


def generate(out: Path = DEMO_DIR, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.csv"):
        old.unlink()
    manifest = {"brand": BRAND, "seed": seed, "today": TODAY.isoformat(), "client": CLIENT,
                "label": f"{BRAND} — demo data, generated by hubricon_content.demo (seed {seed})",
                "files": []}

    def add(name: str, report_type: str, start: date, end: date):
        manifest["files"].append({"file": name, "report_type": report_type,
                                  "period_start": start.isoformat(), "period_end": end.isoformat()})

    prices = [_price_path(rng, s[1], i) for i, s in enumerate(SKUS)]
    # one shared demand factor per month, so good and bad months move the catalogue together
    common = rng.normal(0, 0.10, size=12)
    units = np.zeros((24, 12))
    for i, s in enumerate(SKUS):
        base_units, eps = s[6], s[7]
        for m in range(12):
            rel = prices[i][m] / s[1]
            mean = base_units * SEASON[m] * rel ** eps * np.exp(common[m] + rng.normal(0, 0.12))
            units[i, m] = max(5, rng.poisson(mean))

    # ── monthly SKU economics + business report ────────────────────────────
    monthly_ads = np.zeros(12)
    for m, (y, mo) in enumerate(PERIODS):
        start, end = _month_bounds(y, mo)
        econ_rows, br_rows = [], []
        peak = mo in (10, 11, 12)
        for i, s in enumerate(SKUS):
            u = int(units[i, m])
            p = prices[i][m]
            sales = round(u * p, 2)
            referral = -round(sales * REFERRAL, 2)
            fba = -round(u * FEE_FBA[s[8]], 2)
            storage = -round(s[9] * STORAGE_PER_CUFT["peak" if peak else "offpeak"] * max(20, u * 0.9), 2)
            net = round(sales + referral + fba + storage, 2)
            econ_rows.append([_sku_code(i, s[0]), _asin(i), u, _money(p), _money(sales),
                              f"{referral:.2f}", f"{fba:.2f}", f"{storage:.2f}", _money(net)])
            conv = float(np.clip(rng.normal(0.115, 0.02), 0.06, 0.20))
            sessions = int(round(u / conv))
            br_rows.append([f"B0TH{(i // 4) + 1:03d}PR", _asin(i), s[0], _int(sessions), _int(sessions * 1.6),
                            f"{float(np.clip(rng.normal(94, 3), 80, 99)):.1f}%", u, f"US{_money(sales)}",
                            int(round(u * 0.96)), f"{conv * 100:.2f}%"])
        fn = f"sku_economics_{start:%Y-%m}.csv"
        _write(out / fn, ["MSKU", "ASIN", "Units Sold", "Average Sales Price", "Sales", "Referral Fee",
                          "FBA Fulfillment Fee", "Storage Fee", "Net Proceeds"], econ_rows)
        add(fn, "sku_economics", start, end)
        fn = f"business_report_{start:%Y-%m}.csv"
        _write(out / fn, ["(Parent) ASIN", "(Child) ASIN", "Title", "Sessions - Total", "Page Views - Total",
                          "Featured Offer (Buy Box) Percentage", "Units Ordered", "Ordered Product Sales",
                          "Total Order Items", "Unit Session Percentage"], br_rows)
        add(fn, "business_report", start, end)

    # ── cost sheet ─────────────────────────────────────────────────────────
    rows = [[_sku_code(i, s[0]), _asin(i), s[0], f"{s[2]:.2f}", f"{s[3]:.2f}", f"{s[4]:.2f}", "0.00", s[5], ""]
            for i, s in enumerate(SKUS)]
    _write(out / "cogs.csv", ["sku", "asin", "product_name", "unit_cost_usd", "inbound_freight_per_unit_usd",
                              "packaging_per_unit_usd", "other_cost_per_unit_usd", "supplier_lead_time_days", "notes"], rows)
    add("cogs.csv", "cogs", PERIODS_START := date(2025, 9, 1), date(2026, 8, 31))

    # ── inventory snapshot at the end of the last period ───────────────────
    snap = date(2026, 8, 31)
    inv_rows, health_rows = [], []
    for i, s in enumerate(SKUS):
        daily = units[i, -3:].sum() / 92
        cover = float(rng.choice([22, 29, 36, 44, 53, 64, 78, 96, 118, 150]))
        onhand = int(round(daily * cover))
        inbound = int(round(daily * s[5] * 0.7)) if rng.random() < 0.55 else 0
        inv_rows.append([_sku_code(i, s[0]), _fnsku(i), _asin(i), "NewItem", onhand, 0, inbound, 0, int(daily * 2)])
        aged = int(onhand * 0.35) if cover > 75 else 0
        vol = s[9]
        health_rows.append([snap.isoformat(), _sku_code(i, s[0]), _fnsku(i), _asin(i), s[0], "New", onhand, 0,
                            onhand - aged, aged if cover > 75 else 0, 0, 0, 0,
                            int(daily * 7), int(daily * 30), int(daily * 60), int(daily * 90),
                            f"{min(0.99, 30 / max(cover, 1)):.2f}", int(cover), max(0, onhand - int(daily * 90)),
                            f"{vol:.3f}", f"{vol * onhand:.2f}", f"{vol * onhand * 0.78:.2f}", 0, 0, 0, 0, 0, 0, 0,
                            "No action required" if cover < 75 else "Consider removal",
                            "Yes" if cover < 20 else "No", f"{prices[i][-1]:.2f}", f"{prices[i][-1]:.2f}", "USD",
                            int(daily * 45), "Standard-Size" if s[8] == "standard" else "Oversize", f"{cover / 7:.1f}"])
    _write(out / "fba_inventory.csv", ["sku", "fnsku", "asin", "condition", "afn-fulfillable-quantity",
                                       "afn-inbound-working-quantity", "afn-inbound-shipped-quantity",
                                       "afn-inbound-receiving-quantity", "afn-reserved-quantity"], inv_rows)
    add("fba_inventory.csv", "fba_inventory", snap, snap)
    _write(out / "inventory_health.csv", ["snapshot-date", "sku", "fnsku", "asin", "product-name", "condition", "available",
        "pending-removal-quantity", "inv-age-0-to-90-days", "inv-age-91-to-180-days", "inv-age-181-to-270-days",
        "inv-age-271-to-365-days", "inv-age-365-plus-days", "units-shipped-t7", "units-shipped-t30", "units-shipped-t60",
        "units-shipped-t90", "sell-through", "days-of-supply", "estimated-excess-quantity", "item-volume", "storage-volume",
        "estimated-storage-cost-next-month", "estimated-ais-181-210-days", "estimated-ais-211-240-days",
        "estimated-ais-241-270-days", "estimated-ais-271-300-days", "estimated-ais-301-330-days",
        "estimated-ais-331-365-days", "estimated-ais-365-plus-days", "recommended-action",
        "low-inventory-level-fee-applied", "your-price", "sales-price", "currency", "healthy-inventory-level",
        "storage-type", "weeks-of-cover-t30"], health_rows)
    add("inventory_health.csv", "inventory_health", snap, snap)

    # ── advertising: daily campaign rows for the whole year, search terms for the last three months
    ppc_rows = []
    day = date(2025, 9, 1)
    camp_base = [92, 61, 74, 48, 39, 44, 33, 118]
    while day <= date(2026, 8, 31):
        m = PERIODS.index((day.year, day.month))
        for c, name in enumerate(CAMPAIGNS):
            spend = camp_base[c] * SEASON[m] * (1 + 0.25 * np.sin(day.toordinal() / 9.0)) * np.exp(rng.normal(0, 0.18))
            # concave response: sales rise with spend but flatten (a Hill curve the engine can fit)
            eff = 3.9 if "Exact" in name else 2.4 if "Broad" in name else 1.7
            sales = eff * camp_base[c] * (spend / camp_base[c]) ** 0.62 * np.exp(rng.normal(0, 0.22))
            clicks = int(spend / rng.uniform(0.55, 1.10))
            ppc_rows.append([day.strftime("%b %d, %Y"), name, _money(spend), _money(sales), clicks, _int(clicks * rng.uniform(28, 60))])
            monthly_ads[m] += spend
        day += timedelta(days=1)
    _write(out / "ppc_campaign.csv", ["Date", "Campaign Name", "Spend", "7 Day Total Sales", "Clicks", "Impressions"], ppc_rows)
    add("ppc_campaign.csv", "ppc_campaign", date(2025, 9, 1), date(2026, 8, 31))

    bleed_terms = ["free skillet giveaway", "cast iron recipe ideas", "how to season cast iron", "knife sharpening near me",
                   "bamboo board mold", "coffee shop wholesale", "french press vs drip", "skillet lodge",
                   "walmart cutting board", "cheap knives set"]
    for (y, mo) in PERIODS[-3:]:
        start, end = _month_bounds(y, mo)
        st_rows = []
        for c, name in enumerate(CAMPAIGNS):
            for k in range(6):
                sku_i = CAMPAIGN_SKUS[c][k % len(CAMPAIGN_SKUS[c])]
                term = SKUS[sku_i][0].lower()
                spend = camp_base[c] * 30 * rng.uniform(0.06, 0.16)
                sales = spend * rng.uniform(2.2, 5.0)
                orders = int(sales / prices[sku_i][-1])
                st_rows.append([name, "Core", term.split()[0], "EXACT" if "Exact" in name else "BROAD", term,
                                _int(spend * 45), int(spend / 0.8), _money(spend), _money(sales), orders, orders + int(orders * 0.06)])
            for term in rng.choice(bleed_terms, size=2, replace=False):
                spend = camp_base[c] * 30 * rng.uniform(0.02, 0.07)
                st_rows.append([name, "Core", term.split()[0], "BROAD", term, _int(spend * 60), int(spend / 0.7),
                                _money(spend), "$0.00", 0, 0])
        fn = f"ppc_search_terms_{start:%Y-%m}.csv"
        _write(out / fn, ["Campaign Name", "Ad Group Name", "Targeting", "Match Type", "Customer Search Term", "Impressions",
                          "Clicks", "Spend", "7 Day Total Sales", "7 Day Total Orders (#)", "7 Day Total Units (#)"], st_rows)
        add(fn, "ppc_search_terms", start, end)

    # ── the bleed reports: ledger, returns, reimbursements, settlements ─────
    ledger, returns, reimbs, txns = [], [], [], []
    ref = 77000
    order_n = 4000000
    def oid():
        nonlocal order_n
        order_n += rng.integers(11, 97)
        return f"111-{order_n:07d}-{rng.integers(1000000, 9999999)}"

    for i, s in enumerate(SKUS):
        sku, fn_, asin, title = _sku_code(i, s[0]), _fnsku(i), _asin(i), s[0]
        # receipts
        for k in range(2):
            d = TODAY - timedelta(days=int(rng.integers(20, 200)))
            ledger.append([f"{d.month}/{d.day}/{d.year}", fn_, asin, sku, title, "Receipts", f"FBA15TH{ref}", int(s[6] * 1.5),
                           rng.choice(FCS), "SELLABLE", "", "US", 0, 0, f"{d.month}/{d.day}/{d.year} 10:14:02 AM"])
            ref += 1
        # losses at ages that land in every window state as of TODAY
        for age, reason, qty, unrec in [(int(rng.integers(35, 55)), "M", -int(rng.integers(3, 26)), None),
                                        (int(rng.integers(8, 28)), rng.choice(["D", "Q"]), -int(rng.integers(2, 12)), None),
                                        (int(rng.integers(50, 59)), rng.choice(["H", "K", "6"]), -int(rng.integers(2, 14)), None),
                                        (int(rng.integers(70, 110)), "N", -int(rng.integers(2, 9)), None)]:
            if rng.random() < 0.72:
                d = TODAY - timedelta(days=age)
                units_lost = -qty
                unrec_q = units_lost if rng.random() < 0.4 else ""
                ledger.append([f"{d.month}/{d.day}/{d.year}", fn_, asin, sku, title, "Adjustments", f"ADJ-{ref}", qty,
                               rng.choice(FCS), "SELLABLE" if reason in "MN6" else "DAMAGED", reason, "US",
                               0 if unrec_q else units_lost, unrec_q, f"{d.month}/{d.day}/{d.year} 1:02:44 PM"])
                ref += 1
                if reason == "M" and rng.random() < 0.3:   # some of it is found again
                    d2 = d + timedelta(days=int(rng.integers(3, 20)))
                    ledger.append([f"{d2.month}/{d2.day}/{d2.year}", fn_, asin, sku, title, "Adjustments", f"ADJ-{ref}",
                                   int(rng.integers(1, max(2, units_lost))), rng.choice(FCS), "SELLABLE", "F", "US", 1, 0,
                                   f"{d2.month}/{d2.day}/{d2.year} 8:45:10 AM"])
                    ref += 1
        if rng.random() < 0.25:   # customer damage, not Amazon's liability
            d = TODAY - timedelta(days=int(rng.integers(10, 60)))
            ledger.append([f"{d.month}/{d.day}/{d.year}", fn_, asin, sku, title, "Adjustments", f"ADJ-{ref}", -1,
                           rng.choice(FCS), "CUSTOMER_DAMAGED", "E", "US", 1, 0, f"{d.month}/{d.day}/{d.year} 3:00:00 PM"])
            ref += 1
        # returns: sellable, damaged by Amazon, carrier, customer, defective
        for _ in range(int(rng.integers(3, 9))):
            d = TODAY - timedelta(days=int(rng.integers(3, 100)))
            disp = rng.choice(["SELLABLE", "SELLABLE", "SELLABLE", "DAMAGED", "CARRIER_DAMAGED", "CUSTOMER_DAMAGED", "DEFECTIVE"])
            status = "Unit returned to inventory" if disp == "SELLABLE" else ("Reimbursed" if rng.random() < 0.35 else "Unit not returned to inventory")
            o = oid()
            returns.append([f"{d.isoformat()}T{int(rng.integers(0, 23)):02d}:{int(rng.integers(0, 59)):02d}:00+00:00", o, sku, asin, fn_, title, 1,
                            rng.choice(FCS), disp, rng.choice(["NOT_AS_DESCRIBED", "UNWANTED_ITEM", "DEFECTIVE", "ORDERED_WRONG_ITEM"]),
                            status, f"LPNRR{ref:09d}", ""])
            ref += 1
            # every return has its refund in the settlement report
            dt = datetime.combine(d, datetime.min.time()) - timedelta(days=int(rng.integers(1, 6)), hours=int(rng.integers(1, 20)))
            p = prices[i][-1]
            txns.append([dt.strftime("%b %-d, %Y %-I:%M:%S %p PDT"), "", "Refund", o, sku, title, "1", "amazon.com", "Standard Orders", "Amazon",
                         "", "", "", "MarketplaceFacilitator", f"{-p:.2f}", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0",
                         f"{p * REFERRAL * 0.8:.2f}", "0", "0", "0", f"{-p * (1 - REFERRAL * 0.8):.2f}"])
        # refunds with no return at all: the customer kept both
        for _ in range(int(rng.integers(0, 3))):
            d = TODAY - timedelta(days=int(rng.integers(46, 118)))
            dt = datetime.combine(d, datetime.min.time()) + timedelta(hours=int(rng.integers(1, 22)))
            p = prices[i][-2]
            txns.append([dt.strftime("%b %-d, %Y %-I:%M:%S %p PDT"), "", "Refund", oid(), sku, title, "1", "amazon.com", "Standard Orders", "Amazon",
                         "", "", "", "MarketplaceFacilitator", f"{-p:.2f}", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0",
                         f"{p * REFERRAL * 0.8:.2f}", "0", "0", "0", f"{-p * (1 - REFERRAL * 0.8):.2f}"])
        # a few orders per SKU so the settlement report looks like one
        for _ in range(3):
            d = TODAY - timedelta(days=int(rng.integers(1, 120)))
            dt = datetime.combine(d, datetime.min.time()) + timedelta(hours=int(rng.integers(1, 22)))
            p = prices[i][-1]
            txns.append([dt.strftime("%b %-d, %Y %-I:%M:%S %p PDT"), "", "Order", oid(), sku, title, "1", "amazon.com", "Standard Orders", "Amazon",
                         "SEATTLE", "WA", "98101", "MarketplaceFacilitator", f"{p:.2f}", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0",
                         f"{-p * REFERRAL:.2f}", f"{-FEE_FBA[s[8]]:.2f}", "0", "0", f"{p * (1 - REFERRAL) - FEE_FBA[s[8]]:.2f}"])
        # reimbursements Amazon already paid, in cash and in kind
        if rng.random() < 0.4:
            d = TODAY - timedelta(days=int(rng.integers(5, 80)))
            q = int(rng.integers(1, 4))
            in_kind = rng.random() < 0.3
            landed = s[2] + s[3] + s[4]
            reimbs.append([d.isoformat(), f"RM-{ref}", "", "", rng.choice(["Lost_Warehouse", "Damaged_Warehouse"]), sku, fn_, asin, title, "New", "USD",
                           f"{landed:.2f}", "0.00" if in_kind else f"{landed * q:.2f}", 0 if in_kind else q, q if in_kind else 0, q, "", ""])
            ref += 1
    # one reversal: a reimbursement clawed back
    s0 = SKUS[3]
    d = TODAY - timedelta(days=12)
    reimbs.append([d.isoformat(), f"RM-{ref}", "", "", "Reversal", _sku_code(3, s0[0]), _fnsku(3), _asin(3), s0[0], "New", "USD",
                   f"{-(s0[2] + s0[3] + s0[4]):.2f}", f"{-(s0[2] + s0[3] + s0[4]) * 2:.2f}", 2, 0, 2, "RM-70011", "Reversal"])
    # monthly storage fee lines for the whole year, so the settlement series has a history
    for m, (y, mo) in enumerate(PERIODS):
        d = datetime(y, mo, 7, 0, 0, 0)
        total_vol = sum(s[9] * units[i, m] * 0.9 for i, s in enumerate(SKUS))
        fee = -total_vol * STORAGE_PER_CUFT["peak" if mo in (10, 11, 12) else "offpeak"]
        txns.append([d.strftime("%b %-d, %Y %-I:%M:%S %p PDT"), "", "FBA Inventory Fee", "", "", "FBA storage fee", "", "amazon.com", "", "",
                     "", "", "", "", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", f"{fee:.2f}", f"{fee:.2f}"])
        txns.append([datetime(y, mo, 12, 9, 15, 30).strftime("%b %-d, %Y %-I:%M:%S %p PDT"), "", "Service Fee", "", "", "Subscription", "", "amazon.com", "", "",
                     "", "", "", "", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "-39.99", "-39.99"])

    _write(out / "inventory_ledger.csv", ["Date", "FNSKU", "ASIN", "MSKU", "Title", "Event Type", "Reference ID", "Quantity",
                                          "Fulfillment Center", "Disposition", "Reason", "Country", "Reconciled Quantity",
                                          "Unreconciled Quantity", "Date and Time"], ledger)
    add("inventory_ledger.csv", "inventory_ledger", TODAY - timedelta(days=200), TODAY)
    _write(out / "fba_returns.csv", ["return-date", "order-id", "sku", "asin", "fnsku", "product-name", "quantity",
                                     "fulfillment-center-id", "detailed-disposition", "reason", "status",
                                     "license-plate-number", "customer-comments"], returns)
    add("fba_returns.csv", "fba_returns", TODAY - timedelta(days=100), TODAY)
    _write(out / "fba_reimbursements.csv", ["approval-date", "reimbursement-id", "case-id", "amazon-order-id", "reason", "sku", "fnsku",
                                            "asin", "product-name", "condition", "currency-unit", "amount-per-unit", "amount-total",
                                            "quantity-reimbursed-cash", "quantity-reimbursed-inventory", "quantity-reimbursed-total",
                                            "original-reimbursement-id", "original-reimbursement-type"], reimbs)
    add("fba_reimbursements.csv", "fba_reimbursements", TODAY - timedelta(days=100), TODAY)
    preamble = ['"Includes Amazon Marketplace, Fulfillment by Amazon (FBA), and Amazon Webstore transactions"',
                '"All amounts in USD, unless specified"', '"Definitions:"',
                '"Sales tax collected: Includes sales tax collected from buyers for product sales, shipping, and gift wrap."',
                '"Selling fees: Includes variable closing fees and referral fees."',
                '"Other transaction fees: Includes shipping chargebacks, shipping holdback, per-item fees and sales tax collection fees."',
                '"Other: Includes non-order transaction amounts. For more details, see the ""Type"" and ""Description"" columns for each order ID."']
    _write(out / "transactions.csv", ["date/time", "settlement id", "type", "order id", "sku", "description", "quantity", "marketplace",
        "account type", "fulfillment", "order city", "order state", "order postal", "tax collection model", "product sales",
        "product sales tax", "shipping credits", "shipping credits tax", "gift wrap credits", "giftwrap credits tax", "Regulatory Fee",
        "Tax On Regulatory Fee", "promotional rebates", "promotional rebates tax", "marketplace withheld tax", "selling fees",
        "fba fees", "other transaction fees", "other", "total"], txns, preamble=preamble)
    add("transactions.csv", "transactions", date(2025, 9, 1), TODAY)

    manifest["annual_revenue"] = round(float(sum(units[i, m] * prices[i][m] for i in range(24) for m in range(12))), 2)
    manifest["annual_ad_spend"] = round(float(monthly_ads.sum()), 2)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = generate()
    print(f"{m['brand']}: {len(m['files'])} files, revenue ${m['annual_revenue']:,.0f}, ads ${m['annual_ad_spend']:,.0f}")
