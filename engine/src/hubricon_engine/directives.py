"""Drafts Decision Ledger directives from a run's results.

Doctrine: the client's effort is zero. A directive is a pure financial
instruction — an exact action, an exact number, the expected dollars, and
the promise that the Ledger measures what actually happened. The math
stays on our side.

Cannibalization note: true organic-vs-paid inference needs organic-rank
data we don't collect yet (the Brand Analytics "Search Query Performance"
report, or SP-API, unlocks the full posterior later). V1 flags the
highest-probability case computable today — paid spend on the client's own
branded search terms — using the documented 25–60% incrementality range,
framed as a tracked test the Ledger then measures.
"""

from datetime import date, timedelta

from . import channels
from .models.pricing_engine import price_move

STOCKOUT_ALERT = 0.25
MEASUREMENT_HORIZON_DAYS = 30
BRANDED_SPEND_MIN = 25.0
INCREMENTALITY_MID = 0.4       # midpoint of the 25–60% industry range
GENERIC_NAME_WORDS = {"inc", "llc", "ltd", "the", "and", "co", "company"}
RECOVERY_MIN_VALUE = 50.0      # below this, filing costs more attention than it returns
ANOMALY_MIN_IMPACT = 100.0     # per period
LIQUIDATION_MIN_GAIN = 100.0
ANOMALY_LABELS = {
    "fee_per_unit": "total Amazon fees per unit", "fba_fee_per_unit": "FBA fulfillment fee per unit",
    "referral_rate": "referral fee rate", "storage_fee": "storage fee",
    "sessions": "traffic", "unit_session_pct": "conversion", "buy_box_pct": "Buy Box share", "spend": "daily spend",
}


def _labels(channel: str | None) -> dict:
    """Metric labels with the platform named; the FBA, referral and Buy Box
    metrics only ever come from Amazon data, so those stand."""
    return {**ANOMALY_LABELS, "fee_per_unit": f"total {channels.fee_label(channel)} per unit"}


def _money(v: float) -> str:
    return f"${abs(v):,.0f}"


def _latest_margins_by_sku(margins: list[dict]) -> dict[str, dict]:
    if not margins:
        return {}
    latest = max(m["period_start"] for m in margins)
    return {m["sku"]: m for m in margins if m["period_start"] == latest}


def resolve_brand_terms(client: dict) -> list[str]:
    """Explicit clients.brand_terms wins; else significant company_name words."""
    raw = (client.get("brand_terms") or "").strip()
    if raw:
        return [t.strip().lower() for t in raw.split(",") if t.strip()]
    name = (client.get("company_name") or "").lower()
    return [w for w in name.split() if len(w) >= 3 and w not in GENERIC_NAME_WORDS]


def branded_spend(search_terms: list[dict], brand_terms: list[str]) -> tuple[float, int]:
    """Paid spend on the client's own brand in the latest export window.
    Zero-sale terms are excluded — those are already covered by the bleed
    directive, and double-counting dollars would be dishonest."""
    if not search_terms or not brand_terms:
        return 0.0, 0
    latest_end = max(r["period_end"] for r in search_terms)
    total, n = 0.0, 0
    for r in search_terms:
        if r["period_end"] != latest_end or not (r["sales_7d"] or 0):
            continue
        term = (r["search_term"] or "").lower()
        if any(b in term for b in brand_terms):
            total += float(r["spend"] or 0)
            n += 1
    return total, n


