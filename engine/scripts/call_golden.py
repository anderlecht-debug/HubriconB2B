"""Golden values for lib/call.js, produced by the engine's own code.

    cd engine && uv run python scripts/call_golden.py

Writes ../lib/call.golden.json. `node --test lib/call.test.mjs` then holds the call's
JavaScript to it: reading a Seller Central export the way the ingest does, and pricing
the aged-inventory surcharge and the low-inventory-level fee the way inventory_econ.run
does, so the number shown on a call is the number the Profit Record would count after
a yes. Regenerate after any change to ingest/readers.py, ingest/headers.py,
ingest/inventory_health.py, models/fee_schedule.py or models/inventory_econ.py.
"""
from __future__ import annotations

import io
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hubricon_engine.ingest import headers, inventory_health, readers  # noqa: E402
from hubricon_engine.models import fee_schedule as fees  # noqa: E402
from hubricon_engine.models import inventory_econ as econ  # noqa: E402

TODAY = date(2026, 9, 1)          # fixed: the golden file must not drift with the calendar
ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "engine" / "tests" / "fixtures" / "inventory_health_clean.csv"
OUT = ROOT / "lib" / "call.golden.json"
FIELDS = ["sku", "available", "inv_age_181_to_270", "inv_age_271_to_365", "inv_age_365_plus", "units_shipped_t30",
          "item_volume", "storage_volume", "estimated_aged_surcharge", "low_inventory_level_fee_applied", "storage_type"]


FEE_PREVIEW = ROOT / "engine" / "tests" / "fixtures" / "fee_preview_clean.txt"
# The low-inventory fee's own columns, per fixture row (sku, or fnsku where the sku is
# blank): Amazon's 30- and 90-day historical days of supply and its exemption flag.
LILF_COLUMNS = {
    "WIDGET-BLUE": ("20", "25", "No"),     # Amazon's own supply, 25 days: the 21-28 band
    "WIDGET-RED": ("10", "30", "No"),      # the 90-day supply is over 28: no fee
    "GADGET-PRO": ("12", "13", "No"),      # under 14, but 15 shipped in 7 days: exempt
    "X001ABC4": ("5", "6", "Yes"),         # Amazon's export marks it exempt
}
# Fee Preview's own columns the engine would read for the tier, carried into each row's raw.
TIER_COLUMNS = ("product-size-tier", "item-package-weight", "unit-of-weight", "product-group")


def parse(text: str) -> list[dict]:
    df = readers.read_table(text.encode("utf-8"))
    _, rows, _ = inventory_health.parse(df, {"client_id": "c", "id": "u", "period_start": "2026-08-30"})
    return rows


def priced(rows: list[dict]) -> dict:
    """inventory_econ.run on the parsed rows, at the last 30 days' pace: what the engine would count."""
    inv = [{"sku": r["sku"], "daily_velocity_mean": (r.get("units_shipped_t30") or 0) / 30, "daily_velocity_std": 0.01,
            "lead_time_days": 30, "on_hand_units": r.get("available") or 0, "inbound_units": 0, "reorder_qty": 100} for r in rows]
    margins = [{"sku": r["sku"], "period_start": "2026-08-01", "period_end": "2026-08-31", "units": 30, "revenue": 900.0,
                "amazon_fees": 270.0, "cogs": 225.0, "ad_spend_allocated": 0.0, "net_margin": 405.0} for r in rows]
    out = econ.run({"inventory_health": rows}, inv, margin_rows=margins, rng=np.random.default_rng(0), simulations=2000, today=TODAY)
    return {r["sku"]: {"aged_surcharge_month": r.get("aged_surcharge_month"), "basis": r.get("aged_surcharge_basis"),
                       "low_inventory_fee_month": r.get("low_inventory_fee_month"),
                       "low_inventory_fee_rate": r.get("low_inventory_fee_rate"), "fee_size_tier": r.get("fee_size_tier"),
                       "low_inventory_fee_exempt": r.get("low_inventory_fee_exempt"),
                       "low_inventory_fee_basis": r.get("low_inventory_fee_basis")} for r in out["rows"]}


def with_fee_preview_tiers(rows: list[dict], fee_text: str) -> list[dict]:
    """The health rows with each SKU's Fee Preview size tier, weight and group in its raw
    row: what the engine reads when an export carries them, and what the call reads from
    the Fee Preview beside the Inventory Age report."""
    fp = readers.read_table(fee_text.encode("utf-8"))
    by_sku = {rec["sku"]: rec for rec in fp.to_dict(orient="records")}
    return [{**r, "raw": {**(r.get("raw") or {}), **{k: by_sku[r["sku"]][k] for k in TIER_COLUMNS}}}
            if r["sku"] in by_sku else r for r in rows]


