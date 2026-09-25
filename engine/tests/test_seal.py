"""The Seal: every promise fingerprinted before it goes live, every measurement
chained after it, and a Record anyone can check.

The load-bearing tests here:

  test_the_promise_is_sealed_before_the_email_and_the_email_carries_it
      "written down before it goes live" is a claim about ORDER, so the fake
      mail server looks at the chain at the moment the email is handed to it.
  test_editing_the_expected_dollars_after_sealing_fails_at_that_entry
      the whole point: a promise changed afterwards is caught, and caught at
      the entry that changed.
  test_a_consistent_rewrite_is_caught_only_by_a_witness
      what the chain cannot do on its own, stated as a test rather than hidden.
  test_node_and_python_agree_* (need `node` on PATH)
      the verifier a third party runs is not this code; it has to agree with
      it byte for byte.
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import random
import shutil
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from fakedb import FakeDB
from hubricon_engine import issue, notify, seal

# conftest disarms subprocess for the whole session (the harvest's transports
# shell out to the network). Running the local verifier is not the network,
# so the two tests that need node restore these, for themselves only.
_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen

REPO = Path(__file__).resolve().parents[2]
VERIFIER = REPO / "scripts" / "verify-record.mjs"
GOLDEN = REPO / "scripts" / "record-seal.golden.json"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not on PATH")

CLIENT = {"id": "c0000001-0000-4000-8000-000000000001", "contact_email": "dana@acme.test",
          "contact_name": "Dana Reyes", "company_name": "Acme"}
OTHER = {"id": "c0000002-0000-4000-8000-000000000002", "contact_email": "sam@other.test",
         "contact_name": "Sam", "company_name": "Other"}
T = datetime(2026, 9, 28, 11, 4, 12, 123400, tzinfo=timezone.utc)


def _d(i, client=CLIENT, **kw):
    base = {"id": f"d{i}", "client_id": client["id"], "channel": "amazon", "status": "draft",
            "module": "pricing", "kind": "price_step", "mandate": "standing", "dedupe_key": f"k{i}",
            "action_text": f"Raise SKU-{i} by 3%.", "expected_impact_usd": 100.0 * i + 0.5,
            "issued_at": None, "notified_at": None, "veto_closes_at": None,
            "evidence": {"sku": f"SKU-{i}", "delta_p5": 10.0 * i, "delta_p50": 100.0 * i + 0.5,
                         "delta_p95": 300.0 * i, "elasticity": -1.7, "ci95": [-2.1, -1.3]}}
    base.update(kw)
    return base


def _issued(i, client=CLIENT, **kw):
    return _d(i, client, **{"status": "issued", "issued_at": (T + timedelta(minutes=i)).isoformat(), **kw})


def _mail(monkeypatch, sent: list, on_send=None):
    monkeypatch.setattr("hubricon_engine.notify.email_configured", lambda: True)

    def fake_send(to, subject, text, html=None, **_k):
        if on_send:
            on_send()
        sent.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    monkeypatch.setattr("hubricon_engine.notify.send_email", fake_send)
    monkeypatch.setattr("hubricon_engine.cli._fetch_claims", lambda db, cid: [])
    monkeypatch.setattr("hubricon_engine.cli._fetch_invoices", lambda db, cid: [])


class NoTable(FakeDB):
    """A database the migration has not reached: PostgREST's own words."""

    def table(self, name):
        if name == seal.TABLE:
            err = RuntimeError("{'code': 'PGRST205', 'message': \"Could not find the table "
                               "'public.record_seals' in the schema cache\"}")
            err.code = "PGRST205"
            raise err
        return super().table(name)


# ── the canonical form ───────────────────────────────────────────────────────

def test_the_canonical_form_is_rfc_8785():
    """Sorted keys (by UTF-16 code unit, so an astral character sorts before
    U+FF01), no whitespace, ECMAScript's escapes and ECMAScript's numbers."""
    c = lambda v: seal.canonical(v).decode("utf-8")  # noqa: E731
    assert c({"b": 1, "a": [1, 2], "A": None}) == '{"A":null,"a":[1,2],"b":1}'
    assert c({"！": 1, "\U0001F600": 2}) == '{"\U0001F600":2,"！":1}'
    assert c("é\n\t\"\\\u0001\u007f/") == '"é\\n\\t\\"\\\\\\u0001\u007f/"'
    assert [seal.es_number(x) for x in (1e21, 1e20, 1e-7, 1e-6, -0.0, 100.0, 5e-324, 1.7976931348623157e308,
                                        0.1 + 0.2, -1.25e-8, 123.0e18)] == [
        "1e+21", "100000000000000000000", "1e-7", "0.000001", "0", "100", "5e-324", "1.7976931348623157e+308",
        "0.30000000000000004", "-1.25e-8", "123000000000000000000"]
    # past 2**53 JavaScript rounds an integer as it reads it, and prints the
    # shortest digits that read back (String(2**60) is 1152921504606847000);
    # so does the seal
    assert c(9007199254740993) == "9007199254740992"
    assert c(2 ** 60) == "1152921504606847000"
    for refused in (float("nan"), float("inf"), {1: "a"}, {"s": {1, 2}}, "\ud800", datetime.now()):
        with pytest.raises(seal.SealError):
            seal.canonical(refused)


