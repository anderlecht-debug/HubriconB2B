"""FBA reimbursement recovery — the money Amazon already owes the client.

Industry benchmark: 1–3% of FBA revenue is recoverable each year, and
roughly 40% of it dies of neglect because Amazon's claim windows are
short. This model reconciles four sources the client's own seat exports
and turns every discrepancy into a dated, valued, deadline-aware claim:

    warehouse_lost / warehouse_damaged
        Inventory Ledger adjustments with a loss reason, net of "found"
        adjustments and of reimbursements already paid for the same SKU.
        When Amazon publishes its own Unreconciled Quantity we use it —
        it is Amazon agreeing the units are missing.
    refund_no_return
        A settlement Refund with no matching customer return inside the
        return window. The customer kept the money and the goods.
    damaged_return
        A customer return Amazon graded DAMAGED or CARRIER_DAMAGED (its
        responsibility, not the customer's) with no reimbursement.
    reimbursement_reversal
        A reimbursement Amazon later clawed back — reviewed by hand.

Every claim carries an expected value EV = P(approved) × units × value.
Approval probabilities are stated assumptions (Getida reports ~63%
approval even on previously rejected claims; Amazon's own unreconciled
counts approve far more often). Values use the client's landed cost when
on file — Amazon's 2025 policy reimburses at manufacturing cost — and a
labeled 50%-of-price fallback otherwise. The Ledger measures what was
actually paid; the model never books a claim as money.

Claim windows (Amazon policy in force since late 2024, surfaced in the
payload so a policy change is a constant edit, not a rewrite):
    warehouse loss/damage   eligible 30 days after the adjustment, closes at 60
    refund without return   eligible 60 days after the refund, closes at 120
    damaged return          eligible at once, closes 60 days after the return
"""

import hashlib
from datetime import date, timedelta

from .common import num

WAREHOUSE_ELIGIBLE_AFTER_DAYS = 30
WAREHOUSE_DEADLINE_DAYS = 60
REFUND_MIN_AGE_DAYS = 45            # younger refunds are simply "not yet"
REFUND_ELIGIBLE_AFTER_DAYS = 60
REFUND_DEADLINE_DAYS = 120
DAMAGED_RETURN_DEADLINE_DAYS = 60
EXPIRING_WITHIN_DAYS = 14
FOUND_MATCH_WINDOW_DAYS = 45        # a "found" this long after a loss offsets it
REIMBURSEMENT_MATCH_WINDOW_DAYS = 90
NO_COST_VALUE_FRACTION_OF_PRICE = 0.50

P_APPROVE = {
    "warehouse_lost": 0.85,
    "warehouse_damaged": 0.85,
    "carrier_damaged": 0.70,
    "transit_lost": 0.70,
    "refund_no_return": 0.70,
    "damaged_return": 0.60,
    "reimbursement_reversal": 0.50,
}

# Inventory Ledger / Inventory Adjustments reason codes. Amazon's code
# table shifts between report generations, so descriptive reason text is
# classified too and the code map is deliberately explicit and small.
REASON_CODES = {
    "M": "warehouse_lost",      # misplaced
    "D": "warehouse_damaged",   # damaged at fulfillment center
    "Q": "warehouse_damaged",
    "H": "carrier_damaged",
    "K": "carrier_damaged",     # damaged in transit
    "6": "transit_lost",
    "F": "found",
    "5": "found",
    "E": "customer_damaged",    # not Amazon's liability
    "P": "disposed",
    "U": "transfer",
    "O": "transfer",
    "X": "transfer",
    "N": "warehouse_lost",      # unrecoverable
}
REIMBURSABLE = {"warehouse_lost", "warehouse_damaged", "carrier_damaged", "transit_lost"}
DAMAGED_BY_AMAZON = {"DAMAGED", "CARRIER_DAMAGED"}
DAMAGED_NOT_CLAIMABLE = {"CUSTOMER_DAMAGED", "DEFECTIVE", "EXPIRED"}


