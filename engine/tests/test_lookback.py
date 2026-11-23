"""The free look-back: a synthetic store pulled through the bulk-API path, so
the rows are exactly the ones the CSV ingest would write, then priced with the
engine's own models. Every figure must carry the hindsight label."""

from datetime import date, datetime, timedelta

import numpy as np

from hubricon_engine import lookback, shopify_api

CLIENT = "00000000-0000-0000-0000-00000000cccc"
TODAY = date(2026, 11, 23)
START = TODAY - timedelta(days=60)
TZ = "UTC"


def _m(a):
    return {"shopMoney": {"amount": f"{a:.2f}"}}


def synthetic_store(seed: int = 7, start: date = START, end: date = TODAY, out_since: date | None = None):
    """Bulk JSONL lines for a three-SKU store:
       RAISE  $20 -> $22 halfway through, demand answering at elasticity -1.5
       GONE   steady seller, nothing sold since `out_since`, zero stock now
       SLOW   0.3 a day against 400 on hand"""
    rng = np.random.default_rng(seed)
    out_since = out_since or (end - timedelta(days=12))
    mid = start + (end - start) / 2
    orders, n = [], 0
    d = start
    while d < end:
        for sku, price, rate in (("RAISE", 20.0 if d < mid else 22.0, None), ("GONE", 15.0, 5.0), ("SLOW", 30.0, 0.3)):
            if sku == "RAISE":
                rate = 10.0 * (price / 20.0) ** -1.5
            if sku == "GONE" and d >= out_since:
                continue
            q = int(rng.poisson(rate))
            if q <= 0:
                continue
            n += 1
            oid = f"gid://shopify/Order/{n}"
            stamp = datetime(d.year, d.month, d.day, 15, 0, 0).strftime("%Y-%m-%dT%H:%M:%SZ")
            orders.append({"id": oid, "name": f"#{1000 + n}", "email": f"c{n % 40}@x.co", "createdAt": stamp,
                           "cancelledAt": None, "displayFinancialStatus": "PAID", "totalRefundedSet": _m(0)})
            orders.append({"id": f"gid://shopify/LineItem/{n}", "name": sku.title(), "sku": sku, "quantity": q,
                           "originalUnitPriceSet": _m(price), "totalDiscountSet": _m(0), "__parentId": oid})
        d += timedelta(days=1)
    products = []
    for i, (sku, price, cost, qty) in enumerate((("RAISE", 22.0, 8.0, 300), ("GONE", 15.0, 5.0, 0),
                                                  ("SLOW", 30.0, 12.0, 400)), start=1):
        pid = f"gid://shopify/Product/{i}"
        products.append({"id": pid, "handle": sku.lower(), "title": sku.title(), "vendor": "Acme",
                         "productType": "Pet", "status": "ACTIVE"})
        products.append({"id": f"gid://shopify/ProductVariant/{i}", "sku": sku, "price": f"{price:.2f}",
                         "compareAtPrice": None, "inventoryQuantity": qty,
                         "selectedOptions": [{"name": "Title", "value": "Default Title"}],
                         "inventoryItem": {"id": f"gid://shopify/InventoryItem/{i}", "unitCost": {"amount": f"{cost}"},
                                           "measurement": {"weight": {"value": 300, "unit": "GRAMS"}}},
                         "__parentId": pid})
    inventory = []
    for i, (sku, qty) in enumerate((("RAISE", 300), ("GONE", 0), ("SLOW", 400)), start=1):
        iid = f"gid://shopify/InventoryItem/{i}"
        inventory.append({"id": iid, "sku": sku, "variant": {"id": f"v{i}", "selectedOptions": [
            {"name": "Title", "value": "Default Title"}], "product": {"handle": sku.lower(), "title": sku.title()}}})
        inventory.append({"id": f"gid://shopify/InventoryLevel/{i}", "location": {"name": "Main"},
                          "quantities": [{"name": "available", "quantity": qty}, {"name": "on_hand", "quantity": qty},
                                         {"name": "committed", "quantity": 0}, {"name": "incoming", "quantity": 0}],
                          "__parentId": iid})
    return {"shop": {"timezone": TZ, "single_location": True}, "since": start.isoformat(), "today": end.isoformat(),
            "orders": orders, "products": products, "inventory": inventory}


