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


# What happens to a listed move, true for both mandates (issue.py): a standing
# one goes live when its veto window closes unless declined; an explicit one
# never moves without a yes.
# The window is not named here: 72 hours is only the default, and a stored mandate
# can set its own per module. The move's own email gives its closing time.
MANDATE_SENTENCE = ("Each move is listed before it goes live. Inside your standing mandate it goes live "
                    "when the window on its email closes, unless you say no; anything outside it waits "
                    "for your yes.")


def _proven(proven: dict | None, ledger_measured: float, ledger_count: int) -> dict:
    """The Record's one figure (value.proven_since_day_one). A caller that only
    has the old pair of numbers gets them read as what they are: measured so far."""
    if proven is not None:
        return proven
    from .value import MEASURED_LABEL
    return {"usd": float(ledger_measured or 0), "basis": "measured", "label": MEASURED_LABEL,
            "moves": int(ledger_count or 0)}


def _record_words(proven: dict, spoken: bool = False) -> str:
    """'$1,240 proven since day one across 2 moves', with the first-month aside
    when the figure is still the measured one. Spoken text carries no brackets."""
    from .value import proven_words
    words, aside = proven_words(proven)
    n = int(proven.get("moves") or 0)
    out = f"{_money(float(proven.get('usd') or 0))} {words}"
    if n:
        out += f" across {n} move{'s' if n != 1 else ''}"
    if aside:
        out += f", {aside}" if spoken else f" ({aside})"
    return out


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
               fees_billed: float = 0.0, proven: dict | None = None) -> str:
    """The written letter — the Marks-memo tradition. Same facts as the
    narration script, formatted as prose the founder edits, not reads.
    `channel` only names the platform's fee stack (channels.fee_label).
    `proven` is value.proven_since_day_one; without it the two old numbers are
    read as measured so far."""
    name = first_name or "there"
    proven = _proven(proven, ledger_measured, ledger_count)
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
            f"waiting below — each states the exact move, the expected dollars, and how we'll measure it. "
            f"{MANDATE_SENTENCE}"
        )
    else:
        paragraphs.append("Nothing needs your decision this period — the watch continues either way.")

    paragraphs += [
        "",
        f"Your Profit Record to date: {_record_words(proven)} · "
        f"{_money(ledger_found)} found and filed, not yet banked · "
        f"{_money(fees_billed)} billed. Every claim we make ends up on that Record, "
        f"in our favor or against us.",
        "",
        "— Hubricon",
    ]
    return "\n".join(paragraphs)


def build_beats(company: str, first_name: str, deltas: dict | None,
                directives: list[dict], alerts: list[dict], elasticity: list[dict],
                ledger_measured: float, ledger_count: int, ledger_found: float = 0.0,
                fees_billed: float = 0.0, proven: dict | None = None) -> list[dict]:
    """The briefing as an ordered list of beats.

    One structure, two renderers: `build_script` prints it as recording notes
    for the founder, and video.py speaks `speech` over a slide built from
    `heading`/`points`. Slide N and speech N therefore come from the same
    object and cannot drift apart — which they would within a month if the
    deck and the script were written separately.

    `speech` is what gets said aloud, so it carries no markdown, no stage
    directions and no bracketed asides."""
    name = first_name or company or "there"
    proven = _proven(proven, ledger_measured, ledger_count)
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
    moves = int(proven.get("moves") or 0)
    numbers.append((proven.get("label") or "Measured so far",
                    _money(float(proven.get("usd") or 0)) + (f" across {moves}" if moves else "")))
    numbers.append(("Found and filed, not yet banked", _money(ledger_found)))
    numbers.append(("Billed to date", _money(fees_billed)))
    spoken.append(f"and your Profit Record stands at {_record_words(proven, spoken=True)}, "
                  f"{_money(ledger_found)} found and filed but not yet banked, against "
                  f"{_money(fees_billed)} billed")
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
                  f"we'll measure it. {MANDATE_SENTENCE}")
    else:
        actions = []
        speech = ("Nothing needs your decision this period. The watch continues either way, and I'll "
                  "come to you the moment something does.")
    if approved:
        actions.append(("GOING LIVE", f"{len(approved)} move(s) inside your standing yes, window closed — "
                                      f"going live this week"))
    beats.append({"heading": "Before it goes live", "at": "3:30–5:00", "speech": speech, "points": actions})

    beats.append({"heading": "The record", "at": "last 20s",
                  "speech": (f"Your Profit Record to date: {_record_words(proven, spoken=True)}, "
                             f"{_money(ledger_found)} "
                             f"found and filed, not yet banked, {_money(fees_billed)} billed — in our "
                             f"favour and against us. That's the whole story this period."),
                  "points": []})
    return beats


