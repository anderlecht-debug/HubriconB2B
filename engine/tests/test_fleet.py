"""The network: a change on the platform's side, seen across accounts.

The artifact is a synthetic book. Ten consenting Amazon accounts, twelve SKUs
each, ten months of SKU Economics in which every fee per unit wanders by 3%;
in six of them the FBA fulfilment fee steps up 8% in July 2026, and elsewhere
there is the noise a real book has — one account's referral rate steps on its
own in May, another's in September, one SKU somewhere is re-measured into a
dearer tier. Every account goes through `anomaly.run` exactly as the sweep
runs it, so the network reads the rows a real run stores.

What must hold: the planted change is declared with the right number of
accounts and the right direction, and nothing else is; on books of pure noise
the pass declares at or below its design level; a client who has not granted
the `network` consent is never read as a source; a change is announced once per
client; below the floors the answer is a named status and never a number.
"""

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import binom

from hubricon_engine import fleet
from hubricon_engine.models import anomaly
from fakedb import FakeDB

TODAY = date(2026, 11, 10)       # ten monthly exports, January to October 2026, are on file
STEP_AT = 6                      # 0-based: the seventh month, July 2026
STARTED = "2026-11-09T11:00:00+00:00"
RETIRED = ("desk", "ledger", "quantitative", "retainer", "engagement", "directive",
           "three-minute brief", "40+ fee types", "you never log in anywhere", "the gate is fit")


def _period(i: int) -> tuple[str, str]:
    year, month = 2026 + (i - 1) // 12, (i - 1) % 12 + 1
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-28"