def store_data(pulled: dict, client_id: str = CLIENT, weekly: bool = True) -> dict:
    """The tables a run reads, from a pull: weekly sku_economics (the same
    parser, once per week), the products' cost sheet and the stock snapshot."""
    tables = {t: rows for t, rows, _ in shopify_api.ingest(pulled, client_id)}
    if weekly:
        tables["sku_economics"] = shopify_api.weekly_economics(
            pulled["orders"], client_id, date.fromisoformat(pulled["since"]),
            date.fromisoformat(pulled["today"]) - timedelta(days=1), pulled["shop"]["timezone"])
    return tables


def _look():
    pulled = synthetic_store()
    return lookback.run(store_data(pulled), today=TODAY, window_days=60,
                        last_sold=shopify_api.last_sold(pulled["orders"], TZ))


def test_every_figure_is_labelled_hindsight():
    out = _look()
    assert out["items"]
    assert out["label"] == "hindsight, not a sealed call"
    for it in out["items"]:
        assert it["label"] == "hindsight, not a sealed call"
    assert out["summary"] and all(s.startswith("Hindsight, not a sealed call:") for s in out["summary"])
    assert out["total"]["label"] == lookback.LABEL


def test_the_price_raise_is_found_and_priced_with_a_range():
    out = _look()
    raise_ = [i for i in out["items"] if i["kind"] == "price_change" and i["sku"] == "RAISE"]
    assert len(raise_) == 1
    it = raise_[0]
    assert it["price_from"] == 20.0 and it["price_to"] == 22.0
    assert it["usd"] is not None and it["usd_low"] <= it["usd"] <= it["usd_high"]
    # demand fell when the price rose
    assert it["units_per_day_after"] < it["units_per_day_before"]


def test_the_stockout_costs_profit_over_the_days_out():
    out = _look()
    gone = [i for i in out["items"] if i["kind"] == "stockout"]
    assert [i["sku"] for i in gone] == ["GONE"]
    g = gone[0]
    assert 12 <= g["days_out"] <= 14
    # about 5 a day missed, at $15 less fees less $5 cost
    assert 3 * g["days_out"] < g["units_missed"] < 7 * g["days_out"]
    assert g["usd"] < 0 and g["usd_low"] <= g["usd"] <= g["usd_high"] <= 0


def test_slow_stock_ties_up_capital():
    out = _look()
    slow = [i for i in out["items"] if i["kind"] == "slow_stock"]
    assert "SLOW" in [i["sku"] for i in slow]
    s = next(i for i in slow if i["sku"] == "SLOW")
    assert s["excess_units"] > 300 and s["cash_tied_up"] > 300 * 12 * 0.8
    # 12% a year for 60 days on ~$4,000 is about $80
    assert -150 < s["usd"] < 0
    assert "RAISE" not in [i["sku"] for i in slow]


def test_the_total_adds_the_priced_items():
    out = _look()
    priced = [i for i in out["items"] if i["usd"] is not None]
    assert out["total"]["n_priced"] == len(priced)
    assert abs(out["total"]["usd"] - sum(i["usd"] for i in priced)) < 0.05


def test_no_cost_means_units_only_and_no_dollars():
    pulled = synthetic_store()
    for line in pulled["products"]:
        if "inventoryItem" in line:
            line["inventoryItem"]["unitCost"] = None
    data = store_data(pulled)
    assert data["cogs_inputs"] == []
    out = lookback.run(data, today=TODAY, last_sold=shopify_api.last_sold(pulled["orders"], TZ))
    gone = next(i for i in out["items"] if i["kind"] == "stockout")
    assert gone["usd"] is None and gone["units_missed"] > 0
    assert all(i["usd"] is None for i in out["items"])


def test_an_empty_store_looks_back_on_nothing():
    out = lookback.run({}, today=TODAY)
    assert out["items"] == [] and out["summary"] == [] and out["total"]["usd"] == 0
