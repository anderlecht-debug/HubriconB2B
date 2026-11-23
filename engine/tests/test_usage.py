"""The usage record: right payload, stable key, no network."""

from hubricon_engine import hwm, usage

LINE = "gid://shopify/AppSubscriptionLineItem/1?v=1&index=1"


def _statement(**over):
    s = hwm.run("a.myshopify.com", [{"month": "2026-01", "dollars": [
        {"id": "c", "usd": 1000, "grade": "direct"}]}])[0]
    s.update(over)
    return s


class Transport:
    def __init__(self, response=None, raises=None):
        self.calls, self.response, self.raises = [], response, raises

    def __call__(self, query, variables):
        self.calls.append((query, variables))
        if self.raises:
            raise self.raises
        return self.response


def test_payload_shape():
    p = usage.payload(_statement(), LINE)
    assert "appUsageRecordCreate" in p["query"] and "idempotencyKey" in p["query"]
    v = p["variables"]
    assert v["subscriptionLineItemId"] == LINE
    assert v["price"] == {"amount": "200.00", "currencyCode": "USD"}
    assert "2026-01" in v["description"]
    assert len(v["idempotencyKey"]) <= usage.IDEMPOTENCY_KEY_MAX


def test_idempotency_key_is_stable_and_changes_with_the_statement():
    a, b = _statement(), _statement()
    assert usage.idempotency_key(a) == usage.idempotency_key(b)
    assert usage.idempotency_key(a) != usage.idempotency_key(_statement(fee=199.0, net=199.0))
    assert usage.idempotency_key(a) != usage.idempotency_key(_statement(month="2026-02"))
    assert usage.idempotency_key(a) != usage.idempotency_key(_statement(shop="b.myshopify.com"))


def test_send_success():
    t = Transport({"data": {"appUsageRecordCreate": {
        "appUsageRecord": {"id": "gid://shopify/AppUsageRecord/9"}, "userErrors": []}}})
    r = usage.send(_statement(), t, LINE)
    assert r["status"] == "sent" and r["record_id"].endswith("/9") and r["amount"] == 200.0
    assert len(t.calls) == 1 and t.calls[0][1]["price"]["amount"] == "200.00"


def test_send_cap_reached_is_capped_not_error():
    t = Transport({"data": {"appUsageRecordCreate": {"appUsageRecord": None, "userErrors": [
        {"field": ["price"], "message": "Total price exceeds balance remaining"}]}}})
    r = usage.send(_statement(), t, LINE)
    assert r["status"] == "capped" and r["record_id"] is None


def test_send_other_errors():
    t = Transport({"data": {"appUsageRecordCreate": {"appUsageRecord": None, "userErrors": [
        {"field": ["subscriptionLineItemId"], "message": "Subscription line item not found"}]}}})
    assert usage.send(_statement(), t, LINE)["status"] == "error"
    assert usage.send(_statement(), Transport({"errors": [{"message": "Throttled"}]}), LINE)["status"] == "error"
    r = usage.send(_statement(), Transport(raises=TimeoutError("timed out")), LINE)
    assert r["status"] == "error" and "timed out" in r["errors"][0]


def test_nothing_to_bill_and_refund_due_send_nothing():
    t = Transport()
    zero = _statement(fee=0.0, net=0.0)
    assert usage.send(zero, t, LINE)["status"] == "nothing_to_bill"
    refund = _statement(fee=0.0, refunds=200.0, net=-200.0)
    r = usage.send(refund, t, LINE)
    assert r["status"] == "nothing_to_bill" and r["refund_due"] == 200.0
    assert t.calls == []


def test_refund_nets_against_the_fee():
    s = _statement(fee=300.0, refunds=100.0, net=200.0)
    p = usage.payload(s, LINE)
    assert p["variables"]["price"]["amount"] == "200.00"
    assert "refunded" in p["variables"]["description"]


def test_line_item_from_statement():
    t = Transport({"data": {"appUsageRecordCreate": {
        "appUsageRecord": {"id": "gid://shopify/AppUsageRecord/1"}, "userErrors": []}}})
    assert usage.send(_statement(subscription_line_item_id=LINE), t)["status"] == "sent"
