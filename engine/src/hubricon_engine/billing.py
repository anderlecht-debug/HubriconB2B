"""The guarantee, enforced by the code that writes the invoice.

HUBRICON_SPEC.md, "The mechanics: when the guarantee triggers" (2026-09-30):

    Each month closes on a fixed date. The attribution engine runs once on the
    closed month [monthly.py] ... That produces one number: attributed profit
    for the month. The scoreboard shows it first, always before any invoice.
    If attributed profit clears the $6,000 fee, Stripe bills the fee against
    it. If it does not, the month is unbilled: no invoice is generated, no
    charge, no credit, no balance carried into next month.

So billing runs monthly and in arrears. The Proving Month (and any month a
referral earned) is free whatever it measures. When it ends the subscription is
created with a trial to the end of the first billed month, so Stripe's first
invoice is raised the day that month ends; every later invoice is raised the day
the next one ends. api/stripe-webhook.js holds each at draft. The gate below
judges it against the month it bills, once that month has been measured
(record_months, written by the weekly sweep a week after the month ends):
above the fee it is finalized and sent; at or below, it is voided before anyone
sees it. A month is judged on its own number. Nothing found but not yet measured
counts, and no surplus or shortfall carries from one month to the next.

**Refunded, not credited.** A month that a dispute later takes under the fee,
after ACH has settled, goes back to the bank account it came from, through a
credit note on the invoice.

**Trued up at the exit.** The day Managed Profit ends, every billed month is
checked once more against its own number after disputes: unpaid invoices for
months that no longer clear are voided, paid ones refunded. The month in progress
when a client leaves is never invoiced.

**The recovery-only plan.** The smaller door: no retainer, a share of the
reimbursements Amazon actually paid on claims we filed, invoiced at month end.
"""

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

STRIPE_API = "https://api.stripe.com/v1"
# Every call is made at the version the webhook's Node SDK pins (stripe@18.5 in
# package.json), so the engine and api/stripe-webhook.js read the same shapes.
# Unpinned, each call takes the account's default version, which is whatever
# it was the day the account was opened.
STRIPE_VERSION = "2025-08-27.basil"
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


def due_to_start(client: dict, today: date | None = None) -> tuple[bool, str, dict | None]:
    """Have the free months ended, with no subscription yet? Returns the first
    billed month too: its last day is where the trial runs to."""
    from . import monthly
    today = today or date.today()
    if not client.get("retainer_started_at"):
        return False, "no retainer start date on file — record the yes with `hubricon retainer`", None
    if client.get("stripe_subscription_id"):
        return False, "already billing", None
    months = monthly.billing_months(client, today)
    billed = [m for m in months if not m["free"]]
    if not billed:
        free = int(client.get("free_months") or 1)
        return False, f"month {len(months)} of {free} free", None
    return True, f"month {billed[0]['index'] + 1} has begun — the first that can be billed", billed[0]


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


