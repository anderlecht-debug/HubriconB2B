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
that invoice. "Our invoices never run ahead of your ledger."

**The recovery-only plan.** The smaller door for a founder who will not commit
to the fee: no retainer, a share of the reimbursements Amazon actually paid on
claims we filed, invoiced at month end, nothing else. Nothing landed, no
invoice. It is a `plan` on the client row, so the intake, the ledger, the proof
and the ask are all the same machinery.

Tightened on 2026-09-25, when the guarantee was rebuilt as a stack:

**Held, then judged.** api/stripe-webhook.js stops every retainer invoice at
draft (`auto_advance=false`), so the gate judges it before the client ever sees
it: covered, it is finalized and sent; not covered, it is voided unsent. An
open invoice (a hold that failed) is voided as before.

**Refunded, not credited.** A month the Record stops covering after ACH has
settled goes back to the bank account it came from, through a credit note on
the invoice. A credit on the next bill is worth nothing to a client who leaves.

**Trued up at the exit.** The day Managed Profit ends, the Record is checked
once more against everything billed and not given back. Unpaid invoices are
voided first; whatever gap remains is refunded.
"""

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

STRIPE_API = "https://api.stripe.com/v1"
# Every call is made at the version the webhook's Node SDK pins (stripe@18.5 in
# package.json), so the engine and api/stripe-webhook.js read the same shapes.
# Unpinned, each call takes the account's default version, which is whatever
# it was the day the account was opened.
STRIPE_VERSION = "2025-08-27.basil"
FREE_DAYS = 30
NET_DAYS = 7          # terms.html §4: ACH, net seven days
TIMEOUT = 30


def stripe_configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def _stripe(path: str, data: dict | None = None, idempotency_key: str | None = None,
            method: str | None = None) -> dict:
    key = os.environ["STRIPE_SECRET_KEY"]
    url = f"{STRIPE_API}/{path}"
    body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method or ("POST" if body is not None else "GET"))
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Stripe-Version", STRIPE_VERSION)
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
            "metadata[hubricon_client_id]": client["id"],
        }, idempotency_key=f"customer-{client['id']}")["id"]
    return customer


def start_billing(client: dict, price_id: str, stripe=None) -> dict:
    """Create the subscription terms.html §4 describes: invoiced by email, ACH,
    net seven days, no card on file, nothing charged automatically.

    Never twice. The pass runs hourly, and a subscription created on a pass
    whose database write then failed would otherwise be created again on the
    next one — two $6,000 invoices a month. A live subscription already carrying
    this client's id is returned instead, and the create itself carries an
    idempotency key for the retry that lands inside Stripe's 24 hours."""
    call = stripe or _stripe
    customer = ensure_customer(client, call)
    listed = call(f"subscriptions?{urllib.parse.urlencode({'customer': customer, 'status': 'all', 'limit': 100})}")
    for s in listed.get("data") or []:
        if ((s.get("metadata") or {}).get("hubricon_client_id") == client["id"]
                and s.get("status") not in ("canceled", "incomplete_expired")):
            return s
    return call("subscriptions", {
        "customer": customer,
        "items[0][price]": price_id,
        "collection_method": "send_invoice",
        "days_until_due": NET_DAYS,
        "payment_settings[payment_method_types][0]": "us_bank_account",
        "metadata[hubricon_client_id]": client["id"],
    }, idempotency_key=f"subscribe-{client['id']}-{str(client.get('retainer_started_at') or '')[:10]}")


def cancel_subscription(subscription_id: str, stripe=None) -> dict:
    """End the retainer in Stripe at once: no final invoice, no proration.
    terms §5 — the month after the email is simply never invoiced."""
    call = stripe or _stripe
    return call(f"subscriptions/{subscription_id}", {"invoice_now": "false", "prorate": "false"},
                method="DELETE")


