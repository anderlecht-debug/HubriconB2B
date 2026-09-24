"""The price-testing program: designed price moves, tracked as first-class
records, with Buy Box share watched for Amazon's suppression response.

The wedge in practice: instead of a seller raising prices blind (67% did in
2024; 60% of those got poorer), each move is a scheduled test with a
baseline, a predicted outcome from the elasticity model when one exists,
and the Buy Box monitored so suppression is caught in days, not quarters.
Completed tests create deliberate price variation, which feeds back into
the next elasticity fit.

That last clause used to end "— the moat compounding mechanically", and it was
not true. Measured 2026-09-12, two things stop it:

  * A test's price is chosen by the fit (pricing_engine.price_move solves the
    step against the fitted elasticity, its standard error and the SKU's
    margin), so the resulting price variation is not independent of the demand
    shocks that bias the fit. It is deliberate, which is not the same as
    exogenous, and only the second one identifies anything.
  * DEFAULT_TEST_DAYS = 14 inside a calendar month of sku_economics blends to a
    monthly average price with a coefficient of variation near 0.011, under
    elasticity.MIN_PRICE_CV = 0.02 — so a completed test can leave the SKU
    reporting `insufficient_price_variation` and carrying no elasticity at all.
    A test held for a whole period, or a daily price series read from
    settlement_transactions, is what would make the variation visible.

Both were fixable and, since 2026-09-23, both are fixed by the randomised design
in models/price_experiment.py: `hubricon pricetest <client> plan --sku X
--design randomized --start DATE`, then `analyze` once the six blocks have run.
The fixed-price test here remains for the manual, single-price case.
See engine/MATH_METHODS.md section 2.
"""

BUYBOX_DROP_WARNING = 10.0  # percentage points lost vs. baseline that triggers the alarm
DEFAULT_TEST_DAYS = 14
# The randomised design (models/price_experiment.py): six seven-day blocks. Both
# objections above are answered by it — the arm is drawn independently of the
# data, and the daily settlement series sees every block.
RANDOMISED_DAYS = 42


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
