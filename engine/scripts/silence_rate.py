"""How often the engine finds nothing to say about an Amazon brand from its public pages.

    cd engine && uv run python scripts/silence_rate.py [--today YYYY-MM-DD]

Reads every harvested Amazon seller and listing (harvest_sellers, harvest_products),
runs the cold engine's own detectors (cold/findings.detect) over each seller that has
at least one listing with a price and a volume estimate, and counts the sellers for
whom it returns nothing. Writes ../scripts/case-study/silence.json, which the home
page's case study prints as "of N brands, M showed nothing worth fixing".

COLD_ENGINE.md §2.2 expected roughly half; on single public snapshots the measured
share is higher (cold/run.py explains why), and the page prints the measured one.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hubricon_engine import db  # noqa: E402
from hubricon_engine.cold import findings  # noqa: E402
from hubricon_engine.cold.snapshot import Item, ProspectSnapshot, parse_dims  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "scripts" / "case-study" / "silence.json"
PRODUCT_COLUMNS = ("asin,seller_id,category,bsr,price,reviews,weight_oz,dims,"
                   "fulfilled_by_amazon,est_monthly_units,est_monthly_revenue,seen_at")


def _num(v):
    return float(v) if v is not None else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=None, help="the day whose rate card prices the findings")
    args = ap.parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()

    client = db.connect()
    products = db.fetch_rows(client, "harvest_products", PRODUCT_COLUMNS)
    sellers = {s["seller_id"]: s for s in db.fetch_rows(client, "harvest_sellers", "seller_id,country")}

    by_seller: dict[str, list[dict]] = collections.defaultdict(list)
    for p in products:
        by_seller[p["seller_id"]].append(p)

    modeled = silent = 0
    kinds: collections.Counter = collections.Counter()
    first_seen = last_seen = None
    for seller_id, rows in by_seller.items():
        items = tuple(Item(
            ref=p["asin"], url=f"https://www.amazon.com/dp/{p['asin']}", category=p["category"],
            price=_num(p["price"]), reviews=p["reviews"], rank=p["bsr"],
            item_weight_oz=_num(p["weight_oz"]), dims_in=parse_dims(p["dims"]),
            est_monthly_units=_num(p["est_monthly_units"]),
            est_monthly_revenue=_num(p["est_monthly_revenue"]),
            fulfilled_by_amazon=p["fulfilled_by_amazon"]) for p in rows)
        snap = ProspectSnapshot(key=seller_id or "?", platform="amazon", provider="harvest",
                                country=(sellers.get(seller_id) or {}).get("country"), items=items)
        if not snap.priced_items():
            continue
        modeled += 1
        found = findings.detect(snap, today)
        if not found:
            silent += 1
        kinds.update(f.kind for f in found)
        for p in rows:
            seen = (p.get("seen_at") or "")[:10]
            if seen:
                first_seen = min(first_seen or seen, seen)
                last_seen = max(last_seen or seen, seen)

    out = {
        "measured_on": today.isoformat(),
        "brands_modeled": modeled,
        "brands_silent": silent,
        "share_silent": round(silent / modeled, 4) if modeled else None,
        "listings_read": len(products),
        "captured_between": [first_seen, last_seen],
        "findings_by_kind": dict(kinds.most_common()),
        "basis": ("Amazon sellers in harvest_sellers with at least one listing carrying a price "
                  "and a rank-based volume estimate; silent = cold/findings.detect returned nothing "
                  "on the rate card in force on measured_on."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