def _d(value) -> date | None:
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def classify_reason(code: str | None) -> str | None:
    """Loss-class for an adjustment reason; None when it is not a loss."""
    if not code:
        return None
    raw = str(code).strip()
    if raw.upper() in REASON_CODES:
        return REASON_CODES[raw.upper()]
    text = raw.lower()
    if "found" in text:
        return "found"
    if "customer" in text:
        return "customer_damaged"
    if "dispos" in text or "destroy" in text:
        return "disposed"
    if "transit" in text and "lost" in text:
        return "transit_lost"
    if "carrier" in text:
        return "carrier_damaged"
    if "misplac" in text or "lost" in text or "unrecover" in text:
        return "warehouse_lost"
    if "damag" in text:
        return "warehouse_damaged"
    return None


def claim_key(claim_type: str, sku: str, event_date: str, order_id: str | None = None) -> str:
    return hashlib.sha1(f"{claim_type}|{sku}|{event_date}|{order_id or ''}".encode()).hexdigest()[:16]


def unit_values(data: dict) -> dict[str, dict]:
    """sku -> {"value", "basis", "price"} — landed cost preferred."""
    latest_price: dict[str, tuple[str, float]] = {}
    for r in data.get("sku_economics", []):
        price = r.get("avg_sales_price")
        if not price and r.get("units_sold") and r.get("sales"):
            price = float(r["sales"]) / float(r["units_sold"])
        if not price:
            continue
        if r["sku"] not in latest_price or r["period_start"] > latest_price[r["sku"]][0]:
            latest_price[r["sku"]] = (r["period_start"], float(price))
    out = {}
    for r in data.get("cogs_inputs", []):
        cost = sum(float(r.get(f) or 0) for f in (
            "unit_cost_usd", "inbound_freight_per_unit_usd",
            "packaging_per_unit_usd", "other_cost_per_unit_usd"))
        if cost > 0:
            out[r["sku"]] = {"value": cost, "basis": "landed cost on file",
                             "price": latest_price.get(r["sku"], (None, None))[1]}
    for sku, (_, price) in latest_price.items():
        out.setdefault(sku, {"value": price * NO_COST_VALUE_FRACTION_OF_PRICE,
                             "basis": f"{NO_COST_VALUE_FRACTION_OF_PRICE:.0%} of selling price — no landed cost on file",
                             "price": price})
    return out


def _status(today: date, eligible_from: date, deadline: date) -> tuple[str, int]:
    days_left = (deadline - today).days
    if today > deadline:
        return "expired", days_left
    if today < eligible_from:
        return "not_yet_eligible", days_left
    if days_left <= EXPIRING_WITHIN_DAYS:
        return "expiring", days_left
    return "open", days_left


def window_state(claim: dict, today: date) -> str:
    """Where a STORED claim sits today.

    The database holds the lifecycle (detected → filed → paid/denied); the
    window state is a function of the calendar, and only a claim still sitting
    at 'detected' has one. One definition, used by the chart pack and by the
    value ledger, so a tile and the number beside it can never disagree."""
    status = claim.get("status") or "detected"
    if status != "detected":
        return status
    deadline = date.fromisoformat(str(claim["deadline"])[:10]) if claim.get("deadline") else None
    eligible = date.fromisoformat(str(claim["eligible_from"])[:10]) if claim.get("eligible_from") else today
    if deadline is None:
        return "open" if today >= eligible else "not_yet_eligible"
    return _status(today, eligible, deadline)[0]


WAREHOUSE_REIMBURSEMENT_WORDS = ("lost", "damag", "warehouse", "inventory", "missing")


def _consume_reimbursements(losses: list[dict], reimbursements: list[dict], on_match=None) -> None:
    """FIFO: each reimbursement Amazon approved consumes the earliest open loss
    for that SKU inside the match window.

    Two callers want different halves of this. warehouse_claims wants only the
    side effect — a loss Amazon already paid for must not be re-detected as an
    open claim. `settlements` wants the pairing itself, because that pairing IS
    the proof of payment: it is the only place the system holds Amazon's own
    record that money moved. Dropping it on the floor is why a paid claim sat at
    'detected' until its deadline passed and got stamped 'expired' — a win
    filed as a miss.
    """
    for rb in sorted(reimbursements, key=lambda x: x.get("approval_date") or ""):
        reason = (rb.get("reason") or "").lower()
        if not any(w in reason for w in WAREHOUSE_REIMBURSEMENT_WORDS):
            continue
        qty = int(rb.get("quantity_reimbursed_total") or 0)
        d = _d(rb.get("approval_date"))
        if qty <= 0 or d is None:
            continue
        for loss in losses:
            if qty <= 0:
                break
            if loss["sku"] != (rb.get("sku") or rb.get("fnsku")) or loss["source"] == "amazon_unreconciled_quantity":
                continue
            if loss["date"] <= d <= loss["date"] + timedelta(days=REIMBURSEMENT_MATCH_WINDOW_DAYS):
                take = min(loss["units"], qty)
                loss["units"] -= take
                qty -= take
                if on_match:
                    on_match(loss, rb, take, d)


