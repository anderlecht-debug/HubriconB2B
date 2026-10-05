"""A Shopify seller reads Shopify words (2026-10-01).

Every move printed "Buy Box watched while the step is live", a Shopify markdown
said storage and the aged surcharge were priced in, and a client on both stores
got two notices, two Briefs and a stream of alerts a week with no store named.
Each sentence now comes from channels.py and says only what the code does: a
Shopify step is read on the client's own orders, never watched daily, and a
two-store client is told which store; a one-store client sees no change.
"""

from datetime import date, datetime

from hubricon_engine import alerts, channels, cli, directives, issue, notify
from hubricon_engine.growth_plan import propose_plan

# -- the moves ---------------------------------------------------------------------------

ELASTICITY = [
    {"level": "sku", "item_id": "INELASTIC", "status": "ok", "elasticity": -0.5,
     "std_err": 0.08, "details": {"ci95": [-0.75, -0.25], "dof": 5, "t_critical": 2.571, "residual_sd_log": 0.12}},
    {"level": "sku", "item_id": "RISKY", "status": "ok", "elasticity": -2.0,
     "std_err": 0.144, "details": {"ci95": [-2.4, -1.6], "dof": 5, "t_critical": 2.571, "residual_sd_log": 0.12}},
]
MARGINS = [
    {"sku": "INELASTIC", "period_start": "2026-07-01", "units": 100, "revenue": 10000.0,
     "amazon_fees": 1500.0, "cogs": 2000.0, "net_margin": 2000.0},
    {"sku": "RISKY", "period_start": "2026-07-01", "units": 100, "revenue": 2000.0,
     "amazon_fees": 300.0, "cogs": 500.0, "net_margin": 400.0},
]
MD_FIT = {"level": "sku", "item_id": "X", "status": "ok", "elasticity": -2.0, "std_err": 0.2,
          "details": {"ci95": [-2.5, -1.5], "dof": 6, "t_critical": 2.447, "residual_sd_log": 0.15}}
MD_MARGIN = {"sku": "X", "period_start": "2026-08-01", "period_end": "2026-08-28", "units": 84, "revenue": 1680.0,
             "amazon_fees": 378.0, "cogs": 420.0, "net_margin": 800.0,
             "fee_split": {"basis": "itemized", "proportional_rate": 0.15, "fixed_per_unit": 1.5}}


def _md_row(depth=0.05):
    return {"sku": "X", "status": "ok", "decision": "markdown", "depth": depth, "p0": 20.0,
            "p_new": round(20 * (1 - depth), 2), "excess_units": 500,
            "months_to_clear": {"hold": 8.0, "markdown": 3.0},
            "npv": {"hold": {"p50": 5000.0}, "liquidate": {"p50": 1000.0}, f"markdown_{int(depth * 100)}": {"p50": 5600.0}},
            "delta_vs_hold": {"p5": 150.0, "p50": 600.0, "p95": 1100.0, "mc_se": {}},
            "delta_vs_liquidate": {"p50": 4600.0}, "delta_p5": 150.0, "delta_p50": 600.0, "delta_p95": 1100.0,
            "p_loss": 0.03, "mc_se": {}, "mc_inputs": {"draws": 4000, "seed": 1}, "carry_saving_p50": 800.0,
            "carry_month_now": 160.0, "beyond_observed_range": False, "elasticity": -2.0, "std_err": 0.2,
            "ci95": [-2.5, -1.5], "fee_rate": 0.15, "fixed_fee_per_unit": 1.5}


def _prices(channel):
    drafts = directives.draft_directives([], [], ELASTICITY, MARGINS, channel=channel)
    return [d["action_text"] for d in drafts if d["kind"] == "price_step"]


def test_a_shopify_price_step_is_read_on_orders_and_an_amazon_one_keeps_its_buy_box():
    amazon, shopify = _prices("amazon"), _prices("shopify")
    assert len(amazon) == len(shopify) == 2
    for t in amazon:
        assert t.endswith("Buy Box watched while the step is live.")
    for t in shopify:
        assert "Buy Box watched" not in t and "watched daily" not in t and "conversion" not in t
        assert t.endswith(channels.watch_phrase("shopify"))
        assert "read on your own orders" in t
    # the words change, never the arithmetic
    a = directives.draft_directives([], [], ELASTICITY, MARGINS, channel="amazon")
    s = directives.draft_directives([], [], ELASTICITY, MARGINS, channel="shopify")
    assert [d["expected_impact_usd"] for d in a] == [d["expected_impact_usd"] for d in s]
    assert [d["dedupe_key"] for d in a] == [d["dedupe_key"] for d in s]