def start_billing(client: dict, price_id: str, first_month: dict | None = None, stripe=None) -> dict:
    """Create the subscription terms.html §4 describes: invoiced by email, ACH,
    net seven days, no card on file, nothing charged automatically.

    In arrears: the subscription trials to the day after the first billed month
    ends, so the first invoice Stripe raises is for a month that has happened,
    and the gate can judge it on that month's number.

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
    params = {
        "customer": customer,
        "items[0][price]": price_id,
        "collection_method": "send_invoice",
        "days_until_due": NET_DAYS,
        "payment_settings[payment_method_types][0]": "us_bank_account",
        "metadata[hubricon_client_id]": client["id"],
    }
    if first_month is not None:
        trial_end = datetime.combine(first_month["end"] + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        params["trial_end"] = str(int(trial_end.timestamp()))
        params["metadata[hubricon_first_billed_month]"] = str(first_month["index"])
    return call("subscriptions", params,
                idempotency_key=f"subscribe-{client['id']}-{str(client.get('retainer_started_at') or '')[:10]}")


def cancel_subscription(subscription_id: str, stripe=None) -> dict:
    """End the retainer in Stripe at once: no final invoice, no proration.
    terms §5 — the month after the email is simply never invoiced."""
    call = stripe or _stripe
    return call(f"subscriptions/{subscription_id}", {"invoice_now": "false", "prorate": "false"},
                method="DELETE")


def started_email_blocks(first_month: dict, fee: float, portal_url: str) -> list[dict]:
    """The free months are over; from here a month is billed only if it clears the fee."""
    ends = first_month["end"].strftime("%B %-d")
    return [
        {"p": "Your Proving Month is over. From today, every month is judged on its own number."},
        {"p": f"When a month ends, your Profit Record measures what every move earned in it, on that month's "
              f"exports. If that clears ${fee:,.0f}, the month's invoice goes out by email: ACH, net seven days, "
              f"no card on file, nothing charged automatically. If it does not, the month is free. No invoice, "
              f"no credit, nothing carried into the next one."},
        {"p": f"Your first billed month runs to {ends}. You will see its number on your scoreboard before any "
              f"invoice exists."},
        {"button": "Open your scoreboard", "url": portal_url},
        {"p": "Cancel with one email whenever you like. The month in progress when you leave is never invoiced."},
    ]


# -- the gate: each invoice against the month it bills ---------------------------------

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
           and float(i.get("amount_due") or 0) > 0
           and (not started or not i.get("period_start") or str(i["period_start"])[:10] >= started)]
    return sorted(out, key=_inv_key)


def invoice_month(inv: dict, months: list[dict]) -> dict | None:
    """The month an invoice bills, in arrears: the last retainer month that ended
    before the invoice's period began (Stripe raises it the day that month ends).
    None when no month has ended yet, which a correctly trialed subscription
    never produces."""
    raw = str(inv.get("period_start") or inv.get("issued_at") or "")[:10]
    if not raw:
        return None
    begins = date.fromisoformat(raw)
    ended = [m for m in months if m["end"] < begins]
    return ended[-1] if ended else None


def month_verdict(rows: list[dict], month: dict, client: dict) -> dict:
    """One month's number against the fee, across every channel the client sells
    on, after disputes. `measured` is False until every channel's row exists:
    the invoice waits for the month, never the other way round."""
    from . import channels, monthly
    fee = float(client.get("monthly_fee_usd") or 6000.0)
    mine = [r for r in rows if int(r["month_index"]) == month["index"]]
    have = {r.get("channel") or "amazon" for r in mine}
    want = set(channels.channels_for(client.get("platform")))
    total = round(sum(monthly.standing(r) for r in mine), 2)
    return {"month": month, "fee": fee, "total": total, "measured": want <= have,
            "free": bool(month["free"]), "clears": (not month["free"]) and want <= have and total > fee,
            "disputed": round(sum(float(r.get("disputed_usd") or 0) for r in mine), 2)}


def month_label(month: dict) -> str:
    return f"{month['start'].strftime('%b %-d')} – {month['end'].strftime('%b %-d, %Y')}"


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


def cleared_month_email_blocks(v: dict, portal_url: str) -> list[dict]:
    return [
        {"p": f"Your Profit Record measured ${v['total']:,.0f} for {month_label(v['month'])}, from that month's "
              f"own exports. That clears the ${v['fee']:,.0f} fee by ${v['total'] - v['fee']:,.0f}, so the "
              f"month's invoice is on its way: ACH, net seven days."},
        {"button": "See every move behind that number", "url": portal_url},
        {"p": "Each move on your Record says how we know what it earned. If any of it looks wrong, reply and "
              "tell me: a dollar the record cannot defend comes off, and the month is judged again."},
    ]


def unbilled_email_blocks(v: dict, how: str, portal_url: str) -> list[dict]:
    blocks = [
        {"p": f"Your Profit Record measured ${v['total']:,.0f} for {month_label(v['month'])}. That is under the "
              f"${v['fee']:,.0f} fee, so the month is free."},
        {"p": "No invoice, no credit, nothing carried into next month. You did not have to ask for this, and "
              "there is nothing to do."},
    ]
    if how == "refunded":
        blocks.append({"p": "This month's invoice had already been paid, so it is refunded in full to the bank "
                            "account it came from. Stripe attaches a credit note, and ACH refunds take a few "
                            "business days to land."})
    blocks += [
        {"button": "See the month's working", "url": portal_url},
        {"p": "The work carries on. Next month is judged on its own number."},
    ]
    return blocks


# -- the exit true-up ---------------------------------------------------------------------

def exit_true_up(rows: list[dict], months: list[dict], invoices: list[dict], client: dict) -> dict:
    """terms §5: the day Managed Profit ends, every billed month is checked once
    more against its own number after disputes. An invoice for a month that no
    longer clears is voided if unpaid and refunded in full if paid. A month that
    was never measured cannot be shown to clear, so its invoice comes back too:
    under this guarantee the doubt is always the client's."""
    live = [i for i in invoices if i.get("status") in BILLED_STATUSES and not _is_recovery(i)]
    voids, refunds, judged = [], [], []
    for inv in sorted(live, key=_inv_key):
        m = invoice_month(inv, months)
        v = month_verdict(rows, m, client) if m else None
        judged.append((inv, v))
        if v and v["clears"]:
            continue
        if inv.get("status") in ("open", "uncollectible"):
            voids.append(inv)
        else:
            room = max(0.0, float(inv.get("amount_paid") or 0) - float(inv.get("refunded_usd") or 0))
            if room > 0:
                refunds.append((inv, round(room, 2)))
    billed = round(sum(still_billed(i) for i in live), 2)
    return {"billed": billed, "voids": voids, "refunds": refunds, "judged": judged,
            "voided": round(sum(still_billed(i) for i in voids), 2),
            "refunded": round(sum(a for _, a in refunds), 2),
            "gap": round(sum(still_billed(i) for i in voids) + sum(a for _, a in refunds), 2)}


