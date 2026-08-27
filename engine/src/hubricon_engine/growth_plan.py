"""The Growth Plan: drafts the client's 90-day operating plan from a run.

The plan is the product's spine — targets are budget-vs-actual, the
initiatives are the carried roadmap, and every directive files into the
initiative it executes. The engine proposes; the founder edits and commits
it live on the kickoff call.

Honesty discipline: the profit target applies a 30% haircut to the total
identified opportunity — the plan promises less than the models found, and
the Ledger closes the gap in public.
"""

from datetime import date, timedelta

OPPORTUNITY_HAIRCUT = 0.7  # promise 70% of what the models identified

INITIATIVE_DEFS = {
    "pricing": (
        "Reprice to the measured optimum",
        "Move each SKU toward its profit-maximizing price in tracked, Buy-Box-watched steps.",
    ),
    "advertising": (
        "Cut wasted ad spend",
        "Eliminate zero-sale bleed, test pausing branded terms, trim campaigns past break-even.",
    ),
    "inventory": (
        "De-risk inventory",
        "No SKU above 25% stockout risk; purchase orders sized and wired on schedule.",
    ),
    "margin": (
        "Fix or exit losing SKUs",
        "Reprice, cut ad allocation, or plan the exit for every SKU selling at a loss.",
    ),
}
MODULE_ORDER = ["pricing", "advertising", "inventory", "margin"]


def next_quarter(today: date) -> tuple[str, date, date]:
    """The 90-day window starting now, labeled by the quarter it lands in."""
    q = (today.month - 1) // 3 + 1
    return f"Q{q} {today.year}", today, today + timedelta(days=90)


def latest_period_totals(margins: list[dict]) -> dict | None:
    periods = sorted({m["period_start"] for m in margins})
    if not periods:
        return None
    rows = [m for m in margins if m["period_start"] == periods[-1]]
    rev = sum(float(m["revenue"] or 0) for m in rows)
    net = sum(float(m["net_margin"] or 0) for m in rows)
    return {"net": round(net, 2), "revenue": round(rev, 2),
            "margin_pct": round(net / rev, 4) if rev > 0 else None}


def propose_plan(margins: list[dict], directives: list[dict],
                 today: date | None = None) -> dict | None:
    """Baseline + targets + clustered initiatives. None without margin data."""
    baseline = latest_period_totals(margins)
    if baseline is None:
        return None
    today = today or date.today()
    label, starts, ends = next_quarter(today)

    initiatives = []
    for module in MODULE_ORDER:
        steps = [d for d in directives if d.get("module") == module]
        if not steps:
            continue
        title, thesis = INITIATIVE_DEFS[module]
        expected = sum(float(d["expected_impact_usd"]) for d in steps
                       if d.get("expected_impact_usd") is not None)
        initiatives.append({
            "module": module,
            "title": title,
            "thesis": thesis,
            "expected_impact_usd": round(expected, 2) if expected else None,
            "steps": len(steps),
        })

    opportunity = sum(i["expected_impact_usd"] or 0 for i in initiatives)
    target_net = round(baseline["net"] + OPPORTUNITY_HAIRCUT * opportunity, 2)
    target_revenue = baseline["revenue"]  # hold revenue while margin is repaired
    target_margin = round(target_net / target_revenue, 4) if target_revenue > 0 else None

    return {
        "label": label,
        "starts_on": starts.isoformat(),
        "ends_on": ends.isoformat(),
        "baseline": baseline,
        "targets": {"net": target_net, "revenue": target_revenue, "margin_pct": target_margin},
        "opportunity": round(opportunity, 2),
        "initiatives": initiatives,
    }


def pace(current: float, baseline: float, target: float, elapsed_fraction: float) -> str:
    """on_pace when progress covers the elapsed share of the gap."""
    if target == baseline:
        return "on_pace"
    needed = baseline + (target - baseline) * max(0.0, min(1.0, elapsed_fraction))
    return "on_pace" if current >= needed else "behind"
