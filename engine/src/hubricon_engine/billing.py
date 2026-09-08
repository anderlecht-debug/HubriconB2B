"""Day 30: the guarantee, enforced by the code that writes the invoice.

Eight surfaces — including terms.html §3 — promise "if we don't find you more
than we cost, you walk away owing nothing". `value.compute` has always been
able to test that. Nothing acted on it, and nothing created an invoice either:
scripts/stripe-setup.mjs only *printed* the subscriptions.create call for a
human to run.

So the promise becomes structurally unbreakable by making the same pass that
checks it the only thing that starts billing. Below the bar, no subscription is
created — not "an invoice is written off", but no invoice exists.

The comparison uses measured value PLUS identified-but-unbanked value, which is
the decision taken on 2026-09-04: the measurement engine is deliberately
conservative, and it must not under-claim its way into refusing revenue for
work that was really delivered. The client is shown both numbers either way.

Two more gates live here since 2026-09-08, on the founder's decision:

**The rolling gate.** Day 30 was the only month the promise covered. Now every
invoice Stripe raises for a retainer is judged by the same bar: measured plus
identified value since the retainer began must cover everything billed through
that invoice. One that is not covered is voided — or credited to the next, if
ACH already settled it. "Our invoices never run ahead of your ledger."

**The recovery-only plan.** The smaller door for a founder who will not commit
to the fee: no retainer, a share of the reimbursements Amazon actually paid on
claims we filed, invoiced at month end, nothing else. Nothing landed, no
invoice. It is a `plan` on the client row, so the intake, the ledger, the proof
and the ask are all the same machinery.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

STRIPE_API = "https://api.stripe.com/v1"
FREE_DAYS = 30
NET_DAYS = 7          # terms.html §4: ACH, net seven days
TIMEOUT = 30


def stripe_configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def _stripe(path: str, data: dict | None = None, idempotency_key: str | None = None) -> dict:
    key = os.environ["STRIPE_SECRET_KEY"]
    url = f"{STRIPE_API}/{path}"
    body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if body is not None else "GET")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if idempotency_key:
        req.add_header("Idempotency-Key", idempotency_key)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"Stripe {path}: HTTP {err.code} {err.read().decode(errors='replace')[:200]}")


def due_for_decision(client: dict, today: date | None = None) -> tuple[bool, str]:
    """Has this client's free month run out, with no billing started yet?"""
    today = today or date.today()
    started = client.get("retainer_started_at")
    if not started:
        return False, "no retainer start date on file — record the yes with `hubricon retainer`"
    if client.get("stripe_subscription_id"):
        return False, "already billing"
    day = (today - date.fromisoformat(str(started)[:10])).days
    free = FREE_DAYS * int(client.get("free_months") or 1)
    if day < free:
        return False, f"day {day} of the free {free}"
    return True, f"day {day} — the free month is up"


def verdict(ledger: dict, client: dict) -> dict:
    """Does the ledger clear the fee? The number the promise turns on."""
    fee = float(client.get("monthly_fee_usd") or 6000.0)
    measured = float(ledger.get("value_total") or 0)
    identified = float(ledger.get("identified_unbanked") or 0)
    total = measured + identified
    return {
        "fee": fee,
        "measured": measured,
        "identified": identified,
        "total": total,
        "clears": total > fee,
        "multiple": round(total / fee, 2) if fee else None,
    }


def ensure_customer(client: dict, stripe=None) -> str:
    """The Stripe customer for this client: recorded, found by email, or created."""
    call = stripe or _stripe
    customer = client.get("stripe_customer_id")
    if customer:
        return customer
    found = call(f"customers?{urllib.parse.urlencode({'email': client['contact_email'], 'limit': 1})}")
    customer = (found.get("data") or [{}])[0].get("id")
    if not customer:
        customer = call("customers", {
            "email": client["contact_email"],
            "name": client.get("company_name") or client["contact_email"],
        })["id"]
    return customer


def start_billing(client: dict, price_id: str) -> dict:
    """Create the subscription terms.html §4 describes: invoiced by email, ACH,
    net seven days, no card on file, nothing charged automatically."""
    customer = ensure_customer(client)
    return _stripe("subscriptions", {
        "customer": customer,
        "items[0][price]": price_id,
        "collection_method": "send_invoice",
        "days_until_due": NET_DAYS,
        "payment_settings[payment_method_types][0]": "us_bank_account",
        "metadata[hubricon_client_id]": client["id"],
    })


def cleared_email_blocks(v: dict, portal_url: str) -> list[dict]:
    return [
        {"p": f"Your free month is up, and here is the arithmetic we said we'd be judged on."},
        {"ol": [
            f"Measured on your Decision Ledger, from your own exports: ${v['measured']:,.0f}",
            f"Found and not yet banked: ${v['identified']:,.0f}",
            f"Against the retainer: ${v['fee']:,.0f} a month",
        ]},
        {"p": f"That is {v['multiple']:.1f}× the fee, so the retainer starts and your first invoice "
              f"comes by email — ACH, net seven days, no card on file, nothing charged automatically. "
              f"Cancel with one email whenever you like."},
        {"button": "See every line behind that number", "url": portal_url},
        {"p": "Each entry on the ledger says how we know it, and which export it came from. "
              "If any of it looks wrong, reply and tell me — I'd rather fix the number than keep it."},
    ]