def test_a_plan_computed_before_the_channel_was_known_is_reworded_for_shopify():
    plan = directives.plan_prices(ELASTICITY, MARGINS)            # the default: Amazon's words
    assert plan["channel"] == "amazon"
    drafts = directives.draft_directives([], [], ELASTICITY, MARGINS, channel="shopify", price_plan=plan)
    texts = [d["action_text"] for d in drafts if d["kind"] == "price_step"]
    assert texts and all("Buy Box" not in t.replace("No Buy Box on Shopify", "") for t in texts)
    # and the plan itself, asked for Shopify, speaks Shopify
    shop = directives.plan_prices(ELASTICITY, MARGINS, channel="shopify")
    assert shop["channel"] == "shopify"
    assert all("No Buy Box on Shopify" in d["action_text"] for d in shop["drafts"].values())


def test_a_shopify_markdown_prices_no_storage_and_watches_no_buy_box():
    amz = directives._markdown_directive(_md_row(), MD_MARGIN, MD_FIT)
    assert "storage and the aged surcharge priced in" in amz["action_text"]
    assert amz["action_text"].endswith("Buy Box watched while the markdown is live.")
    shop = directives._markdown_directive(_md_row(), MD_MARGIN, MD_FIT, "shopify")
    t = shop["action_text"]
    assert "storage" not in t and "surcharge" not in t and "Buy Box watched" not in t
    assert "net of fees." in t and t.endswith(channels.watch_phrase("shopify", "markdown"))
    assert shop["expected_impact_usd"] == amz["expected_impact_usd"]
    # through the drafter, too
    drafts = directives.draft_directives([], [], [MD_FIT], [MD_MARGIN], channel="shopify",
                                         markdown={"status": "ok", "rows": [_md_row()]})
    md = next(d for d in drafts if d["kind"] == "markdown")
    assert "storage" not in md["action_text"]


def test_the_stretch_the_liquidation_and_the_reorder_say_no_amazon_carry_on_shopify():
    row = {**_md_row(), "decision": None, "stretch": {
        "status": "ok", "step_fraction": 0.03, "p_new": 20.6, "p0": 20.0, "p_stockout_before": 0.45,
        "p_stockout_after": 0.2, "gain": {"p5": 20.0, "p50": 90.0, "p95": 160.0, "mc_se": {}}, "p_loss": 0.02,
        "mc_inputs": {"draws": 4000, "seed": 1, "lead_days": 40}}}
    st = directives._stretch_directive(row, MD_MARGIN, MD_FIT, "shopify")
    assert st["action_text"].endswith(channels.watch_phrase("shopify"))
    assert directives._stretch_directive(row, MD_MARGIN, MD_FIT)["action_text"].endswith(
        "Buy Box watched while the step is live.")
    inv_econ = {"rows": [{"sku": "X", "decision": "liquidate", "excess_units": 300, "liquidate_value": 900.0,
                          "hold_npv": 200.0, "aged_surcharge_month": 0.0}]}
    shop_liq = directives._liquidation_directives(inv_econ, "shopify")[0]["action_text"]
    amz_liq = directives._liquidation_directives(inv_econ, "amazon")[0]["action_text"]
    assert "a clearance sale" in shop_liq and "storage" not in shop_liq and "surcharge" not in shop_liq
    assert "storage and the aged surcharge priced in" in amz_liq
    econ = {"order_qty_econ": 740, "wire_econ": 3700.0, "critical_fractile": 0.9}
    inv = {"sku": "RISKY", "stockout_probability": 0.62, "reorder_qty": 740, "reorder_point": 690,
           "lead_time_days": 38, "daily_velocity_mean": 10.0, "on_hand_units": 400, "inbound_units": 0}
    shop_re = directives._inventory_directive(inv, MARGINS[1], date(2026, 10, 1), econ, "shopify")["action_text"]
    amz_re = directives._inventory_directive(inv, MARGINS[1], date(2026, 10, 1), econ, "amazon")["action_text"]
    assert "the cost of capital and the season priced in" in shop_re and "storage" not in shop_re
    assert "storage and the season priced in" in amz_re


