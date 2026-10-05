"""Value delivered vs subscription paid — the retention ledger.

The product's spine: a running, conservative, counterfactual-backed
account of what Hubricon has put back into the client's business against
what the client has paid. Three columns, never blended:

    measured    directive outcomes measured against baseline from the
                client's own later exports (measurement.py), or recorded
                by hand (hubricon measure)
    recovered   reimbursement claims Amazon paid on a claim WE filed
    identified  expected value not yet banked: issued directives without
                a measurement, open claims at their expected value —
                shown, never added to the total

Two rules keep this a ledger rather than a sales deck:

**Fees are observed, not assumed.** The multiple's denominator used to be
`months since the row was created × $6,000`, which meant a prospect who never
converted still accrued fees and was shown `0.0× — at risk` in their own desk.
Fees now come from invoices actually issued; where none exist the basis says
so, and an uninvoiced client is in their free month, not failing.

**Recovered dollars must be attributed.** Amazon auto-reimburses a large share
of warehouse loss unprompted, so counting every paid claim would credit us with
money that would have arrived had we never existed. Only claims we filed reach
the total; the rest are shown beside it as the client's record.

The ROI thresholds are the ones the research set — a visible ≥ 5× makes churn
irrational, under 3× is the signal to deepen the work.
"""

from datetime import date

from .models.common import num
from .models.recovery import window_state

DEFAULT_MONTHLY_FEE_USD = 6000.0
DEFAULT_FREE_MONTHS = 1
STRONG_MULTIPLE = 5.0
AT_RISK_MULTIPLE = 3.0

# Claim window states that still represent money in flight. 'expired' and
# 'denied' are neither banked nor identified: the window closed. The portal's
# in-flight display uses this set.
LIVE_CLAIM_STATES = ("open", "expiring", "not_yet_eligible", "filed")
# Claim states that count as "found" on the Profit Record — the printed rule is
# "what we proved, plus what we found and filed", so only a claim actually
# filed with Amazon (not yet paid) is found money. A claim merely detected in
# a report is a lead, not a receipt.
IDENTIFIED_CLAIM_STATES = ("filed",)


def months_elapsed(start: date, today: date) -> int:
    return max(0, (today.year - start.year) * 12 + (today.month - start.month) - (1 if today.day < start.day else 0))


def engagement_start(client: dict, today: date) -> tuple[date, str]:
    """When the retainer began, and how sure we are.

    terms.html §3: "the retainer starts on the day you say yes after the
    Teardown". `created_at` is when the row was provisioned — at booking, before
    the Teardown and before the yes — so it is the last resort, not the default.
    Where the true date is unknown we take the EARLIEST defensible one: an
    earlier start means more billed months, a larger denominator and a smaller
    multiple. Erring that way can never flatter us."""
    started = client.get("retainer_started_at")
    if started:
        return date.fromisoformat(str(started)[:10]), (client.get("retainer_source") or "recorded")
    if client.get("created_at"):
        return date.fromisoformat(str(client["created_at"])[:10]), "provisioned"
    return today, "unknown"


def fee_side(client: dict, invoices: list[dict] | None, today: date) -> dict:
    """The denominator, with its provenance stated.

    Observed beats assumed, and unknown is never treated as accrued — a client
    with no invoice and no start date has not been billed, so the ledger says
    "free month" rather than "0.0×, at risk"."""
    fee = float(client.get("monthly_fee_usd") or DEFAULT_MONTHLY_FEE_USD)
    free = int(client.get("free_months") if client.get("free_months") is not None else DEFAULT_FREE_MONTHS)
    start, source = engagement_start(client, today)
    months = months_elapsed(start, today)

    real = [i for i in (invoices or []) if (i.get("status") or "") != "void"]
    if real:
        # A refunded dollar (the gate, or the true-up at the exit) was given
        # back, so it is not a fee: the invoice counts net of it.
        def kept(i, field):
            return max(0.0, float(i.get(field) or 0) - float(i.get("refunded_usd") or 0))
        paid_rows = [i for i in real if i.get("status") == "paid"]
        paid = sum(kept(i, "amount_paid") for i in paid_rows)
        billed = sum(kept(i, "amount_due") for i in real
                     if i.get("status") in ("open", "paid", "uncollectible"))
        return {"fees_paid": paid, "fees_billed": billed, "fees_basis": "invoiced",
                "billed_months": len([i for i in paid_rows
                                      if not float(i.get("refunded_usd") or 0) or kept(i, "amount_paid") > 0]),
                "monthly_fee": fee, "months_elapsed": months,
                "engagement_start": start, "engagement_start_source": source}

    if client.get("retainer_started_at"):
        billed_months = max(0, months - free)
        return {"fees_paid": billed_months * fee, "fees_billed": billed_months * fee,
                "fees_basis": "assumed", "billed_months": billed_months,
                "monthly_fee": fee, "months_elapsed": months,
                "engagement_start": start, "engagement_start_source": source}

    # No invoice, no agreed start date: nothing has been billed, and saying
    # otherwise is what put "0.0× — at risk" in front of paying clients.
    return {"fees_paid": 0.0, "fees_billed": 0.0, "fees_basis": "unknown", "billed_months": 0,
            "monthly_fee": fee, "months_elapsed": months,
            "engagement_start": start, "engagement_start_source": source}


