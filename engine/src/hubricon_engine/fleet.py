"""A change on the platform's side, seen across accounts: the network effect.

When Amazon moves a fee it moves it for everyone, and each client's own sweep
(models/anomaly.py) is right to be strict about it: thousands of tests a
sweep, Benjamini–Hochberg across all of them, so a seller is never told about
noise. Strict means late. A 5% FBA fee step inside per-unit fees that wander
by 3% is reported by an account's own sweep in about three accounts in ten,
three exports after it, and a small catalogue may never report it. The same
step in six accounts at once is not a coincidence, even when no single account
can call it. That is the one thing a book of accounts knows that none of its
accounts does, and every consenting account makes it know it sooner.

THE SAME ARITHMETIC TWICE: SKUs within an account, then accounts within the
book. A platform change moves every SKU that pays the fee at once; noise, and
a single SKU re-measured into a new size tier, move one.

THE PER-ACCOUNT QUESTION. For a fee type k an account holds m series, one per
SKU, and on each the changepoint scan's p-value and its split — the row's
index on its stored series, kept by the account's own control or demoted,
which keeps its params and its series and loses only the finding fields. A
series is a HIT for direction d when its p ≤ SERIES_P, its split steps the way
d says by at least MIN_STEP, and its onset is inside the lookback. The
account FLAGS (k, d) when its hits inside one window of WINDOW_DAYS reach h*,
the smallest count that m series of pure noise reach with probability at most
ALPHA_ACCOUNT. Under the simulated null of models/null_calibration.py each
series is a hit with probability at most SERIES_P (the direction and the
window only make it rarer), so P(flag) ≤ P(Bin(m, SERIES_P) ≥ h*), and that
number is the account's own false-alarm rate π_a: known, at most
ALPHA_ACCOUNT, and different for a catalogue of two SKUs (0.0025) and one of
forty (0.048) because a count is discrete. A 5% fee step in a series that
wanders by 3% is a coin toss on one SKU and unmistakable on twelve.

THE FLEET TEST. For each (platform, fee type, direction) cell, the agreeing
accounts are the most that fall inside one window of WINDOW_DAYS. Under the
null — no platform change, accounts independent — the number of accounts
flagging (k, d) anywhere in the lookback is at most a Poisson-binomial with
success probabilities π_a over the accounts that carry the fee type, and the
count inside the best window can only be smaller. So P(X ≥ x) is a valid,
conservative p-value for the agreement, and scanning the windows costs
nothing. Benjamini–Hochberg at FLEET_Q runs across every testable cell. A
change is DECLARED when at least MIN_ACCOUNTS agree and its q-value clears;
its size is the median of the agreeing accounts' ratios, with a band from
resampling those accounts. Two things keep it conservative on purpose, at
both levels: the direction is not halved (a null that leans one way — fees
drift up — cannot sneak in through a symmetry we assumed), and the window is
not credited. The second is also the margin for the one thing the noise null
does not count, an account's own real change: at the defaults a window is a
quarter of the lookback, so account-specific changes timed independently of
one another can run to about three times ALPHA_ACCOUNT per account before the
stated level stops holding.

WHAT LEAVES AN ACCOUNT. An event: fee type, direction, approximate date, size
as a ratio. Never a dollar figure, a SKU, an ASIN, a campaign or a name:
`account_events` returns nothing else, `series_evidence` never reads the item
id, and a test serialises the event to hold both to that. The event also
carries π_a for the arithmetic, and π_a depends on how many SKUs carry the fee
(a count is discrete), so it never leaves the pass: it enters the result only
through the aggregate p-value, and nothing per account is stored, printed or
sent. Only clients who granted the separate `network` consent (terms §10), are
current, and are not internal are read as sources (`consenting_accounts`). A
recipient's own rows are read for one purpose — to tell that recipient
whether the change shows in their own exports yet — and never enter the
detection.

FLOORS, AS NAMED REFUSALS. Fewer than MIN_ACCOUNTS consenting accounts with a
fresh run: the whole pass is `insufficient_accounts`. A fee type fewer than
MIN_ACCOUNTS carry, or a direction fewer than MIN_ACCOUNTS agree on:
`insufficient_accounts` for that cell. A testable cell whose agreement could be
coincidence at the stated level: `not_significant`. None of them carries a size.

WHO IS TOLD. `RECIPIENT_POLICY`, one constant, is the founder's call: every
current client on the platform who pays that fee (the consent governs the
source, not the recipient), or only the accounts that contribute. One platform
change is announced once per client: the alert row carries the change's id,
and a unique index in supabase/migrations/20260925000003_network.sql makes a
second announcement a database error, not a habit.

WHAT IT CANNOT TELL YOU. Why the fee moved. A common cause that is not the
platform — consenting accounts re-packaging in the same month, a shared prep
centre, the same seasonal shift in product mix — reads as a platform change,
because the null assumes accounts independent. Shopify's fees: an order
export carries a published-rate estimate until a payouts export lands, and an
estimate cannot see a platform change, so no Shopify fee type is scanned. A
reimbursement-policy or carrier-rate change: no reimbursement-per-unit or
label-cost series is scanned. Storage fees: a dollar total per period moves
with the stock everyone builds before the fourth quarter, which is a common
cause the null would read as the platform — and anomaly.py's all-fees-per-unit
series carries storage inside it, so it is not scanned either, and a new fee
line that lands in "other fees" is not seen. A promotion that carries many
accounts' prices across a referral-fee price threshold at once reads as a
referral-rate change; a scheduled seasonal fee (the holiday peak fulfilment
fee) is a change on the platform's side and is announced as one, with the
founder told whether it matches the rate card on file. The exact size of a
small change: it is measured on the accounts that showed it, and they are the
ones noise pushed the same way, so a 5% step in 3% noise with five of eight
accounts agreeing reads 5.8% (band 4.8–6.4%); a change that reaches some size
tiers and not others reads as its typical SKU, smaller than it is for the
tiers it reached. Anything sooner than three exports after the change: the
changepoint scan cannot place a step with fewer points on its far side. Two
real changes of the same fee type and direction inside the lookback: each
account reports the window more of its SKUs show, so a pass sees one of them,
and two less than MATCH_DAYS apart are one change here. And which accounts
stood behind a change: nothing downstream of `detect` can say.
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from statistics import median

import numpy as np
from scipy.stats import binom

from . import calibration, channels
from .models import fee_schedule
from .models.common import num
from .models.null_calibration import benjamini_hochberg

CONSENT_KIND = "network"
ALERT_MODULE = "network"
MIGRATION = "supabase/migrations/20260925000003_network.sql"

# The per-account bar: an account flags a fee type when so many of its series
# step the same way in one window that noise would do it at most this often.
# One account in twenty is generous on purpose: the agreement across
# accounts, not the account, is what the level below is spent on.
ALPHA_ACCOUNT = 0.05
# A series counts as a hit at this p-value from its own changepoint scan.
SERIES_P = 0.05
# ...and when its step is at least this large. A deterministic fee that wobbles
# by a cent on a flat baseline has a vanishing p-value and no news in it.
MIN_STEP = 0.01
# The fleet's false-discovery level, across every (fee type, direction) cell.
# Stricter than the per-client sweep's 0.05 (anomaly.FDR_Q) because a declared
# change is announced to every client it applies to: a false one is wrong in
# every inbox at once.
FLEET_Q = 0.01
# The floor: fewer agreeing accounts than this is `insufficient_accounts`,
# whatever the arithmetic says. Three is also the smallest book in which an
# aggregate is not one account's figure beside another's.
MIN_ACCOUNTS = 3
# A fee change dated the 15th lands in one monthly export or the next, so two
# accounts' onsets for the same change sit up to a month apart; 45 days holds
# two adjacent month starts and not three.
WINDOW_DAYS = 45
# How far back an onset may sit and still be news. A monthly series needs three
# exports after a step before the changepoint scan can place it, so the step a
# sweep can first see is already ninety days old.
LOOKBACK_DAYS = 183
# A run older than this does not speak for the account this week.
FRESH_DAYS = 21
# A detection this close to a recorded change of the same fee type and
# direction is that change again (its onset moves as accounts join).
MATCH_DAYS = 2 * WINDOW_DAYS
BAND_BOOTSTRAP = 2000
BAND_SEED = 20260925
# Sources are current clients only: a former client's data informs nobody.
SOURCE_STATUSES = ("pending", "active")

# THE FOUNDER'S CALL. Who is told about a declared change:
#   "every_client"       every current client on the platform who pays that fee.
#                        The consent governs the source, not the recipient.
#   "contributors_only"  only clients who granted `network` themselves
#                        (give-to-get: warn others, be warned).
# Nothing else in the engine reads this; changing it changes nothing but who
# gets the alert.
RECIPIENT_POLICY = "every_client"
RECIPIENT_POLICIES = ("every_client", "contributors_only")
RECIPIENT_STATUSES = ("pending", "active")

# The fee types the network scans: rates measured from the platform's own
# records. Not scanned, each for a reason the module docstring gives: Shopify's
# fee lines (a published-rate estimate until a payouts export lands), storage
# (a dollar total that moves with the stock), and anomaly.py's all-fees-per-
# unit series, which carries storage inside it and would bring the fourth
# quarter's stock build back in through the side door.
KINDS = {
    "fba_fee_per_unit": {"platform": "amazon", "scope": "sku", "metric": "fba_fee_per_unit",
                         "label": "FBA fulfilment fee per unit",
                         "subject": "the FBA fulfilment fee per unit"},
    "referral_rate": {"platform": "amazon", "scope": "sku", "metric": "referral_rate",
                      "label": "referral fee rate",
                      "subject": "the referral fee rate (the share of each sale Amazon keeps)"},
}
DIRECTIONS = ("up", "down")
PERSISTED = ("declared", "not_significant")
# Fees up is the adverse direction for every kind above.
SEVERITY = {"up": "warning", "down": "info"}
VISIBILITY = ("visible", "early", "not_yet", "already_in", "no_series")
VISIBILITY_SENTENCE = {
    "visible": "Your own exports show it too.",
    "early": "Your own exports show the start of it, not yet enough to call on your account alone.",
    "not_yet": "It does not show in your own exports yet; we are watching for it.",
    "already_in": "Your exports on file begin after it, so the fees in them already include it.",
}
PORTAL_URL = os.environ.get("INTAKE_BASE_URL", "https://www.hubricon.com") + "/portal"  # mirrors cli.PORTAL_URL


# ── the pure layer ──────────────────────────────────────────────────────────

def _day(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _median_day(days: list[date]) -> date:
    """The lower median: always one of the onsets, never a date between two."""
    ordered = sorted(days)
    return ordered[(len(ordered) - 1) // 2]


def _sig(value: float, digits: int = 4) -> float:
    """A probability to four significant figures: rounding 1e-12 to ten decimal
    places would record a coincidence as impossible."""
    return float(f"{float(value):.{digits}g}")


def kind_of(row: dict, channel: str) -> str | None:
    """The network's fee type for an anomaly row, or None when it is not one."""
    for key, spec in KINDS.items():
        if (spec["platform"] == channel and row.get("scope") == spec["scope"]
                and row.get("metric") == spec["metric"]):
            return key
    return None


