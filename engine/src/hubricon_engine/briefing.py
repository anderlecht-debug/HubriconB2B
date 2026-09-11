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
    return "This month is a clean bill of health — walk the numbers and bank the Record."


def build_memo(company: str, first_name: str, deltas: dict | None,
               directives: list[dict], alerts: list[dict], elasticity: list[dict],
               ledger_measured: float, ledger_count: int, issue_number: int,
               channel: str | None = "amazon", ledger_found: float = 0.0,
               fees_billed: float = 0.0) -> str:
    """The written letter — the Marks-memo tradition. Same facts as the
    narration script, formatted as prose the founder edits, not reads.
    `channel` only names the platform's fee stack (channels.fee_label)."""
    name = first_name or "there"
    issued = [d for d in directives if d.get("status") == "issued"]

    paragraphs = [f"Profit Brief No. {issue_number:03d}", "", f"Dear {name},", ""]

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
            f"last period after every {'Amazon' if (channel or 'amazon') == 'amazon' else 'Shopify'} fee, your landed costs, and advertising — the baseline "
            f"every future issue measures against."
        )
    else:
        paragraphs.append("Your first models have run; the numbers below are your baseline.")

    paragraphs += ["", top_story(directives, alerts, elasticity), ""]

    if issued:
        paragraphs.append(
            f"There {'is one decision' if len(issued) == 1 else f'are {len(issued)} decisions'} "
            f"waiting for your yes below — each states the exact move, the expected dollars, and how "
            f"we'll measure it. Approve or decline; nothing moves without you."
        )
    else:
        paragraphs.append("Nothing needs your decision this period — the watch continues either way.")

    paragraphs += [
        "",
        f"Your Profit Record to date: {_money(ledger_measured)} proven across "
        f"{ledger_count} moves · {_money(ledger_found)} found and filed, not yet banked · "
        f"{_money(fees_billed)} billed. Every claim we make ends up on that Record, "
        f"in our favor or against us.",
        "",
        "— Hubricon",
    ]
    return "\n".join(paragraphs)


