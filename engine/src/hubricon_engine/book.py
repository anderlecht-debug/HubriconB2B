"""What each kind of move has delivered across the book: measured over promised.

`replay.score` answers "is the number we put on this client's moves
calibrated?" for one client. With one client it cannot answer the question a
new client's first month turns on: when the engine promises $1,000 on a price
step, what does a price step actually deliver? That answer is a property of
the book, not of any account, and it is the data asset a later,
bench-validated change will use to price day-one promises — a first month's
expected dollars scaled by what that kind of move has realised elsewhere. This
module builds the asset. It does not use it.

REPORT ONLY. Nothing here writes, and nothing reads what it returns: no
promise, expected dollar, measured dollar or billing figure moves because of
it. It reads the `directives` of consenting accounts, scores each account's
moves with `replay.score`, the arithmetic of `hubricon replay --rescore` (measured
dollars over promised, on the moves that carry both), and pools by move kind
across accounts. A test holds it to reading and never writing.

THE ARITHMETIC. Per move kind: the realisation ratio Σ measured / Σ promised
over every scored move of that kind in the book, the number of accounts and
of moves behind it, and a 90% band from resampling ACCOUNTS (not moves: an
account's moves share its seller, its catalogue and its season, so they are
not independent draws, and a band from resampling moves would be too narrow),
seeded so the same book prints the same band. The same pooled over every kind.

CONSENT AND FLOORS. Only clients who granted the separate `network` consent
(terms §10), are current and are not internal are read — the same sources as
fleet.py, through the same function. Below BOOK_MIN_ACCOUNTS accounts with a
scored move the whole book refuses (`insufficient_accounts`), and a kind below
that many accounts, or below replay's own MIN_SCORED_FOR_CALIBRATION moves,
refuses for itself (`insufficient_accounts`, `insufficient_moves`), each
with no number. Five accounts is where a resampled band stops being a
handful of resamples whose ends are single accounts' own ratios.

WHAT IT CANNOT TELL YOU. Whether a kind's ratio will hold for an account
unlike the ones behind it: no category, size or season is on the row. Why a
kind under-delivers: the ratio is a verdict on the promise, not a diagnosis.
Anything about moves not yet measured, which are most of a young book's.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from . import replay
from .fleet import consenting_accounts
from .models.common import num

BOOK_MIN_ACCOUNTS = 5
BOOK_MIN_MOVES = replay.MIN_SCORED_FOR_CALIBRATION
BOOK_BOOTSTRAP = 2000
BOOK_SEED = 20260925
ALL_KINDS = "all kinds"


def _reading(ratio: float) -> str:
    if ratio < replay.MIN_REALISATION:
        return f"below the {replay.MIN_REALISATION:.2f} a correct engine clears: over-promising"
    if ratio > replay.MAX_REALISATION:
        return f"above {replay.MAX_REALISATION:.2f}: the promise was too small"
    return f"inside the {replay.MIN_REALISATION:.2f}–{replay.MAX_REALISATION:.2f} band a correct engine shows"


def _row(kind: str, per_account: dict[str, list[dict]], seed: int) -> dict:
    """One kind: the pooled ratio with its account-resampled band, or a named
    refusal with no number."""
    accounts = {a: moves for a, moves in per_account.items() if moves}
    n_accounts, n_moves = len(accounts), sum(len(m) for m in accounts.values())
    out = {"kind": kind, "n_accounts": n_accounts, "n_moves": n_moves, "realisation_ratio": None,
           "ratio_p5": None, "ratio_p95": None}
    if n_accounts < BOOK_MIN_ACCOUNTS:
        return {**out, "status": "insufficient_accounts",
                "basis": f"{n_accounts} account(s) with a scored move of this kind; {BOOK_MIN_ACCOUNTS} are needed"}
    if n_moves < BOOK_MIN_MOVES:
        return {**out, "status": "insufficient_moves",
                "basis": f"{n_moves} scored move(s); {BOOK_MIN_MOVES} are needed"}
    promised = np.array([sum(m["promised"] for m in moves) for moves in accounts.values()])
    measured = np.array([sum(m["measured"] for m in moves) for moves in accounts.values()])
    if promised.sum() <= 0:
        return {**out, "status": "no_promise", "basis": "the moves on file promised nothing to measure against"}
    ratio = float(measured.sum() / promised.sum())
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_accounts, (BOOK_BOOTSTRAP, n_accounts))
    p, m = promised[idx].sum(axis=1), measured[idx].sum(axis=1)
    boots = m[p > 0] / p[p > 0]
    row = {**out, "status": "ok", "realisation_ratio": num(ratio, 4), "reading": _reading(ratio),
           "basis": (f"{n_moves} scored moves across {n_accounts} accounts: measured over promised; "
                     f"band from resampling the accounts ({BOOK_BOOTSTRAP:,} draws)")}
    if boots.size < 0.9 * BOOK_BOOTSTRAP:
        # a tenth of the resampled books promise nothing to divide by: a band
        # built from the rest would be a band of the lucky draws
        return {**row, "basis": (f"{n_moves} scored moves across {n_accounts} accounts: measured over "
                                 f"promised; no band — {BOOK_BOOTSTRAP - boots.size:,} of {BOOK_BOOTSTRAP:,} "
                                 f"resampled books promised nothing to measure against")}
    return {**row, "ratio_p5": num(float(np.quantile(boots, 0.05)), 4),
            "ratio_p95": num(float(np.quantile(boots, 0.95)), 4)}


def table(scored_by_account: dict[str, list[dict]], seed: int = BOOK_SEED) -> dict:
    """Pure: {account: replay.score(...)['scored']} -> the book, by move kind.
    Only moves that carry both a promise and a measurement count, as in
    replay.score's own ratio."""
    scored = {a: [s for s in items if s.get("promised") is not None and s.get("measured") is not None]
              for a, items in scored_by_account.items()}
    scored = {a: items for a, items in scored.items() if items}
    base = {"n_accounts": len(scored), "min_accounts": BOOK_MIN_ACCOUNTS, "min_moves": BOOK_MIN_MOVES,
            "seed": seed, "target": [replay.MIN_REALISATION, replay.MAX_REALISATION]}
    if len(scored) < BOOK_MIN_ACCOUNTS:
        return {**base, "status": "insufficient_accounts", "kinds": [],
                "basis": (f"{len(scored)} consenting account(s) with a scored move; {BOOK_MIN_ACCOUNTS} are "
                          f"needed before a ratio across accounts means anything")}
    by_kind: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for a, items in scored.items():
        for s in items:
            by_kind[str(s.get("kind"))][a].append(s)
    rows = [_row(kind, by_kind[kind], seed) for kind in sorted(by_kind)]
    rows.append(_row(ALL_KINDS, scored, seed))
    return {**base, "status": "ok", "kinds": rows,
            "basis": ("measured over promised by move kind, replay.score's arithmetic on each consenting "
                      "account, pooled across accounts; report only — no promise, expected dollar or "
                      "billing figure reads it")}


def run(db) -> dict:
    """Read every consenting account's directives, score each with replay,
    pool. Reads; never writes."""
    scored = {}
    for client in consenting_accounts(db):
        directives = db.table("directives").select("*").eq("client_id", client["id"]).execute().data or []
        scored[client["id"]] = replay.score(directives)["scored"]
    return table(scored)


def render(out: dict) -> str:
    lines = [f"The book: {out['status']} — {out['basis']}"]
    for r in out.get("kinds", []):
        head = f"  {r['kind']:<22} {r['n_accounts']:>3} accounts {r['n_moves']:>5} moves  "
        if r["status"] == "ok":
            band = (f" ({r['ratio_p5']:.2f}–{r['ratio_p95']:.2f})" if r.get("ratio_p5") is not None
                    else " (no band: see --json)")
            lines.append(f"{head}{r['realisation_ratio']:.2f}× promised{band} — {r['reading']}")
        else:
            lines.append(f"{head}{r['status']}: {r['basis']}")
    if out["status"] == "ok":
        lines.append("  Report only: nothing here changes a promise, an expected dollar or an invoice.")
    return "\n".join(lines)