def main() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    no_ais = df[[c for c in df.columns if not c.startswith("estimated-ais")]].to_csv(index=False)

    lilf = df.copy()
    keys = [r["sku"] or r["fnsku"] for r in lilf.to_dict(orient="records")]
    for i, col in enumerate(("short-term-historical-days-of-supply", "long-term-historical-days-of-supply",
                             "exempted-from-low-inventory-level-fee")):
        lilf[col] = [LILF_COLUMNS[k][i] for k in keys]
    with_lilf = lilf.to_csv(index=False)
    # Fee Preview with one SKU moved past 3 lb, so the 3-20 lb row is held to the engine too
    fee_text = FEE_PREVIEW.read_text(encoding="utf-8")
    fp = pd.read_csv(io.StringIO(fee_text), sep="\t", dtype=str, keep_default_na=False)
    fp.loc[fp["sku"] == "WIDGET-RED", "item-package-weight"] = "4.10"
    fee_tiers = fp.to_csv(index=False, sep="\t")

    rows = parse(text)
    rows_schedule = parse(no_ais)
    cases = {
        "fixture": text,
        "fixture_no_ais": no_ais,
        "fixture_lilf": with_lilf,
        "fee_preview_tiers": fee_tiers,
        "parsed": [{k: r.get(k) for k in FIELDS} for r in rows],
        "priced_amazon": priced(rows),
        "priced_schedule": priced(rows_schedule),
        "priced_lilf": priced(parse(with_lilf)),
        "priced_tiers": priced(with_fee_preview_tiers(rows, fee_tiers)),
        "low_inventory_rate": [{"args": [d, t], "want": fees.low_inventory_fee(d, t)}
                               for t in ("standard", "oversize", *fees.LOW_INVENTORY_FEE_PER_UNIT, None)
                               for d in (0, 5, 13.9, 14, 20.9, 21, 27.9, 28, 40)],
        "low_inventory_tier": [{"args": [label, w], "want": list(fees.low_inventory_tier(label, w))}
                               for label, w in (("Small standard", None), ("Large standard", 0.82), ("Large standard", 3.0),
                                                ("Large standard", 3.01), ("Large standard", None), ("Large Standard-Size", 12.0),
                                                ("Small Bulky", None), ("Large bulky", 40.0), ("Standard-Size", None), ("", None),
                                                (None, None), ("Oversize", None), ("Small oversize", None),
                                                ("Extra-large 0 to 50 lb", None), ("Special oversize", None), ("Apparel", None))],
        "aged_rate": [{"args": [a], "want": fees.aged_surcharge_rate(a)} for a in (100, 180, 181, 225, 270, 271, 318, 365, 366, 400)],
        "clean_money": [{"args": [v], "want": headers.clean_money(v)} for v in
                        ["US$1,234.56", "$1,234.56", "1.234,56", "(12.34)", "12,5", "1,234", "n/a", "--", "", "abc", "0.0412", "-3"]],
    }
    preamble = ("Inventory report\nGenerated for: a, b, c\n\n" + text)
    cases["preamble"] = {"text": preamble, "headers": list(readers.read_table(preamble.encode()).columns)}
    cases["constants"] = {"bucket_mid_age": econ.BUCKET_MID_AGE, "default_volume": fees.DEFAULT_ITEM_VOLUME_CUFT,
                          "effective": fees.EFFECTIVE,
                          "low_inventory_fee": fees.LOW_INVENTORY_FEE_PER_UNIT,
                          "low_inventory_assumed_tier": fees.LOW_INVENTORY_ASSUMED_TIER,
                          "low_inventory_min_units_t7": fees.LOW_INVENTORY_MIN_UNITS_T7,
                          "lilf_unmodelled": econ.LILF_UNMODELLED,
                          "synonyms": {"short_term_dos": econ.SHORT_TERM_DOS, "long_term_dos": econ.LONG_TERM_DOS,
                                       "lilf_exempt": econ.LILF_EXEMPT, "product_group": econ.PRODUCT_GROUP,
                                       "product_size_tier": econ.SIZE_TIER, "item_weight": econ.WEIGHT,
                                       "unit_of_weight": econ.WEIGHT_UNIT}}
    OUT.write_text(json.dumps(cases, indent=1, default=str) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} SKUs; " +
          ", ".join(f"{k} {v['aged_surcharge_month']}/{v['low_inventory_fee_month']}" for k, v in cases["priced_amazon"].items()))


if __name__ == "__main__":
    main()
