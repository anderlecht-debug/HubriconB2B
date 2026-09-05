"""Which finding leads, and — more often — that none of them does.

`select` is the last thing between the arithmetic and a stranger's inbox, so
every test here is a refusal except the first two.
"""

from datetime import date

import pytest

from hubricon_engine.cold import findings, select
from hubricon_engine.cold.findings import Finding
from builders import item, snapshot

TODAY = date(2026, 6, 1)


def finding(**kw) -> Finding:
    base = dict(kind="price_band_edge", dollars_low=400.0, dollars_high=1200.0,
                confidence=0.90, assumptions=["a stated assumption"],
                evidence={"chart": "net_vs_price", "per_unit_low": 0.5, "per_unit_high": 0.5,
                          "monthly_units": 900},
                asin_or_sku="B00TEST0001", item_title="A listing", item_url="https://x/dp/B0")
    base.update(kw)
    return Finding(**base)


def test_the_strongest_priced_finding_wins():
    weak = finding(kind="fee_band_edge", dollars_low=300.0, dollars_high=500.0, confidence=0.72)
    strong = finding(dollars_low=900.0, dollars_high=2000.0, confidence=0.90)
    assert select.best([weak, strong], snapshot()).kind == "price_band_edge"


def test_a_real_snapshot_produces_a_real_selection():
    snap = snapshot(items=[item(price=10.49, est_monthly_units=1200.0)])
    chosen = select.best(findings.detect(snap, today=TODAY), snap)
    assert chosen is not None and chosen.kind == "price_band_edge"


def test_nothing_is_selected_below_the_confidence_floor(monkeypatch):
    monkeypatch.setenv("COLD_MIN_CONFIDENCE", "0.85")
    assert select.best([finding(confidence=0.80)], snapshot()) is None


def test_nothing_is_selected_below_the_dollar_floor(monkeypatch):
    monkeypatch.setenv("COLD_MIN_MONTHLY_USD", "250")
    assert select.best([finding(dollars_low=10.0, dollars_high=90.0)], snapshot()) is None


def test_an_unpriced_finding_never_leads():
    unpriced = finding(kind="carrier_band_edge", dollars_low=0.0, dollars_high=0.0,
                       confidence=0.95,
                       evidence={"chart": "fee_vs_weight", "per_unit_low": 0.0,
                                 "per_unit_high": 0.0, "monthly_units": 900})
    assert select.best([unpriced], snapshot()) is None


def test_a_shopify_parcel_over_a_pound_now_leads():
    snap = snapshot(platform="shopify",
                    items=[item(ref="b.com/products/x", price=28.0, item_weight_oz=17.5,
                                dims_in=None)])
    chosen = select.best(findings.detect(snap, today=TODAY), snap)
    assert chosen is not None and chosen.kind == "carrier_band_edge"


def test_a_shopify_finding_with_no_volume_stands_on_its_per_unit_number():
    """The Shopify harvest reads a catalogue, not a sales rank, so most of its
    rows carry no volume. Judging those against a monthly floor they can never
    meet would gate out the whole platform."""
    snap = snapshot(platform="shopify",
                    items=[item(ref="b.com/products/x", price=28.0, item_weight_oz=17.5,
                                dims_in=None, est_monthly_units=None,
                                est_monthly_revenue=None)])
    chosen = select.best(findings.detect(snap, today=TODAY), snap)
    assert chosen is not None
    assert chosen.dollars_high == 0.0 and chosen.per_unit_low >= 0.96


def test_a_small_per_unit_saving_with_no_volume_behind_it_is_refused(monkeypatch):
    monkeypatch.setenv("COLD_MIN_PER_UNIT_ONLY_USD", "2.00")
    verdict = select.review([finding(dollars_low=0.0, dollars_high=0.0,
                                     evidence={"chart": "carrier_bands", "per_unit_low": 0.96,
                                               "per_unit_high": 4.47, "monthly_units": None})],
                            snapshot())
    assert verdict.chosen is None
    assert "no volume estimate" in verdict.rejected[0].reason


def test_no_findings_at_all_is_a_normal_outcome():
    assert select.best([], snapshot()) is None


def test_a_claim_larger_than_a_quarter_of_the_listings_revenue_is_refused():
    # The rank curve occasionally produces a silly volume for a head listing.
    # A silly number is the one thing that must never reach a prospect.
    snap = snapshot(items=[item(est_monthly_revenue=4000.0)])
    assert select.best([finding(dollars_low=1500.0, dollars_high=3000.0)], snap) is None


def test_the_share_guard_uses_the_listing_the_finding_is_about():
    snap = snapshot(items=[item(ref="B00OTHER001", est_monthly_revenue=2000.0),
                           item(ref="B00TEST0001", est_monthly_revenue=90000.0)])
    assert select.best([finding()], snap) is not None


def test_every_rejection_records_why_so_the_gate_can_be_tuned():
    verdict = select.review([finding(confidence=0.40),
                             finding(kind="fee_band_edge", dollars_low=1.0, dollars_high=2.0)],
                            snapshot())
    assert verdict.chosen is None
    assert len(verdict.rejected) == 2
    assert "confidence" in verdict.rejected[0].reason
    assert "month" in verdict.rejected[1].reason


def test_the_verdict_names_the_winner_and_the_runners_up():
    strong = finding(dollars_low=900.0, dollars_high=2000.0, confidence=0.90)
    weak = finding(kind="fee_band_edge", dollars_low=300.0, dollars_high=600.0, confidence=0.72)
    verdict = select.review([weak, strong], snapshot())
    assert verdict.chosen is strong
    assert [r.finding.kind for r in verdict.rejected] == ["fee_band_edge"]
    assert "a stronger finding" in verdict.rejected[0].reason


def test_the_strongest_finding_wins_even_with_no_volume_on_either():
    """Every Shopify row lands here. When both candidates have no monthly figure
    the score fell to zero for both and the winner was whichever the sort left
    first, so the best finding about a company was chosen by luck."""
    snap = snapshot(platform="shopify", items=[
        item(ref="b.com/products/small", price=20.0, item_weight_oz=17.0, dims_in=None,
             est_monthly_units=None, est_monthly_revenue=None),
        item(ref="b.com/products/big", price=90.0, item_weight_oz=33.0, dims_in=None,
             est_monthly_units=None, est_monthly_revenue=None)])
    found = findings.detect(snap, today=TODAY)
    assert len(found) == 2
    assert len({select.score(f) for f in found}) == 2, "two different findings must not tie"
    # The 17 oz parcel drops to the flat sub-pound rate and saves more per unit
    # than the 33 oz one dropping from 3 lb to 2 lb.
    assert select.best(found, snap).asin_or_sku == "b.com/products/small"