def test_a_shopify_price_test_promises_no_watch_it_cannot_keep():
    margin = {"sku": "S000", "period_start": "2026-08-01", "period_end": "2026-08-28", "units": 400,
              "revenue": 8000.0, "amazon_fees": 1800.0, "cogs": 2000.0, "net_margin": 3000.0,
              "fee_split": {"basis": "itemized", "proportional_rate": 0.15, "fixed_per_unit": 1.5}}
    amz = directives._price_experiment_directive(None, margin, "S000", "no_variation", "c", date(2026, 8, 31))
    shop = directives._price_experiment_directive(None, margin, "S000", "no_variation", "c", date(2026, 8, 31),
                                                  channel="shopify")
    assert "Buy Box watched while the test is live. Nothing is banked on the test itself." in amz["action_text"]
    assert shop["action_text"].endswith("Nothing is banked on the test itself.") and "Buy Box" not in shop["action_text"]


def test_sales_per_click_names_the_buy_box_only_on_amazon():
    row = {"flagged": True, "dollar_impact": 500.0, "metric": "sales_per_click", "direction": "down",
           "scope": "campaign", "item_id": "Meta Prospecting", "baseline": 2.0, "current": 1.2, "since": "2026-09-01"}
    shop = directives._anomaly_directives([row], "shopify")[0]["action_text"]
    amz = directives._anomaly_directives([row], "amazon")[0]["action_text"]
    assert "Buy Box" not in shop and "price, reviews or the product page itself." in shop
    assert "price, Buy Box, reviews or the listing itself." in amz


def test_the_plans_pricing_initiative_says_what_each_store_watches():
    def thesis(moves, platform=None):
        plan = propose_plan(MARGINS, moves, today=date(2026, 10, 1), platform=platform)
        return next(i["thesis"] for i in plan["initiatives"] if i["module"] == "pricing")
    step = {"module": "pricing", "expected_impact_usd": 100.0}
    assert "watch your Buy Box while a step is live" in thesis([step])            # an old move: Amazon
    shop = thesis([{**step, "channel": "shopify"}])
    assert "Buy Box" not in shop and "read each step on your own orders" in shop
    both = thesis([{**step, "channel": "amazon"}, {**step, "channel": "shopify"}])
    assert "on Amazon we watch your Buy Box" in both and "on Shopify we read each step" in both
    assert "Buy Box" not in thesis([step], platform="shopify")


# -- the report ---------------------------------------------------------------------------

def _report(tmp_path, platform, channel):
    from fakedb import FakeDB

    from hubricon_engine.report import html_report
    client = {"id": "c1", "company_name": "Acme", "contact_email": "dana@acme.com", "platform": platform,
              "status": "active"}
    db = FakeDB(
        clients=[dict(client)],
        model_runs=[{"id": "run1", "client_id": "c1", "status": "succeeded", "started_at": "2026-09-28T11:00:00Z",
                     "params": {"channel": channel}}],
        directives=[{"id": "d1", "client_id": "c1", "channel": channel, "status": "issued", "module": "pricing",
                     "kind": "price_step", "action_text": "Move X.", "expected_impact_usd": 100, "measured_impact_usd": None,
                     "created_at": "2026-09-28T00:00:00Z"}],
        price_tests=[{"id": "t1", "client_id": "c1", "sku": "X", "baseline_price": 20, "test_price": 21,
                      "status": "running", "created_at": "2026-09-20T00:00:00Z"}],
        record_months=[], recovery_claims=[], invoices=[], briefings=[], alerts=[], margin_results=[],
        elasticity_results=[], inventory_sim_results=[], ad_efficiency_results=[], model_outputs=[])
    return html_report.generate(db, client, "run1", out_dir=str(tmp_path)).read_text()


def test_the_report_speaks_the_runs_store(tmp_path):
    amz = _report(tmp_path / "a", "amazon", "amazon")
    assert "Buy Box share watched so suppression is caught in days" in amz and "Buy Box before" in amz
    shop = _report(tmp_path / "s", "shopify", "shopify")
    assert "Buy Box" not in shop.replace("no Buy Box on Shopify", "")
    assert "read each step on your own orders" in shop
    # a two-store client: the report names its store, each move its store, and keeps
    # the Buy Box column for the Amazon tests, labelled
    both = _report(tmp_path / "b", "both", "shopify")
    assert "Acme · Shopify" in both and "<th>Store</th>" in both and "Buy Box before → during (Amazon)" in both


# -- a client on both stores is told which --------------------------------------------------

MOVES = [{"id": "m1", "mandate": "standing", "expected_impact_usd": 400, "action_text": "Move A.",
          "channel": "shopify"},
         {"id": "m2", "mandate": "standing", "expected_impact_usd": 200, "action_text": "Move B.",
          "channel": "shopify"}]
THU = datetime(2026, 10, 8, 9)