def test_the_same_promise_hashes_the_same_however_it_arrives():
    """Key order, a float's spelling (1e-05 against 0.00001, as Postgres
    returns it), a timestamp's (Python's isoformat against Postgres's trimmed
    fraction and offset) and an amount's cannot change a leaf."""
    a = _issued(1, evidence={"sku": "SKU-1", "x": 1e-05, "ci95": [-2.1, -1.3]})
    b = {k: a[k] for k in reversed(list(a))}
    b["evidence"] = json.loads('{"ci95": [-2.1, -1.3], "x": 0.00001, "sku": "SKU-1"}')
    b["issued_at"] = seal.stamp(a["issued_at"]).replace("Z", "+00:00").replace(".123400", ".1234")
    b["expected_impact_usd"] = "100.50"
    assert a["issued_at"] != b["issued_at"]
    da = seal.called_document(a, CLIENT["id"], T)
    db_ = seal.called_document(b, CLIENT["id"], T)
    assert seal.leaf_of(da) == seal.leaf_of(db_)
    assert da["expected_usd"] == "100.50" and da["issued_at"] == "2026-09-28T11:05:12.123400Z"


def test_money_and_time_each_have_one_spelling():
    assert [seal.money(v) for v in (1234.5, 2.675, "7", 0.1 + 0.2, -0.001, None, 10 ** 6)] == [
        "1234.50", "2.68", "7.00", "0.30", "0.00", None, "1000000.00"]
    same = {seal.stamp(v) for v in ("2026-09-28T06:04:12.1234-05:00", "2026-09-28 11:04:12.1234+00",
                                    "2026-09-28T11:04:12.123400Z", T)}
    assert same == {"2026-09-28T11:04:12.123400Z"}
    with pytest.raises(seal.SealError):
        seal.money(float("nan"))
    with pytest.raises(seal.SealError):
        seal.stamp("next tuesday")


# ── the golden fixture, shared with the JavaScript verifier ──────────────────

