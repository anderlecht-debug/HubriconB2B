"""Shadow mode: weekly calls sealed on the Record before the week, nothing
executed, then graded against the week as it happened."""

import base64
import json
import os
from datetime import UTC, date, datetime, timedelta

import pytest
from fakedb import FakeDB
from test_lookback import CLIENT, store_data, synthetic_store

from hubricon_engine import seal, shadow, shopify_api, shopify_run

WEEK = date(2026, 11, 16)
ISSUED = "2026-11-15T12:00:00Z"
MEASURED = "2026-11-23T12:00:00Z"


def _full():
    return synthetic_store(start=date(2026, 9, 14), end=date(2026, 11, 30), out_since=date(2027, 1, 1))


def _before(full, week=WEEK):
    past = {**full, "today": week.isoformat()}
    data = store_data(past)
    data["sku_economics"] = [r for r in data["sku_economics"] if r["period_end"] < week.isoformat()]
    return data


def _econ(full):
    return shopify_api.weekly_economics(full["orders"], CLIENT, date(2026, 9, 14), date(2026, 11, 29), "UTC")


def test_calls_carry_a_90pct_range_and_are_never_executed():
    calls = shadow.calls(_before(_full()), CLIENT, WEEK, issued_at=ISSUED)
    fc = [c for c in calls if c["kind"] == shadow.FORECAST_KIND]
    assert {c["evidence"]["sku"] for c in fc} == {"RAISE", "GONE", "SLOW"}
    for c in calls:
        ev = c["evidence"]
        assert ev["executed"] is False and c["mandate"] == "shadow" and c["module"] == "shadow"
        assert c["action_text"].startswith("Shadow call, not executed.")
        assert ev["week_start"] == "2026-11-16" and ev["week_end"] == "2026-11-22"
    for c in fc:
        ev = c["evidence"]
        assert 0 <= ev["units_p5"] <= ev["units_p50"] <= ev["units_p95"]
        assert ev["delta_p5"] <= c["expected_impact_usd"] <= ev["delta_p95"]
        assert seal._promise_band(c) == (ev["delta_p5"], ev["delta_p95"])


def test_the_same_call_has_the_same_id_week_to_week_rerun():
    a = shadow.calls(_before(_full()), CLIENT, WEEK, issued_at=ISSUED)
    b = shadow.calls(_before(_full()), CLIENT, WEEK, issued_at=ISSUED)
    assert [c["id"] for c in a] == [c["id"] for c in b]
    c = shadow.calls(_before(_full(), WEEK + timedelta(days=7)), CLIENT, WEEK + timedelta(days=7), issued_at=ISSUED)
    assert not {x["id"] for x in a} & {x["id"] for x in c}


def test_calls_are_sealed_once_and_nothing_else_is_written():
    db = FakeDB()
    out = shadow.run(db, _before(_full()), CLIENT, WEEK, issued_at=ISSUED)
    assert out["seal"]["status"] == seal.SEALED and out["seal"]["sealed"] == len(out["calls"])
    rows = db.store["record_seals"]
    assert {r["document"]["module"] for r in rows} == {"shadow"}
    assert {r["document"]["mandate"] for r in rows} == {"shadow"}
    assert {t for t, *_ in db.writes} == {"record_seals"}      # no directive, no store write
    again = shadow.seal_calls(db, CLIENT, out["calls"], sealed_at=ISSUED)
    assert again["status"] == seal.ALREADY and len(db.store["record_seals"]) == len(rows)
    v = seal.verify(db, CLIENT, live=False)
    assert v["problems"] == [] and v["first_broken_seq"] is None, v