def _is_made(d: dict) -> bool:
    """Has this move actually happened in the client's account?"""
    return bool(d.get("executed_at")) or d.get("status") == "done"


def compute(client: dict, directives: list[dict], claims: list[dict],
            invoices: list[dict] | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    fees = fee_side(client, invoices, today)
    fees_paid = fees["fees_paid"]

    measured_rows = [d for d in directives if d.get("measured_impact_usd") is not None]
    measured = sum(float(d["measured_impact_usd"]) for d in measured_rows)
    # The band: a measured price step, markdown or reallocation carries the
    # distribution it was banked from (evidence.after.measured_distribution);
    # its 5th and 95th percentiles sum with the point values of the rest, and
    # the basis says what share of the dollars actually had a band.
    lo = hi = 0.0
    banded_dollars = 0.0
    for d in measured_rows:
        dist = ((d.get("evidence") or {}).get("after") or {}).get("measured_distribution") or {}
        usd = float(d["measured_impact_usd"])
        if dist.get("p5") is not None and dist.get("p95") is not None:
            # never wider than the banked figure allows above it: the promise cap applied to the point
            lo += min(usd, float(dist["p5"]))
            hi += min(max(usd, float(dist["p95"])), max(usd, float(dist["p95"])))
            banded_dollars += abs(usd)
        else:
            lo += usd
            hi += usd
    banded_share = banded_dollars / sum(abs(float(d["measured_impact_usd"])) for d in measured_rows) if measured_rows and measured else 0.0
    by_attribution: dict[str, float] = {}
    for d in measured_rows:
        tier = d.get("attribution") or "unrecorded"
        by_attribution[tier] = round(by_attribution.get(tier, 0.0) + float(d["measured_impact_usd"]), 2)

    paid = [c for c in claims if c.get("status") == "paid" and c.get("paid_amount") is not None]
    # Amazon paid it because we filed it: ours to claim. Amazon paid it on its
    # own reconciliation: the client's record, not our result.
    ours = [c for c in paid if c.get("filed_at") or c.get("case_id")]
    recovered = sum(float(c["paid_amount"]) for c in ours)
    recovered_unattributed = sum(float(c["paid_amount"]) for c in paid if c not in ours)
    value = measured + recovered

    # "Found" = a move actually made (executed, or recorded done) at its
    # expected dollars, not yet measured. A move that is only issued or
    # approved has not happened yet, so it is not found money and cannot
    # cover an invoice. A move the sweep closed as unmeasurable has been
    # measured and found nothing; it is not found money either.
    unbanked_directives = sum(float(d["expected_impact_usd"]) for d in directives
                              if _is_made(d) and d.get("measured_impact_usd") is None
                              and d.get("measured_at") is None
                              and d.get("status") not in ("closed", "lapsed")
                              and d.get("expected_impact_usd") is not None)
    # Window state, not raw status: only a claim actually filed and not yet
    # paid is found money. A 'detected' claim, open or not, is not yet filed;
    # an expired or denied one is neither banked nor found.
    unbanked_claims = sum(float(c.get("expected_value") or 0) for c in claims
                          if window_state(c, today) in IDENTIFIED_CLAIM_STATES)
    identified = unbanked_directives + unbanked_claims

    multiple = value / fees_paid if fees_paid > 0 else None
    if fees_paid == 0:
        status = "free_month"
    elif multiple >= STRONG_MULTIPLE:
        status = "strong"
    elif multiple >= AT_RISK_MULTIPLE:
        status = "holding"
    else:
        status = "at_risk"

    return {
        "as_of": today.isoformat(),
        "engagement_start": fees["engagement_start"].isoformat(),
        "engagement_start_source": fees["engagement_start_source"],
        "months_elapsed": fees["months_elapsed"],
        "billed_months": fees["billed_months"],
        "monthly_fee": num(fees["monthly_fee"]),
        "fees_paid": num(fees_paid),
        "fees_billed": num(fees["fees_billed"]),
        "fees_basis": fees["fees_basis"],
        "measured": num(measured),
        "measured_count": len(measured_rows),
        "measured_by_attribution": by_attribution,
        "recovered": num(recovered),
        "recovered_count": len(ours),
        "recovered_unattributed": num(recovered_unattributed),
        "value_total": num(value),
        "value_p5": num(lo + recovered),
        "value_p95": num(hi + recovered),
        "value_interval_basis": {"banded_share_of_measured": num(banded_share, 4),
                                 "note": ("measured moves that carry a distribution contribute their 5th and 95th "
                                          "percentiles; the rest and every recovery contribute their point")},
        "roi_multiple": num(multiple, 2),
        "identified_unbanked": num(identified),
        "identified_parts": {"directives": num(unbanked_directives), "claims": num(unbanked_claims)},
        "status": status,
        "thresholds": {"strong": STRONG_MULTIPLE, "at_risk": AT_RISK_MULTIPLE},
        "basis": ("Measured = move outcomes measured against baseline from your own later exports; "
                  "recovered = reimbursements Amazon paid on claims we filed; found = moves made and "
                  "claims filed, at their expected dollars, not yet measured or paid; fees = what was "
                  "actually invoiced where invoices are on file."),
    }


# -- proven since day one: one number, everywhere ------------------------------------------
#
# Until 2026-10-01 a client could read three different "proven since day one"
# figures in one week: the Brief's letter and video said the measured moves
# alone (no reimbursements), the subject and every email footer said
# `value_total`, and the portal summed the closed months. One function now
# makes the figure and every client surface takes it from here.
#
#   months    once a month has closed and been measured (monthly.py), the sum of
#             every record_months row, all channels, after disputes. This is
#             the number each invoice is judged on.
#   measured  before that: what the moves have measured on their own windows,
#             plus what Amazon paid on claims we filed (`value_total`).
#
# A switch of basis is a different label, never a fall; a dispute can lower
# the months figure, and the dollars that came off are carried beside it.

PROVEN_LABEL = "Proven on your Profit Record since day one"
MEASURED_LABEL = "Measured so far"


def first_close(client: dict) -> date | None:
    """The last day of the client's first month (month 0), or None before the yes."""
    started = client.get("retainer_started_at")
    if not started:
        return None
    from datetime import timedelta
    from .monthly import add_months
    start = date.fromisoformat(str(started)[:10])
    return add_months(start, 1) - timedelta(days=1)


def _close_phrase(close: date | None, today: date) -> str | None:
    if close is None:
        return None
    return f"your first month {'closes' if close >= today else 'closed'} {close.strftime('%B %-d')}"


def proven_from(client: dict, ledger: dict, months: list[dict] | None, today: date | None = None) -> dict:
    """The one figure, from what is already loaded. `months` is every
    record_months row of the client (None or [] when there are none or the
    table is not there yet)."""
    today = today or date.today()
    close = first_close(client)
    rows = [r for r in (months or []) if r.get("attributed_usd") is not None]
    if rows:
        usd = round(sum(float(r["attributed_usd"]) - float(r.get("disputed_usd") or 0) for r in rows), 2)
        disputed = round(sum(float(r.get("disputed_usd") or 0) for r in rows), 2)
        moved: set = set()
        tiers: dict[str, float] = {}
        for r in rows:
            for m in r.get("moves") or []:
                if m.get("verdict") != "measured" or m.get("usd") is None:
                    continue
                moved.add(str(m.get("directive_id")))
                tier = m.get("attribution") or "unrecorded"
                tiers[tier] = round(tiers.get(tier, 0.0) + float(m["usd"]), 2)
        ends = sorted(str(r.get("month_end"))[:10] for r in rows if r.get("month_end"))
        return {"usd": usd, "basis": "months", "label": PROVEN_LABEL,
                "as_of": ends[-1] if ends else today.isoformat(),
                "first_close": close.isoformat() if close else (ends[0] if ends else None),
                "moves": len(moved), "disputed_usd": disputed,
                # Before disputes, per move: summing them could not match the figure
                # once dollars came off, so they are offered only while none have.
                "by_attribution": tiers if not disputed else None}
    phrase = _close_phrase(close, today)
    return {"usd": round(float(ledger.get("value_total") or 0), 2), "basis": "measured",
            "label": MEASURED_LABEL + (f" · {phrase}" if phrase else ""),
            "as_of": ledger.get("as_of") or today.isoformat(),
            "first_close": close.isoformat() if close else None,
            "moves": int(ledger.get("measured_count") or 0), "disputed_usd": 0.0,
            "by_attribution": dict(ledger.get("measured_by_attribution") or {}) or None}


def load_ledger(db, client: dict, today: date | None = None) -> dict:
    """`compute` with the client's own rows read. Invoices degrade to none when
    their table is missing, as the CLI's reader does."""
    cid = client["id"]
    directives = db.table("directives").select("*").eq("client_id", cid).execute().data or []
    claims = db.table("recovery_claims").select("*").eq("client_id", cid).order("deadline").execute().data or []
    try:
        invoices = db.table("invoices").select("*").eq("client_id", cid).order("period_start").execute().data or []
    except Exception:
        invoices = []
    return compute(client, directives, claims, invoices, today)


def load_months(db, client_id: str) -> list[dict] | None:
    """Every record_months row of the client; None when the table is not there."""
    try:
        return db.table("record_months").select("*").eq("client_id", client_id).execute().data or []
    except Exception:
        return None


def proven_since_day_one(db, client: dict, ledger: dict | None = None, today: date | None = None) -> dict:
    """{"usd", "basis": "months"|"measured", "label", "as_of", "first_close", ...}:
    the one "proven since day one" figure a client sees, wherever they see it."""
    today = today or date.today()
    if ledger is None:
        ledger = load_ledger(db, client, today)
    return proven_from(client, ledger, load_months(db, client["id"]), today)


def billed_to_date(ledger: dict) -> float:
    """What a client email may call "billed to date": only what was invoiced.
    The ledger's 'assumed' basis (every month after the free ones at the fee)
    predates the per-month guarantee, under which a month is billed only if it
    cleared; with no invoice on file, nothing has been billed."""
    if (ledger.get("fees_basis") or "invoiced") != "invoiced":
        return 0.0
    return float(ledger.get("fees_billed") or 0)


def proven_words(proven: dict) -> tuple[str, str | None]:
    """The figure's name in running prose, and the aside that goes with it:
    ("proven since day one", None) or ("measured so far", "your first month closes November 1")."""
    if proven.get("basis") == "months":
        return "proven since day one", None
    label = proven.get("label") or MEASURED_LABEL
    aside = label.split(" · ", 1)[1] if " · " in label else None
    return "measured so far", aside


def record_line(ledger: dict, proven: dict | None = None) -> str:
    """The Profit Record in one line, for the foot of a client email: the same
    numbers the strip in Hubricon shows, in the same words.

    The figure is `proven` (proven_since_day_one), never re-derived here. A
    caller that has no database to hand passes none, and the line then leaves
    the figure out rather than state a second one: it says what was found and
    what was billed, which no basis can contradict."""
    found = float(ledger.get("identified_unbanked") or 0)
    billed = billed_to_date(ledger)
    tail = f"${found:,.0f} found and filed, not yet banked · ${billed:,.0f} billed to date"
    if proven is None:
        return f"Your Profit Record: {tail}."
    usd = float(proven.get("usd") or 0)
    words, aside = proven_words(proven)
    band = ""
    if proven.get("basis") == "measured":
        # the band beside the number, when at least half the measured dollars carry one;
        # it belongs to the measured figure, so a closed month never carries it
        basis = ledger.get("value_interval_basis") or {}
        if float(basis.get("banded_share_of_measured") or 0) >= 0.5 and ledger.get("value_p5") is not None:
            band = f" (range ${float(ledger['value_p5']):,.0f}–${float(ledger['value_p95']):,.0f})"
    head = f"${usd:,.0f} {words}{band}" + (f", {aside}" if aside else "")
    short = "proven" if proven.get("basis") == "months" else "measured"
    return (f"Your Profit Record: {head} · {tail}"
            + (f" · {usd / billed:.1f}× {short} ÷ billed." if billed > 0 else "."))


def record_footer(db, client: dict, proven: dict | None = None, ledger: dict | None = None) -> str:
    """record_line with everything read: the footer every non-billing client
    email closes on."""
    ledger = ledger if ledger is not None else load_ledger(db, client)
    proven = proven if proven is not None else proven_since_day_one(db, client, ledger)
    return record_line(ledger, proven)
