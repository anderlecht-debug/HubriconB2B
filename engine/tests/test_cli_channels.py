"""The CLI's half of the second platform: which rows a run reads, and how
many runs a client gets.

The engine never talks to Supabase in tests, so these use a tiny stand-in
that answers the handful of PostgREST calls `_load_data` makes. What is being
pinned is the contract, not the client library: a Shopify run must not see a
single Amazon row, and a brand on both platforms gets two runs rather than
one blended one.
"""

from types import SimpleNamespace

import pytest

from hubricon_engine import cli


class _Query:
    """Enough of the PostgREST builder for select/eq/range/limit/execute."""

    def __init__(self, rows):
        self.rows = rows

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        return _Query([r for r in self.rows if r.get(column) == value])

    def range(self, lo, hi):
        return _Query(self.rows[lo : hi + 1])

    def limit(self, n):
        return _Query(self.rows[:n])

    def order(self, *_a, **_k):
        return self

    def execute(self):
        return SimpleNamespace(data=list(self.rows))


class _FakeDB:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _Query(self.tables.get(name, []))


AMAZON_SKU = {"client_id": "c1", "channel": "amazon", "sku": "A", "sales": 100}
SHOPIFY_SKU = {"client_id": "c1", "channel": "shopify", "sku": "A", "sales": 40}
COGS = {"client_id": "c1", "sku": "A", "unit_cost_usd": 4.0}
LEDGER = {"client_id": "c1", "event_type": "Adjustments"}


def _db():
    return _FakeDB({
        "sku_economics": [AMAZON_SKU, SHOPIFY_SKU],
        "cogs_inputs": [COGS],
        "inventory_ledger": [LEDGER],
    })


def test_a_run_reads_only_its_own_channels_rows():
    amazon = cli._load_data(_db(), "c1", "amazon")
    shopify = cli._load_data(_db(), "c1", "shopify")
    assert amazon["sku_economics"] == [AMAZON_SKU]
    assert shopify["sku_economics"] == [SHOPIFY_SKU]
    # the cost sheet belongs to the SKU, not a channel
    assert amazon["cogs_inputs"] == shopify["cogs_inputs"] == [COGS]
    # every table the models read is present either way
    assert set(amazon) == set(shopify) == set(cli.DATA_TABLES)


def test_a_shopify_run_loads_none_of_amazons_bleed_exports():
    """The ledger, returns, reimbursements and Inventory Age exports describe
    a warehouse holding a seller's units. A Shopify store has none, so those
    tables come back empty rather than leaking Amazon rows into it."""
    shopify = cli._load_data(_db(), "c1", "shopify")
    for table in cli.AMAZON_ONLY_TABLES:
        assert shopify[table] == []
    assert cli._load_data(_db(), "c1", "amazon")["inventory_ledger"] == [LEDGER]


def test_the_table_groups_partition_the_canonical_tables():
    groups = cli.CHANNEL_TABLES + cli.SHARED_TABLES + cli.AMAZON_ONLY_TABLES
    assert sorted(groups) == sorted(cli.DATA_TABLES)
    assert len(set(groups)) == len(groups)
    assert "settlement_transactions" in cli.CHANNEL_TABLES   # Shopify Payments lands here too


def test_run_channel_prefers_the_run_over_the_client():
    client = {"platform": "both"}
    assert cli._run_channel(client, {"params": {"channel": "shopify"}}) == "shopify"
    # a run from before the channel was recorded, on a client selling on both
    assert cli._run_channel(client, {"params": {"models": []}}) == "amazon"
    assert cli._run_channel({"platform": "shopify"}, None) == "shopify"


def _patch_cli(monkeypatch, client, calls):
    monkeypatch.setattr(cli.dbmod, "connect", lambda: _db())
    monkeypatch.setattr(cli.dbmod, "resolve_client", lambda _db_, _ident: client)
    monkeypatch.setattr(
        cli, "_run_models",
        lambda db, c, wanted, sims, seed, channel: (calls.append(channel), f"run-{channel}")[1])


def _args(**kw):
    return SimpleNamespace(**{"client": "c1", "models": cli.DEFAULT_MODELS, "simulations": 10,
                              "seed": 1, "channel": None, **kw})


def test_a_two_platform_client_is_run_once_per_channel(monkeypatch):
    calls = []
    _patch_cli(monkeypatch, {"id": "c1", "company_name": "Acme", "contact_email": "a@b.co",
                             "platform": "both"}, calls)
    assert cli.cmd_run(_args()) == "run-shopify"
    assert calls == ["amazon", "shopify"]


def test_a_single_platform_client_is_run_on_its_own_channel(monkeypatch):
    calls = []
    _patch_cli(monkeypatch, {"id": "c1", "company_name": "Acme", "contact_email": "a@b.co",
                             "platform": "shopify"}, calls)
    cli.cmd_run(_args())
    assert calls == ["shopify"]


def test_an_explicit_channel_narrows_a_two_platform_run(monkeypatch):
    calls = []
    _patch_cli(monkeypatch, {"id": "c1", "company_name": "Acme", "contact_email": "a@b.co",
                             "platform": "both"}, calls)
    cli.cmd_run(_args(channel="shopify"))
    assert calls == ["shopify"]


def test_asking_for_a_channel_the_client_does_not_sell_on_exits_clearly(monkeypatch):
    calls = []
    _patch_cli(monkeypatch, {"id": "c1", "company_name": "Acme", "contact_email": "a@b.co",
                             "platform": "amazon"}, calls)
    with pytest.raises(SystemExit) as err:
        cli.cmd_run(_args(channel="shopify"))
    assert "Acme sells on Amazon" in str(err.value)
    assert "hubricon platform" in str(err.value)   # says how to fix it
    assert calls == []