def test_grade_hits_and_gaps_against_the_week_that_happened():
    full = _full()
    db = FakeDB()
    calls = shadow.run(db, _before(full), CLIENT, WEEK, issued_at=ISSUED)["calls"]
    data = store_data(full)
    g = shadow.grade(calls, _econ(full), data["cogs_inputs"], db=db, client_id=CLIENT, measured_at=MEASURED)
    assert g["n_graded"] == 3 and 0 <= g["hits"] <= 3
    assert g["hit_rate"] == round(g["hits"] / 3, 4)
    for r in g["rows"]:
        assert r["hit"] == (r["range_units"][0] <= r["actual_units"] <= r["range_units"][1])
    assert g["gap_units"] == round(sum(r["gap_units"] for r in g["rows"]), 2)
    assert g["gap_usd"] == round(sum(r["gap_usd"] for r in g["rows"]), 2)
    # the same harness that scores issued moves
    assert g["replay"]["n_scored"] == 3 and g["replay"]["n_banded"] == 3
    # each grade sealed as a measured entry answering its call
    assert g["seal"]["status"] == seal.SEALED
    measured = [r for r in db.store["record_seals"] if r["entry"] == "measured"]
    called = {r["leaf"] for r in db.store["record_seals"] if r["entry"] == "called"}
    assert len(measured) == 3 and {r["document"]["called_leaf"] for r in measured} <= called
    v = seal.verify(db, CLIENT, live=False)
    assert v["problems"] == [] and v["first_broken_seq"] is None, v


def test_grade_by_hand_numbers():
    call = {"id": "x", "kind": shadow.FORECAST_KIND, "expected_impact_usd": 100.0,
            "evidence": {"sku": "A", "week_start": "2026-11-16", "units_p50": 10.0, "units_p5": 6.0,
                         "units_p95": 14.0, "delta_p5": 60.0, "delta_p95": 140.0}}
    miss = {**call, "id": "y", "evidence": {**call["evidence"], "sku": "B"}}
    econ = [{"sku": "A", "period_start": "2026-11-16", "period_end": "2026-11-22", "units_sold": 12,
             "sales": 120.0, "channel": "shopify", "asin": None, "referral_fees": 0.0},
            {"sku": "B", "period_start": "2026-11-16", "period_end": "2026-11-22", "units_sold": 20,
             "sales": 200.0, "channel": "shopify", "asin": None, "referral_fees": 0.0}]
    g = shadow.grade([call, miss], econ)
    assert g["hits"] == 1 and g["hit_rate"] == 0.5
    assert g["gap_units"] == 12.0          # (12 - 10) + (20 - 10)
    # no cost sheet: units are graded, profit is not
    assert "gap_usd" not in g["rows"][0] and g["replay"] is None


def test_a_sku_with_no_sales_in_the_week_grades_as_zero():
    call = {"id": "x", "kind": shadow.FORECAST_KIND, "expected_impact_usd": None,
            "evidence": {"sku": "A", "week_start": "2026-11-16", "units_p50": 3.0, "units_p5": 0.0, "units_p95": 6.0}}
    g = shadow.grade([call], [])
    assert g["rows"][0]["actual_units"] == 0 and g["hits"] == 1


def test_moves_the_engine_would_make_are_called_with_dollars(monkeypatch):
    def drafts(*a, **k):
        return [{"module": "pricing", "kind": "price_step", "expected_impact_usd": 42.5, "mandate": "standing",
                 "action_text": "Move RAISE $22.00 → $23.10", "dedupe_key": "abc",
                 "evidence": {"sku": "RAISE", "delta_p5": -5.0, "delta_p50": 42.5, "delta_p95": 90.0}},
                {"module": "pricing", "kind": "price_step", "expected_impact_usd": None, "evidence": {}}]
    monkeypatch.setattr(shadow.directives_mod, "draft_directives", drafts)
    calls = shadow.calls(_before(_full()), CLIENT, WEEK, issued_at=ISSUED)
    moves = [c for c in calls if c["kind"].startswith("shadow_price")]
    assert len(moves) == 1
    m = moves[0]
    assert m["expected_impact_usd"] == 42.5 and m["evidence"]["executed"] is False
    assert m["action_text"] == "Shadow call, not executed. Would do: Move RAISE $22.00 → $23.10"
    db = FakeDB()
    assert shadow.seal_calls(db, CLIENT, calls, sealed_at=ISSUED)["status"] == seal.SEALED
    # a move is never graded: it was not made
    assert all(r["id"] != m["id"] for r in shadow.grade(calls, _econ(_full()))["rows"])


# ── the scheduled job, end to end on fakes ──────────────────────────────────

class _Bucket:
    def __init__(self, files):
        self.files = files

    def upload(self, path, blob, opts=None):
        self.files[path] = blob

    def download(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]