def _is_test(row: dict) -> bool:
    return row.get("p_value") is not None and row.get("p_basis") not in (None, "unavailable")


def _shape(cp: dict) -> dict:
    """Where the series stepped, which way, and by what ratio — read off the
    changepoint row's own split on its stored series, whether the account's
    control kept the row or demoted it (a demoted row keeps its params and its
    series and loses only the finding fields)."""
    none = {"direction": None, "onset": None, "ratio": None}
    details = cp.get("details") or {}
    index = (details.get("params") or {}).get("index")
    series = details.get("series") or []
    n = cp.get("n")
    if index is None or not series or n is None:
        return none
    values = [p.get("v") for p in series]
    if any(v is None for v in values):
        return none
    # the stored series is the last SERIES_TAIL points; the index counts from
    # the first point of the whole series
    i = int(index) - (int(n) - len(series))
    if i < 1 or i >= len(series):
        return none
    before = float(np.mean(values[:i]))
    after = float(np.mean(values[i:]))
    direction = "up" if after > before else "down" if after < before else None
    return {"direction": direction, "onset": _day(series[i].get("t")),
            "ratio": after / before if before > 0 else None,
            "points": [(_day(p.get("t")), float(p["v"])) for p in series]}


def _ratio_at(points: list[tuple], onset: date) -> float | None:
    """A series' after/before ratio split at a given date rather than at its
    own best split: no series is measured where it happens to look largest."""
    before = [v for t, v in points if t is not None and t < onset]
    after = [v for t, v in points if t is not None and t >= onset]
    if not before or not after:
        return None
    base = float(np.mean(before))
    return float(np.mean(after)) / base if base > 0 else None