def cleared_email_blocks(v: dict, portal_url: str) -> list[dict]:
    return [
        {"p": f"Your free month is up, and here is the arithmetic we said we'd be judged on."},
        {"ol": [
            f"Proven on your Profit Record, from your own exports: ${v['measured']:,.0f}",
            f"Found and filed, not yet banked: ${v['identified']:,.0f}",
            f"Against Managed Profit: ${v['fee']:,.0f} a month",
        ]},
        {"p": f"That is {v['multiple']:.1f}× the fee, so the paid months start and your first invoice "
              f"comes by email — ACH, net seven days, no card on file, nothing charged automatically. "
              f"Every invoice after it waits for the same check before it is sent. Cancel with one email "
              f"whenever you like, and we true up on the way out: billed more than the Record shows, and "
              f"the difference comes back."},
        {"button": "See every line behind that number", "url": portal_url},
        {"p": "Each entry on your Profit Record says how we know it, and which export it came from. "
              "If any of it looks wrong, reply and tell me — I'd rather fix the number than keep it."},
    ]


def short_email_blocks(v: dict, portal_url: str, recovery_door: bool = False,
                       share: float | None = None) -> list[dict]:
    blocks = [
        {"p": "Your free month is up, and we did not clear the bar we set ourselves."},
        {"ol": [
            f"Proven on your Profit Record, from your own exports: ${v['measured']:,.0f}",
            f"Found and filed, not yet banked: ${v['identified']:,.0f}",
            f"Against Managed Profit: ${v['fee']:,.0f} a month",
        ]},
        {"p": "So there is no invoice. That is what we promised — if we don't find you more than we "
              "cost, you walk away owing nothing — and it isn't a discount or a credit; nothing was "
              "raised at all."},
        {"button": "See the full working", "url": portal_url},
        {"p": "I'd like to keep going and earn it, and the work carries on either way until you tell "
              "me to stop. But that's your call to make, not mine, and either answer is fine."},
        {"p": "If the Record clears $6,000 later — a claim Amazon pays, a price step that reads out — "
              "the first invoice comes then, by email, with this same arithmetic on top of it. Not before."},
    ]
    if recovery_door:
        pct = f"{(share if share is not None else RECOVERY_SHARE) * 100:.0f}%"
        blocks.append({"p": "There is also a smaller door, if you would rather keep only the reimbursement "
                            "filing (Recovery Only): we keep filing what Amazon owes you, and you pay " + pct +
                            " of what actually lands in your account — nothing else, and nothing until it "
                            "lands. Reply RECOVERY and I will switch you over."})
    return blocks


# -- the rolling gate: every invoice, the same bar ------------------------------------

BILLED_STATUSES = ("open", "paid", "uncollectible")


def _inv_key(inv: dict) -> tuple:
    return (str(inv.get("period_start") or ""), str(inv.get("issued_at") or ""), str(inv.get("stripe_invoice_id") or ""))


def _is_recovery(inv: dict) -> bool:
    return ((inv.get("raw") or {}).get("metadata") or {}).get("hubricon_plan") == "recovery"


def still_billed(inv: dict) -> float:
    """What an invoice still bills: its amount, less anything refunded on it."""
    return max(0.0, float(inv.get("amount_due") or 0) - float(inv.get("refunded_usd") or 0))


def unjudged_invoices(invoices: list[dict], client: dict) -> list[dict]:
    """Retainer invoices the gate has not yet decided, oldest first: held
    drafts, open ones and paid ones. Only ones inside the retainer (a stray
    invoice from before the yes is not a month of ours to judge), and never a
    recovery-share invoice, which is priced off money that already landed."""
    started = str(client.get("retainer_started_at") or "")[:10]
    out = [i for i in invoices
           if i.get("status") in ("draft", "open", "paid") and not i.get("gate_decision") and not _is_recovery(i)
           and (not started or not i.get("period_start") or str(i["period_start"])[:10] >= started)]
    return sorted(out, key=_inv_key)


