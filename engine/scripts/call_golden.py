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
                       "low_inventory_fee_month": r.get("low_inventory_fee_month")} for r in out["rows"]}


def main() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    no_ais = df[[c for c in df.columns if not c.startswith("estimated-ais")]].to_csv(index=False)

    rows = parse(text)
    rows_schedule = parse(no_ais)
    cases = {
        "fixture": text,
        "fixture_no_ais": no_ais,
        "parsed": [{k: r.get(k) for k in FIELDS} for r in rows],
        "priced_amazon": priced(rows),
        "priced_schedule": priced(rows_schedule),
        "low_inventory_rate": [{"args": [d, t], "want": fees.low_inventory_fee(d, t)}
                               for t in ("standard", "oversize") for d in (0, 5, 13.9, 14, 20.9, 21, 27.9, 28, 40)],
        "aged_rate": [{"args": [a], "want": fees.aged_surcharge_rate(a)} for a in (100, 180, 181, 225, 270, 271, 318, 365, 366, 400)],
        "clean_money": [{"args": [v], "want": headers.clean_money(v)} for v in
                        ["US$1,234.56", "$1,234.56", "1.234,56", "(12.34)", "12,5", "1,234", "n/a", "--", "", "abc", "0.0412", "-3"]],
    }
    preamble = ("Inventory report\nGenerated for: a, b, c\n\n" + text)
    cases["preamble"] = {"text": preamble, "headers": list(readers.read_table(preamble.encode()).columns)}
    cases["constants"] = {"bucket_mid_age": econ.BUCKET_MID_AGE, "default_volume": fees.DEFAULT_ITEM_VOLUME_CUFT,
                          "effective": fees.EFFECTIVE}
    OUT.write_text(json.dumps(cases, indent=1, default=str) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} SKUs; " +
          ", ".join(f"{k} {v['aged_surcharge_month']}/{v['low_inventory_fee_month']}" for k, v in cases["priced_amazon"].items()))


if __name__ == "__main__":
    main()