def test_a_move_notice_names_its_store_only_for_a_two_store_client():
    assert issue.veto_subject(MOVES, THU) == "2 moves in your account go live Thursday unless you say no — $600 expected"
    assert issue.veto_subject(MOVES, THU, store="Shopify") == \
        "2 moves in your Shopify store go live Thursday unless you say no — $600 expected"
    assert issue.veto_subject(MOVES, THU, store="Amazon").startswith("2 moves in your Amazon account go live")
    assert issue.veto_subject(MOVES[:1], THU, store="Shopify").startswith("1 move in your Shopify store")
    explicit = [{**m, "mandate": "explicit"} for m in MOVES]
    assert issue.veto_subject(explicit, THU, store="Shopify") == "2 Shopify moves waiting for your yes — $600 expected"
    one, _ = notify.directive_email_body({"contact_name": "Dana", "platform": "shopify"}, MOVES, THU, "https://x/p")
    both, _ = notify.directive_email_body({"contact_name": "Dana", "platform": "both"}, MOVES, THU, "https://x/p")
    assert "Here is what we plan to do next, and what each one is worth." in one
    assert "Here is what we plan to do next in your Shopify store, and what each one is worth." in both


def test_issue_drafts_puts_the_store_in_the_subject(monkeypatch):
    from fakedb import FakeDB
    sent = []
    monkeypatch.setattr(notify, "email_configured", lambda: True)
    monkeypatch.setattr(notify, "send_email", lambda to, subject, text, html=None, **k: sent.append(subject) or True)
    client = {"id": "c1", "contact_email": "dana@acme.com", "contact_name": "Dana", "platform": "both",
              "status": "active", "retainer_started_at": "2026-09-01T00:00:00Z"}
    db = FakeDB(clients=[dict(client)], mandates=[], directives=[
        {**m, "client_id": "c1", "status": "draft", "module": "pricing", "kind": "price_step"} for m in MOVES],
        record_seals=[], record_months=[], recovery_claims=[], invoices=[])
    res = issue.issue_drafts(db, client, "shopify", "https://x/p", send=True)
    assert res["issued"] == 2 and sent and sent[0].startswith("2 moves in your Shopify store go live")


def test_alerts_name_their_store_for_a_two_store_client_and_the_buy_box_is_amazons():
    inv = [{"sku": "A", "stockout_probability": 0.6, "lead_time_days": 30, "reorder_qty": 100}]
    tests = [{"status": "running", "sku": "T", "buy_box_share_before": 90, "buy_box_share_during": 60,
              "test_price": 21.0}]
    one = alerts.compute_alerts(inv, [], [], tests, channel="shopify", platform="shopify")
    assert all(not a["message"].startswith("On ") for a in one)
    assert alerts.compute_alerts(inv, [], [], tests, channel="shopify") == one, "no platform given: as before"
    both = alerts.compute_alerts(inv, [], [], tests, channel="shopify", platform="both")
    stock = next(a for a in both if a["module"] == "inventory")
    bb = next(a for a in both if a["module"] == "pricing")
    assert stock["message"].startswith("On Shopify: A: 60% chance of stockout")
    assert bb["message"].startswith("On Amazon: Price test on T"), "a Buy Box alert is Amazon's whichever sweep finds it"
    # the Amazon sweep writes the same Buy Box message, so the second is deduped
    amz = alerts.compute_alerts([], [], [], tests, channel="amazon", platform="both")
    assert [a["message"] for a in amz] == [bb["message"]]
    assert alerts.dedupe(amz, {bb["message"]}) == []


def test_the_brief_names_its_store_for_a_two_store_client():
    months = {"usd": 13870.0, "basis": "months"}
    assert cli._issue_subject(7, "Profit Brief No. 007 · Shopify — net profit down $300", months, 2400,
                              store="Shopify") == "Profit Brief No. 007 · Shopify — $13,870 proven, $2,400 found on your Record"
    zero = {"usd": 0.0, "basis": "ledger"}
    assert cli._issue_subject(7, "Profit Brief No. 007 · Amazon", zero, 0, store="Amazon") == \
        "Profit Brief No. 007 · Amazon is in Hubricon"
    assert cli._issue_subject(7, "Profit Brief No. 007 · Shopify — net profit up $50", zero, 0, store="Shopify") == \
        "Profit Brief No. 007 · Shopify — net profit up $50"
    blocks = cli._issue_email_blocks(7, months, 2400, has_video=False, store="Shopify")
    assert blocks[0]["p"].startswith("Your Shopify Profit Brief is ready — $13,870 proven on your Record")
    # one store: unchanged
    assert cli._issue_email_blocks(7, months, 2400, has_video=False)[0]["p"].startswith("Your Profit Brief is ready")