def fees_billed_through(invoices: list[dict], inv: dict) -> float:
    """Everything billed up to and including this invoice. Void ones are
    excluded, because a voided month was never billed; refunded dollars are
    taken off; and the invoice being judged counts even while it is a held
    draft, because the question is whether the Record covers it too."""
    key = _inv_key(inv)
    this = inv.get("stripe_invoice_id")
    return sum(still_billed(i) for i in invoices
               if (i.get("status") in BILLED_STATUSES or i.get("stripe_invoice_id") == this)
               and _inv_key(i) <= key)


def rolling_verdict(ledger: dict, invoices: list[dict], inv: dict, client: dict) -> dict:
    """Is this invoice covered? Same bar as day 30 — measured plus identified —
    against everything billed through it.

    Strictly ahead, not merely level. This used to be `>=` while the day-30
    gate was `>`, so the two disagreed on an exact tie and no sentence on the
    site could describe both. The site now says the same thing in both places,
    and a tie resolves the way every ambiguity in this guarantee resolves:
    for the client. An invoice is raised only when the Record is ahead of it."""
    fees = fees_billed_through(invoices, inv)
    measured = float(ledger.get("value_total") or 0)
    identified = float(ledger.get("identified_unbanked") or 0)
    total = measured + identified
    return {"fee": float(client.get("monthly_fee_usd") or 6000.0), "measured": measured,
            "identified": identified, "total": total, "fees_billed": fees,
            "covered": total > fees, "invoice": inv.get("stripe_invoice_id"),
            "amount": float(inv.get("amount_due") or 0), "period_start": inv.get("period_start"),
            "period_end": inv.get("period_end"), "status": inv.get("status")}


def release_invoice(inv: dict, stripe=None) -> dict:
    """A held draft the Record covers: finalize it without Stripe's own
    auto-send, then send it once. Returns the sent invoice."""
    call = stripe or _stripe
    sid = inv["stripe_invoice_id"]
    finalized = call(f"invoices/{sid}/finalize", {"auto_advance": "false"})
    return call(f"invoices/{sid}/send", {}) or finalized


def refund_invoice(inv: dict, cash_usd: float, why: str, credit_usd: float = 0.0, stripe=None) -> dict:
    """Give money back on a paid invoice: a credit note against it, which
    Stripe turns into a refund of the ACH payment to the account it came from
    and prints on the invoice. `credit_usd` returns any part that was paid from
    the customer balance (a referral month) to that balance, where it came from."""
    call = stripe or _stripe
    sid = inv["stripe_invoice_id"]
    cash, credit = int(round(cash_usd * 100)), int(round(credit_usd * 100))
    data = {"invoice": sid, "amount": cash + credit,
            "memo": ("This month was not covered by your Profit Record, so it is refunded." if why == "gate" else
                     "Refunded when Managed Profit ended: you had paid more than your Profit Record shows."),
            "metadata[hubricon_reason]": why}
    if cash:
        data["refund_amount"] = cash
    if credit:
        data["credit_amount"] = credit
    return call("credit_notes", data, idempotency_key=f"refund-{why}-{sid}-{cash + credit}")


def waive_invoice(inv: dict, client: dict, stripe=None) -> tuple[str, float]:
    """Make the month free. Returns how, and the dollars refunded to the bank.

    A held draft is finalized without sending and voided at once, so the
    client never receives it. An open one is voided: nothing to pay. One ACH
    already settled is refunded, not credited to the next invoice: a credit is
    worth nothing to a client who leaves."""
    call = stripe or _stripe
    sid = inv["stripe_invoice_id"]
    status = inv.get("status")
    if status == "draft":
        call(f"invoices/{sid}/finalize", {"auto_advance": "false"})
    if status in ("draft", "open", "uncollectible"):
        call(f"invoices/{sid}/void", {})
        return "voided", 0.0
    cash = max(0.0, float(inv.get("amount_paid") or 0) - float(inv.get("refunded_usd") or 0))
    total = float((inv.get("raw") or {}).get("total") or 0) / 100 or float(inv.get("amount_due") or 0)
    from_balance = max(0.0, round(total - float(inv.get("amount_paid") or 0), 2))
    refund_invoice(inv, cash, "gate", credit_usd=from_balance, stripe=call)
    return "refunded", cash