def _inventory_directive(r: dict, margin_row: dict | None, today: date, econ_row: dict | None = None,
                         channel: str | None = "amazon") -> dict:
    p = float(r["stockout_probability"] or 0)
    rate = float(r["daily_velocity_mean"] or 0)
    position = int(r.get("on_hand_units") or 0) + int(r.get("inbound_units") or 0)
    days_until = max(0, int((position - int(r["reorder_point"] or 0)) / rate)) if rate > 0 else 0
    by = today + timedelta(days=days_until)
    by_text = by.strftime("%a %b %d").replace(" 0", " ")

    unit_cost = None
    if margin_row and margin_row.get("cogs") is not None and float(margin_row.get("units") or 0) > 0:
        unit_cost = float(margin_row["cogs"]) / float(margin_row["units"])

    if econ_row and econ_row.get("order_qty_econ") and econ_row.get("wire_econ") is not None:
        # the newsvendor sized it: the service level is the one the margin justifies
        q = float(econ_row["critical_fractile"])
        text = (
            f"Wire {_money(float(econ_row['wire_econ']))} to your supplier by {by_text} — "
            f"{int(econ_row['order_qty_econ'])} units of {r['sku']}. Sized to a {q:.0%} service level, "
            f"the level your margin justifies (C_u ÷ (C_u + C_o), storage and the season priced in); "
            f"lead time {r['lead_time_days']}d, current stockout risk {p:.0%}."
        )
    elif unit_cost:
        wire = float(r["reorder_qty"]) * unit_cost
        cliff = " and clears Amazon's low-inventory-fee window" if channels.has_fee_cliffs(channel) else ""
        text = (
            f"Wire {_money(wire)} to your supplier by {by_text} — {r['reorder_qty']} units of "
            f"{r['sku']}. That keeps stockout risk under 5%{cliff} "
            f"(lead time {r['lead_time_days']}d, current risk {p:.0%})."
        )
    else:
        text = (
            f"Order {r['reorder_qty']} units of {r['sku']} by {by_text} — {p:.0%} stockout risk "
            f"without it (lead time {r['lead_time_days']}d). Upload unit costs and the next "
            f"directive states the exact PO amount to wire."
        )
    return {
        "module": "inventory",
        "score": p * 100,
        "expected_impact_usd": None,  # avoided-stockout value isn't honestly computable
        "action_text": text,
    }


def _pricing_directive(fit: dict, margin_row: dict) -> dict | None:
    move = price_move(margin_row, fit)
    sku = fit["item_id"]
    if move:
        step = move["p_new"] - move["p0"]
        dest = f"; optimum ${move['destination']:.2f}" if move["destination"] else ""
        rng = ""
        if move["delta_range"]:
            lo, hi = move["delta_range"]
            rng = (f" (95% range {'+' if lo >= 0 else '−'}{_money(lo)} to "
                   f"{'+' if hi >= 0 else '−'}{_money(hi)})")
        sign = "+" if move["expected_delta"] >= 0 else "−"
        return {
            "module": "pricing",
            "score": 20 + abs(move["expected_delta"]) / 100,
            "expected_impact_usd": move["expected_delta"],
            "action_text": (
                f"Move {sku} ${move['p0']:.2f} → ${move['p_new']:.2f} "
                f"({'+' if step >= 0 else '−'}${abs(step):.2f}{dest}). "
                f"Expected {sign}{_money(move['expected_delta'])}/period{rng}. "
                f"Run as a tracked test — Buy Box watched daily."
            ),
        }
    # inelastic without landed cost: bounded test, honest about what's missing
    eps = float(fit["elasticity"]) if fit.get("elasticity") is not None else None
    if eps is not None and -1 < eps < 0:
        return {
            "module": "pricing",
            "score": 20 + 10 * (1 + eps),
            "expected_impact_usd": None,
            "action_text": (
                f"Price-test {sku} +3%: demand is price-insensitive (ε = {eps:.2f}), so volume "
                f"loss should be smaller than the margin gain. Upload unit costs and the next "
                f"directive states the exact optimum. Buy Box watched daily."
            ),
        }
    return None


def _recovery_directive(recovery: dict | None) -> dict | None:
    if not recovery or recovery.get("status") != "ok":
        return None
    live = [c for c in recovery.get("claims", []) if c["status"] in ("open", "expiring")]
    value = sum(float(c.get("value") or 0) for c in live)
    ev = sum(float(c.get("expected_value") or 0) for c in live)
    if not live or value < RECOVERY_MIN_VALUE:
        return None
    expiring = [c for c in live if c["status"] == "expiring"]
    closes = ""
    if expiring:
        soonest = min(c["deadline"] for c in expiring)
        closes = f" {len(expiring)} of them close by {date.fromisoformat(soonest).strftime('%b %d').replace(' 0', ' ')}."
    return {
        "module": "recovery",
        "score": 60 + ev / 100,
        "expected_impact_usd": round(ev, 2),
        "action_text": (
            f"Authorize us to file {len(live)} reimbursement claim{'s' if len(live) != 1 else ''} with Amazon — "
            f"{_money(value)} at face value, {_money(ev)} expected after approval odds.{closes} "
            f"We file through your account; the ledger records what Amazon actually pays."
        ),
    }


