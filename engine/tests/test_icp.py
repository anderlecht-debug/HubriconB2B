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
    """The plausible-sounding version is the dangerous one.

    "the fee side looks like it's costing you more than it should" reads fine
    and asserts a problem we have not measured. The gap stays visible instead.
    """
    facts = _facts(weight=None, title="")
    d = outreach.founder_email(facts, "Sarah", "https://calendly.com/x")
    assert d["complete"] is False
    assert "Do not send this email without one" in d["body"]
    assert "costing you more than it should" not in d["body"]
    assert outreach.founder_email(_facts(), "Sarah", "https://calendly.com/x")["complete"] is True


def test_the_partner_template_refuses_to_send_without_a_number():
    with pytest.raises(ValueError):
        outreach.partner_email(_facts(weight=None), "Jess", "15%")


def test_the_partner_template_labels_the_estimate_and_the_source():
    d = outreach.partner_email(_facts(), "Jess", "15% of anything that renews")
    assert "public listing" in d["body"] and "no account access" in d["body"]
    assert "estimated from public rank" in d["body"]
    assert "15% of anything that renews" in d["body"]
    assert "Tens Towels's" not in d["body"], "possessive of a name ending in s"


# -- prune_dq ------------------------------------------------------------------
# A disqualified prospect that stays enrolled in Instantly still gets emailed.

class _PruneDB:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def table(self, name):
        return self

    def select(self, *_):
        return self

    def eq(self, k, v):
        self._key = (k, v)
        return self

    def execute(self):
        return type("R", (), {"data": [dict(r) for r in self.rows]})()

    def update(self, fields):
        self.updates.append(fields)
        return self


class _PruneApi:
    def __init__(self, objects=()):
        self.deleted = []
        self.objects = list(objects)

    def leads_by_email(self, email):
        return list(self.objects)

    def delete_lead(self, lead_id):
        self.deleted.append(lead_id)


def test_prune_dq_deletes_the_campaign_lead_and_never_the_list_lead():
    """The lists are the harvest's inventory and the founder lane's address book.

    The first version deleted every object leads_by_email returned and emptied
    "Hubricon harvest (auto)" from 34 leads to 1.
    """
    db = _PruneDB([{"email": "x@y.com", "instantly_lead_id": "LIST1", "fit_notes": "agency"}])
    api = _PruneApi(objects=[{"id": "LIST1"},                       # a list row: no campaign
                             {"id": "LIST2", "campaign": "OTHER"},  # someone else's campaign
                             {"id": "CAMP1", "campaign": "C1"}])
    assert outreach.prune_dq(db, api, "C1", log=lambda *_: None) == 1
    assert api.deleted == ["CAMP1"], "only the enrolment in this campaign may be deleted"


def test_prune_dq_deletes_nothing_without_a_campaign_id():
    db = _PruneDB([{"email": "x@y.com", "instantly_lead_id": "LIST1", "fit_notes": "agency"}])
    api = _PruneApi(objects=[{"id": "LIST1"}])
    assert outreach.prune_dq(db, api, None, log=lambda *_: None) == 0
    assert api.deleted == []


def test_prune_dq_marks_the_row_so_it_is_not_looked_up_forever():
    db = _PruneDB([{"email": "x@y.com", "instantly_lead_id": "L1", "fit_notes": "agency"}])
    outreach.prune_dq(db, _PruneApi([{"id": "L1", "campaign": "C1"}]), "C1", log=lambda *_: None)
    assert outreach.DONE_MARK in db.updates[-1]["fit_notes"]
    assert db.updates[-1]["instantly_lead_id"] is None


def test_prune_dq_skips_rows_already_confirmed_gone():
    db = _PruneDB([{"email": "x@y.com", "instantly_lead_id": None,
                    "fit_notes": f"agency; {outreach.DONE_MARK} (2 lead object(s))"}])
    api = _PruneApi()
    assert outreach.prune_dq(db, api, "C1", log=lambda *_: None) == 0
    assert api.deleted == []


def test_prune_dq_leaves_the_row_alone_when_a_delete_fails():
    class _Failing(_PruneApi):
        def delete_lead(self, lead_id):
            raise RuntimeError("500")

    db = _PruneDB([{"email": "x@y.com", "instantly_lead_id": "L1", "fit_notes": "agency"}])
    assert outreach.prune_dq(db, _Failing([{"id": "L1", "campaign": "C1"}]), "C1", log=lambda *_: None) == 0
    assert db.updates == [], "a failed delete must not be recorded as done"


def test_a_short_token_must_start_a_word_or_it_rejects_real_brands():
    # Found live on 2026-09-04: the Shopify harvest lost The Happy Planner
    # because "thehappyplanner.com" contains "app". This gate runs at
    # enrollment, so a false positive silently drops a lead nobody sees.
    for name, site in [("Happy Brands", "thehappyplanner.com"),
                       ("Rapid Gear", "rapidgear.com"),          # r-api-dgear
                       ("Snapware", "snapware.com"),             # sn-app-ware
                       ("Badass Beard Care", "badassbeardcare.com")]:
        assert icp.off_icp(name, None, site) == (None, ""), name

    # the businesses the gate exists to catch are still caught
    for name, site, bucket in [("Acme PPC", "acmeppc.com", "agency"),
                               ("Bright Agency", "brightagency.com", "agency"),
                               ("AMZ Consulting", "amzconsulting.com", "agency"),
                               ("Ship 3PL", "ship3pl.com", "logistics"),
                               ("Helium 10", "helium10.com", "software")]:
        assert icp.off_icp(name, None, site)[0] == bucket, name

    # a long token still matches mid-word, which is what makes the above work
    assert icp.off_icp("Global Prep Center", None, "x.com")[0] == "logistics"