def cash_reimbursed(rb: dict, units: int) -> float:
    """The CASH share of a reimbursement, for `units` of it.

    Amazon reimburses in replacement inventory as often as in money. Units
    replaced in kind are a real remedy, but they are not dollars, and banking
    them on a ledger that claims to measure money returned would be a lie the
    client's own bank statement disproves."""
    total_qty = int(rb.get("quantity_reimbursed_total") or 0)
    cash_qty = rb.get("quantity_reimbursed_cash")
    cash_qty = int(cash_qty) if cash_qty is not None else total_qty
    if cash_qty <= 0 or total_qty <= 0:
        return 0.0
    per_unit = rb.get("amount_per_unit")
    if per_unit is not None and float(per_unit) > 0:
        return round(float(per_unit) * min(units, cash_qty), 2)
    amount = float(rb.get("amount_total") or 0)
    if amount <= 0:
        return 0.0
    # No per-unit figure: split the settled amount across the cash units only.
    return round(amount * (min(units, cash_qty) / cash_qty), 2)


def settlements(data: dict, today: date) -> dict[str, dict]:
    """claim_key -> the reimbursement(s) that closed it, and the cash Amazon
    actually sent.

    Rebuilds the same losses `warehouse_claims` builds and the same claim_key
    each would have carried, then records which reimbursement consumed it. A
    claim that vanishes from detection because Amazon paid it is exactly the
    claim that must be marked paid, not left to expire."""
    ledger = data.get("inventory_ledger") or []
    reimbursements = data.get("fba_reimbursements") or []
    if not ledger or not reimbursements:
        return {}

    losses, founds = _ledger_losses(ledger)
    losses.sort(key=lambda x: x["date"])
    _consume_founds(losses, founds)

    out: dict[str, dict] = {}

    def record(loss, rb, units, approved_on):
        key = claim_key(loss["type"], loss["sku"], loss["date"].isoformat())
        cash = cash_reimbursed(rb, units)
        entry = out.setdefault(key, {
            "claim_key": key, "sku": loss["sku"], "claim_type": loss["type"],
            "units": 0, "paid_amount": 0.0, "paid_at": None,
            "case_id": rb.get("case_id"), "reimbursement_ids": [], "inventory_units": 0,
        })
        entry["units"] += units
        entry["paid_amount"] = round(entry["paid_amount"] + cash, 2)
        if cash <= 0:
            entry["inventory_units"] += units
        entry["case_id"] = entry["case_id"] or rb.get("case_id")
        if rb.get("reimbursement_id"):
            entry["reimbursement_ids"].append(rb["reimbursement_id"])
        iso = approved_on.isoformat()
        entry["paid_at"] = max(entry["paid_at"], iso) if entry["paid_at"] else iso

    _consume_reimbursements(losses, reimbursements, on_match=record)

    for entry in out.values():
        if entry["paid_amount"] > 0 and entry["inventory_units"]:
            entry["note"] = (f"Amazon settled {entry['units']} unit(s): "
                             f"${entry['paid_amount']:,.2f} in cash, "
                             f"{entry['inventory_units']} replaced in inventory.")
        elif entry["paid_amount"] > 0:
            entry["note"] = f"Amazon reimbursed ${entry['paid_amount']:,.2f} across {entry['units']} unit(s)."
        else:
            entry["note"] = (f"Amazon replaced {entry['units']} unit(s) in inventory rather than in cash — "
                             f"the claim is settled, and no dollars are banked.")
    return out


