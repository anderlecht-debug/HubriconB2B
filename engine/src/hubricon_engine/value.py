"""Value delivered vs subscription paid — the retention ledger.

The product's spine: a running, conservative, counterfactual-backed
account of what Hubricon has put back into the client's business against
what the client has paid. Three columns, never blended:

    measured    directive outcomes recorded on the Decision Ledger
                (hubricon measure) — actual, against baseline
    recovered   reimbursement claims Amazon actually paid
                (hubricon recover paid) — actual, from the client's bank
    identified  expected value not yet banked: issued directives without
                a measurement, open claims at their expected value —
                shown, never added to the total

Fees follow the offer doctrine: the first month is free, then a flat
monthly fee. The ROI multiple is measured value over fees invoiced to
date; the thresholds are the ones the research set — a visible ≥ 5×
makes churn irrational, under 3× is the signal to deepen the work.
"""

from datetime import date

from .models.common import num

DEFAULT_MONTHLY_FEE_USD = 6000.0
DEFAULT_FREE_MONTHS = 1
STRONG_MULTIPLE = 5.0
AT_RISK_MULTIPLE = 3.0


def months_elapsed(start: date, today: date) -> int:
    return max(0, (today.year - start.year) * 12 + (today.month - start.month) - (1 if today.day < start.day else 0))


def compute(client: dict, directives: list[dict], claims: list[dict], today: date | None = None) -> dict:
    today = today or date.today()
    start = date.fromisoformat(str(client.get("created_at"))[:10]) if client.get("created_at") else today
    fee = float(client.get("monthly_fee_usd") or DEFAULT_MONTHLY_FEE_USD)
    free = int(client.get("free_months") if client.get("free_months") is not None else DEFAULT_FREE_MONTHS)
    months = months_elapsed(start, today)
    billed_months = max(0, months - free)
    fees_paid = billed_months * fee

    measured_rows = [d for d in directives if d.get("measured_impact_usd") is not None]
    measured = sum(float(d["measured_impact_usd"]) for d in measured_rows)
    paid_claims = [c for c in claims if c.get("status") == "paid" and c.get("paid_amount") is not None]
    recovered = sum(float(c["paid_amount"]) for c in paid_claims)
    value = measured + recovered

    unbanked_directives = sum(float(d["expected_impact_usd"]) for d in directives
                              if d.get("status") in ("issued", "approved") and d.get("measured_impact_usd") is None
                              and d.get("expected_impact_usd") is not None)
    unbanked_claims = sum(float(c.get("expected_value") or 0) for c in claims
                          if c.get("status") in ("detected", "filed", "open", "expiring"))
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
        "engagement_start": start.isoformat(),
        "months_elapsed": months,
        "billed_months": billed_months,
        "monthly_fee": num(fee),
        "fees_paid": num(fees_paid),
        "measured": num(measured),
        "measured_count": len(measured_rows),
        "recovered": num(recovered),
        "recovered_count": len(paid_claims),
        "value_total": num(value),
        "roi_multiple": num(multiple, 2),
        "identified_unbanked": num(identified),
        "identified_parts": {"directives": num(unbanked_directives), "claims": num(unbanked_claims)},
        "status": status,
        "thresholds": {"strong": STRONG_MULTIPLE, "at_risk": AT_RISK_MULTIPLE},
        "basis": ("Measured = directive outcomes recorded against baseline; recovered = reimbursements Amazon paid; "
                  "fees = flat monthly fee after the free month. Identified value is shown, never added."),
    }