def series_evidence(rows: list[dict] | None, channel: str) -> dict[str, list[dict]]:
    """kind -> one entry per series: the changepoint scan's p-value on it and
    its shape. One test per series; the CUSUM row on the same series is the
    same evidence twice. The item id is never read: nothing past this function
    knows which SKU a series was, and the series' own points stay inside the
    account (account_events measures the size on them and returns a ratio)."""
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows or []:
        kind = kind_of(r, channel)
        if kind is None or r.get("detector") != "changepoint" or not _is_test(r):
            continue
        out[kind].append({"p": float(r["p_value"]), **_shape(r)})
    return dict(out)


@lru_cache(maxsize=1024)
def account_threshold(m: int, series_p: float = SERIES_P, alpha: float = ALPHA_ACCOUNT) -> tuple[int, float]:
    """(h*, π): the fewest hits among m series that noise reaches with
    probability at most `alpha`, and that probability — the account's own
    false-alarm rate. Exact binomial tail; a count is discrete, so π sits at or
    below `alpha` and depends on m."""
    for h in range(1, m + 1):
        tail = float(binom.sf(h - 1, m, series_p))
        if tail <= alpha:
            return h, tail
    return m + 1, 0.0


def account_events(rows: list[dict] | None, channel: str, today: date,
                   lookback_days: int = LOOKBACK_DAYS, window_days: int = WINDOW_DAYS) -> dict[str, dict]:
    """What leaves one account: per fee type, the account's own false-alarm
    rate for the question and, for each direction it flags, the approximate
    onset (the median onset of the hits in its best window) and the size as a
    ratio. The size is the median, over EVERY series of the fee type, of its
    after/before ratio split at that onset: measured on the hits alone it would
    be measured where noise happened to push the same way (the winner's
    curse), and a planted 8% step would read as 9%. Nothing else — no SKU, no
    dollar, no identifier; π_a reflects how many SKUs carry the fee, which is
    why nothing per account outlives the pass (see the module docstring)."""
    earliest = today - timedelta(days=lookback_days)
    events: dict[str, dict] = {}
    for kind, series in series_evidence(rows, channel).items():
        h_star, pi = account_threshold(len(series))
        flags = {}
        for d in DIRECTIONS:
            hits = [(None, s["onset"], s["ratio"]) for s in series
                    if s["direction"] == d and s["p"] <= SERIES_P and s["onset"] is not None
                    and earliest <= s["onset"] <= today
                    and s["ratio"] is not None and abs(s["ratio"] - 1.0) >= MIN_STEP]
            best = _best_window(hits, window_days)
            if best and len(best) >= h_star:
                onset = _median_day([h[1] for h in best])
                ratios = [r for r in (_ratio_at(s["points"], onset) for s in series if s.get("points"))
                          if r is not None]
                flags[d] = {"onset": onset, "ratio": float(median(ratios)) if ratios else None}
        events[kind] = {"platform": channel, "pi": pi, "flags": flags}
    return events


