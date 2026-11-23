"""The fee-approval question, and the counter that can kill the fee.

BUILD_PLAN M6: "the meter question, the 20-install kill counter." Whether a
brand that has SEEN a proven dollar will agree to pay a share of it is the one
question the whole offer stands on, and it is answered by brands, not by us.
So it is asked the same way of every store, at the same moment, and read with
a rule written down before the first answer came in.

THE QUESTION
------------
When a store's first proven dollar is banked (a positive measured dollar on
its Record, never a shadow call, never hindsight, never a ledger entry), its
shopify_shops row moves from fee_question 'none' to 'ask', stamped. The app
then asks the brand once whether it approves the fee on proven dollars, and
record() stores 'approved' or 'declined'. A question left open for
ASK_WINDOW_DAYS counts as declined when the rule is read: silence is not a yes.

THE RULE (pre-registered 23 Nov 2026; these constants do not move)
------------------------------------------------------------------
  * The cohort is the first DECIDE_AT (20) stores that saw proof, in the order
    they were asked. Stores after the 20th are reported, not counted.
  * Before 20 stores have seen proof, the verdict is "undecided", whatever the
    answers so far say. No early peeking either way.
  * Kill: fewer than 2 in 10 approve (approvals < KILL_BELOW x 20 = 4), counted
    as soon as even every open question turning yes could not reach the line.
  * Confirm: at least 4 in 10 approve (approvals >= CONFIRM_AT x 20 = 8),
    counted as soon as it is reached.
  * Neither, with every cohort answer in: "between", which means the fee holds
    and nothing is confirmed.
  * Otherwise: "undecided", waiting on open answers.

digest_lines() is what the operator's daily digest prints.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

SHOPS = "shopify_shops"
DECIDE_AT = 20
KILL_BELOW = 0.2        # under 2 in 10 approving: the fee is killed
CONFIRM_AT = 0.4        # 4 in 10 or more approving: the fee is confirmed
ASK_WINDOW_DAYS = 14    # an unanswered question counts as declined after this
SAW_PROOF = ("ask", "approved", "declined")
ANSWERS = ("approved", "declined")

UNDECIDED, KILL, CONFIRM, BETWEEN = "undecided", "kill", "confirm", "between"


def _ts(v) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _iso(v: datetime) -> str:
    return v.astimezone(UTC).isoformat().replace("+00:00", "Z")


def first_proven(statements: list[dict]) -> float | None:
    """The first proven dollar figure from hwm.run's statements: the cumulative
    total of the first month it is above zero. None when nothing is proven."""
    for s in statements or []:
        if float(s.get("cumulative") or 0) > 0:
            return float(s["cumulative"])
    return None


def ask_patch(row: dict, statements: list[dict], now=None) -> dict | None:
    """The shopify_shops patch that opens the question, or None: only once,
    only when a proven dollar is banked."""
    if (row or {}).get("fee_question", "none") != "none":
        return None
    usd = first_proven(statements)
    if usd is None:
        return None
    return {"fee_question": "ask", "fee_question_at": _iso(_ts(now) or datetime.now(UTC)),
            "first_proven_usd": round(usd, 2)}


def answer_patch(row: dict, approved: bool, now=None) -> dict:
    """The brand's answer. Only an open question can be answered, and only once."""
    state = (row or {}).get("fee_question", "none")
    if state != "ask":
        raise ValueError(f"no open fee question (state {state!r})")
    return {"fee_question": "approved" if approved else "declined",
            "fee_answered_at": _iso(_ts(now) or datetime.now(UTC))}


def mark_ask(db, shop: str, row: dict, statements: list[dict], now=None) -> bool:
    patch = ask_patch(row, statements, now)
    if patch:
        db.table(SHOPS).update(patch).eq("shop_domain", shop).execute()
    return bool(patch)


def record(db, shop: str, approved: bool, now=None) -> dict:
    rows = db.table(SHOPS).select("*").eq("shop_domain", shop).execute().data or []
    patch = answer_patch(rows[0] if rows else {}, approved, now)
    db.table(SHOPS).update(patch).eq("shop_domain", shop).execute()
    return patch


def state_of(row: dict, now: datetime) -> str:
    """approved, declined (an expired question counts as declined) or open."""
    s = row.get("fee_question")
    if s in ANSWERS:
        return s
    asked = _ts(row.get("fee_question_at"))
    if asked is not None and now - asked >= timedelta(days=ASK_WINDOW_DAYS):
        return "declined"
    return "open"


def rule(rows: list[dict], now=None) -> dict:
    """The pre-registered verdict over every store's row."""
    now = _ts(now) or datetime.now(UTC)
    saw = sorted((r for r in rows if r.get("fee_question") in SAW_PROOF),
                 key=lambda r: (_ts(r.get("fee_question_at")) or now, r.get("shop_domain") or ""))
    cohort = saw[:DECIDE_AT]
    states = [state_of(r, now) for r in cohort]
    a, d, o = states.count("approved"), states.count("declined"), states.count("open")
    kill_n, confirm_n = KILL_BELOW * DECIDE_AT, CONFIRM_AT * DECIDE_AT
    if len(saw) < DECIDE_AT:
        verdict = UNDECIDED
    elif a >= confirm_n:
        verdict = CONFIRM
    elif a + o < kill_n:
        verdict = KILL
    elif o == 0:
        verdict = BETWEEN
    else:
        verdict = UNDECIDED
    return {"verdict": verdict, "saw_proof": len(saw), "cohort": len(cohort), "approved": a, "declined": d,
            "open": o, "after_cohort": len(saw) - len(cohort), "decide_at": DECIDE_AT,
            "kill_below": KILL_BELOW, "confirm_at": CONFIRM_AT}


def lines(result: dict) -> list[str]:
    r = result
    head = (f"Fee question (pre-registered, decide at {r['decide_at']} stores that saw proof): "
            f"{r['saw_proof']} saw proof; of the first {r['cohort']}, {r['approved']} approved, "
            f"{r['declined']} declined (silence past {ASK_WINDOW_DAYS} days counts as declined), {r['open']} open.")
    say = {
        UNDECIDED: (f"  Verdict: UNDECIDED. {max(0, r['decide_at'] - r['saw_proof'])} more store(s) must see proof "
                    "before the rule is read." if r["saw_proof"] < r["decide_at"]
                    else "  Verdict: UNDECIDED, waiting on open answers in the cohort."),
        KILL: (f"  Verdict: KILL. Fewer than {r['kill_below'] * 10:g} in 10 approve, and the open answers cannot "
               "change that. The fee as offered is dead: rethink it before charging anyone."),
        CONFIRM: f"  Verdict: CONFIRM. At least {r['confirm_at'] * 10:g} in 10 approve. The fee holds.",
        BETWEEN: (f"  Verdict: BETWEEN. Every cohort answer is in; approval is under {r['confirm_at'] * 10:g} in 10 "
                  f"and at least {r['kill_below'] * 10:g} in 10. Not killed, not confirmed."),
    }[r["verdict"]]
    return [head, say]


def digest_lines(db, now=None) -> list[str]:
    try:
        rows = db.table(SHOPS).select("shop_domain, fee_question, fee_question_at").execute().data or []
    except Exception as err:
        return [f"Fee question: could not be read ({type(err).__name__}).", ""]
    if not rows:
        return []
    return lines(rule(rows, now)) + [""]