def short_email_blocks(v: dict, portal_url: str, recovery_door: bool = False,
                       share: float | None = None) -> list[dict]:
    blocks = [
        {"p": "Your free month is up, and we did not clear the bar we set ourselves."},
        {"ol": [
            f"Measured on your Decision Ledger: ${v['measured']:,.0f}",
            f"Found and not yet banked: ${v['identified']:,.0f}",
            f"Against the retainer: ${v['fee']:,.0f} a month",
        ]},
        {"p": "So there is no invoice. That is what we promised — if we don't find you more than we "
              "cost, you walk away owing nothing — and it isn't a discount or a credit; nothing was "
              "raised at all."},
        {"button": "See the full working", "url": portal_url},
        {"p": "I'd like to keep going and earn it, and the work carries on either way until you tell "
              "me to stop. But that's your call to make, not mine, and either answer is fine."},
    ]
    if recovery_door:
        pct = f"{(share if share is not None else RECOVERY_SHARE) * 100:.0f}%"
        blocks.append({"p": "There is also a smaller door, if you would rather keep only the reimbursement "
                            "desk: we keep filing what Amazon owes you, and you pay " + pct +
                            " of what actually lands in your account — nothing else, and nothing until it "
                            "lands. Reply RECOVERY and I will switch you over."})
    return blocks


# -- the rolling gate: every invoice, the same bar ------------------------------------

BILLED_STATUSES = ("open", "paid", "uncollectible")


def _inv_key(inv: dict) -> tuple:
    return (str(inv.get("period_start") or ""), str(inv.get("issued_at") or ""), str(inv.get("stripe_invoice_id") or ""))


def unjudged_invoices(invoices: list[dict], client: dict) -> list[dict]:
    """Invoices Stripe raised that the gate has not yet decided, oldest first.
    Only ones inside the retainer: a stray invoice from before the yes is not
    a month of ours to judge."""
    started = str(client.get("retainer_started_at") or "")[:10]
    out = [i for i in invoices
           if i.get("status") in ("open", "paid") and not i.get("gate_decision")
           and (not started or not i.get("period_start") or str(i["period_start"])[:10] >= started)]
    return sorted(out, key=_inv_key)


def fees_billed_through(invoices: list[dict], inv: dict) -> float:
    """Everything billed up to and including this invoice — void ones excluded,
    because a voided month was never billed."""
    key = _inv_key(inv)
    return sum(float(i.get("amount_due") or 0) for i in invoices
               if i.get("status") in BILLED_STATUSES and _inv_key(i) <= key)


def rolling_verdict(ledger: dict, invoices: list[dict], inv: dict, client: dict) -> dict:
    """Is this invoice covered? Same bar as day 30 — measured plus identified —
    against everything billed through it. Covered means the ledger is at least
    level with the bills: our invoices never run ahead of it."""
    fees = fees_billed_through(invoices, inv)
    measured = float(ledger.get("value_total") or 0)
    identified = float(ledger.get("identified_unbanked") or 0)
    total = measured + identified
    return {"fee": float(client.get("monthly_fee_usd") or 6000.0), "measured": measured,
            "identified": identified, "total": total, "fees_billed": fees,
            "covered": total >= fees, "invoice": inv.get("stripe_invoice_id"),
            "amount": float(inv.get("amount_due") or 0), "period_start": inv.get("period_start"),
            "period_end": inv.get("period_end"), "status": inv.get("status")}


def waive_invoice(inv: dict, client: dict, stripe=None) -> str:
    """Make the month free. An open invoice is voided — nothing to pay, nothing
    raised. One ACH already settled is credited to the customer balance, which
    Stripe applies to the next invoice by itself. Returns 'voided' or 'credited'."""
    call = stripe or _stripe
    sid = inv["stripe_invoice_id"]
    if inv.get("status") == "open":
        call(f"invoices/{sid}/void", {})
        return "voided"
    amount = float(inv.get("amount_paid") or inv.get("amount_due") or 0)
    customer = inv.get("stripe_customer_id") or client.get("stripe_customer_id")
    call(f"customers/{customer}/balance_transactions",
         {"amount": int(round(-amount * 100)), "currency": inv.get("currency") or "usd",
          "description": f"Month not covered by the ledger — invoice {inv.get('number') or sid}"},
         idempotency_key=f"gate-{sid}")
    return "credited"