def poisson_binomial_sf(probs, k: int) -> float:
    """P(X ≥ k) for X a sum of independent Bernoulli(p_i). Exact, by the
    convolution recurrence, and summed from the tail so a small probability is
    not the difference of two numbers near one."""
    probs = [float(p) for p in probs]
    if k <= 0:
        return 1.0
    if k > len(probs):
        return 0.0
    dist = np.zeros(len(probs) + 1)
    dist[0] = 1.0
    for p in probs:
        dist[1:] = dist[1:] * (1.0 - p) + dist[:-1] * p
        dist[0] *= 1.0 - p
    return float(min(1.0, dist[k:].sum()))


def _best_window(flags: list[tuple], window_days: int) -> list[tuple]:
    """The most flags (account, onset, ratio) inside one window of
    `window_days`; on a tie the later window, which is the newer change."""
    ordered = sorted(flags, key=lambda f: f[1])
    best: list[tuple] = []
    for i, (_, start, _) in enumerate(ordered):
        members = [f for f in ordered[i:] if (f[1] - start).days <= window_days]
        if len(members) >= len(best):
            best = members
    return best


def pooled_size(ratios: list[float], seed: int = BAND_SEED,
                draws: int = BAND_BOOTSTRAP) -> tuple[float, float, float]:
    """The median ratio across accounts and a 90% band from resampling the
    accounts: a book of five is not a population, and the band says so."""
    r = np.asarray(ratios, dtype=float)
    rng = np.random.default_rng(seed)
    medians = np.median(r[rng.integers(0, r.size, (draws, r.size))], axis=1)
    return float(np.median(r)), float(np.quantile(medians, 0.05)), float(np.quantile(medians, 0.95))


def _blank(kind: str, spec: dict, d: str, n_eligible: int) -> dict:
    return {"platform": spec["platform"], "kind": kind, "label": spec["label"], "direction": d,
            "n_eligible": n_eligible, "n_accounts": 0, "status": None, "onset": None,
            "window_start": None, "window_end": None, "pooled_ratio": None, "ratio_low": None,
            "ratio_high": None, "p_value": None, "q_value": None, "basis": None}


def detect(events_by_account: dict[str, dict], today: date, *, min_accounts: int = MIN_ACCOUNTS,
           q: float = FLEET_Q, window_days: int = WINDOW_DAYS) -> dict:
    """Every (platform, fee type, direction) cell, tested; see the module
    docstring. `events_by_account` maps an opaque key to `account_events`
    output. Pure: reads nothing, writes nothing."""
    pool = [a for a, ev in events_by_account.items() if ev]
    base = {"as_of": today.isoformat(), "n_accounts": len(pool), "min_accounts": min_accounts,
            "fdr_q": q, "alpha_account": ALPHA_ACCOUNT, "window_days": window_days}
    if len(pool) < min_accounts:
        return {**base, "status": "insufficient_accounts", "cells": [], "n_tests": 0,
                "basis": (f"{len(pool)} consenting account(s) with a fresh run; {min_accounts} are needed "
                          f"before any agreement between them means anything")}

    cells, private = [], []
    for kind, spec in KINDS.items():
        eligible = {a: ev[kind] for a, ev in events_by_account.items() if kind in ev}
        for d in DIRECTIONS:
            cell = _blank(kind, spec, d, len(eligible))
            cells.append(cell)
            if len(eligible) < min_accounts:
                cell["status"] = "insufficient_accounts"
                cell["basis"] = (f"{len(eligible)} consenting account(s) carry this fee type; "
                                 f"{min_accounts} are needed")
                private.append(None)
                continue
            flags = [(a, e["flags"][d]["onset"], e["flags"][d]["ratio"])
                     for a, e in eligible.items() if d in e["flags"]]
            members = _best_window(flags, window_days)
            cell["n_accounts"] = len(members)
            if len(members) < min_accounts:
                cell["status"] = "insufficient_accounts"
                cell["basis"] = (f"{len(members)} of {len(eligible)} accounts agree inside {window_days} days; "
                                 f"{min_accounts} are needed")
                # testable, but it can never be declared: it counts in the
                # family and cannot pull the threshold down for another cell
                private.append({"p": 1.0, "members": []})
                continue
            private.append({"p": poisson_binomial_sf([e["pi"] for e in eligible.values()], len(members)),
                            "members": members})

    family = [(c, s) for c, s in zip(cells, private) if s is not None]
    rejected, adjusted, _cutoff = (benjamini_hochberg([s["p"] for _, s in family], q)
                                   if family else ([], [], 0.0))
    for (cell, s), keep, q_value in zip(family, rejected, adjusted):
        if cell["n_accounts"] < min_accounts:
            continue
        onsets = sorted(m[1] for m in s["members"])
        cell.update(p_value=_sig(s["p"]), q_value=_sig(q_value), onset=_median_day(onsets),
                    window_start=onsets[0], window_end=onsets[-1])
        agree = f"{cell['n_accounts']} of {cell['n_eligible']} consenting accounts carrying this fee type"
        if not keep:
            cell["status"] = "not_significant"
            cell["basis"] = (f"{agree} agree inside {window_days} days, but that many could agree by "
                             f"coincidence: q = {q_value:.2g} against {q}")
            continue
        cell["status"] = "declared"
        ratios = [m[2] for m in s["members"] if m[2] is not None]
        if len(ratios) >= min_accounts:
            mid, lo, hi = pooled_size(ratios)
            cell.update(pooled_ratio=num(mid, 4), ratio_low=num(lo, 4), ratio_high=num(hi, 4))
        cell["basis"] = (f"{agree} show it inside {window_days} days; that many agreeing by coincidence has "
                         f"probability {s['p']:.2g} (Poisson-binomial over each account's own false-alarm "
                         f"rate), q = {q_value:.2g} across {len(family)} tests")
    return {**base, "status": "ok", "cells": cells, "n_tests": len(family),
            "basis": (f"{len(pool)} consenting account(s) with a fresh run; each flags a fee type at its own "
                      f"false-alarm rate (at most {ALPHA_ACCOUNT}); Benjamini–Hochberg at {q} across "
                      f"{len(family)} (fee type, direction) tests; {min_accounts} agreeing accounts at least")}


