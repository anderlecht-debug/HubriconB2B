"""The ledger of anyone's moves: seen in the data, sealed when seen, graded
where it can be, labelled not randomised, and never billed."""

from datetime import date, timedelta

import pytest
from fakedb import FakeDB
from test_lookback import CLIENT, store_data, synthetic_store

from hubricon_engine import hwm, ledger, seal, shopify_run

D0, D1 = date(2026, 10, 20), date(2026, 10, 27)


def _products(price="20.00", qty=300, status="ACTIVE", extra=()):
    return [{"id": "gid://shopify/Product/1", "title": "Raise", "status": status},
            {"id": "gid://shopify/ProductVariant/1", "sku": "RAISE", "price": price, "inventoryQuantity": qty,
             "__parentId": "gid://shopify/Product/1"}, *extra]


def test_detects_price_archive_and_receipt_and_skips_ours():
    a = ledger.snapshot(_products(), D0)
    b = ledger.snapshot(_products("22.00", 600, "ARCHIVED"), D1)
    found = ledger.detect(a, b, CLIENT, detected_at="2026-10-27T03:00:00Z")
    kinds = {e["kind"]: e for e in found}
    assert set(kinds) == set(ledger.KINDS)
    p = kinds["observed_price_change"]
    assert p["evidence"]["price_from"] == 20.0 and p["evidence"]["price_to"] == 22.0
    assert kinds["observed_receipt"]["evidence"]["units_received"] == 300
    assert kinds["observed_archive"]["evidence"]["status_to"] == "ARCHIVED"
    for e in found:
        assert e["module"] == "ledger" and e["mandate"] == "observed" and e["status"] == "observed"
        assert e["evidence"]["executed"] is False and e["evidence"]["ours"] is False
        assert e["action_text"].startswith("Observed, not ours:") and e["label"] == "observed, not ours"
        assert e["expected_impact_usd"] is None
    ours = ledger.detect(a, b, CLIENT, ours={("gid://shopify/ProductVariant/1", 22.0)})
    assert "observed_price_change" not in {e["kind"] for e in ours}
    assert ledger.detect(None, b, CLIENT) == []
    # small restock and sales are not receipts
    assert not ledger.detect(a, ledger.snapshot(_products(qty=310), D1), CLIENT)


def test_sealed_when_seen():
    db = FakeDB()
    found = ledger.detect(ledger.snapshot(_products(), D0), ledger.snapshot(_products("22.00"), D1), CLIENT,
                          detected_at="2026-10-27T03:00:00Z")
    out = ledger.seal(db, CLIENT, found, sealed_at="2026-10-27T03:00:00Z")
    assert out["status"] == seal.SEALED
    doc = db.store["record_seals"][0]["document"]
    assert doc["module"] == "ledger" and doc["mandate"] == "observed" and doc["expected_usd"] is None


def test_price_change_graded_with_the_lookback_measurement_and_labelled():
    full = synthetic_store(start=date(2026, 9, 24), end=date(2026, 11, 23))   # RAISE goes 20 -> 22 on 24 Oct
    data = store_data(full)
    e = ledger.detect(ledger.snapshot(_products(), D0), ledger.snapshot(_products("22.00"), D1), CLIENT)[0]
    early = ledger.grade_one(e, data, D1 + timedelta(days=3))
    assert not early["graded"] and "not graded yet" in early["basis"]
    db = FakeDB()
    ledger.seal(db, CLIENT, [e])
    g = ledger.grade([e], data, date(2026, 11, 23), db=db, client_id=CLIENT)[0]
    assert g["graded"] and g["usd_low"] <= g["usd"] <= g["usd_high"]
    assert g["label"] == ledger.GRADE_LABEL and "not randomised" in g["label"] and "never billed" in g["label"]
    assert g["billed"] is False and g["randomised"] is False
    measured = [r["document"] for r in db.store["record_seals"] if r["document"]["entry"] == "measured"]
    assert measured and measured[0]["grade"] == ledger.ATTRIBUTION


def test_hwm_never_includes_ledger_entries():
    """A ledger entry, even graded and measured, never reaches the fee."""
    e = ledger.detect(ledger.snapshot(_products(), D0), ledger.snapshot(_products("22.00"), D1), CLIENT)[0]
    as_measured = {**e, "measured_impact_usd": 900.0, "measured_at": "2026-11-23T00:00:00Z",
                   "attribution": ledger.ATTRIBUTION}
    ours = {"id": "d-1", "module": "pricing", "mandate": "standing", "measured_impact_usd": 100.0,
            "measured_at": "2026-11-20T00:00:00Z", "attribution": "isolated"}
    months = shopify_run.months_of([as_measured, ours, {**as_measured, "module": "pricing", "id": "x"}])
    ids = [d["id"] for m in months for d in m["dollars"]]
    assert ids == ["d-1"]
    statements = hwm.run("s.myshopify.com", months)
    assert statements[-1]["cumulative"] == 100.0
    # and the grade label itself is refused by the fee rule
    with pytest.raises(ValueError):
        hwm.grade_of(ledger.ATTRIBUTION)
    with pytest.raises(ValueError):
        hwm.run("s.myshopify.com", [{"month": "2026-11", "dollars": [
            {"id": "L", "usd": 900.0, "grade": ledger.ATTRIBUTION}]}])


def test_summary_carries_labels():
    e = ledger.detect(ledger.snapshot(_products(), D0), ledger.snapshot(_products("22.00"), D1), CLIENT)
    s = ledger.summary(e, [ledger.grade_one(x, {}, D1) for x in e])
    assert s["label"] == "observed, not ours" and "never billed" in s["note"]
    assert s["entries"][0]["grade"]["label"] == ledger.GRADE_LABEL


def test_nightly_ingest_keeps_a_sealed_ledger_for_the_app():
    import json

    from test_shadow import StoreDB
    db = StoreDB()
    store = {"shop": "acme.myshopify.com", "token": "t", "client_id": CLIENT, "row": {}}
    tables = {"sku_economics": [], "cogs_inputs": []}
    first = shopify_run.ledger_store(db, store, D0, tables, {"products": _products()})
    assert first["seen"] == 0 and "shopify/acme.myshopify.com/snapshot.json" in db.files
    second = shopify_run.ledger_store(db, store, D1, tables, {"products": _products("22.00")})
    assert second["seen"] == 1 and second["seal"] == seal.SEALED and second["entries"] == 1
    page = json.loads(db.files["shopify/acme.myshopify.com/ledger.json"])
    assert page["label"] == "observed, not ours" and page["entries"][0]["kind"] == "observed_price_change"
    # seen again the next night: nothing new
    third = shopify_run.ledger_store(db, store, D1 + timedelta(days=1), tables, {"products": _products("22.00")})
    assert third["seen"] == 0 and third["entries"] == 1