class StoreDB(FakeDB):
    def __init__(self, **tables):
        super().__init__(**tables)
        self.files = {}
        bucket = _Bucket(self.files)
        self.storage = type("S", (), {"from_": staticmethod(lambda name: bucket)})()


def test_shadow_job_seals_next_week_then_grades_it_once_it_has_happened():
    full = _full()
    db = StoreDB()
    store = {"shop": "acme.myshopify.com", "token": "t", "client_id": CLIENT, "row": {}}
    at = lambda d: datetime(d.year, d.month, d.day, 9, 45, tzinfo=UTC)
    first = shopify_run.shadow_store(db, store, WEEK, 60, pulled={**full, "today": WEEK.isoformat()}, now=at(WEEK))
    nxt = WEEK + timedelta(days=7)
    assert first["graded"] is None and first["seal"] == seal.SEALED and first["week_start"] == nxt.isoformat()
    assert f"shopify/acme.myshopify.com/shadow/{nxt.isoformat()}.json" in db.files
    after = nxt + timedelta(days=7)           # the Monday after the predicted week ends
    second = shopify_run.shadow_store(db, store, after, 60, pulled={**full, "today": after.isoformat()},
                                      now=at(after))
    assert second["graded"]["n_graded"] == first["calls"] and second["refused"] == []
    assert f"shopify/acme.myshopify.com/shadow/{nxt.isoformat()}.grade.json" in db.files


def test_no_call_is_sealed_once_its_week_is_about_to_begin():
    db = StoreDB()
    store = {"shop": "acme.myshopify.com", "token": "t", "client_id": CLIENT, "row": {}}
    late = datetime(2026, 11, 22, 23, 0, tzinfo=UTC)      # Sunday night: the week starts Monday
    out = shopify_run.shadow_store(db, store, WEEK, 60, pulled={**_full(), "today": WEEK.isoformat()}, now=late)
    assert out["seal"] == "too_late" and not [p for p in db.files if p.endswith("-23.json")]


def test_a_stored_call_edited_after_sealing_is_refused():
    db = FakeDB()
    calls = shadow.run(db, _before(_full()), CLIENT, WEEK, issued_at=ISSUED)["calls"]
    edited = json.loads(json.dumps(calls))
    edited[0]["evidence"]["units_p95"] = 10 ** 6
    ok, bad = shopify_run.untampered(db, CLIENT, edited)
    assert bad == [edited[0]["id"]] and len(ok) == len(calls) - 1


def test_token_decrypts_as_lib_shopify_encrypts_it():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key, iv, shop = os.urandom(32), os.urandom(12), "acme.myshopify.com"
    sealed = AESGCM(key).encrypt(iv, b"shpat_secret", shop.encode())   # ciphertext || tag
    blob = "v1:" + base64.urlsafe_b64encode(iv + sealed[-16:] + sealed[:-16]).decode().rstrip("=")
    assert shopify_run.decrypt_token(blob, key.hex(), shop) == "shpat_secret"
    from cryptography.exceptions import InvalidTag
    with pytest.raises(InvalidTag):     # the shop domain is bound as AAD
        shopify_run.decrypt_token(blob, key.hex(), "other.myshopify.com")


def test_meter_months_leave_out_shadow_calls():
    ds = [{"id": 1, "module": "pricing", "measured_impact_usd": 120.0, "measured_at": "2026-10-03", "attribution": "direct"},
          {"id": 2, "module": "shadow", "measured_impact_usd": 999.0, "measured_at": "2026-10-04"},
          {"id": 3, "module": "pricing", "measured_impact_usd": None, "measured_at": None},
          {"id": 4, "module": "ads", "measured_impact_usd": -20.0, "measured_at": "2026-11-02", "attribution": "attributable"}]
    months = shopify_run.months_of(ds)
    assert [m["month"] for m in months] == ["2026-10", "2026-11"]
    assert [d["id"] for m in months for d in m["dollars"]] == ["1", "4"]


def test_cli_parses_the_three_jobs():
    p = shopify_run.parser()
    assert p.parse_args(["ingest"]).days == 60
    assert p.parse_args(["meter", "--send"]).send is True
    with pytest.raises(SystemExit):
        p.parse_args(["sweep"])