def _golden_module():
    spec = importlib.util.spec_from_file_location("seal_golden", REPO / "engine" / "scripts" / "seal_golden.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mutate(bundle, t):
    b = copy.deepcopy(bundle)
    for path, value in t.get("set", []):
        o = b
        for p in path[:-1]:
            o = o[p]
        o[path[-1]] = value
    if "remove" in t:
        o = b
        for p in t["remove"][:-1]:
            o = o[p]
        del o[t["remove"][-1]]
    return b


def test_the_golden_fixture_is_what_this_code_produces():
    """The file the JavaScript verifier is pinned to must be what seal.py makes
    today. A change to the canonical form or the documents fails here first."""
    committed = json.loads(GOLDEN.read_text())
    assert json.loads(json.dumps(_golden_module().build(), ensure_ascii=False)) == committed


def test_the_golden_fixture_verifies_here_as_it_does_in_node():
    g = json.loads(GOLDEN.read_text())
    for case in g["canonical"]:
        assert seal.canonical(case["value"]).decode("utf-8") == case["canonical"]
        assert seal.sha256_hex(case["canonical"].encode("utf-8")) == case["sha256"]
    h = seal.GENESIS
    for doc, leaf, head in zip(g["chain"]["documents"], g["chain"]["leaves"], g["chain"]["heads"]):
        assert seal.leaf_of(doc) == leaf
        h = seal.link(h, leaf)
        assert h == head
    ok = seal.verify_bundle(g["export"])
    assert ok["status"] == "ok" and (ok["called"], ok["measured"]) == (3, 3), ok["problems"]
    for t in g["tampered"]:
        r = seal.verify_bundle(_mutate(g["export"], t))
        assert r["status"] == "broken" and r["first_broken_seq"] == t["first_broken_seq"], t["name"]
        assert any(p["check"] == t["check"] and p["seq"] == t["first_broken_seq"] for p in r["problems"]), t["name"]
    rw = g["rewritten"]
    assert seal.verify_bundle(rw["bundle"])["status"] == "ok"
    for w in rw["witness_that_catches_it"]:
        assert [p["check"] for p in seal.verify_bundle(rw["bundle"], [w])["problems"]] == ["witness"]
    assert seal.verify_bundle(rw["bundle"], rw["witness_it_still_has"])["status"] == "ok"


# ── issuing: the called entry, and the email ─────────────────────────────────

def test_the_promise_is_sealed_before_the_email_and_the_email_carries_it(monkeypatch):
    db = FakeDB(directives=[_d(1), _d(2, mandate="explicit", module="inventory")])
    chain_at_send = []
    sent = []
    _mail(monkeypatch, sent, on_send=lambda: chain_at_send.append([dict(r) for r in db.rows(seal.TABLE)]))
    res = issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    assert res["notified"] is True and res["seal"] == seal.SEALED

    # the chain already held both promises when the email was handed over
    assert len(chain_at_send) == 1 and {r["directive_id"] for r in chain_at_send[0]} == {"d1", "d2"}
    rows = sorted(db.rows(seal.TABLE), key=lambda r: r["seq"])
    by_id = {r["directive_id"]: r for r in rows}
    doc = by_id["d2"]["document"]
    assert doc["entry"] == "called" and doc["sealed"] == seal.AT_ISSUE
    assert doc["expected_usd"] == "200.50" and doc["band_usd"] == {"p5": "20.00", "p95": "600.00"}
    assert doc["mandate"] == "explicit" and doc["target"] == {"sku": "SKU-2"}
    # sealed as issued: the time on the promise is the time on the row
    issued_row = next(d for d in db.rows("directives") if d["id"] == "d2")
    assert doc["issued_at"] == seal.stamp(issued_row["issued_at"]) == doc["sealed_at"]

    text, html = sent[0]["text"], sent[0]["html"]
    for did, usd in (("d1", "$100"), ("d2", "$200")):
        mark = by_id[did]["leaf"][:12]
        assert f"(expected {usd} · seal {mark})" in text and mark in html
    assert notify.SEAL_NOTE in text
    assert text.index("nothing would move") < text.index(notify.SEAL_NOTE)
    assert "directive" not in text.lower() and "ledger" not in text.lower()     # retired words stay retired


def test_the_email_reads_exactly_as_before_when_nothing_is_sealed():
    d = [{"id": "d1", "action_text": "Raise SKU-1 by 3%.", "expected_impact_usd": 400, "mandate": "standing"},
         {"id": "d2", "action_text": "Reorder SKU-2.", "expected_impact_usd": None, "mandate": "explicit"}]
    text, _ = notify.directive_email_body({"contact_name": "Dana"}, d, datetime(2026, 9, 14, 9), "https://x")
    assert "1. Raise SKU-1 by 3%. (expected $400)" in text and "1. Reorder SKU-2.\n" in text + "\n"
    assert "seal" not in text.lower()
    sealed, _ = notify.directive_email_body({"contact_name": "Dana"}, d, datetime(2026, 9, 14, 9), "https://x",
                                            seals={"d1": "3f9a1c0b2e7d", "d2": "0123456789ab"})
    assert "Raise SKU-1 by 3%. (expected $400 · seal 3f9a1c0b2e7d)" in sealed
    assert "Reorder SKU-2. (seal 0123456789ab)" in sealed


def test_without_the_table_the_notice_goes_out_unsealed_and_says_why(monkeypatch):
    """A database the migration has not reached must not cost a client their
    notice: the email goes, the window opens, and the status names the gap."""
    sent = []
    _mail(monkeypatch, sent)
    db = NoTable(directives=[_d(1)])
    res = issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    assert res["notified"] is True and res["seal"] == seal.TABLE_MISSING
    assert seal.MIGRATION in res["seal_reason"]
    row = db.rows("directives")[0]
    assert row["status"] == "issued" and row["veto_closes_at"] and row["notified_at"]
    assert "seal" not in sent[0]["text"].lower()


def test_a_seal_that_cannot_be_written_never_holds_the_email(monkeypatch):
    class Refuses(FakeDB):
        def table(self, name):
            q = super().table(name)
            if name == seal.TABLE:
                real = q.insert

                def insert(rows):
                    real(rows)
                    raise RuntimeError("connection reset by peer")
                q.insert = insert
            return q

    sent = []
    _mail(monkeypatch, sent)
    db = Refuses(directives=[_d(1)])
    res = issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    assert res["notified"] is True and res["seal"] == seal.FAILED and "connection reset" in res["seal_reason"]
    assert db.rows("directives")[0]["veto_closes_at"]
    assert "seal" not in sent[0]["text"].lower()          # no seal printed that the Record does not hold


def test_a_move_whose_document_is_refused_is_named_and_the_rest_are_sealed(monkeypatch):
    sent = []
    _mail(monkeypatch, sent)
    bad = _d(2, evidence={"sku": "SKU-2", "delta_p5": "a lot", "delta_p95": 3.0})
    db = FakeDB(directives=[_d(1), bad])
    res = issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    assert res["seal"] == seal.PARTIAL and "d2" in res["seal_reason"]
    assert [r["directive_id"] for r in db.rows(seal.TABLE)] == ["d1"]
    assert "seal " in sent[0]["text"]


# ── the chain ────────────────────────────────────────────────────────────────

def _sealed_db(n=3):
    db = FakeDB(directives=[_issued(i) for i in range(1, n + 1)])
    res = seal.seal_called(db, CLIENT["id"], db.rows("directives"), sealed_at=T)
    assert res["status"] == seal.SEALED and res["sealed"] == n
    return db


def test_two_chains_one_per_client_and_one_across_them():
    db = FakeDB(directives=[_issued(1), _issued(2), _issued(7, OTHER), _issued(3)])
    ds = {d["id"]: d for d in db.rows("directives")}
    seal.seal_called(db, CLIENT["id"], [ds["d1"], ds["d2"]], sealed_at=T)
    seal.seal_called(db, OTHER["id"], [ds["d7"]], sealed_at=T)
    seal.seal_called(db, CLIENT["id"], [ds["d3"]], sealed_at=T)
    rows = sorted(db.rows(seal.TABLE), key=lambda r: r["global_seq"])
    assert [(r["directive_id"], r["seq"], r["global_seq"]) for r in rows] == [
        ("d1", 1, 1), ("d2", 2, 2), ("d7", 1, 3), ("d3", 3, 4)]
    prev = seal.GENESIS
    for r in rows:
        assert r["leaf"] == seal.leaf_of(r["document"])
        assert r["global_prev_head"] == prev and r["global_head"] == seal.link(prev, r["leaf"])
        prev = r["global_head"]
    mine = [r for r in rows if r["client_id"] == CLIENT["id"]]
    assert mine[2]["prev_head"] == mine[1]["head"]           # the client chain skips the other client's entry
    assert seal.verify(db, CLIENT["id"])["status"] == "ok"
    assert seal.verify(db, OTHER["id"])["status"] == "ok"
    g = seal.verify(db, None)
    assert g["status"] == "ok" and g["entries"] == 4 and g["head"] == rows[-1]["global_head"]


def test_editing_the_expected_dollars_after_sealing_fails_at_that_entry():
    db = _sealed_db(3)
    # in the directives table: the Record no longer says what was called
    db.rows("directives")[1]["expected_impact_usd"] = 999.0
    v = seal.verify(db, CLIENT["id"])
    assert v["status"] == "broken" and v["first_broken_seq"] == 2
    assert v["problems"][0]["check"] == "live_promise" and "200.50" in v["problems"][0]["detail"]
    assert seal.verify(db, CLIENT["id"], live=False)["status"] == "ok"      # the chain itself is intact

    # in the seal itself: the document no longer hashes to its leaf
    db = _sealed_db(3)
    row = next(r for r in db.rows(seal.TABLE) if r["seq"] == 2)
    row["document"]["expected_usd"] = "999.00"
    v = seal.verify(db, CLIENT["id"])
    assert v["first_broken_seq"] == 2 and {p["check"] for p in v["problems"] if p["seq"] == 2} >= {"leaf"}
    g = seal.verify(db, None)
    assert g["status"] == "broken" and g["first_broken_seq"] == 2


def test_evidence_edited_after_sealing_is_caught():
    db = _sealed_db(2)
    db.rows("directives")[0]["evidence"]["elasticity"] = -0.4
    v = seal.verify(db, CLIENT["id"])
    assert v["first_broken_seq"] == 1 and {"evidence", "live_promise"} <= {p["check"] for p in v["problems"]}
    # …but a measurement adding `after` is not an edit to the promise
    db = _sealed_db(2)
    db.rows("directives")[0]["evidence"]["after"] = {"measured": 1.0}
    assert seal.verify(db, CLIENT["id"])["status"] == "ok"


def test_a_consistent_rewrite_is_caught_only_by_a_witness(monkeypatch):
    """Whoever holds the database can recompute every leaf and head after an
    edit. The chain then verifies; the short seal already in the client's
    inbox, and a global head captured before, do not."""
    sent = []
    _mail(monkeypatch, sent)
    db = FakeDB(directives=[_d(1), _d(2), _d(3)])
    issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    rows = sorted(db.rows(seal.TABLE), key=lambda r: r["seq"])
    in_inbox = rows[1]["leaf"][:12]
    assert f"seal {in_inbox}" in sent[0]["text"]
    published_before = rows[-1]["global_head"]

    target = rows[1]
    target["document"]["expected_usd"] = "9999.00"
    next(d for d in db.rows("directives") if d["id"] == target["directive_id"])["expected_impact_usd"] = 9999.0
    head = gh = seal.GENESIS
    for r in rows:
        r["leaf"] = seal.leaf_of(r["document"])
        r["prev_head"], r["head"] = head, seal.link(head, r["leaf"])
        r["global_prev_head"], r["global_head"] = gh, seal.link(gh, r["leaf"])
        head, gh = r["head"], r["global_head"]

    assert seal.verify(db, CLIENT["id"])["status"] == "ok"
    for witness in (in_inbox, published_before):
        v = seal.verify(db, CLIENT["id"], witnesses=[witness])
        assert v["status"] == "broken" and [p["check"] for p in v["problems"]] == ["witness"]
    assert seal.verify(db, None, witnesses=[published_before])["status"] == "broken"


def test_sealing_again_writes_nothing():
    db = _sealed_db(3)
    again = seal.seal_called(db, CLIENT["id"], db.rows("directives"), sealed_at=T + timedelta(days=1))
    assert again["status"] == seal.ALREADY and again["sealed"] == 0 and len(again["short"]) == 3
    assert seal.catch_up(db, CLIENT["id"])["status"] == seal.ALREADY
    assert len(db.rows(seal.TABLE)) == 3


def test_a_lost_race_is_retried_from_a_fresh_read():
    """Two writers reading the same tip: the database refuses the second
    insert (unique keys, and the trigger), and the loser re-plans on top."""
    class Racy(FakeDB):
        raced = False

        def table(self, name):
            q = super().table(name)
            if name == seal.TABLE and not Racy.raced:
                real = q.insert

                def insert(rows):
                    Racy.raced = True
                    seal.seal_called(self, OTHER["id"], [_issued(9, OTHER)], sealed_at=T)   # the other writer lands first
                    err = RuntimeError('duplicate key value violates unique constraint "record_seals_pkey"')
                    err.code = "23505"
                    raise err
                q.insert = insert
            return q

    db = Racy(directives=[_issued(1)])
    res = seal.seal_called(db, CLIENT["id"], db.rows("directives"), sealed_at=T)
    assert res["status"] == seal.SEALED
    rows = sorted(db.rows(seal.TABLE), key=lambda r: r["global_seq"])
    assert [(r["client_id"], r["global_seq"], r["seq"]) for r in rows] == [(OTHER["id"], 1, 1), (CLIENT["id"], 2, 1)]
    assert seal.verify(db, None)["status"] == "ok"


# ── measuring: the second entry ──────────────────────────────────────────────

def _measure_setup(monkeypatch, db, verdicts):
    from hubricon_engine import cli, measurement
    monkeypatch.setattr(cli, "_load_data", lambda *_a, **_k: {})
    monkeypatch.setattr(cli, "_load_switchbacks", lambda *_a: [])
    monkeypatch.setattr(cli, "_load_experiments", lambda *_a: [])
    monkeypatch.setattr(cli, "_fetch_claims", lambda *_a: [])
    monkeypatch.setattr(measurement, "measure", lambda *a, **k: verdicts)
    return cli


def _verdict(did, verdict, usd, attribution, after=None):
    return {"directive_id": did, "kind": "price_step", "verdict": verdict, "measured_impact_usd": usd,
            "attribution": attribution, "measurement_notes": "measured", "evidence_after": after, "window": None}


def test_measurement_seals_a_second_entry_that_answers_the_first(monkeypatch, capsys):
    db = _sealed_db(2)
    for d in db.rows("directives"):
        d["status"] = "approved"
    cli = _measure_setup(monkeypatch, db, [_verdict("d1", "measured", 180.0, "attributable", {"p50": 180.0}),
                                           _verdict("d2", "unmeasurable", None, "none")])
    cli._measure_for_run(db, CLIENT, "run1", "amazon")
    assert "seal: sealed, 2 measured entries" in capsys.readouterr().out
    rows = sorted(db.rows(seal.TABLE), key=lambda r: r["seq"])
    called = {r["directive_id"]: r for r in rows if r["entry"] == "called"}
    m1, m2 = [r["document"] for r in rows if r["entry"] == "measured"]
    assert m1["called_leaf"] == called["d1"]["leaf"] and m2["called_leaf"] == called["d2"]["leaf"]
    assert (m1["measured_usd"], m1["grade"], m1["status"]) == ("180.00", "attributable", "done")
    assert (m2["measured_usd"], m2["grade"], m2["status"]) == (None, "unmeasurable", "closed")
    assert m1["after_sha256"] == seal.digest({"p50": 180.0}) and m2["after_sha256"] is None
    assert seal.verify(db, CLIENT["id"])["status"] == "ok"

    # the sweep again: nothing is due, nothing is resealed
    cli._measure_for_run(db, CLIENT, "run2", "amazon")
    assert len(db.rows(seal.TABLE)) == 4

    # the measured dollars edited afterwards: caught at the measured entry
    next(d for d in db.rows("directives") if d["id"] == "d1")["measured_impact_usd"] = 999.0
    v = seal.verify(db, CLIENT["id"])
    assert v["first_broken_seq"] == 3 and v["problems"][0]["check"] == "live_measurement"


def test_a_number_recorded_by_hand_is_sealed_as_one_and_a_correction_supersedes(monkeypatch):
    from hubricon_engine import cli
    db = _sealed_db(1)
    db.rows("directives")[0]["status"] = "approved"
    monkeypatch.setattr(cli.dbmod, "connect", lambda: db)
    monkeypatch.setattr(cli.dbmod, "resolve_client", lambda _db, _ident: CLIENT)
    args = SimpleNamespace(client="acme", auto=False, directive="d1", impact=150.0, notes=None, force=False,
                           remeasure=False, dry_run=False)
    cli.cmd_measure(args)
    cli.cmd_measure(SimpleNamespace(**{**vars(args), "impact": 120.0, "remeasure": True}))
    rows = sorted(db.rows(seal.TABLE), key=lambda r: r["seq"])
    assert [r["entry"] for r in rows] == ["called", "measured", "measured"]
    first, second = rows[1]["document"], rows[2]["document"]
    assert first["sealed"] == second["sealed"] == seal.BY_HAND
    assert (first["measured_usd"], second["measured_usd"]) == ("150.00", "120.00")
    assert second["supersedes"] == rows[1]["leaf"] and second["called_leaf"] == rows[0]["leaf"]
    assert seal.verify(db, CLIENT["id"])["status"] == "ok"


def test_measuring_without_the_table_still_banks(monkeypatch, capsys):
    db = NoTable(directives=[_issued(1, status="approved")])
    cli = _measure_setup(monkeypatch, db, [_verdict("d1", "measured", 90.0, "isolated")])
    cli._measure_for_run(db, CLIENT, "run1", "amazon")
    row = db.rows("directives")[0]
    assert row["status"] == "done" and row["measured_impact_usd"] == 90.0
    assert "seal: table_missing" in capsys.readouterr().out


# ── late entries ─────────────────────────────────────────────────────────────

def test_a_move_issued_before_the_seal_is_sealed_late_and_never_passes_for_called_before():
    db = FakeDB(directives=[_issued(1, status="approved", notified_at=T.isoformat(),
                                    executed_at=(T + timedelta(days=1)).isoformat()),
                            _issued(2, status="done", measured_impact_usd=55.0, attribution="isolated",
                                    measured_at="2026-10-20T00:00:00+00:00"),
                            _d(3)])                                    # a draft is never sealed
    out = seal.catch_up(db, CLIENT["id"], sealed_at=T + timedelta(days=30))
    assert out["status"] == seal.SEALED and out["sealed"] == 3
    docs = [r["document"] for r in sorted(db.rows(seal.TABLE), key=lambda r: r["seq"])]
    assert [(d["entry"], d["directive_id"], d["sealed"]) for d in docs] == [
        ("called", "d1", "late"), ("called", "d2", "late"), ("measured", "d2", "late")]
    v = seal.verify(db, CLIENT["id"])
    assert v["status"] == "ok" and v["late"] == 3
    assert seal.catch_up(db, CLIENT["id"])["status"] == seal.ALREADY

    # a seal claiming "at_issue" after the notice went out is refused by verify
    bad = _live_problems_for(dict(docs[0], sealed=seal.AT_ISSUE), db.rows("directives")[0])
    assert [p["check"] for p in bad] == ["order", "order"]


def _live_problems_for(doc, row):
    entry = {"seq": 1, "document": doc, "leaf": seal.leaf_of(doc)}
    return [p for p in seal._live_problems([entry], {row["id"]: row}, CLIENT["id"]) if p["check"] == "order"]


def test_measuring_a_move_never_sealed_seals_its_call_first(monkeypatch):
    db = FakeDB(directives=[_issued(1, status="approved")])
    cli = _measure_setup(monkeypatch, db, [_verdict("d1", "measured", 90.0, "isolated")])
    cli._measure_for_run(db, CLIENT, "run1", "amazon")
    rows = sorted(db.rows(seal.TABLE), key=lambda r: r["seq"])
    assert [(r["entry"], r["document"]["sealed"]) for r in rows] == [("called", "late"), ("measured", "at_measurement")]
    assert rows[1]["document"]["called_leaf"] == rows[0]["leaf"]


def test_a_deleted_clients_rows_keep_the_global_chain_whole():
    db = FakeDB(directives=[_issued(1), _issued(2, OTHER), _issued(3)])
    ds = {d["id"]: d for d in db.rows("directives")}
    seal.seal_called(db, CLIENT["id"], [ds["d1"]], sealed_at=T)
    seal.seal_called(db, OTHER["id"], [ds["d2"]], sealed_at=T)
    seal.seal_called(db, CLIENT["id"], [ds["d3"]], sealed_at=T)
    for r in db.rows(seal.TABLE):                  # what the migration's trigger does on a client's deletion
        if r["client_id"] == OTHER["id"]:
            r.update(client_id=None, document=None, directive_id=None)
    g = seal.verify(db, None)
    assert g["status"] == "ok" and g["redacted"] == 1
    assert seal.verify(db, CLIENT["id"])["status"] == "ok"


# ── the export, and the verifier a third party runs ──────────────────────────

def _export(db, client_id=CLIENT["id"]) -> tuple[bytes, list[str]]:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        lines = seal.write_export(z, db, client_id, VERIFIER)
    return buf.getvalue(), lines


def test_the_export_carries_what_an_offline_verifier_needs(monkeypatch):
    db = _sealed_db(2)
    for d in db.rows("directives"):
        d["status"] = "approved"
    cli = _measure_setup(monkeypatch, db, [_verdict("d1", "measured", 180.0, "attributable", {"p50": 180.0})])
    cli._measure_for_run(db, CLIENT, "run1", "amazon")
    seal.seal_called(db, OTHER["id"], [_issued(8, OTHER)], sealed_at=T)      # another client's entry after ours

    blob, lines = _export(db)
    z = zipfile.ZipFile(io.BytesIO(blob))
    assert {"record-seal.json", "verify-record.mjs"} <= set(z.namelist())
    assert "3 sealed entries (2 called, 1 measured)" in lines[0]
    b = json.loads(z.read("record-seal.json"))
    assert b["format"] == seal.FORMAT and b["client_id"] == CLIENT["id"] and b["algorithm"]
    for e in b["entries"]:
        assert {"seq", "global_seq", "entry", "entry_key", "document", "leaf", "prev_head", "head",
                "global_prev_head", "global_head"} <= set(e)
        assert e["document"]["client_id"] == CLIENT["id"]
    assert set(b["evidence"]) == {"d1", "d2"} and b["evidence"]["d1"]["after"] == {"p50": 180.0}
    assert "after" not in b["evidence"]["d1"]["before"]
    assert b["global"]["entries"] == 4 and len(b["global"]["leaves"]) == 4          # up to the other client's entry
    assert b["global"]["head"] == max(db.rows(seal.TABLE), key=lambda r: r["global_seq"])["global_head"]
    assert seal.verify_bundle(b)["status"] == "ok"
    assert z.read("verify-record.mjs") == VERIFIER.read_bytes()


def test_an_export_before_the_migration_says_so():
    blob, lines = _export(NoTable(directives=[]))
    b = json.loads(zipfile.ZipFile(io.BytesIO(blob)).read("record-seal.json"))
    assert b["status"] == seal.TABLE_MISSING and b["entries"] == [] and seal.MIGRATION in b["reason"]
    assert "nothing sealed yet (the Seal is not switched on for this Record yet)" in lines[0]   # the client's words
    assert seal.verify_bundle(b)["status"] == "empty"


@needs_node
def test_node_and_python_agree_on_the_engines_own_export(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", _REAL_RUN)
    monkeypatch.setattr(subprocess, "Popen", _REAL_POPEN)
    db = _sealed_db(3)
    blob, _ = _export(db)
    path = tmp_path / "acme-hubricon-export.zip"
    path.write_bytes(blob)
    short = sorted(db.rows(seal.TABLE), key=lambda r: r["seq"])[0]["leaf"][:12]
    run = subprocess.run([NODE, str(VERIFIER), str(path), "--seal", short, "--json"], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    theirs = json.loads(run.stdout)
    mine = seal.verify_bundle(json.loads(zipfile.ZipFile(io.BytesIO(blob)).read("record-seal.json")), [short])
    assert theirs == json.loads(json.dumps(mine))

    b = json.loads(zipfile.ZipFile(io.BytesIO(blob)).read("record-seal.json"))
    b["entries"][1]["document"]["expected_usd"] = "999.00"
    tampered = tmp_path / "record-seal.json"
    tampered.write_text(json.dumps(b))
    run = subprocess.run([NODE, str(VERIFIER), str(tampered)], capture_output=True, text=True)
    assert run.returncode == 1 and "BROKEN at entry 2" in run.stdout


@needs_node
def test_node_and_python_agree_on_leaves_of_random_documents(monkeypatch):
    """Random documents built to hurt: floats of every magnitude, integers past
    2**53, keys that sort differently by code point and by code unit, every
    escape. The leaf node computes is the leaf Python computes."""
    monkeypatch.setattr(subprocess, "run", _REAL_RUN)
    monkeypatch.setattr(subprocess, "Popen", _REAL_POPEN)
    rng = random.Random(20260925)
    keys = ["a", "B", "é", "€", "\U0001F600", "！", "", "10", "9", "sku", " "]

    def value(depth=0):
        kind = rng.randrange(8 if depth < 3 else 5)
        if kind == 0:
            return rng.random() * 10 ** rng.randint(-30, 30) * rng.choice((1, -1))
        if kind == 1:
            return rng.randint(-2 ** 62, 2 ** 62)
        if kind == 2:
            return "".join(rng.choice("aé€😀\"\\\n\t\u0001\u007f/ ") for _ in range(rng.randint(0, 8)))
        if kind == 3:
            return rng.choice([None, True, False, 0.0, -0.0, 1e21, 1e-7])
        if kind == 4:
            return round(rng.uniform(-1e6, 1e6), rng.randint(0, 6))
        if kind in (5, 6):
            return {rng.choice(keys) + str(rng.randint(0, 3)): value(depth + 1) for _ in range(rng.randint(0, 5))}
        return [value(depth + 1) for _ in range(rng.randint(0, 4))]

    docs = [value(1) for _ in range(300)]
    text = json.dumps(docs)
    js = ("import('" + VERIFIER.as_uri() + "').then(m => { const docs = JSON.parse(require('fs').readFileSync(0, "
          "'utf8')); process.stdout.write(JSON.stringify(docs.map(m.leafOf))); })")
    run = subprocess.run([NODE, "-e", js], input=text, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == [seal.leaf_of(d) for d in json.loads(text)]


# ── the command ──────────────────────────────────────────────────────────────

def test_the_command_verifies_reports_and_exits_by_the_result():
    db = _sealed_db(2)
    db.store["clients"] = [CLIENT]
    out: list[str] = []
    resolve = lambda _db, ident: CLIENT  # noqa: E731
    args = SimpleNamespace(action="verify", client="acme", global_chain=False, witness=[], no_live=False)
    assert seal.run_cli(db, args, resolve, out.append) == 0 and out[-1].startswith("OK")
    assert seal.run_cli(db, SimpleNamespace(**{**vars(args), "global_chain": True}), resolve, out.append) == 0
    db.rows("directives")[0]["expected_impact_usd"] = 1.0
    assert seal.run_cli(db, args, resolve, out.append) == 1
    assert any(line.startswith("BROKEN at entry 1") for line in out)

    out.clear()
    assert seal.run_cli(db, SimpleNamespace(action="status"), resolve, out.append) == 0
    assert "2 entries on the global chain" in out[0] and any("Acme" in line and "2 called" in line for line in out)
    assert any("not callable" in line for line in out)       # the fake has no public_record_seal()

    out.clear()
    assert seal.run_cli(NoTable(), SimpleNamespace(action="status"), resolve, out.append) == 2
    assert seal.MIGRATION in out[0]
    assert seal.run_cli(NoTable(), args, resolve, out.append) == 2


def test_hubricon_promises_names_the_seal_and_the_migration_it_waits_for():
    from hubricon_engine import cli
    rows = {r[0]: r for r in cli.promise_rows(FakeDB(clients=[], data_requests=[], invoices=[]))}
    assert rows["Every move sealed before its email"][2] is True
    rows = {r[0]: r for r in cli.promise_rows(NoTable(clients=[], data_requests=[], invoices=[]))}
    ok, detail = rows["Every move sealed before its email"][2:]
    assert ok is False and seal.MIGRATION in detail and "unsealed" in detail


def test_the_status_reports_the_published_head_when_it_matches():
    db = _sealed_db(1)
    head = db.rows(seal.TABLE)[0]["global_head"]
    db.rpcs[seal.RPC] = lambda: {"head": head, "entries": 1, "last_sealed_at": T.isoformat()}
    out: list[str] = []
    seal.run_cli(db, SimpleNamespace(action="status"), lambda *_: CLIENT, out.append)
    assert any("the same head" in line for line in out)