def _claim(claim_type, sku, units, event_date: date, eligible_from: date, deadline: date,
           values: dict, today: date, order_id=None, fnsku=None, asin=None,
           unit_value_override=None, basis_override=None, evidence=None) -> dict:
    v = values.get(sku, {})
    unit_value = unit_value_override if unit_value_override is not None else v.get("value")
    basis = basis_override or v.get("basis") or "no price or cost on file — units only"
    value = units * unit_value if unit_value is not None else None
    p = P_APPROVE[claim_type]
    status, days_left = _status(today, eligible_from, deadline)
    return {
        "claim_key": claim_key(claim_type, sku, event_date.isoformat(), order_id),
        "claim_type": claim_type,
        "sku": sku, "fnsku": fnsku, "asin": asin, "order_id": order_id,
        "event_date": event_date.isoformat(),
        "units": int(units),
        "unit_value": num(unit_value),
        "value": num(value),
        "value_basis": basis,
        "p_approve": p,
        "expected_value": num(value * p) if value is not None else None,
        "eligible_from": eligible_from.isoformat(),
        "deadline": deadline.isoformat(),
        "days_left": days_left,
        "status": status,
        "evidence": evidence or {},
    }


def _ledger_losses(ledger: list[dict]) -> tuple[list[dict], list[dict]]:
    """Reimbursable losses and offsetting "found" adjustments, read out of the
    Inventory Ledger. Split out so the settlement pass rebuilds exactly the
    same losses the claims were detected from — two readings of this file that
    could drift apart is two different answers about what Amazon owes."""
    losses, founds = [], []
    for r in ledger:
        etype = (r.get("event_type") or "Adjustments").lower()
        if "adjust" not in etype:
            continue
        cls = classify_reason(r.get("reason"))
        if cls is None:
            continue
        qty = r.get("quantity")
        d = _d(r.get("event_date"))
        if d is None or qty is None:
            continue
        sku = r.get("sku") or r.get("fnsku")
        if not sku:
            continue
        if cls == "found":
            if float(qty) > 0:
                founds.append({"sku": sku, "date": d, "qty": int(qty)})
            continue
        if cls not in REIMBURSABLE:
            continue
        unreconciled = r.get("unreconciled_qty")
        if unreconciled is not None:
            units = int(unreconciled)
            source = "amazon_unreconciled_quantity"
        else:
            units = int(-float(qty)) if float(qty) < 0 else 0
            source = "adjustment_quantity"
        if units <= 0:
            continue
        losses.append({"sku": sku, "fnsku": r.get("fnsku"), "asin": r.get("asin"),
                       "date": d, "units": units, "type": cls, "source": source,
                       "reference": r.get("reference_id"), "reason": r.get("reason")})
    return losses, founds


def _consume_founds(losses: list[dict], founds: list[dict]) -> None:
    """A unit Amazon later found was never lost: FIFO, same as reimbursements."""
    for f in sorted(founds, key=lambda x: x["date"]):
        for loss in losses:
            if f["qty"] <= 0:
                break
            if loss["sku"] != f["sku"] or loss["source"] == "amazon_unreconciled_quantity":
                continue
            if loss["date"] <= f["date"] <= loss["date"] + timedelta(days=FOUND_MATCH_WINDOW_DAYS):
                take = min(loss["units"], f["qty"])
                loss["units"] -= take
                f["qty"] -= take


def warehouse_claims(ledger: list[dict], reimbursements: list[dict], values: dict, today: date) -> list[dict]:
    losses, founds = _ledger_losses(ledger)
    # FIFO offsets: found units and reimbursed units consume the earliest open loss
    losses.sort(key=lambda x: x["date"])
    _consume_founds(losses, founds)
    _consume_reimbursements(losses, reimbursements)

    claims = []
    for loss in losses:
        if loss["units"] <= 0:
            continue
        claims.append(_claim(
            loss["type"], loss["sku"], loss["units"], loss["date"],
            loss["date"] + timedelta(days=WAREHOUSE_ELIGIBLE_AFTER_DAYS),
            loss["date"] + timedelta(days=WAREHOUSE_DEADLINE_DAYS),
            values, today, fnsku=loss["fnsku"], asin=loss["asin"],
            evidence={"source": loss["source"], "reference_id": loss["reference"],
                      "reason": loss["reason"]},
        ))
    return claims


