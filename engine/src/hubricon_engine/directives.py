"""Drafts Decision Ledger directives from a run's results.

Each directive carries the action in plain language plus an expected dollar
impact where one is honestly computable — otherwise the field stays empty
rather than inventing a number. The operator reviews drafts, edits, and
issues them; clients see only issued directives in the portal.
"""

STOCKOUT_ALERT = 0.25
PRICE_TEST_STEP = 0.03  # the standard "test a 3% increase" directive
MEASUREMENT_HORIZON_DAYS = 30


def _latest_margin_revenue(margins: list[dict]) -> dict[str, float]:
    """sku -> latest-period revenue, for sizing pricing directives."""
    if not margins:
        return {}
    latest = max(m["period_start"] for m in margins)
    return {
        m["sku"]: float(m["revenue"] or 0)
        for m in margins
        if m["period_start"] == latest
    }


def draft_directives(inventory, ads, elasticity, margins) -> list[dict]:
    drafts = []

    for r in inventory:
        p = float(r["stockout_probability"] or 0)
        if p >= STOCKOUT_ALERT:
            drafts.append({
                "module": "inventory",
                "score": p * 100,
                "expected_impact_usd": None,  # avoided-stockout value isn't honestly computable yet
                "action_text": (
                    f"Reorder {r['sku']} now — {p:.0%} chance of stocking out before a "
                    f"replenishment lands. Suggested order: {r['reorder_qty']} units "
                    f"(reorder point {r['reorder_point']}, lead time {r['lead_time_days']}d)."
                ),
            })

    bleed_total = sum(t["spend"] or 0 for r in ads for t in (r["bleed_terms"] or []))
    if bleed_total > 0:
        n = sum(len(r["bleed_terms"] or []) for r in ads)
        drafts.append({
            "module": "advertising",
            "score": bleed_total,
            "expected_impact_usd": round(bleed_total, 2),
            "action_text": (
                f"Negative-match {n} search terms that spent with zero attributed sales — "
                f"${bleed_total:,.0f} of pure bleed in the export window. "
                f"Term list attached to this cycle's report."
            ),
        })

    for r in ads:
        if r["status"] == "ok" and r["current_spend"] and r["breakeven_spend"] \
                and float(r["current_spend"]) > float(r["breakeven_spend"]):
            excess = float(r["current_spend"]) - float(r["breakeven_spend"])
            drafts.append({
                "module": "advertising",
                "score": excess,
                "expected_impact_usd": round(excess * MEASUREMENT_HORIZON_DAYS, 2),
                "action_text": (
                    f"Trim “{r['campaign_name']}” toward its marginal break-even: "
                    f"${float(r['breakeven_spend']):,.0f} vs ${float(r['current_spend']):,.0f} today. "
                    f"The last dollars in are buying less than a dollar back."
                ),
            })

    revenue_by_sku = _latest_margin_revenue(margins)
    for r in elasticity:
        if r["status"] == "ok" and r["elasticity"] is not None and -1 < float(r["elasticity"]) < 0:
            revenue = revenue_by_sku.get(r["item_id"]) if r["level"] == "sku" else None
            expected = round(PRICE_TEST_STEP * revenue, 2) if revenue else None
            drafts.append({
                "module": "pricing",
                "score": 20 + 10 * (1 + float(r["elasticity"])) + (expected or 0) / 1000,
                "expected_impact_usd": expected,
                "action_text": (
                    f"Price-test {r['item_id']} +{PRICE_TEST_STEP:.0%}: demand is price-insensitive "
                    f"(ε = {float(r['elasticity']):.2f}), so volume loss should be smaller than "
                    f"the margin gain. Run as a tracked test with Buy Box share monitored."
                ),
            })

    if margins:
        latest = max(m["period_start"] for m in margins)
        for m in margins:
            if m["period_start"] == latest and m["net_margin"] is not None and float(m["net_margin"]) < 0:
                loss = abs(float(m["net_margin"]))
                drafts.append({
                    "module": "margin",
                    "score": loss,
                    "expected_impact_usd": round(loss, 2),
                    "action_text": (
                        f"{m['sku']} sold at a loss last period (net -${loss:,.0f} after fees, "
                        f"COGS and ads) — reprice, cut its ad allocation, or plan its exit."
                    ),
                })

    drafts.sort(key=lambda d: d["score"], reverse=True)
    return drafts
