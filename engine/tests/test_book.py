"""`hubricon book`: what each kind of move delivered, measured over promised,
across the accounts that granted the `network` consent.

Report only. It reads directives and scores them with replay's own arithmetic;
it must never write, never change a promise, an expected dollar or a measured
one, and never read an account that did not consent. Below its floor it says so
and prints no number.
"""

import copy
from collections import defaultdict

import pytest

from hubricon_engine import book, replay
from fakedb import FakeDB


def _move(cid: str, i: int, kind: str, promised: float, measured: float) -> dict:
    return {"id": f"{cid}-{kind}-{i}", "client_id": cid, "kind": kind, "dedupe_key": f"{cid}:{kind}:{i}",
            "status": "approved", "expected_impact_usd": promised, "measured_impact_usd": measured,
            "measured_at": f"2026-0{1 + i % 8}-15", "evidence": {}}


def _book_db(consenting: list[str], moves: dict[str, list[dict]], others: list[str] = ()) -> FakeDB:
    clients = [{"id": c, "contact_email": f"owner@{c}-brand.com", "contact_name": "Pat Owner",
                "status": "active", "platform": "amazon"} for c in [*consenting, *others]]
    consents = [{"client_id": c, "kind": "network", "granted": True} for c in consenting]
    consents += [{"client_id": c, "kind": "calibration", "granted": True} for c in others]
    directives = [d for rows in moves.values() for d in rows]
    return FakeDB(clients=clients, consents=consents, directives=directives)


def _moves() -> dict[str, list[dict]]:
    """Six consenting accounts. Price steps in every one (two each, twelve in
    all); budget reallocations in three; campaign trims in five, one each; and
    an unmeasured step that must not count."""
    out = defaultdict(list)
    for a in range(6):
        cid = f"c{a}"
        out[cid] += [_move(cid, 0, "price_step", 1000.0, 600.0 + 50 * a),
                     _move(cid, 1, "price_step", 500.0, 300.0 + 20 * a)]
        if a < 3:
            out[cid].append(_move(cid, 2, "budget_reallocation", 800.0, 700.0))
        if a < 5:
            out[cid].append(_move(cid, 3, "campaign_trim", 400.0, 380.0))
        out[cid].append({**_move(cid, 4, "price_step", 900.0, 0.0), "measured_impact_usd": None})
    return dict(out)


class SpyDB(FakeDB):
    def __init__(self, **tables):
        super().__init__(**tables)
        self.read = set()

    def table(self, name):
        q = super().table(name)
        if name == "directives":
            inner = q.execute

            def execute():
                res = inner()
                self.read |= {r.get("client_id") for r in res.data or []}
                return res

            q.execute = execute
        return q


def test_below_the_floor_the_book_refuses_and_prints_no_number():
    moves = {k: v for k, v in _moves().items() if k in ("c0", "c1", "c2", "c3")}
    out = book.run(_book_db(list(moves), moves))
    assert out["status"] == "insufficient_accounts" and out["kinds"] == []
    assert out["n_accounts"] == 4 and "5 are needed" in out["basis"]
    assert "×" not in book.render(out)


def test_the_book_pools_replays_arithmetic_by_kind_with_a_band_from_resampling_accounts():
    moves = _moves()
    out = book.run(_book_db(list(moves), moves))
    assert out["status"] == "ok" and out["n_accounts"] == 6
    rows = {r["kind"]: r for r in out["kinds"]}

    step = rows["price_step"]
    assert step["status"] == "ok" and step["n_accounts"] == 6 and step["n_moves"] == 12
    promised = sum(d["expected_impact_usd"] for ds in moves.values() for d in ds
                   if d["kind"] == "price_step" and d["measured_impact_usd"] is not None)
    measured = sum(d["measured_impact_usd"] for ds in moves.values() for d in ds
                   if d["kind"] == "price_step" and d["measured_impact_usd"] is not None)
    assert step["realisation_ratio"] == pytest.approx(measured / promised, abs=1e-4)
    # the same number replay.score gives the pooled moves: its arithmetic, not a new one
    pooled = [d for ds in moves.values() for d in ds if d["kind"] == "price_step"]
    assert step["realisation_ratio"] == pytest.approx(replay.score(pooled)["realisation_ratio"], abs=1e-4)
    assert step["ratio_p5"] <= step["realisation_ratio"] <= step["ratio_p95"]
    assert "inside the" in step["reading"]

    # three accounts: refused, with no number; five accounts and five moves:
    # refused for want of moves, with no number
    for kind, status in (("budget_reallocation", "insufficient_accounts"), ("campaign_trim", "insufficient_moves")):
        r = rows[kind]
        assert r["status"] == status
        assert r["realisation_ratio"] is None and r["ratio_p5"] is None and r["ratio_p95"] is None
    assert rows[book.ALL_KINDS]["status"] == "ok" and rows[book.ALL_KINDS]["n_moves"] == 20

    # seeded: the same book prints the same band
    again = book.run(_book_db(list(moves), moves))
    assert again["kinds"] == out["kinds"]


def test_a_book_whose_resamples_promise_nothing_prints_no_band_rather_than_a_lucky_one():
    """Moves recorded with a negative promise: a third of the resampled books
    promise nothing to divide by. The ratio stands; the band is refused."""
    moves = {}
    for a in range(5):
        cid = f"n{a}"
        moves[cid] = [_move(cid, i, "price_step", 250.0 if a == 0 else -50.0, 10.0) for i in range(2)]
    out = book.run(_book_db(list(moves), moves))
    step = next(r for r in out["kinds"] if r["kind"] == "price_step")
    assert step["status"] == "ok" and step["realisation_ratio"] == pytest.approx(1.0)
    assert step["ratio_p5"] is None and step["ratio_p95"] is None and "no band" in step["basis"]
    assert "(no band" in book.render(out)


def test_the_book_never_writes_and_never_touches_a_directive():
    moves = _moves()
    db = _book_db(list(moves), moves)
    before = copy.deepcopy(db.rows("directives"))
    out = book.run(db)
    assert out["status"] == "ok"
    assert db.writes == []
    assert db.rows("directives") == before


def test_the_book_reads_only_accounts_that_granted_network():
    moves = _moves()
    wild = {c: [_move(c, i, "price_step", 100.0, 5000.0) for i in range(4)] for c in ("x1", "x2")}
    db = _book_db(list(moves), {**moves, **wild}, others=list(wild))
    db.__class__ = SpyDB
    db.read = set()
    out = book.run(db)
    assert db.read <= set(moves)
    step = next(r for r in out["kinds"] if r["kind"] == "price_step")
    assert step["n_accounts"] == 6 and step["realisation_ratio"] < 1.0
