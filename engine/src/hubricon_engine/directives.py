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

from .models.pricing_engine import price_move

STOCKOUT_ALERT = 0.25
MEASUREMENT_HORIZON_DAYS = 30
BRANDED_SPEND_MIN = 25.0
INCREMENTALITY_MID = 0.4       # midpoint of the 25–60% industry range
GENERIC_NAME_WORDS = {"inc", "llc", "ltd", "the", "and", "co", "company"}


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


def _inventory_directive(r: dict, margin_row: dict | None, today: date) -> dict:
    p = float(r["stockout_probability"] or 0)
    rate = float(r["daily_velocity_mean"] or 0)
    position = int(r.get("on_hand_units") or 0) + int(r.get("inbound_units") or 0)
    days_until = max(0, int((position - int(r["reorder_point"] or 0)) / rate)) if rate > 0 else 0
    by = today + timedelta(days=days_until)
    by_text = by.strftime("%a %b %d").replace(" 0", " ")

    unit_cost = None
    if margin_row and margin_row.get("cogs") is not None and float(margin_row.get("units") or 0) > 0:
        unit_cost = float(margin_row["cogs"]) / float(margin_row["units"])

    if unit_cost:
        wire = float(r["reorder_qty"]) * unit_cost
        text = (
            f"Wire {_money(wire)} to your supplier by {by_text} — {r['reorder_qty']} units of "
            f"{r['sku']}. That keeps stockout risk under 5% and clears Amazon's "
            f"low-inventory-fee window (lead time {r['lead_time_days']}d, current risk {p:.0%})."
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


def draft_directives(inventory, ads, elasticity, margins,
                     search_terms=None, brand_terms=None) -> list[dict]:
    today = date.today()
    latest_by_sku = _latest_margins_by_sku(margins)
    drafts = []

    for r in inventory:
        if float(r["stockout_probability"] or 0) >= STOCKOUT_ALERT:
            drafts.append(_inventory_directive(r, latest_by_sku.get(r["sku"]), today))

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
