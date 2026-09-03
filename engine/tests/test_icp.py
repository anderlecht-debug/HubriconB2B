"""The ICP gate and the manual lane it feeds.

Every case here is a row that was actually enrolled into the live campaign on
2026-09-03, so the tests are a record of what went wrong rather than invented
examples.
"""

import pytest

from hubricon_engine import icp, outreach


# -- off_icp -------------------------------------------------------------------

@pytest.mark.parametrize("company, bucket", [
    ("Bellavix", "agency"),
    ("Omg Commerce", "agency"),
    ("Anthem Branding | Promotional Products & Branding Agency", "agency"),
    ("Smartscout", "software"),                       # a direct competitor
    ("Whipstitch Capital", "finance"),
    ("Finlocker", "finance"),
    ("Unicargo", "logistics"),
    ("Shipoffers", "logistics"),
    ("Amz Atlas: Succeed With Amazon", "education"),
    ("Calmare Therapeutics Incorporated (otcqb: Cttc)", "public company"),
    ("Sol de Janeiro", "too_big"),
])
def test_service_businesses_and_giants_are_not_customers(company, bucket):
    got, why = icp.off_icp(company)
    assert got == bucket, f"{company!r} classified {got!r}: {why}"


@pytest.mark.parametrize("company", [
    "Tens Towels", "beetles Gel Polish", "KITESSENSU", "RICCLE", "Amish Country Popcorn",
    "American Soft Linen", "Rhino USA", "kinder Fluff",
])
def test_real_private_label_brands_pass(company):
    """A false positive here costs a customer, so these must never be filtered."""
    bucket, why = icp.off_icp(company)
    assert bucket is None, f"{company!r} was wrongly rejected as {bucket}: {why}"


def test_a_free_mail_provider_is_not_a_brand_domain():
    assert icp.off_icp("Some Brand", "someone@gmail.com")[0] == "no_domain"


# -- the data-quality checks ---------------------------------------------------

def test_role_inbox_detects_the_queues_we_actually_collected():
    for e in ("hello@artistro.com", "info@riccle.com", "support@carfidant.com",
              "help@americansoftlinen.com", "concierge@portmantos.com",
              "consumerrelations@weiman.com", "orders@shieldline.com"):
        assert icp.is_role_inbox(e), e


def test_a_named_person_is_not_a_role_inbox():
    for e in ("david@mycarpe.com", "micah@micahrich.com", "barney@casportswear.com"):
        assert not icp.is_role_inbox(e), e


def test_domain_mismatch_catches_the_enrichment_failures():
    # harvest resolved Rhino USA's site correctly and its address to someone else's.
    assert icp.domain_mismatch("micah@micahrich.com", "https://rhinousa.com/")
    # BigFoot the Amazon brand vs bigfoot.com, a 1990s email provider.
    assert icp.domain_mismatch("help@bigfoot.com", "https://bigfootproducts.com/")


def test_domain_mismatch_allows_subdomains_and_exact_matches():
    assert not icp.domain_mismatch("hello@tenstowels.com", "https://tenstowels.com/")
    assert not icp.domain_mismatch("hi@mail.tenstowels.com", "https://tenstowels.com")
    assert not icp.domain_mismatch("hello@tenstowels.com", "https://www.tenstowels.com/")


def test_bad_greeting_flags_the_two_that_would_have_shipped():
    assert icp.bad_greeting("Leather")      # Leather Honey
    assert icp.bad_greeting("Washington")   # Sol de Janeiro, a word off an address
    assert icp.bad_greeting(None)
    assert icp.bad_greeting("")


def test_the_brand_team_fallback_is_fine():
    assert not icp.bad_greeting("RICCLE team")
    assert not icp.bad_greeting("Sarah")


# -- the founder lane ----------------------------------------------------------

def test_bad_data_routes_to_the_founder_lane_not_the_bin():
    """Rhino USA is squarely in the ICP; only the address we hold is wrong."""
    for bucket in ("role_inbox", "bad_greeting", "domain_mismatch"):
        assert bucket in outreach.FOUNDER_LANE_BUCKETS
    for bucket in ("agency", "software", "finance", "too_big"):
        assert bucket not in outreach.FOUNDER_LANE_BUCKETS


def _facts(weight=75.2, title="Tens Towels 4 Piece Extra Large Bath Towels 30 x 60 Inches, Dark Grey"):
    from hubricon_engine.harvest import amazon
    cliff = amazon.fee_cliff(weight)
    return {
        "seller": {"brand": "Tens Towels", "seller_name": "Tens Home LLC",
                   "email": "hello@tenstowels.com", "website": "https://tenstowels.com/"},
        "items": [{"asin": "B08LBN2JPS", "title": title, "price": 36.0, "weight_oz": weight,
                   "bsr": 130, "units": 6128, "revenue": 220553.92,
                   "band_edge": cliff[0] if cliff else None,
                   "over_by": cliff[1] if cliff else None}],
    }


def test_the_draft_quotes_the_real_gap_not_a_round_number():
    d = outreach.founder_email(_facts(), "Sarah", "https://calendly.com/x")
    assert "3.2 oz" in d["subject"] and "3.2 oz" not in d["subject"].replace("3.2 oz", "", 1)
    assert "75.2 oz" in d["body"] and "72 oz" in d["body"]
    assert d["to"] == "hello@tenstowels.com"


def test_the_draft_says_what_the_website_says():
    d = outreach.founder_email(_facts(), "Sarah", "https://calendly.com/x")
    body = d["body"].lower()
    assert "free" in body and "24 hours" in body
    assert "no seat" in body
    # No claim of access to their account: the whole hook is public data.
    assert "no access to your account" in body


def test_the_draft_trims_amazon_keyword_stuffing():
    d = outreach.founder_email(_facts(), "Sarah", "https://calendly.com/x")
    assert "30 x 60 Inches" not in d["body"], "the full title reads like a scrape"


def test_a_seller_with_no_cliff_gets_no_invented_number():
    facts = _facts(weight=None, title="")
    d = outreach.founder_email(facts, "Sarah", "https://calendly.com/x")
    assert "oz" not in d["subject"]
    assert "band" not in d["body"]


def test_the_partner_template_refuses_to_send_without_a_number():
    with pytest.raises(ValueError):
        outreach.partner_email(_facts(weight=None), "Jess", "15%")


def test_the_partner_template_labels_the_estimate_and_the_source():
    d = outreach.partner_email(_facts(), "Jess", "15% of anything that renews")
    assert "public listing" in d["body"] and "no account access" in d["body"]
    assert "estimated from public rank" in d["body"]
    assert "15% of anything that renews" in d["body"]
    assert "Tens Towels's" not in d["body"], "possessive of a name ending in s"