def schedule_note(cell: dict) -> str | None:
    """For the founder, never the client: does a declared FBA fee change match
    the rate card on file (models/fee_schedule.EFFECTIVE), or post-date it?"""
    if cell.get("kind") != "fba_fee_per_unit" or cell.get("onset") is None:
        return None
    card = date.fromisoformat(fee_schedule.EFFECTIVE)
    onset = _day(cell["onset"])
    # a mid-month card lands in that month's export or the next
    if abs((onset - card).days) <= WINDOW_DAYS:
        return f"matches the rate card on file (effective {fee_schedule.EFFECTIVE})"
    if onset > card:
        return (f"after the rate card on file (effective {fee_schedule.EFFECTIVE}): check whether Amazon "
                f"published a new schedule, and update models/fee_schedule.py if it did")
    return None


def _pct(ratio: float, direction: str) -> int:
    """The move in the change's own direction, in whole percent; a band end
    past no change at all reads as zero, never as a move the other way."""
    signed = (float(ratio) - 1.0) if direction == "up" else (1.0 - float(ratio))
    return max(0, int(round(signed * 100)))


def visibility(own_rows: list[dict] | None, cell: dict, today: date) -> str:
    """Is the change in this recipient's own exports yet? Their data, for them.

    visible   their own sweep already reports it (flagged after their own
              false-discovery control), same direction, near the window, on
              as many SKUs as the network's own bar asks of them — one SKU
              re-measured into a dearer tier is that SKU's news, not this
    early     it clears the network's per-account bar, not their own control
    not_yet   they carry the fee type and show nothing near the window
    already_in their exports begin after it: no step can ever show, and the
              fees on file are already the new ones
    no_series they carry no such fee line: the change is not theirs to hear about
    """
    channel, kind, d = cell["platform"], cell["kind"], cell["direction"]
    mine = [r for r in own_rows or [] if kind_of(r, channel) == kind]
    series = (series_evidence(mine, channel)).get(kind) or []
    if not series:
        return "no_series"
    starts = [min(days) for days in ([t for t, _ in s.get("points") or [] if t is not None] for s in series)
              if days]
    if starts and min(starts) >= _day(cell["window_start"]):
        return "already_in"
    lo = _day(cell["window_start"]) - timedelta(days=WINDOW_DAYS)
    hi = _day(cell["window_end"]) + timedelta(days=WINDOW_DAYS)
    reported = {r.get("item_id") for r in mine
                if r.get("flagged") and r.get("direction") == d
                and _day(r.get("since")) and lo <= _day(r.get("since")) <= hi}
    if len(reported) >= account_threshold(len(series))[0]:
        return "visible"
    flag = ((account_events(mine, channel, today).get(kind) or {}).get("flags") or {}).get(d)
    if flag and lo <= flag["onset"] <= hi:
        return "early"
    return "not_yet"


