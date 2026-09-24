"""The settlement file read as a daily per-SKU price series."""

from hubricon_engine.models import daily


def _txn(day, sku, qty, sales, rebate=0.0, kind="Order"):
    return {"txn_datetime": f"{day}T10:00:00", "txn_date": day, "txn_type": kind, "sku": sku,
            "quantity": qty, "product_sales": sales, "promotional_rebates": rebate, "total": sales}


ROWS = [
    _txn("2026-08-01", "A", 2, 40.0), _txn("2026-08-01", "A", 1, 20.0, rebate=-2.0),
    _txn("2026-08-02", "A", 1, 21.0), _txn("2026-08-02", "B", 3, 30.0),
    _txn("2026-08-03", "A", 1, -20.0, kind="Refund"),     # a refund is not demand
    _txn("2026-08-09", "A", 1, 22.0),                      # outside the window below
]


def test_orders_only_and_gross_and_net_prices():
    series = daily.daily_sku_series(ROWS, "A", "2026-08-01", "2026-08-05")
    assert [s["date"] for s in series] == ["2026-08-01", "2026-08-02"]
    first = series[0]
    assert first["units"] == 3 and first["orders"] == 2
    assert first["price"] == 20.0
    assert first["price_net"] == round(58.0 / 3, 4)   # the $2 coupon lands on the net line only
    assert series[1]["price"] == 21.0


def test_days_without_orders_are_absent_not_zero():
    series = daily.daily_sku_series(ROWS, "A", "2026-08-01", "2026-08-31")
    assert "2026-08-03" not in {s["date"] for s in series}
    assert series[-1]["date"] == "2026-08-09"


def test_totals_span_the_account_and_accept_sku_less_rows():
    rows = ROWS + [{"txn_date": "2026-08-02", "txn_type": "Order", "sku": None, "quantity": None,
                    "product_sales": 15.0}]
    totals = daily.daily_totals(rows, "2026-08-01", "2026-08-05")
    by_day = {t["date"]: t for t in totals}
    assert by_day["2026-08-02"]["revenue"] == 66.0 and by_day["2026-08-02"]["orders"] == 3
    only_a = daily.daily_totals(rows, "2026-08-01", "2026-08-05", skus={"A"})
    assert {t["date"]: t["revenue"] for t in only_a}["2026-08-02"] == 36.0
