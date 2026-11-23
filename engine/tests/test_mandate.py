"""The brand's limits: moves inside them run after shadow mode, sealed before
the write; everything else waits for the brand's tap."""

from datetime import date

from fakedb import FakeDB

from hubricon_engine import mandate, seal

CLIENT = "00000000-0000-0000-0000-00000000cccc"
INSTALLED = "2026-10-01T00:00:00Z"
AFTER = date(2026, 11, 23)        # more than four weeks after install
DURING = date(2026, 10, 15)
WRITE = "read_orders,read_products,read_inventory,write_products"
ON = mandate.settings({"price_moves_enabled": True, "max_price_step_pct": 5})


def _step(sku="RAISE", p0=20.0, p_new=21.0, expected=42.5, kind="price_step", standing=True):
    return {"module": "pricing", "kind": kind, "mandate": "standing" if standing else "explicit",
            "expected_impact_usd": expected, "action_text": f"Move {sku} ${p0} -> ${p_new}",
            "dedupe_key": f"pricing:{kind}:{sku}",
            "evidence": {"sku": sku, "p0": p0, "p_new": p_new, "step_fraction": p_new / p0 - 1}}


VARIANTS = {"RAISE": {"variant_id": "gid://shopify/ProductVariant/1", "product_id": "gid://shopify/Product/1",
                      "price": 20.0}}


class Transport:
    def __init__(self, db=None, fail=False):
        self.calls, self.db, self.fail = [], db, fail
        self.seals_at_write = None

    def __call__(self, query, variables):
        self.calls.append((query, variables))
        if self.db is not None:
            self.seals_at_write = len(self.db.store.get("record_seals", []))
        if self.fail:
            return {"data": {"productVariantsBulkUpdate": {"productVariants": [],
                                                          "userErrors": [{"message": "nope"}]}}}
        v = variables["variants"][0]
        return {"data": {"productVariantsBulkUpdate": {"productVariants": [{"id": v["id"], "price": v["price"]}],
                                                      "userErrors": []}}}


def test_defaults_act_on_nothing():
    s = mandate.settings(None)
    assert s == {"max_price_step_pct": 5.0, "price_moves_enabled": False, "reorder_needs_tap": True,
                 "shadow_weeks": 4}
    out = mandate.sort([_step()], s, installed_at=INSTALLED, today=AFTER, scopes=WRITE)
    assert not out["execute"] and out["awaiting_tap"][0]["mandate_why"] == "price moves are off in your limits"
    # a row can only narrow the terms' 5%
    assert mandate.settings({"max_price_step_pct": 12})["max_price_step_pct"] == 5.0


def test_sort_by_the_limits():
    narrow = mandate.settings({"price_moves_enabled": True, "max_price_step_pct": 3})
    moves = [_step(), _step("SMALL", 20.0, 20.5), _step("GUARD", 20.0, 20.5, standing=False),
             _step("REORDER", kind="inventory_reorder"), _step("NOEXP", expected=None)]
    out = mandate.sort(moves, narrow, installed_at=INSTALLED, today=AFTER, scopes=WRITE)
    assert [m["evidence"]["sku"] for m in out["execute"]] == ["SMALL"]
    tap = {m["evidence"]["sku"]: m["mandate_why"] for m in out["awaiting_tap"]}
    assert set(tap) == {"RAISE", "GUARD", "REORDER", "NOEXP"}
    assert "larger than your 3% limit" in tap["RAISE"] and "tap" in tap["REORDER"]


def test_shadow_mode_and_missing_write_scope_execute_nothing():
    during = mandate.sort([_step()], ON, installed_at=INSTALLED, today=DURING, scopes=WRITE)
    assert not during["execute"] and len(during["shadow"]) == 1
    assert mandate.in_shadow(None, ON, AFTER)                  # unknown install date: shadow
    longer = mandate.settings({"price_moves_enabled": True, "shadow_weeks": 12})
    assert mandate.sort([_step()], longer, installed_at=INSTALLED, today=AFTER, scopes=WRITE)["shadow"]
    read_only = mandate.sort([_step()], ON, installed_at=INSTALLED, today=AFTER, scopes="read_products")
    assert not read_only["execute"] and "write access" in read_only["awaiting_tap"][0]["mandate_why"]


