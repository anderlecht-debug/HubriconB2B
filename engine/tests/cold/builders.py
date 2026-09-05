"""Builders for cold-engine tests. Nothing here touches a database or a network."""

from hubricon_engine.cold.snapshot import Item, ProspectSnapshot


def item(**kw) -> Item:
    base = dict(ref="B00TEST0001", url="https://www.amazon.com/dp/B00TEST0001",
                title="Test Brand Bamboo Cutting Board, Large", category="Home & Kitchen",
                price=24.99, reviews=1400, rank=3200, item_weight_oz=12.0,
                dims_in=(11.0, 8.0, 0.6), est_monthly_units=900.0,
                fulfilled_by_amazon=True)
    base.update(kw)
    # The harvest derives revenue from price x units, and select's plausibility
    # guard compares a finding against it. A fixture that overrides one without
    # the other trips that guard for a reason that has nothing to do with the
    # test.
    if "est_monthly_revenue" not in kw:
        price, units = base.get("price"), base.get("est_monthly_units")
        base["est_monthly_revenue"] = round(price * units, 2) if price and units else None
    return Item(**base)


def snapshot(items=None, **kw) -> ProspectSnapshot:
    base = dict(key="A1TESTSELLER", platform="amazon", provider="harvest",
                brand="Test Brand", business_name="Test Brand LLC",
                website="https://testbrand.com", email="dana@testbrand.com",
                email_confidence="published", first_name="Dana", last_name="Reyes",
                city="Austin", state="TX", country="US",
                est_monthly_revenue=180000.0, ratings_12mo=420)
    base.update(kw)
    return ProspectSnapshot(items=tuple(items if items is not None else [item()]), **base)
