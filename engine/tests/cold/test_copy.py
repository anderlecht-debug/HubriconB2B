"""What reaches a stranger's inbox.

The tests that matter here are the negative ones: no invented number, no
message without a way to stop it, no draft that can go out addressed to nobody.
"""

import re
from datetime import date

import pytest

from hubricon_engine.cold import copy, findings, priors, select
from builders import item, snapshot

TODAY = date(2026, 6, 1)
CAL = "https://calendly.com/hubricon/margin-audit"


@pytest.fixture(autouse=True)
def _postal(monkeypatch):
    monkeypatch.setenv("POSTAL_ADDRESS", "PO Box 1, Austin TX 78701")


def chosen(**kw):
    snap = snapshot(items=[item(**kw)])
    f = select.best(findings.detect(snap, today=TODAY), snap)
    assert f is not None, f"no finding for {kw}"
    return f, snap


def test_every_finding_kind_has_copy():
    assert set(copy.HOOKS) >= {f for f in
                               ("price_band_edge", "fee_band_edge", "dim_weight_overage",
                                "size_tier_edge", "price_cut_no_rank_gain", "carrier_band_edge")}


def test_the_subject_leads_with_the_consequence_not_with_us():
    f, snap = chosen(price=10.49, est_monthly_units=1200.0)
    message = copy.email(f, snap, "Dana", "https://hubricon.com/t/tok", CAL)
    assert "Hubricon" not in message["subject"]
    assert "$10.49" in message["subject"]


def test_every_number_in_the_body_comes_from_the_finding():
    """No figure may appear that is not in the Finding's own evidence.

    This is the guard behind COLD_ENGINE.md §5: the numbers are templated from
    the object and nothing writes a plausible-sounding one alongside them.
    """
    f, snap = chosen(price=10.49, est_monthly_units=1200.0)
    body = copy.email(f, snap, "Dana", "https://hubricon.com/t/tok", CAL)["body"]
    _, opening = copy.hook(f, snap.display_name)
    allowed = {f"{v:g}" for v in f.evidence.values() if isinstance(v, (int, float))}
    allowed |= {f"{v:,.2f}" for v in f.evidence.values() if isinstance(v, (int, float))}
    allowed |= {f"{v * 100:.0f}" for v in f.evidence.values() if isinstance(v, (int, float))}
    # Constants of the published schedule itself, which the prose names to
    # explain the mechanism. They are Amazon's numbers, not claims about this
    # prospect, which is the distinction this test exists to police.
    allowed |= {f"{v:g}" for v in priors.PRICE_BAND_EDGES}
    allowed |= {"2026", str(priors.FBA_EFFECTIVE.year)}
    allowed |= {"15", "24", "20"}          # the referral rate, the 24 hours, the 20 minutes
    for number in re.findall(r"\d[\d,]*(?:\.\d+)?", opening):
        assert number.rstrip(",").replace(",", "") in {a.replace(",", "") for a in allowed}, \
            f"{number!r} in the hook is not in the finding's evidence"
    assert body.count("$") >= 2


def test_the_assumptions_are_rendered_verbatim_when_there_is_no_page():
    f, snap = chosen(price=10.49, est_monthly_units=1200.0)
    body = copy.email(f, snap, "Dana", None, CAL)["body"]
    for assumption in f.assumptions:
        assert assumption in body


def test_a_message_always_carries_a_postal_address_and_a_way_to_stop_it():
    f, snap = chosen(price=10.49)
    body = copy.email(f, snap, "Dana", "https://hubricon.com/t/tok", CAL)["body"]
    assert "PO Box 1, Austin TX 78701" in body
    assert "STOP" in body


def test_a_missing_postal_address_is_visible_rather_than_silent(monkeypatch):
    monkeypatch.delenv("POSTAL_ADDRESS", raising=False)
    f, snap = chosen(price=10.49)
    assert "POSTAL_ADDRESS is not set" in copy.email(f, snap, "Dana", None, CAL)["body"]


def test_a_role_inbox_gets_a_note_that_names_nobody_and_asks_for_a_hand_off():
    f, _ = chosen(price=10.49)
    shared = snapshot(first_name=None, email="info@testbrand.com",
                      items=[item(price=10.49)])
    message = copy.email(f, shared, None, "https://hubricon.com/t/tok", CAL)
    assert message["complete"], "a shared inbox has no name to get wrong"
    assert "FIRST NAME" not in message["body"]
    assert "Hi there" not in message["body"]
    assert "whoever looks after pricing" in message["body"]
    assert "forwarding it" in message["body"]


def test_a_draft_with_no_first_name_is_incomplete_and_says_so():
    f, _ = chosen(price=10.49)
    nameless = snapshot(first_name=None, email="dana@testbrand.com",
                        items=[item(price=10.49)])
    message = copy.email(f, nameless, None, None, CAL)
    assert not message["complete"]
    assert "FIRST NAME" in message["body"]
    assert "first name" in message["missing"]


def test_a_shopify_prospect_is_never_asked_for_seller_central_exports():
    snap = snapshot(platform="shopify", country="US",
                    items=[item(ref="b.com/products/x", price=28.0, item_weight_oz=17.5,
                                dims_in=None)])
    found = findings.detect(snap, today=TODAY)
    message = copy.email(found[0], snap, "Dana", None, CAL)
    assert "Seller Central" not in message["body"]
    assert "Shopify admin" in message["body"]
    assert "seat in your account" not in message["body"]


def test_the_narration_script_says_the_same_numbers_as_the_email():
    f, snap = chosen(price=10.49, est_monthly_units=1200.0)
    text = copy.script(f, snap)
    assert "$10.49" in text and "$9.99" in text
    for assumption in f.assumptions:
        assert assumption.split(",")[0][:24].lower() in text.lower()


def test_the_teardown_url_is_built_from_the_configured_base(monkeypatch):
    monkeypatch.setenv("COLD_TEARDOWN_BASE_URL", "https://example.test/t/")
    assert copy.teardown_url("abc") == "https://example.test/t/abc"