def test_execute_seals_before_the_write_and_records_for_measurement():
    db = FakeDB()
    t = Transport(db)
    out = mandate.execute(db, CLIENT, [_step()], ON, VARIANTS, t, installed_at=INSTALLED, today=AFTER,
                          scopes=WRITE, now="2026-11-23T09:00:00Z")
    assert [r["status"] for r in out] == ["executed"]
    assert t.seals_at_write == 1                         # the seal was on the chain when the write went out
    q, v = t.calls[0]
    assert "productVariantsBulkUpdate" in q
    assert v == {"productId": "gid://shopify/Product/1",
                 "variants": [{"id": "gid://shopify/ProductVariant/1", "price": "21.00"}]}
    doc = db.store["record_seals"][0]["document"]
    assert doc["entry"] == "called" and doc["kind"] == "price_step" and doc["mandate"] == "standing"
    row = db.store["directives"][0]
    assert row["status"] == "done" and row["executed_by"] == mandate.EXECUTED_BY and row["executed_at"]
    assert row["evidence"]["executed"] is True and row["evidence"]["variant_id"] == VARIANTS["RAISE"]["variant_id"]
    assert seal.verify(db, CLIENT, live=False)["problems"] == []
    # the same day again: already sealed, and the directive row is the same id
    again = mandate.execute(db, CLIENT, [_step()], ON, VARIANTS, Transport(), installed_at=INSTALLED,
                            today=AFTER, scopes=WRITE)
    assert again[0]["id"] == out[0]["id"] and len(db.store["record_seals"]) == 1


def test_a_moved_live_price_or_an_outside_move_is_never_written():
    db = FakeDB()
    t = Transport()
    moved = {"RAISE": {**VARIANTS["RAISE"], "price": 19.0}}
    out = mandate.execute(db, CLIENT, [_step(), _step("RAISE", 20.0, 23.0)], ON, moved, t,
                          installed_at=INSTALLED, today=AFTER, scopes=WRITE)
    assert [r["status"] for r in out] == ["refused", "refused"]
    assert "live price" in out[0]["why"] and "larger" in out[1]["why"]
    assert not t.calls and not db.store.get("record_seals") and not db.store.get("directives")


def test_no_seal_means_no_write(monkeypatch):
    db, t = FakeDB(), Transport()
    monkeypatch.setattr(mandate.sealmod, "seal_called",
                        lambda *a, **k: {"status": seal.FAILED, "reason": "down", "short": {}})
    out = mandate.execute(db, CLIENT, [_step()], ON, VARIANTS, t, installed_at=INSTALLED, today=AFTER, scopes=WRITE)
    assert out[0]["status"] == "refused" and "nothing written" in out[0]["why"] and not t.calls


def test_a_refused_write_is_recorded_closed():
    db = FakeDB()
    out = mandate.execute(db, CLIENT, [_step()], ON, VARIANTS, Transport(fail=True), installed_at=INSTALLED,
                          today=AFTER, scopes=WRITE)
    assert out[0]["status"] == "failed"
    row = db.store["directives"][0]
    assert row["status"] == "closed" and row["executed_at"] is None and "nope" in row["measurement_notes"]


def test_variant_index_reads_bulk_lines():
    lines = [{"id": "gid://shopify/Product/1", "title": "W"},
             {"id": "gid://shopify/ProductVariant/11", "sku": "A", "price": "19.98", "__parentId": "gid://shopify/Product/1"}]
    assert mandate.variant_index(lines) == {"A": {"variant_id": "gid://shopify/ProductVariant/11",
                                                  "product_id": "gid://shopify/Product/1", "price": 19.98}}


def test_the_weekly_job_executes_inside_and_parks_the_rest(monkeypatch):
    import json

    from test_shadow import StoreDB

    import hubricon_engine.directives as directives_mod
    from hubricon_engine import shopify_run
    db = StoreDB()
    db.table("shopify_mandates").insert({"shop_domain": "acme.myshopify.com", "price_moves_enabled": True,
                                         "max_price_step_pct": 5}).execute()
    db.table("shopify_shops").insert({"shop_domain": "acme.myshopify.com", "mode": "shadow"}).execute()
    monkeypatch.setattr(directives_mod, "draft_directives",
                        lambda *a, **k: [_step(), _step("BIG", 20.0, 25.0)])
    row = {"installed_at": INSTALLED, "scopes": WRITE, "mode": "shadow"}
    store = {"shop": "acme.myshopify.com", "token": "t", "client_id": CLIENT, "row": row}
    products = [{"id": "gid://shopify/Product/1"},
                {"id": "gid://shopify/ProductVariant/1", "sku": "RAISE", "price": "20.00",
                 "__parentId": "gid://shopify/Product/1"}]
    t = Transport(db)
    out = shopify_run.mandate_store(db, store, AFTER, {}, {"products": products}, transport=t)
    assert out["executed"] == 1 and out["awaiting_tap"] == 1 and not out["in_shadow"]
    tap = json.loads(db.files["shopify/acme.myshopify.com/awaiting_tap.json"])
    assert tap["label"] == "awaiting your tap" and tap["moves"][0]["sku"] == "BIG"
    assert db.store["shopify_shops"][0]["mode"] == "live"
    # in shadow mode the same week writes nothing
    t2 = Transport()
    out2 = shopify_run.mandate_store(db, {**store, "row": {**row, "installed_at": "2026-11-20"}}, AFTER, {},
                                     {"products": products}, transport=t2)
    assert out2["executed"] == 0 and out2["in_shadow"] and not t2.calls