def alert_for(cell: dict, state: str) -> dict:
    """One alert: what changed, around when, how big, how many accounts stand
    behind it, and whether the recipient's own exports show it yet. Client
    copy: HUBRICON.md's retired vocabulary does not appear."""
    spec = KINDS[cell["kind"]]
    d = cell["direction"]
    platform = channels.label(cell["platform"])
    verb = "rose" if d == "up" else "fell"
    month = _day(cell["onset"]).strftime("%B %Y")
    size = ""
    if cell.get("pooled_ratio") is not None:
        pct = _pct(cell["pooled_ratio"], d)
        size = f", by about {pct}% on the typical SKU" if pct >= 1 else ", by less than 1% on the typical SKU"
        lo, hi = sorted((_pct(cell["ratio_low"], d), _pct(cell["ratio_high"], d)))
        if lo != hi:
            size += f" (somewhere between {lo}% and {hi}%)"
    message = (f"Across {cell['n_accounts']} accounts we watch, {spec['subject']} {verb} around {month}{size}. "
               f"That is a change on {platform}'s side, not something in your account. "
               + VISIBILITY_SENTENCE[state])
    return {"severity": SEVERITY[d], "module": ALERT_MODULE, "message": message}


# ── the database layer ──────────────────────────────────────────────────────

def consenting_accounts(db) -> list[dict]:
    """The only sources: clients who granted `network` and have not withdrawn
    it, who are current, and who are not internal — through the same gate the
    calibration consent uses (calibration.consented_clients). Nothing else is
    read as a source, anywhere in this module."""
    return calibration.consented_clients(db, CONSENT_KIND, SOURCE_STATUSES)


def _run_channel(client: dict, run: dict) -> str:
    return ((run.get("params") or {}).get("channel") or channels.client_channel(client) or "amazon")


def latest_rows(db, client: dict, channel: str, today: date, fresh: bool = True) -> list[dict] | None:
    """The anomaly rows of the client's newest succeeded run on `channel` that
    ran the change detection (a `hubricon run --models margin` by hand does
    not), or None. A SOURCE must be fresh to speak for its account this week;
    a recipient's newest detection, however old, is still the best answer to
    whether they pay the fee and whether it shows yet (`fresh=False`)."""
    runs = (db.table("model_runs").select("id, started_at, params").eq("client_id", client["id"])
            .eq("status", "succeeded").order("started_at", desc=True).limit(20).execute().data)
    for run in (r for r in runs if _run_channel(client, r) == channel):
        out = (db.table("model_outputs").select("payload").eq("run_id", run["id"])
               .eq("model", "anomaly").limit(1).execute().data)
        if not out:
            continue
        started = _day(run.get("started_at"))
        if fresh and (started is None or started < today - timedelta(days=FRESH_DAYS)):
            return None
        return (out[0].get("payload") or {}).get("rows") or []
    return None


def collect(db, today: date) -> dict[str, dict]:
    """Events from every consenting account with a fresh run: the only place
    this module reads a source's rows."""
    platforms = {spec["platform"] for spec in KINDS.values()}
    events: dict[str, dict] = {}
    for client in consenting_accounts(db):
        ev: dict[str, dict] = {}
        for channel in channels.channels_for(client.get("platform")):
            if channel not in platforms:
                continue
            rows = latest_rows(db, client, channel, today)
            if rows:
                ev.update(account_events(rows, channel, today))
        if ev:
            events[client["id"]] = ev
    return events


def recipients(db, platform: str) -> list[dict]:
    """Who hears about a change on `platform`, under RECIPIENT_POLICY."""
    if RECIPIENT_POLICY not in RECIPIENT_POLICIES:
        raise ValueError(f"RECIPIENT_POLICY is {RECIPIENT_POLICY!r}; choose one of {RECIPIENT_POLICIES}")
    clients = db.table("clients").select("*").in_("status", list(RECIPIENT_STATUSES)).execute().data
    clients = [c for c in clients if platform in channels.channels_for(c.get("platform"))]
    if RECIPIENT_POLICY == "contributors_only":
        contributors = {c["id"] for c in consenting_accounts(db)}
        clients = [c for c in clients if c["id"] in contributors]
    return clients


def _schema_problem(db) -> str | None:
    try:
        db.table("platform_changes").select("id").limit(1).execute()
        db.table("alerts").select("platform_change_id").limit(1).execute()
    except Exception as err:   # the migration is the founder's to apply
        return f"{MIGRATION} not applied ({str(err)[:80]}); nothing recorded, nobody alerted"
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(cell: dict) -> dict:
    return {"platform": cell["platform"], "kind": cell["kind"], "label": cell["label"],
            "direction": cell["direction"], "onset": _day(cell["onset"]).isoformat(),
            "window_start": _day(cell["window_start"]).isoformat(),
            "window_end": _day(cell["window_end"]).isoformat(),
            "n_accounts": cell["n_accounts"], "n_eligible": cell["n_eligible"], "min_accounts": MIN_ACCOUNTS,
            "pooled_ratio": cell["pooled_ratio"], "ratio_low": cell["ratio_low"], "ratio_high": cell["ratio_high"],
            "p_value": cell["p_value"], "q_value": cell["q_value"], "fdr_q": FLEET_Q,
            "alpha_account": ALPHA_ACCOUNT, "status": cell["status"],
            "basis": "; ".join(x for x in (cell["basis"], schedule_note(cell)) if x)}


