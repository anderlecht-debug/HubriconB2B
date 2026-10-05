"""What a Shopify store's own files show that no Amazon model looks for.

Two openers book a Shopify seller's call (cold/findings.py): a product listed
under its own compare-at price for good, and a parcel that weighs just over a
pound line on the USPS card. Before 2026-10-01 both vanished after the yes,
because nothing on the client side read the compare-at or the grams. This
module reads them off the client's own Products export (kept on every row it
writes, ingest/shopify_products, raw["_variant"]) and the orders behind them
(sku_economics, channel shopify), with the same arithmetic the cold lane uses
(models/compare_at.py).

COMPARE-AT. A variant whose price sits at least MIN_DISCOUNT_SHARE under its
own compare-at, and which has sold at that same price in at least
STABLE_OBSERVATIONS months of its orders spanning STABLE_DAYS, is "below its
own compare-at, the discount permanent". The dollars beside it are the gap
(compare-at less price, the store's own two published numbers) times the
units a 30-day month of those same months sold: the discount's FACE VALUE at
today's volume. That is not what a price change would earn, since demand
answers a price, and the payload says so. What a step back toward the
compare-at earns is priced by the SKU's fitted demand curve and measured
like any price step (directives.compare_at_directives, measurement's
price-step family). Found, never proven: nothing here enters the Profit
Record.

PARCEL BAND. A variant whose shipping weight (Variant Grams) sits within
MAX_SHAVEABLE_CARRIER_OZ over a pound line is billed, if it ships alone, at
the next pound; the published USPS Ground Advantage card prices the step per
parcel across zones 1 to 8. Label costs are not ingested and nothing says
which orders shipped alone, so this is an observation, found and not
measured, with a per-parcel range off the published card and no monthly
dollar figure.

WHAT IT CANNOT TELL YOU. Whether the compare-at stood through those months
(the Products export is a snapshot; only the price history is the orders');
what the store pays per label; anything about a variant that stated neither
a cost nor a stock count, since the export wrote no row for it.
"""

from __future__ import annotations

from datetime import date

from . import compare_at as ca
from .common import num, period_days

CHANNEL = "shopify"
VARIANT_KEY = "_variant"   # ingest/shopify_products.VARIANT_KEY
# A month's average list price within this share of today's price is the same
# price: one order at an old price, or a wholesale line, does not make a month
# a different price.
SAME_PRICE_SHARE = 0.01
MONTH_DAYS = 30.0
INACTIVE = {"archived", "draft"}


