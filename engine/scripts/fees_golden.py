"""Golden values for lib/fees.js, produced by the Python engine.

    cd engine && uv run python scripts/fees_golden.py

Writes ../lib/fees.golden.json. `node --test lib/fees.test.mjs` then pins the
JavaScript port of priors/findings/shelf to these numbers, so the figure a
visitor sees on /teardown is the figure the cold engine would have emailed.
Regenerate after any change to priors.py, findings.py or harvest/amazon.py.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hubricon_engine.cold import findings, priors  # noqa: E402
from hubricon_engine.cold.snapshot import Item, ProspectSnapshot, dim_weight_oz, parse_dims, size_tier  # noqa: E402
from hubricon_engine.harvest import amazon  # noqa: E402

TODAY = date(2026, 9, 8)          # fixed: the golden file must not drift with the calendar
OUT = Path(__file__).resolve().parents[2] / "lib" / "fees.golden.json"


def main() -> None:
    cases = {"fees": [], "edges": [], "tiers": [], "units": [], "detect": []}
    for tier, oz, price, day, cardname in [
        ("small_standard", 3.0, 9.49, "2026-09-08", None), ("small_standard", 3.0, 9.49, "2026-10-15", None),
        ("small_standard", 3.0, 9.49, "2026-09-08", "peak"), ("small_standard", 12.0, 24.99, "2026-09-08", None),
        ("small_standard", 16.0, 55.0, "2026-09-08", None), ("small_standard", 16.5, 55.0, "2026-09-08", None),
        ("large_standard", 4.0, 12.0, "2026-09-08", None), ("large_standard", 17.2, 24.99, "2026-09-08", None),
        ("large_standard", 48.0, 24.99, "2026-09-08", None), ("large_standard", 50.0, 25.0, "2026-12-01", None),
        ("large_standard", 57.0, 25.0, "2026-09-08", None), ("large_standard", 400.0, 25.0, "2026-09-08", None),
        ("small_standard", 3.0, 9.49, "2027-02-01", None), ("small_standard", 3.0, 9.49, "2026-03-01", None),
    ]:
        d = date.fromisoformat(day)
        card = priors.card_named(cardname) if cardname else None
        cases["fees"].append({"args": [tier, oz, price, day, cardname],
                              "want": priors.fulfilment_fee(tier, oz, price, d, card)})
    for tier, oz in [("small_standard", 12.3), ("small_standard", 12.0), ("small_standard", 1.5),
                     ("large_standard", 52.0), ("large_standard", 57.0), ("large_standard", 4.0), ("large_standard", 4.01)]:
        cases["edges"].append({"args": [tier, oz], "want": priors.band_edge_below(tier, oz)})
    for dims, oz in [("9 x 6 x 2 inches", 13.0), ("15 x 12 x 0.75 inches", 16.0), ("15 x 12 x 0.8 inches", 16.0),
                     ("18 x 14 x 8 inches", 300.0), ("19 x 14 x 8 inches", 100.0), ("14 x 13 x 13 inches", 40.0), (None, 10.0)]:
        p = parse_dims(dims)
        cases["tiers"].append({"args": [dims, oz], "want": size_tier(p, oz),
                               "dims": list(p) if p else None, "dim_weight_oz": dim_weight_oz(p)})
    for bsr, cat in [(5000, "kitchen & dining"), (1200, "baby"), (30000, "home & kitchen"), (800, "beauty & personal care"),
                     (150, "automotive"), (250000, "unknown cat"), (None, "baby")]:
        cases["units"].append({"args": [bsr, cat], "want": amazon.estimate_units(bsr, cat)})

    def mk(price, category, rank, oz, dims):
        p = parse_dims(dims) if dims else None
        return Item(ref="X", url="u", title="t", category=category, price=price, rank=rank, item_weight_oz=oz,
                    dims_in=p, est_monthly_units=amazon.estimate_units(rank, category), est_monthly_revenue=None)

    for price, cat, rank, oz, dims in [
        (10.49, "kitchen & dining", 5000, 13.0, "9 x 6 x 2 inches"),
        (24.99, "baby", 1200, 17.2, "12 x 9 x 3 inches"),
        (52.0, "home & kitchen", 30000, 8.5, "14 x 11 x 1.2 inches"),
        (19.99, "beauty & personal care", 800, 3.2, None),
        (35.0, "automotive", 20000, 20.0, "18 x 12 x 9 inches"),
        (12.99, "kitchen & dining", 9000, 6.0, "15 x 12 x 0.9 inches"),
        (29.99, "home & kitchen", 4000, 12.6, "10 x 8 x 6 inches"),
        (9.49, "baby", 700, 4.4, "8 x 5 x 1 inches"),
        (44.0, "pet supplies", 15000, 40.0, "20 x 16 x 14 inches"),
    ]:
        it = mk(price, cat, rank, oz, dims)
        snap = ProspectSnapshot(key="k", platform="amazon", provider="golden", items=(it,))
        found = findings.detect(snap, today=TODAY)
        cases["detect"].append({
            "args": {"price": price, "category": cat, "bsr": rank, "itemWeightOz": oz, "dims": dims},
            "item": {"tier": it.tier, "billableWeightOz": it.billable_weight_oz, "dimWeightOz": it.dim_weight_oz,
                     "estMonthlyUnits": it.est_monthly_units},
            "want": [{"kind": f.kind, "perUnitLow": f.per_unit_low, "perUnitHigh": f.per_unit_high,
                      "dollarsLow": f.dollars_low, "dollarsHigh": f.dollars_high, "confidence": f.confidence}
                     for f in found]})
    # -- the Shopify lane ----------------------------------------------------------
    from hubricon_engine.cold import shelf
    from hubricon_engine.harvest import shopify
    cases["carrier"] = {
        "cliff": [{"args": [w], "want": list(shopify.shipping_cliff(w)) if shopify.shipping_cliff(w) else None,
                   "names": list(shopify.band_names(shopify.shipping_cliff(w)[0])) if shopify.shipping_cliff(w) else None}
                  for w in (15.9, 16.0, 16.5, 17.2, 31.9, 33.0, 48.5, 100.0, None)],
        "rows": {str(e): (list(priors.carrier_rows(e)) if priors.carrier_rows(e) else None) for e in (16, 32, 48)},
        "steps": {str(k): list(v) for k, v in priors.CARRIER_GROUND_USD.items()},
    }
    cases["payments"] = [{"args": [plan, amt], "want": priors.payments_fee(plan, amt)}
                         for plan, amt in (("basic", 30.0), ("grow", 30.0), ("advanced", 100.0), ("plus", 10.0),
                                           (None, 30.0), ("nope", 30.0), ("basic", 0))]
    def sitem(ref, price, compare_at, oz, units):
        return Item(ref=f"shop.example/products/{ref}", url="u", title=ref, price=price, compare_at_price=compare_at,
                    item_weight_oz=oz, est_monthly_units=units, est_monthly_revenue=None)
    shops = {
        "one_over_pound": [sitem("a", 32.0, None, 17.2, 400)],
        "anchor_on_a_marked_shelf": [sitem("a", 32.0, 45.0, 12.0, 300), sitem("b", 20.0, 28.0, 8.0, None), sitem("c", 15.0, None, 6.0, None)],
        "anchor_on_a_clean_shelf": [sitem("a", 32.0, 45.0, 12.0, 300), sitem("b", 20.0, None, 8.0, None), sitem("c", 15.0, None, 6.0, None), sitem("d", 9.0, None, 4.0, None)],
        "both": [sitem("a", 32.0, 45.0, 33.0, 250)],
        "too_far_over": [sitem("a", 32.0, None, 22.0, 400)],
        "under_a_pound": [sitem("a", 32.0, None, 12.0, 400)],
        "off_the_card": [sitem("a", 60.0, None, 49.0, 100)],
    }
    cases["shopify_detect"] = []
    for name, items in shops.items():
        snap = ProspectSnapshot(key=name, platform="shopify", provider="golden", items=tuple(items))
        found = [f for f in findings.detect(snap, today=TODAY) if f.asin_or_sku == items[0].ref]
        cases["shopify_detect"].append({
            "name": name,
            "args": {"price": items[0].price, "compareAtPrice": items[0].compare_at_price, "weightOz": items[0].item_weight_oz,
                     "orders": None, "units": 1, "estMonthlyUnits": items[0].est_monthly_units,
                     "catalogueShare": findings._catalogue_discount_share(snap)},
            "want": [{"kind": f.kind, "perUnitLow": f.per_unit_low, "perUnitHigh": f.per_unit_high,
                      "dollarsLow": f.dollars_low, "dollarsHigh": f.dollars_high, "confidence": f.confidence,
                      "edge": f.evidence.get("edge")} for f in found]})
    rows = [{"platform": "shopify", "seller_id": f"s{i % 7}", "weight_oz": 14 + (i % 9) * 0.7} for i in range(60)]
    rows += [{"platform": "amazon", "seller_id": "x", "weight_oz": 17.0}] * 5
    b = shelf.benchmark(rows, None, your_weight_oz=17.2, platform="shopify")
    cases["shopify_bench"] = {"rows": rows, "your_weight_oz": 17.2,
                              "want": {"measured": b.measured, "near": b.near, "share": b.share,
                                       "buckets": [list(x) for x in b.buckets], "your_over_by": b.your_over_by}}
    thin = shelf.benchmark(rows[:20], None, your_weight_oz=17.2, platform="shopify")
    cases["shopify_bench_thin"] = {"rows": rows[:20], "want": None if thin is None else "not none"}
    OUT.write_text(json.dumps(cases, indent=1))
    print(f"wrote {OUT} — " + ", ".join(f"{k} {len(v)}" for k, v in cases.items()))


if __name__ == "__main__":
    main()
