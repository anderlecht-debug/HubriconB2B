"""The price-testing program: designed price moves, tracked as first-class
records, with Buy Box share watched for Amazon's suppression response.

The wedge in practice: instead of a seller raising prices blind (67% did in
2024; 60% of those got poorer), each move is a scheduled test with a
baseline, a predicted outcome from the elasticity model when one exists,
and the Buy Box monitored so suppression is caught in days, not quarters.
Completed tests create deliberate price variation, which feeds back into
the next elasticity fit — the moat compounding mechanically.
"""

BUYBOX_DROP_WARNING = 10.0  # percentage points lost vs. baseline that triggers the alarm
DEFAULT_TEST_DAYS = 14


def resolve_baseline(econ_rows: list[dict], sku: str) -> float | None:
    """Latest observed price for the SKU from SKU Economics uploads."""
    rows = [r for r in econ_rows if r["sku"] == sku]
    if not rows:
        return None
    latest = max(rows, key=lambda r: r["period_start"])
    if latest.get("avg_sales_price"):
        return float(latest["avg_sales_price"])
    if latest.get("units_sold") and latest.get("sales"):
        return float(latest["sales"]) / float(latest["units_sold"])
    return None


def predict_units_change(elasticity: float, baseline: float, test_price: float) -> float:
    """Expected % change in units for the proposed move, from the fitted
    constant-elasticity curve: (p1/p0)^e - 1."""
    return (test_price / baseline) ** elasticity - 1.0


def buybox_warning(before: float | None, during: float | None) -> str | None:
    if before is None or during is None:
        return None
    drop = float(before) - float(during)
    if drop >= BUYBOX_DROP_WARNING:
        return (
            f"Buy Box share dropped {drop:.0f} points ({before:.0f}% → {during:.0f}%) — "
            f"Amazon is suppressing the Featured Offer at this price. Consider aborting "
            f"and stepping the increase in smaller moves."
        )
    return None


def latest_elasticity(elasticity_rows: list[dict], sku: str) -> dict | None:
    ok = [r for r in elasticity_rows if r["level"] == "sku" and r["item_id"] == sku and r["status"] == "ok"]
    return ok[0] if ok else None