def _day(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _raw(row: dict) -> dict:
    raw = row.get("raw")
    return raw if isinstance(raw, dict) else {}


def _is_shopify(row: dict) -> bool:
    return str(row.get("channel") or CHANNEL).lower() == CHANNEL


def variants(data: dict) -> dict[str, dict]:
    """{sku: the variant's parsed numbers} from the latest Products export on
    file: every inventory_levels and cogs_inputs row the export wrote carries
    them, and the newest snapshot wins."""
    out: dict[str, dict] = {}
    rows = [r for r in data.get("inventory_levels") or [] if _is_shopify(r)] + list(data.get("cogs_inputs") or [])
    for r in rows:
        v = _raw(r).get(VARIANT_KEY)
        if not isinstance(v, dict) or not r.get("sku"):
            continue
        seen = out.get(r["sku"])
        if seen is None or str(v.get("snapshot_date") or "") >= str(seen.get("snapshot_date") or ""):
            out[r["sku"]] = {**v, "sku": r["sku"]}
    return out


def history(data: dict) -> dict[str, list[dict]]:
    """{sku: [{day, price, units_month, orders_month}]} per period of the
    store's orders, oldest first. price is the period's average list price
    (Lineitem price before line discounts); the counts are scaled to a
    30-day month."""
    out: dict[str, list[dict]] = {}
    for r in data.get("sku_economics") or []:
        if not _is_shopify(r) or not r.get("sku") or not r.get("period_start") or not r.get("period_end"):
            continue
        units = float(r.get("units_sold") or 0)
        if units <= 0 or r.get("avg_sales_price") is None:
            continue
        days = period_days(str(r["period_start"])[:10], str(r["period_end"])[:10])
        out.setdefault(r["sku"], []).append({
            "day": _day(r["period_start"]), "price": float(r["avg_sales_price"]),
            "units_month": units * MONTH_DAYS / days,
            "orders_month": float(_raw(r).get("orders") or 0) * MONTH_DAYS / days,
        })
    for rows in out.values():
        rows.sort(key=lambda h: h["day"])
    return out


def _same_price(p: float, price: float) -> bool:
    return abs(p - price) < max(ca.SAME_PRICE_USD, SAME_PRICE_SHARE * price)


def compare_at_finding(data: dict) -> dict:
    """Variants listed under their own compare-at, and which of them have held
    that price long enough to call the discount permanent."""
    vs = {s: v for s, v in variants(data).items() if (v.get("status") or "") not in INACTIVE}
    hist = history(data)
    rows = []
    for sku, v in vs.items():
        price, anchor = v.get("price"), v.get("compare_at_price")
        share = ca.discount_share(price, anchor)
        if not share or share < ca.MIN_DISCOUNT_SHARE:
            continue
        months = hist.get(sku, [])
        tol = max(ca.SAME_PRICE_USD, SAME_PRICE_SHARE * float(price))
        settled, readings, span = ca.price_is_settled(price, [(h["day"], h["price"]) for h in months], tol)
        same = [h for h in months if _same_price(h["price"], float(price))][-ca.STABLE_OBSERVATIONS:]
        units_month = sum(h["units_month"] for h in same) / len(same) if same else None
        per_unit = ca.per_unit_gap(price, anchor)
        rows.append({
            "sku": sku, "product_name": v.get("product_name"), "handle": v.get("handle"),
            "price": num(price), "compare_at": num(anchor), "discount_share": share, "per_unit": per_unit,
            "settled": settled, "months_at_price": readings, "days_observed": span,
            "units_month": num(units_month, 1),
            "usd_month_face_value": num(per_unit * units_month) if units_month else None,
            "snapshot_date": v.get("snapshot_date"),
        })
    rows.sort(key=lambda r: (not r["settled"], -(r["usd_month_face_value"] or 0)))
    permanent = [r for r in rows if r["settled"]]
    face = sum(r["usd_month_face_value"] or 0 for r in permanent)
    return {
        "kind": "compare_at",
        "status": "found" if permanent else ("watching" if rows else "none"),
        "proof": "found",          # never "proven": the Profit Record banks measured moves only
        "n_variants": len(permanent),
        "n_below_anchor": len(rows),
        "usd_month_face_value": num(face) if permanent else None,
        "catalogue_share": ca.catalogue_share((v.get("price"), v.get("compare_at_price")) for v in vs.values()),
        "rows": rows,
        "basis": (f"your Products export's price and compare-at for each variant, and your orders' monthly price: "
                  f"a variant at least {ca.MIN_DISCOUNT_SHARE:.0%} under its compare-at that has sold at the same "
                  f"price in {ca.STABLE_OBSERVATIONS} or more months spanning {ca.STABLE_DAYS}+ days. The dollars "
                  f"are face value (the gap times a month of those months' units) before any change in demand, "
                  f"not what a price change would earn."),
    }


def parcel_band_finding(data: dict) -> dict:
    """Variants just over a pound line on the USPS card: an observation, found
    and not measured, since what the store pays per label is not on file."""
    from ..cold import priors
    from ..cold.findings import MAX_SHAVEABLE_CARRIER_OZ
    from ..harvest import shopify as harvest_shopify

    hist = history(data)
    rows = []
    for sku, v in variants(data).items():
        if (v.get("status") or "") in INACTIVE:
            continue
        oz = harvest_shopify.grams_to_oz(v.get("grams"))
        cliff = harvest_shopify.shipping_cliff(oz)
        if not cliff:
            continue
        edge, over_by = cliff
        if over_by > MAX_SHAVEABLE_CARRIER_OZ:
            continue
        below, above = harvest_shopify.band_names(edge)
        priced = priors.CARRIER_GROUND_USD.get(edge)
        recent = hist.get(sku, [])[-ca.STABLE_OBSERVATIONS:]
        rows.append({
            "sku": sku, "product_name": v.get("product_name"), "weight_oz": oz, "edge_oz": edge,
            "over_by_oz": over_by, "band_below": below, "band_above": above,
            "per_parcel_low": priced[0] if priced else None, "per_parcel_high": priced[1] if priced else None,
            "orders_month": num(sum(h["orders_month"] for h in recent) / len(recent), 1) if recent else None,
        })
    rows.sort(key=lambda r: -(r["orders_month"] or 0))
    return {
        "kind": "parcel_band",
        "status": "found" if rows else "none",
        "proof": "found",
        "measured": False,
        "n_variants": len(rows),
        "rows": rows,
        "rate_card": priors.CARRIER_SOURCE,
        "basis": (f"the shipping weight on each variant (Variant Grams) against the pound lines of "
                  f"{priors.CARRIER_SOURCE}, per parcel across zones 1 to 8. Your label costs are not in the files "
                  f"you sent, and nothing in them says which orders shipped alone, so this is found, not measured: "
                  f"no monthly dollar figure is stated."),
    }


def run(data: dict) -> dict:
    """Both findings for one Shopify read. Pure: the caller saves it as the
    run's `shopify_findings` output."""
    ca_f = compare_at_finding(data)
    pb_f = parcel_band_finding(data)
    has_products = bool(variants(data))
    return {
        "channel": CHANNEL,
        "status": ("found" if "found" in (ca_f["status"], pb_f["status"])
                   else "no_products_export" if not has_products else "none"),
        "compare_at": ca_f,
        "parcel_band": pb_f,
    }


def _names(rows: list[dict], n: int = 3) -> str:
    parts = [f"{r.get('product_name') or r['sku']} at ${float(r['price']):,.2f} against ${float(r['compare_at']):,.2f}"
             for r in rows[:n]]
    more = len(rows) - n
    return "; ".join(parts) + (f"; and {more} more" if more > 0 else "")


def letter_paragraphs(findings: dict | None, stepped: set[str] | None = None) -> list[str]:
    """The findings in the first read's own words, each marked found and not
    proven. `stepped` names the SKUs this read drafted a price step up on."""
    if not findings:
        return []
    out = []
    cf = findings.get("compare_at") or {}
    permanent = [r for r in cf.get("rows") or [] if r.get("settled")]
    if permanent:
        n = len(permanent)
        face = float(cf.get("usd_month_face_value") or 0)
        text = (f"Found in your own files, not yet proven: {n} variant{'s' if n != 1 else ''} "
                f"{'have' if n != 1 else 'has'} sold at the same price for at least {ca.STABLE_OBSERVATIONS} months "
                f"and {'are' if n != 1 else 'is'} listed today under {'their' if n != 1 else 'its'} own compare-at, "
                f"so the discount reads as permanent rather than a promotion: {_names(permanent)}. At the volume "
                f"your orders show, the gap comes to "
                f"${face:,.0f} a month at face value: the two prices you published times the units you sold, before "
                f"any change in demand, not what raising a price would earn.")
        hit = sorted(set(stepped or ()) & {r["sku"] for r in permanent})
        if hit:
            text += (f" {len(hit)} of them {'have' if len(hit) != 1 else 'has'} a price step back toward the "
                     f"compare-at among the moves this read drafted, each with its expected dollars from your own "
                     f"demand history and measured on your orders once made.")
        else:
            text += (" No step back toward the compare-at is drafted yet: a step needs a demand curve your price "
                     "history can fit, and a price that has not moved for months cannot show one.")
        out.append(text)
    pb = findings.get("parcel_band") or {}
    rows = pb.get("rows") or []
    if rows:
        r = rows[0]
        n = len(rows)
        priced = r.get("per_parcel_low") is not None
        text = (f"Found, not measured: {n} variant{'s' if n != 1 else ''} weigh{'' if n != 1 else 's'} just over "
                f"a pound line, such as {r.get('product_name') or r['sku']} at {float(r['weight_oz']):.1f} oz, "
                f"{float(r['over_by_oz']):.1f} oz over the {int(r['edge_oz'])} oz line. USPS Ground Advantage "
                f"bills a parcel over that line at {r['band_above']}")
        text += (f"; on the published card, the same parcel under it costs ${float(r['per_parcel_low']):,.2f} to "
                 f"${float(r['per_parcel_high']):,.2f} less, zones 1 to 8." if priced else ".")
        text += (" Your label costs are not in the files you sent, and nothing in them says which orders shipped "
                 "alone, so we have not measured what this costs you.")
        out.append(text)
    return out