def build_beats(company: str, first_name: str, deltas: dict | None,
                directives: list[dict], alerts: list[dict], elasticity: list[dict],
                ledger_measured: float, ledger_count: int, ledger_found: float = 0.0,
                fees_billed: float = 0.0) -> list[dict]:
    """The briefing as an ordered list of beats.

    One structure, two renderers: `build_script` prints it as recording notes
    for the founder, and video.py speaks `speech` over a slide built from
    `heading`/`points`. Slide N and speech N therefore come from the same
    object and cannot drift apart — which they would within a month if the
    deck and the script were written separately.

    `speech` is what gets said aloud, so it carries no markdown, no stage
    directions and no bracketed asides."""
    name = first_name or company or "there"
    # Waiting for a decision means issued, exactly as the letter counts it
    # (build_memo). An approved move is past deciding: it is inside the standing
    # yes with the window closed, and is named as going live, not as waiting.
    issued = [d for d in directives if d.get("status") == "issued"]
    approved = [d for d in directives if d.get("status") == "approved" and not d.get("executed_at")]

    if deltas and deltas["net_delta"] is not None:
        hook = (f"{name} — your net profit is {_signed(deltas['net_delta'])} versus the "
                f"period before. Here's exactly where that came from.")
    elif deltas:
        hook = (f"{name} — first full read of your catalog: {_money(deltas['latest']['net'])} "
                f"of true net profit last period, after every fee, your costs, and ads. "
                f"Here's what the models found.")
    else:
        hook = f"{name} — your numbers are in. Here's what the models found."

    beats = [{"heading": "Hook", "at": "0:00–0:20", "speech": hook, "points": []}]

    numbers, spoken = [], []
    if deltas:
        d = deltas
        numbers.append(("Net profit last period", _money(d["latest"]["net"])
                        + (f" ({_signed(d['net_delta'])})" if d["net_delta"] is not None else "")))
        numbers.append(("Revenue", _money(d["latest"]["revenue"])
                        + (f" ({_signed(d['revenue_delta'])})" if d["revenue_delta"] is not None else "")))
        if d["latest"]["pct"] is not None:
            numbers.append(("Blended net margin", f"{d['latest']['pct']:.1%}"))
        spoken.append(f"Net profit last period was {_money(d['latest']['net'])}"
                      + (f", {_signed(d['net_delta'])} on the period before" if d["net_delta"] is not None else "")
                      + f", on {_money(d['latest']['revenue'])} of revenue")
        if d["latest"]["pct"] is not None:
            spoken.append(f"that is a blended net margin of {d['latest']['pct']:.1%}")
    numbers.append(("Proven on your Profit Record", f"{_money(ledger_measured)} across {ledger_count}"))
    numbers.append(("Found and filed, not yet banked", _money(ledger_found)))
    numbers.append(("Billed to date", _money(fees_billed)))
    spoken.append(f"and your Profit Record stands at {_money(ledger_measured)} proven across "
                  f"{ledger_count} move{'s' if ledger_count != 1 else ''}, {_money(ledger_found)} found "
                  f"and filed but not yet banked, against {_money(fees_billed)} billed")
    beats.append({"heading": "The three numbers", "at": "0:20–1:30",
                  "speech": ("Three numbers. " + ", ".join(spoken) + ".") if spoken else
                            "Your baseline numbers are on screen.",
                  "points": numbers})

    beats.append({"heading": "The why", "at": "1:30–3:30",
                  "speech": top_story(directives, alerts, elasticity), "points": []})

    if issued:
        actions = [(d["module"].upper(),
                    d["action_text"] + (f" — expected {_money(float(d['expected_impact_usd']))}"
                                        if d.get("expected_impact_usd") else ""))
                   for d in issued]
        speech = (f"There {'is one decision' if len(issued) == 1 else f'are {len(issued)} decisions'} "
                  f"waiting below this video. Each one states the action, the expected dollars, and how "
                  f"we'll measure it. Approve or decline — nothing moves without you.")
    else:
        actions = []
        speech = ("Nothing needs your decision this period. The watch continues either way, and I'll "
                  "come to you the moment something does.")
    if approved:
        actions.append(("GOING LIVE", f"{len(approved)} move(s) inside your standing yes, window closed — "
                                      f"going live this week"))
    beats.append({"heading": "Before it goes live", "at": "3:30–5:00", "speech": speech, "points": actions})

    beats.append({"heading": "The record", "at": "last 20s",
                  "speech": (f"Your Profit Record to date: {_money(ledger_measured)} proven across "
                             f"{ledger_count} move{'s' if ledger_count != 1 else ''}, {_money(ledger_found)} "
                             f"found and filed, not yet banked, {_money(fees_billed)} billed — in our "
                             f"favour and against us. That's the whole story this period."),
                  "points": []})
    return beats


def build_script(company: str, first_name: str, deltas: dict | None,
                 directives: list[dict], alerts: list[dict], elasticity: list[dict],
                 ledger_measured: float, ledger_count: int) -> str:
    """Recording notes, for when the founder wants their own voice on an issue.
    Rendered from the same beats the generated video speaks."""
    beats = build_beats(company, first_name, deltas, directives, alerts, elasticity,
                        ledger_measured, ledger_count)
    lines = [
        f"# Briefing script — {company}",
        "",
        "Recording notes: portal on screen, their name and headline visible in frame 1.",
        "One take, no polish, 4–6 minutes. Speed matters more than perfection.",
        "",
    ]
    for b in beats:
        lines += [f"## {b['heading']} ({b['at']})", b["speech"]]
        for point in b["points"]:
            lines.append(f"- {point[0]}: {point[1]}" if isinstance(point, tuple) else f"- {point}")
        lines.append("")
    return "\n".join(lines)