def exit_subject(t: dict) -> str:
    if t["gap"] <= 0:
        return "Trued up: every month you paid for cleared the fee"
    parts = ([f"${t['voided']:,.0f} voided"] if t["voided"] else []) + \
            ([f"${t['refunded']:,.2f} refunded to your bank"] if t["refunded"] else [])
    return "Trued up: " + ", ".join(parts)


def exit_email_blocks(t: dict, portal_url: str) -> list[dict]:
    lines = []
    for inv, v in t["judged"]:
        if v is None:
            continue
        lines.append(f"{month_label(v['month'])}: ${v['total']:,.0f} on your Record against the "
                     f"${v['fee']:,.0f} fee — {'cleared' if v['clears'] else 'did not clear'}")
    blocks = [{"p": "Managed Profit has ended, and as promised we checked every month we billed once more, each "
                    "against its own number."}]
    if lines:
        blocks.append({"ol": lines})
    if t["gap"] <= 0:
        blocks.append({"p": "Every month you paid for cleared the fee, so nothing changes hands. The month that was "
                            "in progress when you left is never invoiced."})
    else:
        done = []
        if t["voided"]:
            done.append(f"the unpaid invoice{'s' if len(t['voids']) > 1 else ''} worth ${t['voided']:,.0f} "
                        f"{'are' if len(t['voids']) > 1 else 'is'} void, so there is nothing more to pay")
        if t["refunded"]:
            done.append(f"${t['refunded']:,.2f} is refunded to the bank account it came from; Stripe attaches "
                        f"a credit note to the invoice, and ACH refunds take a few business days to land")
        blocks.append({"p": "For the months that did not clear: " + "; and ".join(done) + "."})
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