def _liquidation_directives(inv_econ: dict | None, channel: str | None = "amazon") -> list[dict]:
    out = []
    program = "Amazon's liquidation program" if channels.has_fee_cliffs(channel) else "a clearance sale"
    for r in (inv_econ or {}).get("rows", []):
        if r.get("decision") != "liquidate":
            continue
        gain = float(r.get("liquidate_value") or 0) - float(r.get("hold_npv") or 0)
        if gain < LIQUIDATION_MIN_GAIN:
            continue
        aged = float(r.get("aged_surcharge_month") or 0)
        out.append({
            "module": "inventory",
            "score": 30 + gain / 100,
            "expected_impact_usd": round(gain, 2),
            "action_text": (
                f"Liquidate {int(r['excess_units'])} excess units of {r['sku']}: {program} returns about "
                f"{_money(float(r['liquidate_value']))} now, against {_money(float(r['hold_npv']))} from holding and "
                f"selling them down with storage, the aged surcharge and capital priced in"
                + (f" — the surcharge alone is {_money(aged)}/month." if aged else ".")
            ),
        })
    return out


def _anomaly_directives(anomaly_rows: list[dict] | None, channel: str | None = "amazon") -> list[dict]:
    """One instruction per (item, metric) for adverse shifts worth ≥ $100/period."""
    labels, plat = _labels(channel), channels.label(channel)
    best: dict[tuple, dict] = {}
    for r in anomaly_rows or []:
        if not r.get("flagged") or (r.get("dollar_impact") or 0) < ANOMALY_MIN_IMPACT:
            continue
        adverse_up = r["metric"] in ("fee_per_unit", "fba_fee_per_unit", "referral_rate", "storage_fee", "spend", "monthly_total")
        if (adverse_up and r.get("direction") != "up") or (not adverse_up and r.get("direction") != "down"):
            continue
        key = (r.get("scope"), r.get("item_id"), r.get("metric"))
        if key not in best or (r.get("detector") == "changepoint" and best[key].get("detector") != "changepoint"):
            best[key] = r
    out = []
    for r in best.values():
        since = date.fromisoformat(str(r["since"])[:10]).strftime("%b %Y") if r.get("since") else "recently"
        impact = float(r["dollar_impact"])
        b, c = float(r.get("baseline") or 0), float(r.get("current") or 0)
        m = r["metric"]
        if m in ("fee_per_unit", "fba_fee_per_unit"):
            fix = ("Verify the listing's weight and dimensions in Seller Central and request a re-measure; "
                   "overcharged fees are reimbursable." if channels.has_fee_cliffs(channel) else
                   "Check the order mix: smaller orders each carry the fixed processing fee, and a refund "
                   "returns none of it. A minimum order value or a bundle moves it back.")
            out.append({"module": "margin", "score": 25 + impact / 100, "expected_impact_usd": round(impact, 2),
                        "action_text": (
                            f"{plat}'s {labels[m]} on {r['item_id']} rose from ${b:.2f} to ${c:.2f} since {since} "
                            f"— {_money(impact)}/period at last period's volume. {fix}")})
        elif m == "referral_rate":
            out.append({"module": "margin", "score": 25 + impact / 100, "expected_impact_usd": round(impact, 2),
                        "action_text": (
                            f"The referral fee rate on {r['item_id']} moved from {b:.1%} to {c:.1%} since {since} — "
                            f"{_money(impact)}/period. Check the listing's category assignment; a wrong category "
                            f"bills a higher rate and the difference is reimbursable.")})
        elif m == "monthly_total":
            out.append({"module": "margin", "score": 20 + impact / 100, "expected_impact_usd": round(impact, 2),
                        "action_text": (
                            f"{plat}'s {r['item_id']} charges rose from {_money(b)} to {_money(c)} per month since "
                            f"{since}. We are tracing the lines to the SKUs behind the step.")})
        elif m == "unit_session_pct":
            out.append({"module": "general", "score": 15 + impact / 100, "expected_impact_usd": None,
                        "action_text": (
                            f"Conversion on {r['item_id']} fell from {b:.1f}% to {c:.1f}% since {since} — "
                            f"{_money(impact)}/period at current traffic. We check the Buy Box, price against "
                            f"competitors, and recent listing or review changes before touching price.")})
        elif m == "sessions":
            out.append({"module": "general", "score": 15 + impact / 100, "expected_impact_usd": None,
                        "action_text": (
                            f"Traffic on {r['item_id']} fell from {b:,.0f} to {c:,.0f} sessions a period since {since} — "
                            f"{_money(impact)}/period at current conversion. Ranking, ads, or a suppressed listing; "
                            f"we find which.")})
        elif m == "buy_box_pct":
            out.append({"module": "pricing", "score": 40 + impact / 100, "expected_impact_usd": None,
                        "action_text": (
                            f"Buy Box share on {r['item_id']} fell from {b:.0f}% to {c:.0f}% since {since}. "
                            f"Amazon is suppressing the Featured Offer — price, competitor, or account health; "
                            f"we step the price back if that is the cause.")})
        elif m == "spend":
            out.append({"module": "advertising", "score": 15 + impact / 100, "expected_impact_usd": None,
                        "action_text": (
                            f"Daily spend on “{r['item_id']}” stepped up from {_money(b)} to {_money(c)} since "
                            f"{since} — about {_money(impact)} per 30 days. Confirm it was intended; we hold it "
                            f"at the marginal break-even otherwise.")})
    return out


