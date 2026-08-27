"""The briefing pipeline: turns a run's real numbers into a read-and-record
narration script, so a personalized 4–6 minute Loom costs the founder one
take and zero preparation.

Structure follows the retention research: hook with the client's name and
the single biggest dollar outcome inside 15 seconds, three numbers, one
"why" story, the actions waiting below the video, ledger close.
"""

import re


def parse_loom_id(url_or_id: str) -> str | None:
    """Accepts a bare Loom id or any loom.com share/embed URL."""
    v = url_or_id.strip()
    m = re.search(r"loom\.com/(?:share|embed)/([0-9a-f]{16,64})", v)
    if m:
        return m.group(1)
    if re.fullmatch(r"[0-9a-f]{16,64}", v):
        return v
    return None


def period_deltas(margins: list[dict]) -> dict | None:
    """Latest vs prior period across the whole catalog: profit, revenue,
    blended margin pct — the delta strip and the script's three numbers."""
    periods = sorted({m["period_start"] for m in margins})
    if not periods:
        return None

    def totals(p):
        rows = [m for m in margins if m["period_start"] == p]
        rev = sum(float(m["revenue"] or 0) for m in rows)
        net = sum(float(m["net_margin"] or 0) for m in rows)
        return {"revenue": rev, "net": net, "pct": (net / rev if rev > 0 else None)}

    latest = totals(periods[-1])
    prior = totals(periods[-2]) if len(periods) >= 2 else None
    return {
        "period": periods[-1],
        "latest": latest,
        "prior": prior,
        "net_delta": latest["net"] - prior["net"] if prior else None,
        "revenue_delta": latest["revenue"] - prior["revenue"] if prior else None,
    }


def _money(v: float) -> str:
    return f"${abs(v):,.0f}"


def _signed(v: float) -> str:
    return ("up " if v >= 0 else "down ") + _money(v)


def top_story(directives: list[dict], alerts: list[dict], elasticity: list[dict]) -> str:
    """One 'why' story per month — the single most consequential finding."""
    critical = [a for a in alerts if a.get("severity") == "critical"]
    if critical:
        return f"The one thing to understand this month: {critical[0]['message']}"
    money_directives = [d for d in directives if d.get("expected_impact_usd")]
    if money_directives:
        d = max(money_directives, key=lambda x: float(x["expected_impact_usd"]))
        return (f"The biggest opportunity on the table: {d['action_text']} "
                f"Expected impact ≈ {_money(float(d['expected_impact_usd']))}.")
    testable = [e for e in elasticity if e.get("status") == "ok"
                and e.get("elasticity") is not None and -1 < float(e["elasticity"]) < 0]
    if testable:
        e = testable[0]
        return (f"The finding worth teaching this month: {e['item_id']} is price-insensitive "
                f"(ε = {float(e['elasticity']):.2f}) — a careful increase converts almost "
                f"directly into margin, and we can test it safely.")
    return "This month is a clean bill of health — walk the numbers and bank the ledger."