def _economics(seed: int, n_skus: int = 12, n_periods: int = 10, fba_step: float | None = None,
               referral_step: float | None = None, referral_at: int = STEP_AT, fee_sd: float = 0.03,
               one_sku_step: float | None = None, fba_at: int = STEP_AT, prefix: str = "SKU") -> dict:
    """SKU Economics rows: per-unit FBA fees and referral rates that wander by
    `fee_sd`, with the steps asked for. Every SKU carries the prefix, so a test
    can look for it anywhere it must not be."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_skus):
        base_fba = rng.uniform(2.5, 6.0)
        for j in range(n_periods):
            units = max(1.0, rng.normal(100, 15))
            price = max(1.0, rng.normal(20, 1))
            sales = units * price
            fba = base_fba
            if fba_step is not None and j >= fba_at:
                fba *= 1 + fba_step
            if one_sku_step is not None and i == 0 and j >= STEP_AT:
                fba *= 1 + one_sku_step
            ref = 0.15 * (1 + (referral_step if referral_step is not None and j >= referral_at else 0.0))
            start, end = _period(j + 1)
            rows.append({
                "sku": f"{prefix}-{seed}-{i}", "asin": f"B0{prefix}{seed}{i:02d}",
                "period_start": start, "period_end": end, "units_sold": units, "avg_sales_price": price,
                "sales": sales, "referral_fees": -ref * (1 + rng.normal(0, 0.01)) * sales,
                "fba_fulfillment_fees": -fba * (1 + rng.normal(0, fee_sd)) * units,
                "storage_fees": -abs(rng.normal(12, 1.5)), "other_fees": 0.0, "net_proceeds": sales,
            })
    return {"sku_economics": rows, "asin_traffic": [], "ppc_spend": [], "settlement_transactions": []}


def _rows(seed: int, **kw) -> list[dict]:
    return anomaly.run(_economics(seed, **kw))


# The book: six accounts carry the July FBA step; four do not, and those four
# carry the independent noise flags.
PLANTED = {f"acct{i}": {"fba_step": 0.08} for i in range(6)}
QUIET = {"acct6": {"referral_step": 0.12, "referral_at": 4},     # its own referral step, May
         "acct7": {"referral_step": 0.12, "referral_at": 8},     # its own referral step, September
         "acct8": {"one_sku_step": 0.25},                        # one SKU re-measured, July
         "acct9": {}}
BOOK = {**PLANTED, **QUIET}
_ROWS: dict[str, list[dict]] = {}


def _book_rows(key: str) -> list[dict]:
    if key not in _ROWS:
        spec = {**BOOK, **EXTRA}[key]
        _ROWS[key] = _rows(100 + int(re.sub(r"\D", "", key) or 0), **spec)
    return _ROWS[key]


# Accounts that must never count, each carrying a 30% step at the same month.
EXTRA = {"calib1": {"fba_step": 0.3}, "withdrawn2": {"fba_step": 0.3}, "none3": {"fba_step": 0.3},
         "internal4": {"fba_step": 0.3}, "former5": {"fba_step": 0.3}}


def _client(cid: str, **kw) -> dict:
    return {"id": cid, "company_name": f"Brand {cid}", "contact_email": f"owner@{cid}-brand.com",
            "contact_name": "Pat Owner", "status": "active", "platform": "amazon", **kw}


def _db(consenting: list[str], others: dict[str, dict] | None = None, cls=FakeDB, run_date: str = STARTED,
        extra_rows: dict[str, list[dict]] | None = None) -> FakeDB:
    """A database holding each account's latest run and its anomaly rows, the
    way the sweep stores them (model_runs + model_outputs 'anomaly')."""
    clients, consents, runs, outputs = [], [], [], []
    everyone = {cid: {} for cid in consenting}
    everyone.update(others or {})
    for cid, kw in everyone.items():
        clients.append(_client(cid, **kw.get("client", {})))
        if cid in consenting:
            consents.append({"client_id": cid, "kind": "network", "granted": True})
        for c in kw.get("consents", []):
            consents.append({"client_id": cid, **c})
        rows = (extra_rows or {}).get(cid)
        if rows is None:
            rows = _book_rows(cid) if kw.get("rows", True) else []
        runs.append({"id": f"run-{cid}", "client_id": cid, "status": "succeeded", "started_at": run_date,
                     "params": {"channel": "amazon"}})
        outputs.append({"run_id": f"run-{cid}", "client_id": cid, "model": "anomaly", "payload": {"rows": rows}})
    return cls(clients=clients, consents=consents, model_runs=runs, model_outputs=outputs, alerts=[],
               platform_changes=[])


def _cell(out: dict, kind: str, direction: str) -> dict:
    return next(c for c in out["cells"] if c["kind"] == kind and c["direction"] == direction)


class SpyDB(FakeDB):
    """Records the client of every row a data table hands back."""

    WATCHED = ("model_runs", "model_outputs", "directives")

    def __init__(self, **tables):
        super().__init__(**tables)
        self.read = defaultdict(set)

    def table(self, name):
        q = super().table(name)
        if name in self.WATCHED:
            inner = q.execute

            def execute():
                res = inner()
                if q.op == "select":
                    for r in res.data or []:
                        self.read[name].add(r.get("client_id"))
                return res

            q.execute = execute
        return q


# ── the planted change ────────────────────────────────────────────────────

def test_the_planted_fee_step_is_declared_with_its_accounts_and_its_direction():
    db = _db(list(BOOK))
    out = fleet.detect(fleet.collect(db, TODAY), TODAY)
    assert out["status"] == "ok" and out["n_accounts"] == 10

    fba = _cell(out, "fba_fee_per_unit", "up")
    assert fba["status"] == "declared", fba["basis"]
    assert fba["n_accounts"] == 6 and fba["n_eligible"] == 10
    assert fba["window_start"] <= date(2026, 7, 1) <= fba["window_end"]
    assert fba["onset"] == date(2026, 7, 1)
    assert fba["q_value"] <= fleet.FLEET_Q and fba["p_value"] < 1e-6
    # the size, pooled across the six: median ratio near the planted 1.08,
    # inside its own band
    assert fba["pooled_ratio"] == pytest.approx(1.08, abs=0.02)
    assert fba["ratio_low"] <= fba["pooled_ratio"] <= fba["ratio_high"]
    assert fba["ratio_low"] > 1.0
    # the all-fees series carries storage, the stock-build common cause: not scanned
    assert {c["kind"] for c in out["cells"]} == {"fba_fee_per_unit", "referral_rate"}

    # and the independent noise stays noise: two referral steps months apart,
    # one re-measured SKU, and nothing in the other direction
    declared = [(c["kind"], c["direction"]) for c in out["cells"] if c["status"] == "declared"]
    assert declared == [("fba_fee_per_unit", "up")]
    assert _cell(out, "referral_rate", "up")["status"] == "insufficient_accounts"
    assert _cell(out, "referral_rate", "up")["pooled_ratio"] is None


def test_the_network_calls_a_step_that_most_accounts_cannot_yet_call_alone():
    """Sooner. A 5% FBA step in fees that wander by 3%, three monthly exports
    after it, in eight accounts: the network declares it, while most of the
    eight accounts' own sweeps, rightly strict over a hundred tests each, do
    not report it yet."""
    today = date(2026, 10, 10)          # nine exports on file, January to September
    events, own = {}, 0
    for a in range(8):
        rows = anomaly.run(_economics(1100 + a, n_periods=9, fba_step=0.05))
        events[f"a{a}"] = fleet.account_events(rows, "amazon", today)
        own += any(r["flagged"] and r["metric"] == "fba_fee_per_unit" and r["direction"] == "up" for r in rows)
    cell = _cell(fleet.detect(events, today), "fba_fee_per_unit", "up")
    assert cell["status"] == "declared" and cell["n_accounts"] >= 5 and cell["q_value"] < 1e-5
    # measured on the accounts that showed it, the size leans high (they are
    # the ones noise pushed the same way); named in MATH_METHODS §8c
    assert cell["pooled_ratio"] == pytest.approx(1.05, abs=0.015)
    assert own <= 2, own


def test_one_sku_moving_does_not_flag_its_account_although_its_own_sweep_reports_it():
    """Fewer false alarms: a single re-measured SKU is a finding for that
    client and no evidence at all about the platform."""
    rows = _book_rows("acct8")
    own = [r for r in rows if r["metric"] == "fba_fee_per_unit" and r["flagged"] and r["direction"] == "up"]
    assert own, "the account's own sweep reports its re-measured SKU"
    events = fleet.account_events(rows, "amazon", TODAY)
    assert events["fba_fee_per_unit"]["flags"] == {}


def test_the_account_threshold_is_exact_and_the_account_rate_depends_on_its_catalogue():
    for m in (1, 2, 3, 8, 12, 40, 400):
        h, pi = fleet.account_threshold(m)
        assert pi == pytest.approx(binom.sf(h - 1, m, fleet.SERIES_P))
        assert pi <= fleet.ALPHA_ACCOUNT
        assert h == 1 or binom.sf(h - 2, m, fleet.SERIES_P) > fleet.ALPHA_ACCOUNT   # h* is the fewest
    assert fleet.account_threshold(2)[1] == pytest.approx(0.0025)
    assert fleet.account_threshold(40)[1] == pytest.approx(0.048, abs=5e-4)


# ── the null ──────────────────────────────────────────────────────────────

def test_on_books_of_pure_noise_the_pass_declares_at_or_below_its_design_level():
    """Forty books of eight accounts each, every fee a random walk around a
    constant, every account through anomaly.run. The design level is FLEET_Q:
    under the complete null Benjamini–Hochberg's false-discovery rate is its
    familywise rate, the chance of declaring anything at all."""
    books, declared, flags, questions = 40, 0, 0, 0
    for b in range(books):
        events = {}
        for a in range(8):
            rows = anomaly.run(_economics(7000 + 97 * b + a, n_skus=8))
            ev = fleet.account_events(rows, "amazon", TODAY)
            events[f"a{a}"] = ev
            for e in ev.values():
                questions += len(fleet.DIRECTIONS)
                flags += len(e["flags"])
        out = fleet.detect(events, TODAY)
        declared += any(c["status"] == "declared" for c in out["cells"])
    assert declared / books <= fleet.FLEET_Q
    # and each account asks its own question at or below its stated rate
    assert flags / questions <= fleet.ALPHA_ACCOUNT


def test_the_coincidence_probability_is_a_valid_p_value_at_the_worst_case_null():
    """The worst case the arithmetic allows: every account flags at exactly its
    own rate, every flag in the same direction on the same day. X is then
    exactly Poisson-binomial, so P(p ≤ t) ≤ t must hold for the tail, and the
    whole pass may declare at most FLEET_Q of the time."""
    rng = np.random.default_rng(20260925)
    sims, declared = 4000, 0
    small = {0.001: 0, 0.01: 0, 0.05: 0}
    day = date(2026, 7, 1)
    for _ in range(sims):
        events, probs = {}, []
        for a in range(10):
            ev = {}
            for kind in fleet.KINDS:
                _, pi = fleet.account_threshold(int(rng.integers(1, 60)))
                hit = rng.random() < pi
                ev[kind] = {"platform": "amazon", "pi": pi,
                            "flags": {"up": {"onset": day, "ratio": 1.05}} if hit else {}}
                if kind == "fba_fee_per_unit":
                    probs.append((pi, hit))
            events[f"a{a}"] = ev
        x = sum(h for _, h in probs)
        p = fleet.poisson_binomial_sf([pi for pi, _ in probs], x)
        for t in small:
            small[t] += p <= t
        out = fleet.detect(events, TODAY)
        declared += any(c["status"] == "declared" for c in out["cells"])
    for t, n in small.items():
        assert n / sims <= t + 3 * np.sqrt(t * (1 - t) / sims), (t, n / sims)
    assert declared / sims <= fleet.FLEET_Q + 3 * np.sqrt(fleet.FLEET_Q / sims)


def test_the_poisson_binomial_tail_is_exact():
    probs = [0.05, 0.01, 0.2, 0.0025, 0.048, 0.3]
    # brute force over every outcome
    for k in range(len(probs) + 2):
        brute = 0.0
        for mask in range(1 << len(probs)):
            hits = [(mask >> i) & 1 for i in range(len(probs))]
            if sum(hits) >= k:
                brute += np.prod([p if h else 1 - p for p, h in zip(probs, hits)])
        assert fleet.poisson_binomial_sf(probs, k) == pytest.approx(brute, rel=1e-12, abs=1e-15)
    # the binomial special case, and a tail far past one minus anything
    assert fleet.poisson_binomial_sf([0.05] * 10, 4) == pytest.approx(binom.sf(3, 10, 0.05), rel=1e-10)
    assert fleet.poisson_binomial_sf([0.01] * 12, 12) == pytest.approx(1e-24, rel=1e-9)
    assert fleet.poisson_binomial_sf([0.3], 0) == 1.0 and fleet.poisson_binomial_sf([0.3], 2) == 0.0


# ── consent ───────────────────────────────────────────────────────────────

NON_CONSENTING = {
    "calib1": {"consents": [{"kind": "calibration", "granted": True}]},     # a different consent
    "withdrawn2": {"consents": [{"kind": "network", "granted": False}]},    # said yes, then no
    "none3": {},                                                           # never asked
}


def test_an_account_that_has_not_granted_network_is_never_read_as_a_source():
    consenting = list(BOOK)
    db = _db(consenting, {
        **NON_CONSENTING,
        # granted, but internal, and granted, but no longer a client
        "internal4": {"client": {"contact_email": "dry@hubricon.internal"}},
        "former5": {"client": {"status": "churned"}},
    }, cls=SpyDB)
    events = fleet.collect(db, TODAY)
    assert set(events) == set(consenting)
    for table in ("model_runs", "model_outputs"):
        assert db.read[table] <= set(consenting), (table, db.read[table] - set(consenting))

    # and the five who carry a 30% step count for nothing in the detection
    out = fleet.detect(events, TODAY)
    assert _cell(out, "fba_fee_per_unit", "up")["n_accounts"] == 6


def test_a_recipient_is_read_only_for_its_own_alert_and_never_enters_the_detection():
    """The consent governs the source. A client who did not consent still pays
    Amazon's fees; their own rows are read to tell them whether the change is in
    their exports yet, and nothing of theirs reaches the count."""
    quiet = fleet.run(_db(list(BOOK), {"none3": {}}, extra_rows={"none3": _rows(301)}), TODAY)
    loud = fleet.run(_db(list(BOOK), {"none3": {}}), TODAY)       # none3 carries a 30% step
    for out in (quiet, loud):
        assert _cell(out, "fba_fee_per_unit", "up")["n_accounts"] == 6
        assert _cell(out, "fba_fee_per_unit", "up")["pooled_ratio"] == pytest.approx(1.08, abs=0.02)
    told = {a["client_id"]: a["message"] for a in loud["alerts"]}
    assert "Your own exports show it too." in told["none3"]
    told = {a["client_id"]: a["message"] for a in quiet["alerts"]}
    assert "does not show in your own exports yet" in told["none3"]


# ── announcing ────────────────────────────────────────────────────────────

def test_one_platform_change_is_announced_once_per_client_and_says_so_plainly():
    db = _db(list(BOOK), {"none3": {}, "nofba6": {"rows": False}})
    first = fleet.run(db, TODAY)
    changes = db.rows("platform_changes")
    declared = [r for r in changes if r["status"] == "declared"]
    assert len(declared) == 1 and declared[0]["kind"] == "fba_fee_per_unit"
    assert declared[0]["n_accounts"] == 6 and declared[0]["pooled_ratio"] is not None
    alerts = db.rows("alerts")
    # every Amazon client that pays the fee, consenting or not; not the one
    # without an FBA line
    assert {a["client_id"] for a in alerts} == set(BOOK) | {"none3"}
    assert all(a["platform_change_id"] == declared[0]["id"] and a["module"] == "network" for a in alerts)
    assert len(first["alerts"]) == len(alerts)

    by = {a["client_id"]: a for a in first["alerts"]}
    for cid in PLANTED:
        assert by[cid]["visibility"] in ("visible", "early")
    assert by["none3"]["visibility"] == "visible"
    assert by["acct9"]["visibility"] == "not_yet"
    # its own sweep reports one re-measured SKU; that is not the platform's change
    assert by["acct8"]["visibility"] == "not_yet"
    msg = by["acct9"]["message"]
    assert msg.startswith("Across 6 accounts we watch, the FBA fulfilment fee per unit rose around July 2026, "
                          "by about 8% on the typical SKU (somewhere between ")
    assert "change on Amazon's side" in msg and "does not show in your own exports yet" in msg
    assert by["acct9"]["severity"] == "warning"

    # the next week, and the one after: the same change, the same row, no new alert
    second = fleet.run(db, TODAY)
    third = fleet.run(db, date(2026, 11, 17))
    assert second["alerts"] == [] and third["alerts"] == []
    assert len(db.rows("alerts")) == len(alerts)
    assert [r["id"] for r in db.rows("platform_changes") if r["status"] == "declared"] == [declared[0]["id"]]


def test_whether_a_recipient_sees_it_yet_is_read_from_their_own_exports():
    july = {"platform": "amazon", "kind": "fba_fee_per_unit", "direction": "up", "onset": date(2026, 7, 1),
            "window_start": date(2026, 7, 1), "window_end": date(2026, 7, 1)}
    assert fleet.visibility(_book_rows("none3"), july, TODAY) == "visible"       # their own sweep reports it
    assert fleet.visibility(_book_rows("acct9"), july, TODAY) == "not_yet"       # nothing moved
    assert fleet.visibility(_book_rows("acct8"), july, TODAY) == "not_yet"       # one SKU is not the platform
    assert fleet.visibility([], july, TODAY) == "no_series"                      # no FBA line: not told at all
    # clears the network's bar on their SKUs taken together, not their own sweep's
    modest = anomaly.run(_economics(1103, n_periods=9, fba_step=0.05))
    assert not any(r["flagged"] and r["metric"] == "fba_fee_per_unit" for r in modest)
    assert fleet.visibility(modest, july, date(2026, 10, 10)) == "early"
    # exports that begin after the change can never show it as a step
    last_winter = {**july, "onset": date(2025, 12, 1), "window_start": date(2025, 12, 1),
                   "window_end": date(2025, 12, 1)}
    assert fleet.visibility(_book_rows("acct9"), last_winter, TODAY) == "already_in"
    assert fleet.VISIBILITY_SENTENCE["already_in"] in fleet.alert_for(
        {**last_winter, "n_accounts": 3, "pooled_ratio": None}, "already_in")["message"]


def test_the_email_follows_the_row_and_one_that_did_not_go_is_caught_up_not_duplicated(monkeypatch):
    from hubricon_engine import notify

    sent, down = [], {"owner@acct9-brand.com"}
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("FOUNDER_EMAIL", "founder@example.org")
    monkeypatch.setattr(notify, "send_email",
                        lambda to, subject, text, **kw: sent.append((to, subject, text)) or to not in down)
    db = _db(list(BOOK))

    # a run by hand without --alert: the alerts land in Hubricon, nobody is emailed
    fleet.run(db, TODAY)
    assert sent == [] and all(a["emailed_at"] is None for a in db.rows("alerts"))

    # the Monday run with --alert emails every one of them once, writes no second row
    first = fleet.run(db, TODAY, send=True)
    assert first["alerts"] == [] and len(db.rows("alerts")) == len(BOOK)
    by = {a["client_id"]: a for a in db.rows("alerts")}
    assert by["acct0"]["emailed_at"] is not None
    assert by["acct9"]["emailed_at"] is None                 # its send failed; the alert stands in Hubricon
    letters = [(to, s, t) for to, s, t in sent if s == "A change on Amazon's side"]
    assert len(letters) == len(BOOK)
    assert "Something changed on Amazon's side, not in your account." in letters[0][2]
    assert "weekly sweep" not in letters[0][2]

    # a week later the one that failed is tried again, and only that one
    down.clear()
    before = len(sent)
    fleet.run(db, date(2026, 11, 17), send=True)
    assert [to for to, _, _ in sent[before:]] == ["owner@acct9-brand.com"]
    assert all(a["emailed_at"] is not None for a in db.rows("alerts"))
    assert len(db.rows("alerts")) == len(BOOK)


def test_a_later_estimate_of_the_same_onset_is_the_same_change():
    db = _db(list(BOOK))
    out = fleet.run(db, TODAY)
    change_id = next(r["id"] for r in db.rows("platform_changes") if r["status"] == "declared")
    cell = {**_cell(out, "fba_fee_per_unit", "up")}
    cell.update(onset=date(2026, 8, 1), window_start=date(2026, 7, 1), window_end=date(2026, 8, 1), n_accounts=7)
    saved = fleet.persist(db, [cell], out["n_tests"])
    assert saved[0]["id"] == change_id and saved[0]["n_accounts"] == 7
    assert fleet.announce(db, [cell], saved, TODAY) == []


def test_every_alert_is_client_copy_in_the_house_vocabulary():
    cell = {"platform": "amazon", "kind": "referral_rate", "direction": "down", "n_accounts": 4,
            "onset": date(2026, 3, 1), "pooled_ratio": 0.93, "ratio_low": 0.9, "ratio_high": 0.95}
    for state in ("visible", "early", "not_yet"):
        a = fleet.alert_for(cell, state)
        assert a["severity"] == "info" and a["module"] == "network"
        assert a["message"].startswith(
            "Across 4 accounts we watch, the referral fee rate (the share of each sale Amazon keeps) fell around "
            "March 2026, by about 7% on the typical SKU (somewhere between 5% and 10%). That is a change on "
            "Amazon's side, not something in your account. ")
        assert a["message"].endswith(fleet.VISIBILITY_SENTENCE[state])
        low = a["message"].lower()
        assert not [w for w in RETIRED if w in low], low
    # no pooled size: the alert still says what, when and how many, and no number
    bare = fleet.alert_for({**cell, "pooled_ratio": None, "ratio_low": None, "ratio_high": None}, "not_yet")
    assert "fell around March 2026. That is" in bare["message"] and "%" not in bare["message"]
    # a band that reaches past no change reads as zero, never as a move the other way
    wide = fleet.alert_for({**cell, "direction": "up", "pooled_ratio": 1.02, "ratio_low": 0.99,
                            "ratio_high": 1.05}, "not_yet")
    assert "rose around March 2026, by about 2% on the typical SKU (somewhere between 0% and 5%)" in wide["message"]
    assert wide["severity"] == "warning"


def test_the_recipient_policy_is_one_constant_and_contributors_only_is_give_to_get(monkeypatch):
    db = _db(["acct0", "acct1", "acct2"], {"none3": {}, "shop7": {"client": {"platform": "shopify"}, "rows": False}})
    assert fleet.RECIPIENT_POLICY == "every_client"
    assert {c["id"] for c in fleet.recipients(db, "amazon")} == {"acct0", "acct1", "acct2", "none3"}
    monkeypatch.setattr(fleet, "RECIPIENT_POLICY", "contributors_only")
    assert {c["id"] for c in fleet.recipients(db, "amazon")} == {"acct0", "acct1", "acct2"}
    monkeypatch.setattr(fleet, "RECIPIENT_POLICY", "whoever")
    with pytest.raises(ValueError):
        fleet.recipients(db, "amazon")


# ── what leaves an account ────────────────────────────────────────────────

def test_what_leaves_an_account_is_an_event_and_nothing_else():
    rows = anomaly.run(_economics(42, fba_step=0.08, prefix="SECRETSKU"))
    events = fleet.account_events(rows, "amazon", TODAY)
    dump = json.dumps(events, default=str)
    assert "SECRETSKU" not in dump and "B0SECRETSKU" not in dump and "$" not in dump
    for e in events.values():
        assert set(e) == {"platform", "pi", "flags"}
        for flag in e["flags"].values():
            assert set(flag) == {"onset", "ratio"}
    assert events["fba_fee_per_unit"]["flags"]["up"]["onset"] == date(2026, 7, 1)

    # and nothing downstream of the detection knows which accounts stood behind it
    out = fleet.detect({f"who-{i}-secret": events for i in range(4)}, TODAY)
    assert "secret" not in json.dumps(out, default=str)


def test_the_shopify_fee_line_is_an_estimate_and_is_never_read_as_a_platform_change():
    rows = anomaly.run(_economics(3, fba_step=0.08))
    for r in rows:
        assert fleet.kind_of(r, "shopify") is None
    assert fleet.account_events(rows, "shopify", TODAY) == {}


# ── the floors ────────────────────────────────────────────────────────────

def test_below_the_floors_the_answer_is_a_named_status_and_never_a_number():
    # two consenting accounts: the whole pass refuses
    db = _db(["acct0", "acct1"])
    out = fleet.run(db, TODAY)
    assert out["status"] == "insufficient_accounts" and out["cells"] == [] and out["alerts"] == []
    assert "2 consenting account(s)" in out["basis"]
    assert db.rows("platform_changes") == [] and db.rows("alerts") == []

    # six accounts, two of them with the step: the cell refuses, with no size,
    # no p, no window, and nobody is told
    db = _db(["acct0", "acct1", "acct6", "acct7", "acct8", "acct9"])
    out = fleet.run(db, TODAY)
    cell = _cell(out, "fba_fee_per_unit", "up")
    assert cell["status"] == "insufficient_accounts" and cell["n_accounts"] == 2
    for field in ("pooled_ratio", "ratio_low", "ratio_high", "p_value", "q_value", "window_start", "onset"):
        assert cell[field] is None, field
    assert db.rows("platform_changes") == [] and out["alerts"] == []

    # a fee type only two accounts carry cannot be tested at all
    events = fleet.collect(_db(list(BOOK)), TODAY)
    for key in list(events)[2:]:
        events[key] = {k: v for k, v in events[key].items() if k != "referral_rate"}
    out = fleet.detect(events, TODAY)
    for d in fleet.DIRECTIONS:
        c = _cell(out, "referral_rate", d)
        assert c["status"] == "insufficient_accounts" and c["n_eligible"] == 2 and c["p_value"] is None


def test_a_stale_run_does_not_speak_for_its_account():
    db = _db(list(BOOK), run_date="2026-09-01T11:00:00+00:00")
    assert fleet.collect(db, TODAY) == {}
    assert fleet.run(db, TODAY)["status"] == "insufficient_accounts"


def test_an_unapplied_migration_is_named_and_nothing_is_written():
    class NoTable(FakeDB):
        def table(self, name):
            if name == "platform_changes":
                raise RuntimeError('relation "public.platform_changes" does not exist')
            return super().table(name)

    db = _db(list(BOOK), cls=NoTable)
    out = fleet.run(db, TODAY)
    assert out["status"] == "schema_missing" and "20260925000003_network.sql" in out["basis"]
    assert db.rows("alerts") == [] and out["alerts"] == []


def test_a_dry_run_detects_and_writes_nothing():
    db = _db(list(BOOK))
    out = fleet.run(db, TODAY, dry=True)
    assert _cell(out, "fba_fee_per_unit", "up")["status"] == "declared"
    assert db.writes == []


# ── the rate card, and the sweep ──────────────────────────────────────────

def test_a_declared_fba_change_is_checked_against_the_rate_card_on_file():
    card = date.fromisoformat(fleet.fee_schedule.EFFECTIVE)
    near = {"kind": "fba_fee_per_unit", "onset": date(card.year, card.month, 1)}
    later = {"kind": "fba_fee_per_unit", "onset": date(2026, 7, 1)}
    assert "matches the rate card on file" in fleet.schedule_note(near)
    assert "after the rate card on file" in fleet.schedule_note(later)
    assert fleet.schedule_note({"kind": "referral_rate", "onset": date(2026, 7, 1)}) is None


SWEEP_YML = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "sweep.yml"


# The sweep step is held on the local branch `workflow-fleet` until the GitHub
# token can push workflow edits (OPERATIONS.md, "Where it runs"). Skipped only
# while the step is absent: the day it lands, this runs again unchanged.
@pytest.mark.skipif("hubricon fleet" not in SWEEP_YML.read_text(),
                    reason="the Monday sweep step waits on branch workflow-fleet")
def test_the_weekly_sweep_runs_the_network_pass_after_the_models_and_never_fails_on_it():
    workflow = SWEEP_YML.read_text()
    sweep_at = workflow.index("hubricon sweep")
    fleet_at = workflow.index("hubricon fleet")
    assert fleet_at > sweep_at
    step = workflow[workflow.rindex("- name:", 0, fleet_at):]
    assert "if: always()" in step
    assert re.search(r"hubricon fleet --alert \|\| echo", step)