def _match(existing: list[dict], cell: dict) -> dict | None:
    onset = _day(cell["onset"])
    near = [r for r in existing if r.get("platform") == cell["platform"] and r.get("kind") == cell["kind"]
            and r.get("direction") == cell["direction"] and _day(r.get("onset"))
            and abs((_day(r["onset"]) - onset).days) <= MATCH_DAYS]
    return min(near, key=lambda r: abs((_day(r["onset"]) - onset).days)) if near else None


def persist(db, cells: list[dict], n_tests: int, today: date | None = None) -> dict[int, dict]:
    """Write the cells worth keeping to platform_changes. A detection near a
    recorded change of the same fee type and direction updates that row, so
    the change keeps one id across weeks. A declaration is sticky: a week in
    which it is not re-confirmed leaves the row as it was."""
    q = db.table("platform_changes").select("*")
    if today is not None:
        # nothing older than the lookback and the match distance can match
        q = q.gte("onset", (today - timedelta(days=LOOKBACK_DAYS + MATCH_DAYS)).isoformat())
    existing = q.execute().data or []
    saved: dict[int, dict] = {}
    for i, cell in enumerate(cells):
        if cell["status"] not in PERSISTED:
            continue
        row = {**_record(cell), "n_tests": n_tests, "last_seen_at": _now()}
        match = _match(existing, cell)
        if match and match.get("status") == "declared" and cell["status"] == "not_significant":
            saved[i] = match
            continue
        if cell["status"] == "declared":
            row["first_declared_at"] = (match or {}).get("first_declared_at") or row["last_seen_at"]
        if match:
            db.table("platform_changes").update(row).eq("id", match["id"]).execute()
            match.update(row)
            saved[i] = match
        else:
            inserted = db.table("platform_changes").insert(row).execute().data[0]
            existing.append(inserted)
            saved[i] = inserted
    return saved


def _told(db, change_id: str) -> dict[str, dict]:
    """client_id -> the alert already written for this change (one query)."""
    rows = (db.table("alerts").select("id, client_id, message, severity, emailed_at")
            .eq("platform_change_id", change_id).execute().data or [])
    return {r["client_id"]: r for r in rows}


def announce(db, cells: list[dict], saved: dict[int, dict], today: date, send: bool = False,
             log=print) -> list[dict]:
    """One alert per recipient per declared change, never twice. Returns the
    alerts newly written. With `send`, an alert written earlier without an
    email (a run without --alert, a send that failed) is emailed now: the row
    makes the announcement once-only, the email catches up. A failure on one
    recipient is logged and the rest go on."""
    declared = [(c, saved[i]) for i, c in enumerate(cells) if c["status"] == "declared" and i in saved]
    if not declared:
        return []
    by_platform: dict[str, list[dict]] = {}
    own_rows: dict[tuple[str, str], list[dict] | None] = {}
    pending: dict[str, dict] = {}
    for cell, row in declared:
        platform = cell["platform"]
        if platform not in by_platform:
            by_platform[platform] = recipients(db, platform)
        told = _told(db, row["id"])
        for client in by_platform[platform]:
            entry = pending.setdefault(client["id"], {"client": client, "new": [], "unsent": [],
                                                      "platforms": set()})
            earlier = told.get(client["id"])
            if earlier:
                if send and earlier.get("emailed_at") is None:
                    entry["unsent"].append(earlier)
                    entry["platforms"].add(platform)
                continue
            key = (client["id"], platform)
            if key not in own_rows:
                own_rows[key] = latest_rows(db, client, platform, today, fresh=False)
            state = visibility(own_rows[key], cell, today)
            if state == "no_series":
                continue
            entry["platforms"].add(platform)
            entry["new"].append({**alert_for(cell, state), "platform_change_id": row["id"],
                                 "_visibility": state})

    written: list[dict] = []
    for entry in pending.values():
        client, new, unsent = entry["client"], entry["new"], entry["unsent"]
        if not new and not unsent:
            continue
        name = client.get("company_name") or client.get("contact_email") or client["id"][:8]
        try:
            # the row first: it is what makes the announcement once-only
            rows = [{"client_id": client["id"], "run_id": None, "severity": a["severity"],
                     "module": a["module"], "message": a["message"],
                     "platform_change_id": a["platform_change_id"], "emailed_at": None} for a in new]
            inserted = (db.table("alerts").insert(rows).execute().data or []) if rows else []
            emailed = bool(send and _email(client, new + unsent, entry["platforms"]))
            if emailed:
                stamp = _now()
                ids = [r["id"] for r in inserted] + [r["id"] for r in unsent]
                db.table("alerts").update({"emailed_at": stamp}).in_("id", ids).execute()
                for r in rows:
                    r["emailed_at"] = stamp
            written += [{**r, "visibility": a["_visibility"]} for r, a in zip(rows, new)]
            log(f"  {name}: {len(rows)} new network alert(s)"
                + (f", {len(unsent)} earlier one(s) caught up" if unsent else "")
                + (" (emailed)" if emailed else ""))
        except Exception as err:
            log(f"  {name}: network alert FAILED — {err}")
    return written