def refund_claims(transactions: list[dict], returns: list[dict], reimbursements: list[dict],
                  values: dict, today: date) -> list[dict]:
    returned: dict[tuple, int] = {}
    for r in returns:
        key = (r.get("order_id"), r.get("sku") or r.get("fnsku"))
        returned[key] = returned.get(key, 0) + int(r.get("quantity") or 0)
        returned[(r.get("order_id"), None)] = returned.get((r.get("order_id"), None), 0) + int(r.get("quantity") or 0)
    reimbursed_orders = {
        rb.get("amazon_order_id") for rb in reimbursements
        if rb.get("amazon_order_id") and "return" in (rb.get("reason") or "").lower()
    }
    claims = []
    seen = set()
    for t in transactions:
        if (t.get("txn_type") or "").strip().lower() != "refund":
            continue
        order_id, sku = t.get("order_id"), t.get("sku")
        d = _d(t.get("txn_datetime"))
        if not order_id or not sku or d is None:
            continue
        if (today - d).days < REFUND_MIN_AGE_DAYS or order_id in reimbursed_orders:
            continue
        qty = abs(int(t.get("quantity") or 1)) or 1
        amount = abs(float(t.get("product_sales") or t.get("total") or 0))
        back = returned.get((order_id, sku), returned.get((order_id, None), 0))
        short = qty - back
        if short <= 0 or (order_id, sku) in seen:
            continue
        seen.add((order_id, sku))
        per_unit = amount / qty if amount else None
        claims.append(_claim(
            "refund_no_return", sku, short, d,
            d + timedelta(days=REFUND_ELIGIBLE_AFTER_DAYS),
            d + timedelta(days=REFUND_DEADLINE_DAYS),
            values, today, order_id=order_id,
            unit_value_override=per_unit,
            basis_override="refunded amount per unit — Amazon reimburses at its determined value, so this is the ceiling",
            evidence={"refund_amount": num(amount), "refunded_units": qty, "returned_units": back},
        ))
    return claims


def damaged_return_claims(returns: list[dict], reimbursements: list[dict], values: dict, today: date) -> tuple[list[dict], dict]:
    reimbursed_orders = {
        rb.get("amazon_order_id") for rb in reimbursements
        if rb.get("amazon_order_id") and any(w in (rb.get("reason") or "").lower() for w in ("return", "damag"))
    }
    claims, excluded = [], {"customer_or_defective": 0, "already_reimbursed": 0, "sellable": 0}
    for r in returns:
        disp = (r.get("detailed_disposition") or "").strip().upper()
        status = (r.get("status") or "").lower()
        sku = r.get("sku") or r.get("fnsku")
        d = _d(r.get("return_date"))
        if not sku or d is None:
            continue
        if disp in DAMAGED_NOT_CLAIMABLE:
            excluded["customer_or_defective"] += 1
            continue
        if disp not in DAMAGED_BY_AMAZON:
            excluded["sellable"] += 1
            continue
        if "reimburs" in status or r.get("order_id") in reimbursed_orders:
            excluded["already_reimbursed"] += 1
            continue
        claims.append(_claim(
            "damaged_return", sku, int(r.get("quantity") or 1), d, d,
            d + timedelta(days=DAMAGED_RETURN_DEADLINE_DAYS),
            values, today, order_id=r.get("order_id"), fnsku=r.get("fnsku"), asin=r.get("asin"),
            evidence={"disposition": disp, "status": r.get("status"), "reason": r.get("reason")},
        ))
    return claims, excluded


def reversal_claims(reimbursements: list[dict], values: dict, today: date) -> list[dict]:
    claims = []
    for rb in reimbursements:
        kind = (rb.get("original_reimbursement_type") or "").lower()
        amount = float(rb.get("amount_total") or 0)
        if "revers" not in kind and amount >= 0:
            continue
        d = _d(rb.get("approval_date"))
        sku = rb.get("sku") or rb.get("fnsku")
        if d is None or not sku:
            continue
        qty = abs(int(rb.get("quantity_reimbursed_total") or 1)) or 1
        claims.append(_claim(
            "reimbursement_reversal", sku, qty, d, d, d + timedelta(days=WAREHOUSE_DEADLINE_DAYS),
            values, today, order_id=rb.get("amazon_order_id"), fnsku=rb.get("fnsku"), asin=rb.get("asin"),
            unit_value_override=abs(amount) / qty,
            basis_override="the reversed reimbursement amount",
            evidence={"reimbursement_id": rb.get("reimbursement_id"),
                      "original_reimbursement_id": rb.get("original_reimbursement_id"), "reason": rb.get("reason")},
        ))
    return claims


