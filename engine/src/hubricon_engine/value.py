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
        paid = sum(float(i.get("amount_paid") or 0) for i in real if i.get("status") == "paid")
        billed = sum(float(i.get("amount_due") or 0) for i in real
                     if i.get("status") in ("open", "paid", "uncollectible"))
        return {"fees_paid": paid, "fees_billed": billed, "fees_basis": "invoiced",
                "billed_months": len([i for i in real if i.get("status") == "paid"]),
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


def record_line(ledger: dict) -> str:
    """The Profit Record in one line, for the foot of every client email: the
    same four numbers the strip in Hubricon shows, in the same words."""
    proven = float(ledger.get("value_total") or 0)
    found = float(ledger.get("identified_unbanked") or 0)
    billed = float(ledger.get("fees_billed") or 0)
    return (f"Your Profit Record: ${proven:,.0f} proven since day one · "
            f"${found:,.0f} found and filed, not yet banked · ${billed:,.0f} billed to date"
            + (f" · {proven / billed:.1f}× proven ÷ billed." if billed > 0 else "."))
