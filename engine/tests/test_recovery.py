from datetime import date, timedelta

from hubricon_engine.models import recovery

TODAY = date(2026, 9, 1)


def _ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()


def _data(**overrides):
    base = {
        "sku_economics": [{"sku": "WIDGET-BLUE", "asin": "B0CHILD001", "period_start": "2026-08-01",
                           "period_end": "2026-08-31", "units_sold": 300, "avg_sales_price": 29.99, "sales": 8997}],
        "cogs_inputs": [{"sku": "WIDGET-BLUE", "unit_cost_usd": 4.0, "inbound_freight_per_unit_usd": 1.0,
                         "packaging_per_unit_usd": 0, "other_cost_per_unit_usd": 0}],
        "inventory_ledger": [], "fba_reimbursements": [], "fba_returns": [], "settlement_transactions": [],
    }
    base.update(overrides)
    return base


def _adj(days_ago, qty, reason, sku="WIDGET-BLUE", unreconciled=None, ref="T1"):
    return {"event_date": _ago(days_ago), "event_type": "Adjustments", "reference_id": ref, "sku": sku,
            "fnsku": "X001", "asin": "B0CHILD001", "quantity": qty, "reason": reason,
            "unreconciled_qty": unreconciled, "fulfillment_center": "PHX7", "disposition": "SELLABLE"}


def test_warehouse_loss_nets_found_and_reimbursed_units():
    data = _data(
        inventory_ledger=[_adj(40, -5, "M"), _adj(35, 2, "F", ref="T2")],
        fba_reimbursements=[{"approval_date": _ago(20), "reimbursement_id": "R1", "reason": "Lost:Warehouse",
                             "sku": "WIDGET-BLUE", "quantity_reimbursed_total": 1, "amount_total": 5.0}],
    )
    out = recovery.run(data, today=TODAY)
    assert out["status"] == "ok"
    claims = [c for c in out["claims"] if c["claim_type"] == "warehouse_lost"]
    assert len(claims) == 1
    c = claims[0]
    assert c["units"] == 2                      # 5 lost − 2 found − 1 reimbursed
    assert c["unit_value"] == 5.0               # landed cost 4 + 1 freight
    assert c["value"] == 10.0
    assert c["expected_value"] == 8.5           # × 0.85 approval assumption
    assert c["status"] == "open" and c["days_left"] == 20
    assert "landed cost" in c["value_basis"]


def test_amazon_unreconciled_quantity_is_trusted_verbatim():
    data = _data(inventory_ledger=[_adj(45, -8, "Damaged", unreconciled=3)])
    c = recovery.run(data, today=TODAY)["claims"][0]
    assert c["claim_type"] == "warehouse_damaged"
    assert c["units"] == 3 and c["evidence"]["source"] == "amazon_unreconciled_quantity"


def test_claim_window_statuses():
    data = _data(inventory_ledger=[_adj(10, -1, "M", ref="a"), _adj(50, -1, "M", ref="b"), _adj(70, -1, "M", ref="c")])
    by_ref = {c["evidence"]["reference_id"]: c for c in recovery.run(data, today=TODAY)["claims"]}
    assert by_ref["a"]["status"] == "not_yet_eligible"
    assert by_ref["b"]["status"] == "expiring"     # 10 days left
    assert by_ref["c"]["status"] == "expired"
    assert recovery.run(data, today=TODAY)["summary"]["n_expiring"] == 1


def test_non_reimbursable_reasons_are_ignored():
    data = _data(inventory_ledger=[_adj(40, -3, "E"), _adj(40, -3, "P"), _adj(40, -3, "Customer damaged")])
    assert recovery.run(data, today=TODAY)["claims"] == []


def test_refund_without_return_is_a_claim_and_a_return_cancels_it():
    refund = {"txn_datetime": _ago(70), "txn_type": "Refund", "order_id": "111-222", "sku": "WIDGET-BLUE",
              "quantity": 1, "product_sales": -29.99, "total": -25.0}
    out = recovery.run(_data(settlement_transactions=[refund]), today=TODAY)
    c = out["claims"][0]
    assert c["claim_type"] == "refund_no_return" and c["status"] == "open"
    assert c["unit_value"] == 29.99 and c["deadline"] == _ago(70 - 120)
    ret = {"return_date": _ago(60), "order_id": "111-222", "sku": "WIDGET-BLUE", "quantity": 1,
           "detailed_disposition": "SELLABLE", "status": "Unit returned to inventory"}
    assert recovery.run(_data(settlement_transactions=[refund], fba_returns=[ret]), today=TODAY)["claims"] == []


def test_young_refunds_are_not_listed():
    refund = {"txn_datetime": _ago(20), "txn_type": "Refund", "order_id": "1", "sku": "WIDGET-BLUE",
              "quantity": 1, "product_sales": -29.99}
    assert recovery.run(_data(settlement_transactions=[refund]), today=TODAY)["claims"] == []


def test_damaged_returns_split_by_liability():
    returns = [
        {"return_date": _ago(10), "order_id": "o1", "sku": "WIDGET-BLUE", "quantity": 1,
         "detailed_disposition": "CARRIER_DAMAGED", "status": "Unit returned to inventory"},
        {"return_date": _ago(10), "order_id": "o2", "sku": "WIDGET-BLUE", "quantity": 1,
         "detailed_disposition": "CUSTOMER_DAMAGED", "status": "Unit returned to inventory"},
        {"return_date": _ago(10), "order_id": "o3", "sku": "WIDGET-BLUE", "quantity": 1,
         "detailed_disposition": "DAMAGED", "status": "Reimbursed"},
    ]
    out = recovery.run(_data(fba_returns=returns), today=TODAY)
    assert [c["order_id"] for c in out["claims"]] == ["o1"]
    assert out["summary"]["returns_excluded"] == {"customer_or_defective": 1, "already_reimbursed": 1, "sellable": 0}