def waived_email_blocks(v: dict, how: str, portal_url: str) -> list[dict]:
    when = f" for {str(v['period_start'])[:10]} to {str(v['period_end'])[:10]}" if v.get("period_start") else ""
    return [
        {"p": "We said our invoices would never run ahead of your ledger, and this month they did."},
        {"ol": [
            f"Measured on your Decision Ledger since the retainer began: ${v['measured']:,.0f}",
            f"Found and not yet banked: ${v['identified']:,.0f}",
            f"Billed through this invoice{when}: ${v['fees_billed']:,.0f}",
        ]},
        {"p": ("So the invoice is void and there is nothing to pay for the month."
               if how == "voided" else
               "That invoice had already settled, so the same amount is credited to your next one, "
               "which will show it as paid down to zero.")},
        {"button": "See the working", "url": portal_url},
        {"p": "The work carries on. The ledger has to catch up with the bills before another invoice "
              "stands, and that is on us, not you."},
    ]


# -- the recovery-only plan --------------------------------------------------------------

RECOVERY_SHARE = float(os.environ.get("RECOVERY_SHARE", "0.25"))
RECOVERY_MIN_INVOICE_USD = float(os.environ.get("RECOVERY_MIN_INVOICE_USD", "50"))


def _month_start(d: date) -> date:
    return d.replace(day=1)


def recovery_due(claims: list[dict], today: date, share: float | None = None,
                 min_usd: float | None = None) -> dict | None:
    """What a recovery-only client owes for the months that have ended.

    Only claims we filed, only ones Amazon actually paid, only ones paid before
    this month began, and only ones no earlier invoice carried. Under the
    minimum they wait and roll forward, so nobody receives a nine-dollar
    invoice. Returns None with nothing due."""
    share = RECOVERY_SHARE if share is None else float(share)
    min_usd = RECOVERY_MIN_INVOICE_USD if min_usd is None else float(min_usd)
    cutoff = _month_start(today)
    ours = []
    for c in claims:
        if c.get("status") != "paid" or not (c.get("filed_at") or c.get("case_id")):
            continue
        if c.get("recovery_invoice_id") or float(c.get("paid_amount") or 0) <= 0:
            continue
        paid_on = str(c.get("paid_at") or "")[:10]
        if not paid_on or date.fromisoformat(paid_on) >= cutoff:
            continue
        ours.append(c)
    if not ours:
        return None
    recovered = round(sum(float(c["paid_amount"]) for c in ours), 2)
    amount = round(recovered * share, 2)
    first = min(date.fromisoformat(str(c["paid_at"])[:10]) for c in ours)
    result = {"claims": ours, "n_claims": len(ours), "recovered": recovered, "share": share,
              "amount": amount, "period_start": _month_start(first), "period_end": cutoff - timedelta(days=1)}
    if amount < min_usd:
        return {**result, "deferred": f"${amount:,.2f} is under the ${min_usd:,.0f} minimum; it rolls forward"}
    return result


def invoice_recovery_share(client: dict, due: dict, stripe=None) -> dict:
    """One Stripe invoice for the period: an item for the share, sent by email,
    ACH, net seven days. Nothing recurring is created."""
    call = stripe or _stripe
    customer = ensure_customer(client, call)
    label = (f"Reimbursement desk — {due['share'] * 100:.0f}% of ${due['recovered']:,.2f} Amazon paid on "
             f"{due['n_claims']} claim(s) we filed, {due['period_start']} to {due['period_end']}")
    call("invoiceitems", {"customer": customer, "amount": int(round(due["amount"] * 100)),
                          "currency": "usd", "description": label})
    inv = call("invoices", {
        "customer": customer,
        "collection_method": "send_invoice",
        "days_until_due": NET_DAYS,
        "pending_invoice_items_behavior": "include",
        "payment_settings[payment_method_types][0]": "us_bank_account",
        "metadata[hubricon_client_id]": client["id"],
        "metadata[hubricon_plan]": "recovery",
        "metadata[period_start]": str(due["period_start"]),
        "metadata[period_end]": str(due["period_end"]),
    })
    inv = call(f"invoices/{inv['id']}/finalize", {}) or inv
    try:
        sent = call(f"invoices/{inv['id']}/send", {})
        if sent:
            inv = sent
    except RuntimeError:
        pass        # Stripe emails send_invoice invoices itself when configured to; ours is the letter
    inv["customer"] = customer
    return inv


def recovery_email_blocks(due: dict, invoice_url: str | None, portal_url: str) -> list[dict]:
    return [
        {"p": f"Amazon paid ${due['recovered']:,.2f} on {due['n_claims']} claim(s) we filed between "
              f"{due['period_start']:%B %-d} and {due['period_end']:%B %-d, %Y}."},
        {"p": f"Our share is {due['share'] * 100:.0f}% of what landed: ${due['amount']:,.2f}. That is the whole "
              f"invoice — there is no retainer on this plan, and a month in which nothing lands produces no "
              f"invoice at all. ACH, net seven days, no card on file."},
        *([{"button": "Open the invoice", "url": invoice_url}] if invoice_url else []),
        {"button": "See each claim on your desk", "url": portal_url},
        {"p": "Every claim says which report it came from and what Amazon's own record shows. If any of it "
              "looks wrong, reply and tell me."},
    ]