def build_script(company: str, first_name: str, deltas: dict | None,
                 directives: list[dict], alerts: list[dict], elasticity: list[dict],
                 ledger_measured: float, ledger_count: int, proven: dict | None = None) -> str:
    """Recording notes, for when the founder wants their own voice on an issue.
    Rendered from the same beats the generated video speaks."""
    beats = build_beats(company, first_name, deltas, directives, alerts, elasticity,
                        ledger_measured, ledger_count, proven=proven)
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


# -- the Monday note ----------------------------------------------------------------------
#
# HUBRICON_SPEC.md, "Customer experience" 4: the human layer is a short weekly
# note in the brand voice, a doctor's follow-up: what was found, what is sealed
# and holding, what is being watched. Drafted by the system from the graded
# numbers and approved by the founder, never written from scratch. So every
# line below is a fact line built from a row, verbatim; no model writes any of
# it. And item 5: a sealed leak never goes invisible, so every live move is
# named with what it held in the latest closed month, quiet week or not.

QUIET_WATCH = "Nothing new crossed a line this week."


def _when(v):
    from datetime import datetime, timezone
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _move(d: dict, parts: list[str]) -> str:
    text = (d.get("action_text") or "A move").strip()
    return text + (f" ({' · '.join(parts)})" if parts else "")


def _found_state(d: dict) -> str:
    status = d.get("status")
    if d.get("executed_at") or status == "done":
        return "made"
    if status == "approved":
        return "approved; going live"
    if status == "issued":
        return ("notice sent; goes live unless you say no" if d.get("mandate") == "standing"
                else "notice sent; waits for your yes")
    return "in review; it comes to you before it goes live"


def note_found_lines(directives: list[dict], since, seals: dict | None = None) -> list[str]:
    """Moves drafted or issued since the last note, each with its expected
    dollars and, where it was sealed, the first twelve characters of its seal.
    Expected dollars are what a move says it will earn, not found money: the
    Record's 'found' is only what was made or filed, and stays in the footer."""
    seals = seals or {}
    rows = []
    for d in directives:
        if d.get("status") not in ("draft", "issued", "approved", "done"):
            continue
        stamps = [t for t in (_when(d.get("created_at")), _when(d.get("issued_at"))) if t]
        if any(t >= since for t in stamps):
            rows.append(d)
    rows.sort(key=lambda d: -float(d.get("expected_impact_usd") or 0))
    out = []
    for d in rows:
        parts = []
        if d.get("expected_impact_usd") is not None:
            parts.append(f"expected ${float(d['expected_impact_usd']):,.0f}")
        if seals.get(d.get("id")):
            parts.append(f"seal {seals[d.get('id')]}")
        parts.append(_found_state(d))
        out.append(_move(d, parts))
    return out


def _month_label(row: dict) -> str:
    from datetime import date
    start = date.fromisoformat(str(row["month_start"])[:10])
    end = date.fromisoformat(str(row["month_end"])[:10])
    return f"{start.strftime('%b %-d')} – {end.strftime('%b %-d, %Y')}"


def live_moves(directives: list[dict]) -> list[dict]:
    """Moves made and still measured every month: exactly the ones
    monthly.measure_month reads, so each can hold dollars in a month."""
    from .measurement import MEASURABLE_STATUSES
    from .monthly import NO_DOLLARS
    return [d for d in directives
            if d.get("status") in MEASURABLE_STATUSES and (d.get("executed_at") or d.get("status") == "done")
            and d.get("kind") and d.get("kind") not in NO_DOLLARS]