def build_memo(company: str, first_name: str, deltas: dict | None,
               directives: list[dict], alerts: list[dict], elasticity: list[dict],
               ledger_measured: float, ledger_count: int, issue_number: int) -> str:
    """The written letter — the Marks-memo tradition. Same facts as the
    narration script, formatted as prose the founder edits, not reads."""
    name = first_name or "there"
    issued = [d for d in directives if d.get("status") == "issued"]

    paragraphs = [f"Issue No. {issue_number:03d}", "", f"Dear {name},", ""]

    if deltas and deltas["net_delta"] is not None:
        d = deltas
        direction = "up" if d["net_delta"] >= 0 else "down"
        paragraphs.append(
            f"Your catalog earned {_money(d['latest']['net'])} of true net profit last period — "
            f"{direction} {_money(d['net_delta'])} from the period before, on "
            f"{_money(d['latest']['revenue'])} of revenue"
            + (f" ({d['latest']['pct']:.1%} blended net margin)." if d["latest"]["pct"] is not None else ".")
        )
    elif deltas:
        paragraphs.append(
            f"This is your first full read: {_money(deltas['latest']['net'])} of true net profit "
            f"last period after every Amazon fee, your landed costs, and advertising — the baseline "
            f"every future issue measures against."
        )
    else:
        paragraphs.append("Your first models have run; the numbers below are your baseline.")

    paragraphs += ["", top_story(directives, alerts, elasticity), ""]

    if issued:
        paragraphs.append(
            f"There {'is one decision' if len(issued) == 1 else f'are {len(issued)} decisions'} "
            f"on your desk below — each states the exact action, the expected dollars, and how "
            f"we'll measure it. Approve or decline; nothing moves without you."
        )
    else:
        paragraphs.append("Nothing needs your decision this period — the watch continues either way.")

    paragraphs += [
        "",
        f"The record to date: {_money(ledger_measured)} of measured impact across "
        f"{ledger_count} directives. Every claim we make ends up on that ledger, "
        f"in our favor or against us.",
        "",
        "— Hubricon",
    ]
    return "\n".join(paragraphs)


def build_script(company: str, first_name: str, deltas: dict | None,
                 directives: list[dict], alerts: list[dict], elasticity: list[dict],
                 ledger_measured: float, ledger_count: int) -> str:
    name = first_name or company or "there"
    issued = [d for d in directives if d.get("status") == "issued"]

    if deltas and deltas["net_delta"] is not None:
        hook = (f"{name} — your net profit is {_signed(deltas['net_delta'])} versus the "
                f"period before. Here's exactly where that came from, in four minutes.")
    elif deltas:
        hook = (f"{name} — first full read of your catalog: {_money(deltas['latest']['net'])} "
                f"of true net profit last period, after every fee, your costs, and ads. "
                f"Here's what the models found.")
    else:
        hook = f"{name} — your numbers are in. Here's what the models found, in four minutes."

    lines = [
        f"# Briefing script — {company}",
        "",
        "Recording notes: portal on screen, their name and headline visible in frame 1.",
        "One take, no polish, 4–6 minutes. Speed matters more than perfection.",
        "",
        "## Hook (0:00–0:20)",
        hook,
        "",
        "## The three numbers (0:20–1:30)",
    ]
    if deltas:
        d = deltas
        lines.append(f"- Net profit last period: {_money(d['latest']['net'])}"
                     + (f" ({_signed(d['net_delta'])})" if d["net_delta"] is not None else ""))
        lines.append(f"- Revenue: {_money(d['latest']['revenue'])}"
                     + (f" ({_signed(d['revenue_delta'])})" if d["revenue_delta"] is not None else ""))
        if d["latest"]["pct"] is not None:
            lines.append(f"- Blended net margin: {d['latest']['pct']:.1%}")
    else:
        lines.append("- (No margin periods yet — lead with the audit's headline findings.)")
    lines += [
        f"- Measured impact to date on the Ledger: {_money(ledger_measured)} across {ledger_count} directives",
        "",
        "## The why — teach ONE thing (1:30–3:30)",
        top_story(directives, alerts, elasticity),
        "",
        "## Actions waiting below this video (3:30–5:00)",
    ]
    if issued:
        for d in issued:
            expected = (f" — expected {_money(float(d['expected_impact_usd']))}"
                        if d.get("expected_impact_usd") else "")
            lines.append(f"- [{d['module'].upper()}] {d['action_text']}{expected}")
        lines.append("")
        lines.append('Say it explicitly: "these are waiting for your approve or decline, right below this video."')
    else:
        lines.append("- No directives awaiting review — say so, and preview what's being watched.")
    lines += [
        "",
        "## Close (last 20s)",
        f"Ledger to date: {_money(ledger_measured)} of measured impact. One sentence on "
        f"what's being tested or watched next period. Stop recording.",
        "",
    ]
    return "\n".join(lines)