def draft_directives(inventory, ads, elasticity, margins,
                     search_terms=None, brand_terms=None,
                     recovery=None, inv_econ=None, anomaly_rows=None,
                     channel: str | None = "amazon") -> list[dict]:
    """`channel` names the platform the run was computed on (channels.py):
    it changes the words, never the arithmetic."""
    today = date.today()
    latest_by_sku = _latest_margins_by_sku(margins)
    econ_by_sku = {r["sku"]: r for r in (inv_econ or {}).get("rows", [])}
    drafts = []

    rec = _recovery_directive(recovery)
    if rec:
        drafts.append(rec)
    drafts += _liquidation_directives(inv_econ, channel)
    drafts += _anomaly_directives(anomaly_rows, channel)

    for r in inventory:
        if float(r["stockout_probability"] or 0) >= STOCKOUT_ALERT:
            drafts.append(_inventory_directive(r, latest_by_sku.get(r["sku"]), today, econ_by_sku.get(r["sku"]), channel))

    bleed_total = sum(t["spend"] or 0 for r in ads for t in (r["bleed_terms"] or []))
    if bleed_total > 0:
        n = sum(len(r["bleed_terms"] or []) for r in ads)
        drafts.append({
            "module": "advertising",
            "score": bleed_total,
            "expected_impact_usd": round(bleed_total, 2),
            "action_text": (
                f"Negative-match {n} search terms that spent with zero attributed sales — "
                f"{_money(bleed_total)} of pure bleed in the export window. "
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

    spend, n_terms = branded_spend(search_terms or [], brand_terms or [])
    if spend >= BRANDED_SPEND_MIN:
        saving = round(spend * INCREMENTALITY_MID, 2)
        drafts.append({
            "module": "advertising",
            "score": spend,
            "expected_impact_usd": saving,
            "action_text": (
                f"You're paying for your own brand: {_money(spend)} across {n_terms} branded "
                f"search terms last window. Industry incrementality studies put 25–60% of that "
                f"as sales you'd capture organically anyway. Pause exact-match branded targeting "
                f"as a tracked test — expected savings ≈ {_money(saving)}/period, and the Ledger "
                f"measures the truth."
            ),
        })

    for fit in elasticity:
        if fit.get("status") != "ok" or fit.get("level") != "sku":
            continue
        margin_row = latest_by_sku.get(fit["item_id"])
        if not margin_row:
            continue
        d = _pricing_directive(fit, margin_row)
        if d:
            drafts.append(d)

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
                        f"{m['sku']} sold at a loss last period (net -{_money(loss)} after fees, "
                        f"COGS and ads) — reprice, cut its ad allocation, or plan its exit."
                    ),
                })

    drafts.sort(key=lambda d: d["score"], reverse=True)
    return drafts