def reimbursed_recently(reimbursements: list[dict], today: date, days: int = 90) -> tuple[float, int]:
    total, n = 0.0, 0
    for rb in reimbursements:
        d = _d(rb.get("approval_date"))
        amount = float(rb.get("amount_total") or 0)
        if d and (today - d).days <= days and amount > 0:
            total += amount
            n += 1
    return total, n


def run(data: dict, rng=None, simulations=None, today: date | None = None) -> dict:
    today = today or date.today()
    values = unit_values(data)
    ledger = data.get("inventory_ledger", []) or []
    reimbursements = data.get("fba_reimbursements", []) or []
    returns = data.get("fba_returns", []) or []
    transactions = data.get("settlement_transactions", []) or []

    claims = warehouse_claims(ledger, reimbursements, values, today)
    claims += refund_claims(transactions, returns, reimbursements, values, today)
    damaged, excluded = damaged_return_claims(returns, reimbursements, values, today)
    claims += damaged
    claims += reversal_claims(reimbursements, values, today)

    for c in claims:
        c["details"] = {"basis": (
            f"{c['units']} unit(s) of {c['sku']} valued at {c['value_basis']}; "
            f"claim window {c['eligible_from']} → {c['deadline']}; "
            f"expected value applies a {c['p_approve']:.0%} approval assumption."
        )}
    claims.sort(key=lambda c: ({"expiring": 0, "open": 1, "not_yet_eligible": 2, "expired": 3}[c["status"]],
                               -(c["expected_value"] or 0)))

    live = [c for c in claims if c["status"] in ("open", "expiring")]
    by_type: dict[str, dict] = {}
    for c in claims:
        b = by_type.setdefault(c["claim_type"], {"n": 0, "units": 0, "value": 0.0, "ev": 0.0, "live_value": 0.0})
        b["n"] += 1
        b["units"] += c["units"]
        b["value"] += c["value"] or 0
        b["ev"] += c["expected_value"] or 0
        if c["status"] in ("open", "expiring"):
            b["live_value"] += c["value"] or 0
    reimbursed_90d, reimbursed_n = reimbursed_recently(reimbursements, today)

    data_present = {k: bool(data.get(k)) for k in
                    ("inventory_ledger", "fba_reimbursements", "fba_returns", "settlement_transactions")}
    return {
        "status": "ok" if any(data_present.values()) else "insufficient_data",
        "as_of": today.isoformat(),
        "claims": claims,
        # Claims Amazon has already settled. They are absent from `claims`
        # precisely BECAUSE they were paid — the FIFO offset consumed them — so
        # without this the sweep would let each one expire as an unclaimed miss.
        "settlements": settlements(data, today),
        "summary": {
            "n_claims": len(claims),
            "n_live": len(live),
            "live_value": num(sum(c["value"] or 0 for c in live)),
            "live_ev": num(sum(c["expected_value"] or 0 for c in live)),
            "expiring_value": num(sum(c["value"] or 0 for c in claims if c["status"] == "expiring")),
            "n_expiring": sum(1 for c in claims if c["status"] == "expiring"),
            "expired_value": num(sum(c["value"] or 0 for c in claims if c["status"] == "expired")),
            "pending_value": num(sum(c["value"] or 0 for c in claims if c["status"] == "not_yet_eligible")),
            "reimbursed_90d": num(reimbursed_90d),
            "reimbursed_90d_count": reimbursed_n,
            "by_type": {k: {kk: (num(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                        for k, v in by_type.items()},
            "returns_excluded": excluded,
        },
        "data_present": data_present,
        "assumptions": [
            f"Approval probabilities by claim class: {', '.join(f'{k} {v:.0%}' for k, v in P_APPROVE.items())}",
            "Units valued at landed cost when on file (Amazon reimburses at manufacturing cost); "
            f"otherwise {NO_COST_VALUE_FRACTION_OF_PRICE:.0%} of selling price, labeled as such",
            f"Windows: warehouse loss eligible after {WAREHOUSE_ELIGIBLE_AFTER_DAYS}d, closes {WAREHOUSE_DEADLINE_DAYS}d; "
            f"refund without return eligible after {REFUND_ELIGIBLE_AFTER_DAYS}d, closes {REFUND_DEADLINE_DAYS}d; "
            f"damaged return closes {DAMAGED_RETURN_DEADLINE_DAYS}d",
            "Inbound-shipment shortages need the shipment reconciliation export (not yet collected) — not claimed here",
        ],
    }
