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


def _stripe(path: str, data: dict | None = None) -> dict:
    key = os.environ["STRIPE_SECRET_KEY"]
    url = f"{STRIPE_API}/{path}"
    body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if body is not None else "GET")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
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


def start_billing(client: dict, price_id: str) -> dict:
    """Create the subscription terms.html §4 describes: invoiced by email, ACH,
    net seven days, no card on file, nothing charged automatically."""
    customer = client.get("stripe_customer_id")
    if not customer:
        found = _stripe(f"customers?{urllib.parse.urlencode({'email': client['contact_email'], 'limit': 1})}")
        customer = (found.get("data") or [{}])[0].get("id")
        if not customer:
            customer = _stripe("customers", {
                "email": client["contact_email"],
                "name": client.get("company_name") or client["contact_email"],
            })["id"]
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


def short_email_blocks(v: dict, portal_url: str) -> list[dict]:
    return [
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