def note_holding_lines(directives: list[dict], months: list[dict] | None, client: dict,
                       seals: dict | None = None, today=None) -> list[str]:
    """Every live move and what it held in the latest closed month, read from
    that month's record_months rows (all channels). A month a dispute lowered
    says so, so the lines and the Record's figure never disagree."""
    from datetime import date
    from .monthly import billing_months
    seals = seals or {}
    today = today or date.today()
    rows = [r for r in (months or []) if r.get("month_index") is not None]
    latest = []
    if rows:
        top = max(int(r["month_index"]) for r in rows)
        latest = [r for r in rows if int(r["month_index"]) == top]
    held = {}
    for r in latest:
        for m in r.get("moves") or []:
            held[str(m.get("directive_id"))] = (m, r)
    spans = billing_months(client, today)

    def usd_of(d):
        hit = held.get(str(d.get("id")))
        return float(hit[0].get("usd") or 0) if hit and hit[0].get("verdict") == "measured" else 0.0

    out = []
    for d in sorted(live_moves(directives), key=lambda d: (-usd_of(d), str(d.get("executed_at") or ""))):
        parts = []
        hit = held.get(str(d.get("id")))
        if hit:
            m, r = hit
            label = _month_label(r)
            usd = float(m["usd"]) if m.get("verdict") == "measured" and m.get("usd") is not None else 0.0
            if usd > 0:
                parts.append(f"holding ${usd:,.0f} in {label}")
            elif usd < 0:
                parts.append(f"measured −${abs(usd):,.0f} in {label}")
            else:
                parts.append(f"nothing measured in {label}")
        else:
            made = _when(d.get("executed_at"))
            day = made.date() if made else None
            span = next((s for s in spans if day and s["start"] <= day <= s["end"]), None)
            if day and span:
                parts.append(f"live since {day.strftime('%b %-d')}; first on your Record when the month "
                             f"ending {span['end'].strftime('%b %-d')} closes")
            elif day:
                parts.append(f"live since {day.strftime('%b %-d')}")
            else:
                parts.append("live")
        if seals.get(d.get("id")):
            parts.append(f"seal {seals[d.get('id')]}")
        out.append(_move(d, parts))
    for r in latest:
        if float(r.get("disputed_usd") or 0) > 0:
            out.append(f"${float(r['disputed_usd']):,.0f} came off {_month_label(r)} after a dispute.")
    return out


def note_watching_lines(alerts: list[dict]) -> list[str]:
    """This week's alerts, the urgent first, each in its own words."""
    ordered = sorted(alerts, key=lambda a: 0 if a.get("severity") == "critical" else 1)
    return [("Urgent — " if a.get("severity") == "critical" else "") + (a.get("message") or "").strip()
            for a in ordered if a.get("message")]


def weekly_note(company: str, found: list[str], holding: list[str], watching: list[str],
                record_line: str | None, portal_url: str, n_live: int | None = None) -> dict:
    """The note as a subject and letter blocks (notify.letter renders them).
    Three sections, always in this order, each saying plainly when it is empty."""
    urgent = sum(1 for w in watching if w.startswith("Urgent — "))
    n_live = len(holding) if n_live is None else n_live
    watch = f"{len(watching)} to watch" if watching else "nothing new to watch"
    moves = f"{len(found)} move{'s' if len(found) != 1 else ''} found"
    subject = (("Urgent: " if urgent else "")
               + f"This week on {company}: {moves} · {n_live} sealed and holding · {watch}")
    blocks = [{"p": "Your week, from the numbers: what the models found, what is sealed and holding, "
                    "and what we are watching."}]
    if found:
        blocks += [{"p": "Found this week:"}, {"ol": found}]
    else:
        blocks.append({"p": "Found this week: nothing new."})
    if holding:
        blocks += [{"p": "Sealed and holding:"}, {"ol": holding}]
    else:
        blocks.append({"p": "Sealed and holding: nothing is live yet."})
    if watching:
        blocks += [{"p": "Watching:"}, {"ol": watching}]
    else:
        blocks.append({"p": "Watching: " + QUIET_WATCH[0].lower() + QUIET_WATCH[1:]})
    blocks.append({"button": "Open Hubricon", "url": portal_url})
    blocks.append({"p": "Reply to this email if any of it looks wrong; it comes straight to me."})
    if record_line:
        blocks.append({"p": record_line})
    return {"subject": subject, "blocks": blocks, "urgent": urgent}