def email_blocks(alerts: list[dict], platforms: set[str]) -> list[dict]:
    """The letter a network alert travels in: not the weekly watch, which
    reports on the client's own account and arrives on its own."""
    names = " and ".join(sorted(channels.label(p) for p in platforms)) or "the platform"
    one = len(alerts) == 1
    return [
        {"p": (f"Something changed on {names}'s side, not in your account. We saw it across the "
               f"accounts we watch, and it reaches every seller who pays that fee:" if one else
               f"Some things changed on {names}'s side, not in your account. We saw them across the "
               f"accounts we watch, and they reach every seller who pays those fees:")},
        {"ol": [a["message"] for a in alerts]},
        {"p": "It is in Hubricon too:"},
        {"button": "Open Hubricon", "url": PORTAL_URL},
        {"p": "Reply to this email if any of it looks wrong — it comes straight to me."},
    ]


def _email(client: dict, alerts: list[dict], platforms: set[str]) -> bool:
    from .notify import email_configured, letter, send_email

    if not (email_configured() and client.get("contact_email")):
        return False
    text, html = letter(client.get("contact_name"), email_blocks(alerts, platforms))
    names = sorted(channels.label(p) for p in platforms)
    subject = f"A change on {names[0]}'s side" if len(names) == 1 else "A change on the platforms' side"
    return send_email(client["contact_email"], subject, text, html=html,
                      sender=os.environ.get("EMAIL_FROM", "Hagen Simmons <hagen.simmons@hubricon.com>"),
                      reply_to=os.environ.get("EMAIL_REPLY_TO",
                                              os.environ.get("EMAIL_FROM", "hagen.simmons@hubricon.com")))


def run(db, today: date | None = None, send: bool = False, dry: bool = False, log=print) -> dict:
    """The weekly network pass: collect, detect, record, announce. `dry`
    detects and writes nothing. Never raises for a refusal: a refusal is a
    status, and the sweep step that calls this is guarded besides."""
    today = today or date.today()
    out = detect(collect(db, today), today)
    out["recipient_policy"] = RECIPIENT_POLICY
    out["alerts"] = []
    if out["status"] != "ok" or dry:
        return out
    problem = _schema_problem(db)
    if problem:
        out["status"], out["basis"] = "schema_missing", problem
        return out
    saved = persist(db, out["cells"], out["n_tests"], today)
    out["alerts"] = announce(db, out["cells"], saved, today, send=send, log=log)
    if send:
        _digest(out, log)
    return out


def _digest(out: dict, log=print) -> None:
    from .notify import email_configured, send_email

    founder = os.environ.get("FOUNDER_EMAIL")
    if not out["alerts"]:
        return   # a change still declared this week was announced already; nothing new to say
    if not founder or not email_configured():
        log("Network digest not emailed: set FOUNDER_EMAIL and RESEND_API_KEY.")
        return
    sent = send_email(founder, "Hubricon network pass", render(out))
    log(f"Network digest {'emailed' if sent else 'NOT emailed — see the error above'} to {founder}.")


def render(out: dict) -> str:
    """The pass in a few lines, for the CLI and the founder."""
    lines = [f"Network pass, {out['as_of']}: {out['status']} — {out['basis']}"]
    for c in out.get("cells", []):
        head = f"  {c['platform']:<7} {c['kind']:<17} {c['direction']:<4} {c['status']:<22}"
        if c["status"] == "declared":
            size = (f"median ratio {c['pooled_ratio']:.3f} ({c['ratio_low']:.3f}–{c['ratio_high']:.3f}), "
                    if c.get("pooled_ratio") is not None else "")
            note = schedule_note(c)
            lines.append(f"{head} {c['n_accounts']}/{c['n_eligible']} accounts, {size}onset "
                         f"{_day(c['onset']).isoformat()}, p {c['p_value']:.2g}, q {c['q_value']:.2g}"
                         + (f"\n{'':<9}{note}" if note else ""))
        elif c["status"] == "not_significant":
            lines.append(f"{head} {c['n_accounts']}/{c['n_eligible']} accounts, q {c['q_value']:.2g}")
        else:
            lines.append(f"{head} {c['basis']}")
    if out.get("alerts"):
        told = len({a["client_id"] for a in out["alerts"]})
        lines.append(f"  {len(out['alerts'])} alert(s) to {told} client(s), recipient policy "
                     f"{out.get('recipient_policy')}")
    return "\n".join(lines)


def show(db) -> str:
    rows = db.table("platform_changes").select("*").order("last_seen_at", desc=True).limit(50).execute().data
    if not rows:
        return "No platform change recorded yet — `hubricon fleet` runs the pass; the sweep runs it weekly."
    return "\n".join(
        f"  {r['onset']}  {r['platform']:<7} {r['kind']:<17} {r['direction']:<4} {r['status']:<15} "
        f"{r['n_accounts']}/{r['n_eligible']} accounts"
        + (f", median ratio {float(r['pooled_ratio']):.3f}" if r.get("pooled_ratio") is not None else "")
        + (f", q {float(r['q_value']):.2g}" if r.get("q_value") is not None else "")
        for r in rows)