def waived_email_blocks(v: dict, how: str, portal_url: str) -> list[dict]:
    when = f" for {str(v['period_start'])[:10]} to {str(v['period_end'])[:10]}" if v.get("period_start") else ""
    return [
        {"p": "We said an invoice your Profit Record hasn't covered is void, and this month that is what happened."},
        {"ol": [
            f"Proven on your Profit Record since day one: ${v['measured']:,.0f}",
            f"Found and filed, not yet banked: ${v['identified']:,.0f}",
            f"Billed through this invoice{when}: ${v['fees_billed']:,.0f}",
        ]},
        {"p": ("So the invoice is void and there is nothing to pay for the month."
               if how == "voided" else
               "That invoice had already settled, so it is refunded in full to the bank account it came "
               "from. Stripe attaches a credit note to the invoice, and ACH refunds take a few business "
               "days to land.")},
        {"button": "See the working", "url": portal_url},
        {"p": "The work carries on. Your Profit Record has to catch up with the bills before another invoice "
              "stands, and that is on us, not you."},
    ]


# -- the exit true-up ---------------------------------------------------------------------

def exit_true_up(ledger: dict, invoices: list[dict]) -> dict:
    """terms §5: the day Managed Profit ends, the Record is checked once more
    against everything billed and not already given back.

    The gate judged each invoice when it was raised, partly on found dollars
    (moves made, claims filed) that can later measure short. So at the exit,
    whatever is billed beyond the Record comes back: unpaid invoices are voided
    first, newest first, whole — never a smaller refund where a void can do it —
    and the gap left after that is refunded on paid invoices, newest first. A
    tie owes nothing either way, the same reading as both gates."""
    measured = float(ledger.get("value_total") or 0)
    identified = float(ledger.get("identified_unbanked") or 0)
    total = measured + identified
    live = [i for i in invoices if i.get("status") in ("open", "paid", "uncollectible")]
    billed = round(sum(still_billed(i) for i in live), 2)
    gap = round(max(0.0, billed - total), 2)
    voids, refunds, left = [], [], gap
    for i in sorted([i for i in live if i.get("status") in ("open", "uncollectible")], key=_inv_key, reverse=True):
        if left <= 0:
            break
        voids.append(i)
        left = round(left - still_billed(i), 2)
    for i in sorted([i for i in live if i.get("status") == "paid"], key=_inv_key, reverse=True):
        if left <= 0:
            break
        room = max(0.0, float(i.get("amount_paid") or 0) - float(i.get("refunded_usd") or 0))
        take = round(min(room, left), 2)
        if take > 0:
            refunds.append((i, take))
            left = round(left - take, 2)
    return {"measured": measured, "identified": identified, "total": total, "billed": billed, "gap": gap,
            "voids": voids, "refunds": refunds, "refunded": round(sum(a for _, a in refunds), 2),
            "voided": round(sum(still_billed(i) for i in voids), 2)}


def exit_subject(t: dict) -> str:
    if t["gap"] <= 0:
        return "Trued up: your Profit Record is ahead of the bills"
    parts = ([f"${t['voided']:,.0f} voided"] if t["voided"] else []) + \
            ([f"${t['refunded']:,.2f} refunded to your bank"] if t["refunded"] else [])
    return "Trued up: " + ", ".join(parts)


