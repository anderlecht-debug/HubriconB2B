"""Every demo export parses through the engine, and the models that the videos
lean on all speak."""
import pytest

from hubricon_content import facts as F
from hubricon_engine.models import recovery


@pytest.fixture(scope="module")
def data():
    return F.load_data()


def test_every_table_the_videos_need_is_populated(data):
    for t in ("sku_economics", "asin_traffic", "cogs_inputs", "inventory_levels", "ppc_spend", "ppc_search_terms",
              "inventory_ledger", "fba_returns", "fba_reimbursements", "settlement_transactions", "inventory_health"):
        assert data[t], t


def test_recovery_finds_every_claim_family(data):
    rec = recovery.run(data, today=F.TODAY)
    types = {c["claim_type"] for c in rec["claims"]}
    assert {"warehouse_lost", "warehouse_damaged", "refund_no_return", "damaged_return", "reimbursement_reversal"} <= types
    assert types & {"carrier_damaged", "transit_lost"}
    statuses = {c["status"] for c in rec["claims"]}
    assert {"open", "expiring", "not_yet_eligible", "expired"} <= statuses


def test_facts_are_strings_with_sources(data):
    run = F.run_models(data, simulations=1500)
    f = F.build_facts(run, data)
    assert len(f) > 120
    for k, v in f.items():
        assert isinstance(v["value"], str) and v["label"] and v["source"], k
    assert run["cash"] and run["paths_year"]["n"] == F.PATH_SAMPLE
    assert any(e.get("status") == "ok" for e in run["elasticity"])
