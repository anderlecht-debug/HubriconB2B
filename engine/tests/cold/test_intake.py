"""Leads the founder found by hand.

The parser is deliberately forgiving because its input is a person working
quickly — a paste from a spreadsheet, a browser, or their own notes. Every shape
below is one someone would plausibly type.
"""

from hubricon_engine.cold import intake


def idents(text):
    leads, _ = intake.parse(text)
    return [(l.ident, l.email, l.first_name) for l in leads]


def test_a_bare_domain_is_a_lead():
    assert idents("holtzleather.com") == [("holtzleather.com", None, None)]


def test_a_domain_an_address_and_a_name_in_any_order():
    one = idents("holtzleather.com, nora@holtzleather.com, Nora")
    two = idents("Nora, nora@holtzleather.com, holtzleather.com")
    assert one == two == [("holtzleather.com", "nora@holtzleather.com", "Nora")]


def test_tabs_and_commas_are_both_a_paste_from_a_spreadsheet():
    assert idents("holtzleather.com\tnora@holtzleather.com\tNora") == \
        idents("holtzleather.com,nora@holtzleather.com,Nora")


def test_an_amazon_seller_id_is_recognised_and_a_domain_is_not():
    leads, _ = intake.parse("A1TIL6RG80Z0E0\nholtzleather.com")
    assert [l.is_amazon for l in leads] == [True, False]


def test_an_address_alone_names_its_own_domain():
    assert idents("nora@riverbendgoods.com") == \
        [("riverbendgoods.com", "nora@riverbendgoods.com", None)]


def test_a_header_row_blank_lines_and_comments_are_skipped():
    text = "domain,email,first_name\n\n# from the Shopify marketplace\nholtzleather.com\n"
    assert idents(text) == [("holtzleather.com", None, None)]


def test_the_same_company_twice_is_a_slip_not_two_leads():
    assert len(idents("holtzleather.com\nwww.holtzleather.com\nhttps://holtzleather.com/")) == 1


def test_a_line_that_makes_no_sense_is_reported_not_raised():
    leads, bad = intake.parse("holtzleather.com\nnot a lead\n")
    assert len(leads) == 1 and bad == ["not a lead"]


def test_a_url_is_reduced_to_its_host():
    leads, _ = intake.parse("https://www.holtzleather.com/collections/all")
    assert leads[0].handle == "holtzleather.com"


# -- resolving a brand's domain to the store behind it ------------------------------

class FakeFetcher:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def get(self, url):
        self.calls.append(url)
        return self.pages.get(url)


META = '{"name":"Holtz Leather","myshopify_domain":"holtz-leather.myshopify.com",' \
       '"country":"US","currency":"USD"}'


def test_a_brand_domain_resolves_to_the_myshopify_handle():
    """The row key is the handle, because a primary domain can be re-pointed and
    a handle cannot. Passing the domain in where a handle belongs asks for
    `brand.com.myshopify.com`, which is nobody's store."""
    f = FakeFetcher({"https://holtzleather.com/meta.json": META})
    handle, meta = intake.resolve_handle(f, "https://www.holtzleather.com/")
    assert handle == "holtz-leather"
    assert meta["name"] == "Holtz Leather"
    assert f.calls == ["https://holtzleather.com/meta.json"]


def test_a_handle_or_a_myshopify_domain_costs_no_request():
    f = FakeFetcher({})
    assert intake.resolve_handle(f, "holtz-leather") == ("holtz-leather", None)
    assert intake.resolve_handle(f, "holtz-leather.myshopify.com") == ("holtz-leather", None)
    assert f.calls == [], "already a handle: nothing to look up"


def test_a_domain_that_is_not_a_shopify_store_says_so_rather_than_guessing():
    f = FakeFetcher({"https://example.com/meta.json": "<html>not json</html>"})
    handle, _ = intake.resolve_handle(f, "example.com")
    assert handle is None