def exit_email_blocks(t: dict, portal_url: str) -> list[dict]:
    blocks = [
        {"p": "Managed Profit has ended, and as promised we checked your Profit Record one last time against "
              "what we billed you."},
        {"ol": [
            f"Proven on your Profit Record since day one: ${t['measured']:,.0f}",
            f"Found and filed, not yet banked: ${t['identified']:,.0f}",
            f"Billed to you, after anything already refunded: ${t['billed']:,.0f}",
        ]},
    ]
    if t["gap"] <= 0:
        blocks.append({"p": "The Record is ahead of the bills, so nothing changes hands. You owe nothing more, "
                            "and nothing is owed to you."})
    else:
        done = []
        if t["voided"]:
            done.append(f"the unpaid invoice{'s' if len(t['voids']) > 1 else ''} worth ${t['voided']:,.0f} "
                        f"{'are' if len(t['voids']) > 1 else 'is'} void, so there is nothing more to pay")
        if t["refunded"]:
            done.append(f"${t['refunded']:,.2f} is refunded to the bank account it came from; Stripe attaches "
                        f"a credit note to the invoice, and ACH refunds take a few business days to land")
        blocks.append({"p": f"We billed ${t['gap']:,.0f} more than the Record shows, so: " + "; and ".join(done) + "."})
    blocks += [
        {"button": "Download your full Profit Record", "url": portal_url},
        {"p": "Your data and the full Record export stay free to request, any day. Thank you for the chance to "
              "earn it. If any of these numbers looks wrong, reply and tell me."},
    ]
    return blocks


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
    ACH, net seven days. Nothing recurring is created.

    The invoice is created first and the item attached to it by id. The other
    way round, an item left pending by a failure between the two calls would
    ride along on the next pass's invoice beside its replacement: the share
    billed twice. The invoice carries a key made of the claims it bills, and a
    retry finds it by that key at any distance (Stripe's own idempotency keys
    last 24 hours) and finishes it rather than starting another."""
    call = stripe or _stripe
    customer = ensure_customer(client, call)
    label = (f"Recovery Only — {due['share'] * 100:.0f}% of ${due['recovered']:,.2f} Amazon paid on "
             f"{due['n_claims']} claim(s) we filed, {due['period_start']} to {due['period_end']}")
    claims_key = hashlib.sha256(",".join(sorted(str(c.get("id")) for c in due["claims"])).encode()).hexdigest()[:24]
    recent = call(f"invoices?{urllib.parse.urlencode({'customer': customer, 'limit': 100})}")
    inv = next((i for i in recent.get("data") or []
                if (i.get("metadata") or {}).get("hubricon_claims") == claims_key and i.get("status") != "void"), None)
    if inv is None:
        inv = call("invoices", {
            "customer": customer,
            "collection_method": "send_invoice",
            "days_until_due": NET_DAYS,
            "auto_advance": "false",
            "pending_invoice_items_behavior": "exclude",
            "payment_settings[payment_method_types][0]": "us_bank_account",
            "metadata[hubricon_client_id]": client["id"],
            "metadata[hubricon_plan]": "recovery",
            "metadata[hubricon_claims]": claims_key,
            "metadata[period_start]": str(due["period_start"]),
            "metadata[period_end]": str(due["period_end"]),
        }, idempotency_key=f"recovery-invoice-{claims_key}")
    if inv.get("status", "draft") != "draft":
        # A run that sent it and then failed to record it: it went out once, and once is enough.
        inv["customer"] = customer
        return inv
    if not inv.get("amount_due"):
        call("invoiceitems", {"customer": customer, "invoice": inv["id"], "amount": int(round(due["amount"] * 100)),
                              "currency": "usd", "description": label},
             idempotency_key=f"recovery-item-{claims_key}")
    inv = call(f"invoices/{inv['id']}/finalize", {"auto_advance": "false"}) or inv
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
              f"invoice — there is no monthly fee on this plan, and a month in which nothing lands produces no "
              f"invoice at all. ACH, net seven days, no card on file."},
        *([{"button": "Open the invoice", "url": invoice_url}] if invoice_url else []),
        {"button": "See each claim in Hubricon", "url": portal_url},
        {"p": "Every claim says which report it came from and what Amazon's own record shows. If any of it "
              "looks wrong, reply and tell me."},
    ]