def test_reversal_and_recent_reimbursements_context():
    rb = [
        {"approval_date": _ago(5), "reimbursement_id": "R9", "reason": "Reversal", "sku": "WIDGET-BLUE",
         "quantity_reimbursed_total": 2, "amount_total": -12.0, "original_reimbursement_type": "Reversal"},
        {"approval_date": _ago(30), "reimbursement_id": "R8", "reason": "Lost:Warehouse", "sku": "WIDGET-BLUE",
         "quantity_reimbursed_total": 4, "amount_total": 20.0},
    ]
    out = recovery.run(_data(fba_reimbursements=rb), today=TODAY)
    c = out["claims"][0]
    assert c["claim_type"] == "reimbursement_reversal" and c["value"] == 12.0 and c["units"] == 2
    assert out["summary"]["reimbursed_90d"] == 20.0 and out["summary"]["reimbursed_90d_count"] == 1


def test_no_cost_on_file_falls_back_to_half_price_and_says_so():
    data = _data(cogs_inputs=[], inventory_ledger=[_adj(40, -2, "M")])
    c = recovery.run(data, today=TODAY)["claims"][0]
    assert c["unit_value"] == round(29.99 * 0.5, 2)
    assert "no landed cost" in c["value_basis"]


def test_empty_sources_are_insufficient_data_not_zero_money():
    out = recovery.run(_data(), today=TODAY)
    assert out["status"] == "insufficient_data" and out["claims"] == []


# ── settlements: closing a claim from Amazon's own record (Phase 4) ──────────
# The FIFO matcher always knew which reimbursement closed which loss and threw
# the pairing away, so a PAID claim stopped being re-detected, sat at
# 'detected', and was then stamped 'expired' — a win filed as a miss.

def _reimb(days_ago, qty, sku="WIDGET-BLUE", rid="R1", cash=None, per_unit=None,
           total=None, reason="Lost:Warehouse", case="CASE-1"):
    return {"approval_date": _ago(days_ago), "reimbursement_id": rid, "case_id": case,
            "reason": reason, "sku": sku, "quantity_reimbursed_total": qty,
            "quantity_reimbursed_cash": qty if cash is None else cash,
            "quantity_reimbursed_inventory": 0 if cash is None else qty - cash,
            "amount_per_unit": per_unit, "amount_total": total}


def test_settlement_pairs_a_reimbursement_to_the_claim_it_closed():
    data = _data(
        inventory_ledger=[_adj(40, -3, "M")],
        fba_reimbursements=[_reimb(20, 3, per_unit=5.0)],
    )
    out = recovery.run(data, today=TODAY)
    # Fully reimbursed, so it is no longer an open claim...
    assert not [c for c in out["claims"] if c["claim_type"] == "warehouse_lost"]
    # ...but it is now a settlement, keyed the way the stored claim was keyed.
    key = recovery.claim_key("warehouse_lost", "WIDGET-BLUE", _ago(40))
    s = out["settlements"][key]
    assert s["units"] == 3 and s["paid_amount"] == 15.0
    assert s["paid_at"] == _ago(20) and s["case_id"] == "CASE-1"
    assert "reimbursed $15.00" in s["note"]


def test_inventory_only_reimbursement_settles_the_claim_but_banks_nothing():
    """Amazon reimburses in replacement units as often as in money. Units
    replaced in kind are a real remedy but they are not dollars."""
    data = _data(
        inventory_ledger=[_adj(40, -4, "M")],
        fba_reimbursements=[_reimb(15, 4, cash=0, per_unit=None, total=0)],
    )
    out = recovery.run(data, today=TODAY)
    s = out["settlements"][recovery.claim_key("warehouse_lost", "WIDGET-BLUE", _ago(40))]
    assert s["paid_amount"] == 0.0
    assert s["inventory_units"] == 4
    assert "replaced" in s["note"] and "no dollars are banked" in s["note"]


def test_reimbursement_outside_the_match_window_settles_nothing():
    # 120 days after the loss is past REIMBURSEMENT_MATCH_WINDOW_DAYS = 90.
    data = _data(
        inventory_ledger=[_adj(130, -3, "M")],
        fba_reimbursements=[_reimb(5, 3, per_unit=5.0)],
    )
    out = recovery.run(data, today=TODAY)
    assert out["settlements"] == {}


def test_partial_settlement_leaves_the_rest_claimable():
    data = _data(
        inventory_ledger=[_adj(40, -5, "M")],
        fba_reimbursements=[_reimb(20, 2, per_unit=5.0)],
    )
    out = recovery.run(data, today=TODAY)
    claim = next(c for c in out["claims"] if c["claim_type"] == "warehouse_lost")
    assert claim["units"] == 3                      # 5 lost − 2 settled
    s = out["settlements"][recovery.claim_key("warehouse_lost", "WIDGET-BLUE", _ago(40))]
    assert s["units"] == 2 and s["paid_amount"] == 10.0


def test_cash_share_falls_back_to_amount_total_when_no_per_unit_figure():
    data = _data(
        inventory_ledger=[_adj(40, -2, "M")],
        fba_reimbursements=[_reimb(20, 2, per_unit=None, total=17.0)],
    )
    out = recovery.run(data, today=TODAY)
    s = out["settlements"][recovery.claim_key("warehouse_lost", "WIDGET-BLUE", _ago(40))]
    assert s["paid_amount"] == 17.0
