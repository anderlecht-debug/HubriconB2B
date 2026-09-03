"""The free lead harvest: parsers over the public Amazon pages, the website /
contact enrichment, the polite fetcher, and the crawl → enrich → push pipeline
against in-memory doubles. No network anywhere in here."""

import base64
import urllib.error
from datetime import date
from pathlib import Path

import pytest

from hubricon_engine.harvest import amazon, enrich, run
from hubricon_engine.harvest.fetch import Blocked, Cache, Fetcher

# -- fixtures modeled on the live markup (2026-09-02) ----------------------------

PRODUCT_3P = """<html><head><title>Amazon.com: HydroJug Traveler 40oz</title></head><body>
<span id="productTitle">   HydroJug Traveler 40oz, Insulated Tumbler  </span>
<a id="bylineInfo" class="a-link-normal" href="/stores/HydroJug/page/123">Visit the HydroJug Store</a>
<span class="a-price-whole">31<span class="a-price-decimal">.</span></span><span class="a-price-fraction">99</span>
<span id="acrCustomerReviewText" class="a-size-base">17,222 ratings</span>
<div class="a-row"><span class="a-size-small"> Ships from: </span> <span class="a-size-small"> Amazon </span></div>
<div class="a-row"><span class="a-size-small"> Sold by: </span> <span class="a-size-small"> HydroJug </span></div>
<a href='/gp/help/seller/at-a-glance.html/ref=dp_merchant_link?ie=UTF8&amp;seller=AXSP4G6IQFYIQ&amp;asin=B0CQVWT2NH&amp;ref_=dp_merchant_link&amp;isAmazonFulfilled=1' id='sellerProfileTriggerId'>HydroJug</a>
<table><tr><th class="prodDetSectionEntry">Best Sellers Rank</th><td><span><span>#400 in Kitchen &amp; Dining (<a href="/gp/bestsellers/kitchen">See Top 100 in Kitchen &amp; Dining</a>)</span> <span>#1 in Tumblers &amp; Water Glasses</span></span></td></tr>
<tr><th class="prodDetSectionEntry">Item Weight</th><td class="prodDetAttrValue"> 1.3 pounds </td></tr>
<tr><th class="prodDetSectionEntry">Product Dimensions</th><td class="prodDetAttrValue"> 6"W x 9.84"H </td></tr></table>
<div data-asin="B0CQVWT2NH"></div><div data-asin="B0AAAAAAA1"></div><div data-asin="B0AAAAAAA2"></div>
</body></html>"""

PRODUCT_AMZ = """<html><head><title>Echo Dot</title></head><body><span id="productTitle">Echo Dot</span>
<a id="bylineInfo" href="/stores/x">Visit the Amazon Echo &amp; Alexa Store</a>
<div class="a-row"><span class="a-size-small"> Ships from: </span> <span class="a-size-small"> Amazon.com </span></div>
<div class="a-row"><span class="a-size-small"> Sold by: </span> <span class="a-size-small"> Amazon.com </span></div>
<script>var x = {"merchantId":"ATVPDKIKX0DER"};</script></body></html>"""

SELLER_PAGE = """<html><body><h1 id="seller-name">HydroJug</h1>
<div class="a-box"><div class="a-box-inner"><!-- Detailed Seller Information --> <div class="a-row a-spacing-small"><h3>Detailed Seller Information</h3></div><div class="a-row a-spacing-none"><span class="a-text-bold">Business Name: </span><span>HYDROJUG LLC</span></div><div class="a-row a-spacing-none"><span class="a-text-bold">Business Address: </span></div><div class="a-row a-spacing-none indent-left"><span>1 MAIN ST</span></div><div class="a-row a-spacing-none indent-left"><span>STE 2</span></div><div class="a-row a-spacing-none indent-left"><span>OGDEN</span></div><div class="a-row a-spacing-none indent-left"><span>UT</span></div><div class="a-row a-spacing-none indent-left"><span>84401</span></div><div class="a-row a-spacing-none indent-left"><span>US</span></div></div></div></body></html>"""

BESTSELLER_PAGE = """<html><body>
<a href="/HydroJug-Traveler/dp/B0CQVWT2NH/ref=zg_bs_g_kitchen_d_sccl_1/000-0000000-0000000?psc=1">x</a>
<a href="/Echo-Dot/dp/B09B8V1LZ3/ref=zg_bs_g_kitchen_d_sccl_2/000?psc=1">y</a>
<a href="/HydroJug-Traveler/dp/B0CQVWT2NH/ref=dup">dup</a>
<a href="/Best-Sellers-Kitchen-Dining-Bakeware/zgbs/kitchen/289668/ref=zg_bs_nav_kitchen_1">Bakeware</a>
<a href="/Best-Sellers-Kitchen-Dining/zgbs/kitchen/ref=zg_bs_pg_2_kitchen?_encoding=UTF8&amp;pg=2">Next</a>
</body></html>"""


def bing_page(*urls: str) -> str:
    items = []
    for u in urls:
        enc = "a1" + base64.urlsafe_b64encode(u.encode()).decode().rstrip("=")
        items.append(f'<li class="b_algo"><h2><a href="https://www.bing.com/ck/a?!&amp;&amp;p=abc&amp;u={enc}&amp;ntb=1">r</a></h2></li>')
    return "<html><body><ol>" + "".join(items) + "</ol></body></html>"


# -- doubles ----------------------------------------------------------------------

class _Result:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, store, name):
        self.rows = store.setdefault(name, [])
        self._filters, self._order, self._limit, self._op, self._payload = [], None, None, None, None

    def select(self, *_):
        self._op = "select"
        return self

    def eq(self, k, v):
        self._filters.append(lambda r: r.get(k) == v)
        return self

    def gte(self, k, v):
        self._filters.append(lambda r: r.get(k) is not None and r.get(k) >= v)
        return self

    def order(self, k, desc=False):
        self._order = (k, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def upsert(self, rows, on_conflict="id"):
        self._op, self._payload = "upsert", (rows if isinstance(rows, list) else [rows], on_conflict)
        return self

    def update(self, d):
        self._op, self._payload = "update", d
        return self

    def insert(self, row):
        self._op, self._payload = "insert", row
        return self

    def execute(self):
        if self._op == "select":
            rows = [r for r in self.rows if all(f(r) for f in self._filters)]
            if self._order:
                k, desc = self._order
                rows = sorted(rows, key=lambda r: r.get(k) or 0, reverse=desc)
            if self._limit:
                rows = rows[: self._limit]
            return _Result([dict(r) for r in rows])
        if self._op == "upsert":
            rows, key = self._payload
            for new in rows:
                for i, old in enumerate(self.rows):
                    if old.get(key) == new.get(key):
                        self.rows[i] = {**old, **new}
                        break
                else:
                    self.rows.append(dict(new))
            return _Result(rows)
        if self._op == "update":
            for r in self.rows:
                if all(f(r) for f in self._filters):
                    r.update(self._payload)
            return _Result([])
        if self._op == "insert":
            self.rows.append(dict(self._payload))
            return _Result([self._payload])
        raise AssertionError("no op")


class FakeDB:
    def __init__(self):
        self.store: dict[str, list[dict]] = {}

    def table(self, name):
        return FakeTable(self.store, name)


class FakeFetcher:
    def __init__(self, pages: dict[str, str]):
        self.pages, self.calls = pages, []
        self.stats = {"requests": 0, "ok": 0, "missing": 0, "errors": 0, "blocked": 0, "chars": 0}

    def get(self, url, headers=None):
        self.calls.append(url)
        self.stats["requests"] += 1
        page = self.pages.get(url)
        self.stats["ok" if page else "missing"] += 1
        return page


class FakeApi:
    def __init__(self, lists=None):
        self.lists, self.added, self.created = list(lists or []), [], []

    def lead_lists(self):
        return self.lists

    def create_lead_list(self, name):
        self.created.append(name)
        lst = {"id": "L1", "name": name}
        self.lists.append(lst)
        return lst

    def add_leads(self, list_id=None, campaign_id=None, leads=None):
        self.added.append((list_id, leads))
        return {"ok": True}


quiet = lambda *_: None  # noqa: E731


# -- amazon parsers ----------------------------------------------------------------

def test_bestseller_page_lists_asins_children_and_next_page():
    p = amazon.bestseller_page(BESTSELLER_PAGE)
    assert p["asins"] == ["B0CQVWT2NH", "B09B8V1LZ3"]  # deduped, in order
    assert p["subcategories"] == ["https://www.amazon.com/Best-Sellers-Kitchen-Dining-Bakeware/zgbs/kitchen/289668"]
    assert p["next"].endswith("zgbs/kitchen/ref=zg_bs_pg_2_kitchen?_encoding=UTF8&pg=2")


def test_product_page_third_party_fba():
    p = amazon.product(PRODUCT_3P, "B0CQVWT2NH")
    assert p["brand"] == "HydroJug" and p["seller_id"] == "AXSP4G6IQFYIQ" and p["seller_name"] == "HydroJug"
    assert p["fba"] and not p["sold_by_amazon"]
    assert p["price"] == 31.99 and p["reviews"] == 17222
    assert p["bsr"] == 400 and p["category"] == "Kitchen & Dining"
    assert p["weight_oz"] == 20.8 and p["dims"] == '6"W x 9.84"H'
    assert p["related"] == ["B0AAAAAAA1", "B0AAAAAAA2"]
    assert p["est_monthly_units"] > 0 and p["est_monthly_revenue"] == round(p["est_monthly_units"] * 31.99, 2)


def test_product_page_sold_by_amazon_has_no_seller():
    p = amazon.product(PRODUCT_AMZ, "B09B8V1LZ3")
    assert p["seller_id"] is None and p["sold_by_amazon"]
    assert p["brand"] == "Amazon Echo & Alexa"


def test_seller_profile_parses_the_public_business_identity():
    s = amazon.seller(SELLER_PAGE)
    assert s["seller_name"] == "HydroJug" and s["business_name"] == "HYDROJUG LLC"
    assert (s["city"], s["state"], s["zip"], s["country"]) == ("OGDEN", "UT", "84401", "US")
    assert s["address"] == "1 MAIN ST, STE 2, OGDEN, UT 84401, US"


def test_weight_units_normalise_to_ounces():
    assert amazon.weight_to_oz("1.3 pounds") == 20.8
    assert amazon.weight_to_oz("2.4 ounces") == 2.4
    assert amazon.weight_to_oz("200 g") == 7.055
    assert amazon.weight_to_oz("1.2 Kilograms") == 42.329
    assert amazon.weight_to_oz(None) is None and amazon.weight_to_oz("n/a") is None


def test_bsr_curve_is_monotonic_and_flattens_at_the_top():
    u = lambda r: amazon.estimate_units(r, "Home & Kitchen")  # noqa: E731
    assert u(1) > u(10) > u(1000) > u(100000) > 0
    assert u(1) < 120_000  # the head is capped by the knee, not extrapolated
    assert abs(u(1000) - 1995) < 60
    assert amazon.estimate_units(None, "x") is None
    assert amazon.estimate_units(5000, "Musical Instruments") < amazon.estimate_units(5000, "Home & Kitchen")


def test_private_label_reseller_and_offshore_heuristics():
    assert amazon.looks_private_label("HydroJug", "HydroJug", "HYDROJUG LLC")
    assert amazon.looks_private_label("Anker", "AnkerDirect", "FANTASIA TRADING LLC")
    assert not amazon.looks_private_label("JBL", "Huppins", "HUPPINS ONECALL")
    assert amazon.looks_reseller("Huppins", "HUPPINS ONECALL", 3)
    assert amazon.looks_reseller("X", "Best Deals Warehouse", 1)
    assert not amazon.looks_reseller("HydroJug", "HYDROJUG LLC", 1)
    assert amazon.looks_offshore("Shenzhen Foo Technology Co., Ltd", None)
    assert not amazon.looks_offshore("HYDROJUG LLC", "1 MAIN ST, OGDEN, UT 84401, US")


# -- enrichment -----------------------------------------------------------------------

def test_candidate_domains_start_with_the_obvious_one():
    d = enrich.candidate_domains("Alpha Grillers")
    assert d[0] == "alphagrillers.com" and "alpha-grillers.com" in d
    assert enrich.candidate_domains("Ab") == []


def test_bing_links_are_unwrapped():
    assert enrich.bing_results(bing_page("https://www.anker.com/", "https://www.amazon.com/x")) == \
        ["https://www.anker.com/", "https://www.amazon.com/x"]
    assert enrich.bing_results(None) == []


def test_site_matches_requires_the_brand_and_rejects_parked_domains():
    assert enrich.site_matches("<html><head><title>Anker | Official</title></head></html>", "Anker")
    assert not enrich.site_matches("<html><title>Anker</title>This domain is for sale</html>", "Anker")
    assert not enrich.site_matches("<html><title>Something else</title></html>", "Anker")


def test_founder_name_from_about_copy():
    assert enrich.founder_name("<p>Founded by Jane Doe in 2015, we make jugs.</p>") == ("Jane", "Doe")
    assert enrich.founder_name("<p>John Smith, founder of HydroJug, says hi.</p>") == ("John", "Smith")
    assert enrich.founder_name("<h2>Meet Our Team</h2><p>Our Founder is here.</p>") == (None, None)


def test_page_emails_filter_noise_and_prefer_hello():
    page = ('<a href="mailto:support@brand.com">s</a> <a href="mailto:hello@brand.com">h</a> '
            'noreply@brand.com logo@2x.png sentry@sentry.io')
    assert enrich.page_emails(page, "brand.com") == ["hello@brand.com", "support@brand.com"]


def test_guess_emails_lead_with_a_found_first_name():
    assert enrich.guess_emails("d.com", "Jane", "Doe")[:2] == ["jane@d.com", "hello@d.com"]
    assert enrich.guess_emails("d.com")[0] == "hello@d.com"


def test_enrich_seller_direct_domain_with_published_address():
    f = FakeFetcher({"https://hydrojug.com/": '<html><head><title>HydroJug | Official Store</title></head>'
                                             '<body><a href="mailto:hello@hydrojug.com">Email</a> Founded by Jane Doe in 2016.</body></html>'})
    upd = enrich.enrich_seller(f, {"brand": "HydroJug", "business_name": "HYDROJUG LLC"}, resolver=lambda d: True)
    assert upd["status"] == "enriched" and upd["website"] == "https://hydrojug.com/"
    assert upd["email"] == "hello@hydrojug.com" and upd["email_confidence"] == "published"
    assert (upd["first_name"], upd["last_name"]) == ("Jane", "Doe")


def test_enrich_seller_falls_back_to_bing_and_a_pattern_address():
    q = "https://www.bing.com/search?q=" + enrich.urllib.parse.quote('"Alpha Grillers" official site')
    f = FakeFetcher({q: bing_page("https://www.amazon.com/stores/x", "https://www.alphagrillers.shop/"),
                     "https://alphagrillers.shop/": "<html><head><title>Alpha Grillers</title></head><body>no mail here</body></html>"})
    upd = enrich.enrich_seller(f, {"brand": "Alpha Grillers", "business_name": "ALPHA GRILLERS LLC"}, resolver=lambda d: True)
    assert upd["status"] == "enriched" and upd["website"] == "https://alphagrillers.shop/"
    assert upd["email"] == "hello@alphagrillers.shop" and upd["email_confidence"] == "pattern"
    assert "Instantly verifies" in upd["notes"]
    assert not any("amazon.com" in c for c in f.calls)  # marketplace results are never "the site"


def test_enrich_seller_reports_no_website_and_no_mx():
    assert enrich.enrich_seller(FakeFetcher({}), {"brand": "Nowhere Brand"})["status"] == "no_website"
    f = FakeFetcher({"https://nomx.com/": "<html><title>NoMX</title></html>"})
    assert enrich.enrich_seller(f, {"brand": "NoMX"}, resolver=lambda d: False)["status"] == "no_email"


# -- fetcher / cache --------------------------------------------------------------------

def test_fetcher_waits_once_then_stops_on_repeated_captchas():
    sleeps = []

    def transport(url, headers, timeout):
        return 200, "<html>Robot Check</html>" if "amazon." in url else "<html>ok</html>"

    f = Fetcher(min_interval=0, jitter=0, transport=transport, sleep=sleeps.append, clock=lambda: 0.0, block_pause=5)
    assert f.get("https://example.com/") == "<html>ok</html>"
    assert f.get("https://www.amazon.com/dp/X") is None and sleeps == [5]
    with pytest.raises(Blocked):
        f.get("https://www.amazon.com/dp/Y")
    assert f.stats["blocked"] == 2 and f.stats["ok"] == 1


def test_fetcher_treats_404_as_missing_and_paces_a_host():
    def transport(url, headers, timeout):
        raise urllib.error.HTTPError(url, 404, "nf", {}, None)

    sleeps, now = [], [100.0]
    f = Fetcher(min_interval=4, jitter=0, transport=transport, sleep=sleeps.append, clock=lambda: now[0])
    assert f.get("https://www.amazon.com/dp/X") is None and f.stats["missing"] == 1
    now[0] += 1
    f.get("https://www.amazon.com/dp/Y")
    assert sleeps and abs(sleeps[0] - 3) < 1e-6  # 4s spacing, 1s already elapsed


def test_cache_roundtrip_and_expiry(tmp_path):
    c = Cache(tmp_path)
    assert c.get("product", "B0X", 30) is None
    c.put("product", "B0X", {"brand": "X"})
    assert c.get("product", "B0X", 30) == {"brand": "X"}
    assert c.get("product", "B0X", 0) is None


# -- pipeline ------------------------------------------------------------------------------

def test_categories_rotate_by_day():
    a, b = run.pick_categories(3, date(2026, 9, 3)), run.pick_categories(3, date(2026, 9, 4))
    assert len(a) == 3 and set(a) <= set(amazon.CATEGORIES) and a != b


def _agg(brand="HydroJug", seller="HydroJug", brands=None, rev=95000.0, reviews=1000):
    return {"seller_id": "S1", "seller_name": seller, "brand": brand, "brands": brands or [brand],
            "asins": [{"asin": "A", "brand": brand, "bsr": 400, "price": 30.0, "reviews": reviews,
                       "est_monthly_revenue": rev}],
            "reviews_max": reviews, "top_bsr": 400, "top_category": "Kitchen & Dining"}


def test_classify_keeps_us_founder_brands_and_skips_the_rest():
    us = {"business_name": "HYDROJUG LLC", "country": "US", "address": "1 MAIN ST, OGDEN, UT 84401, US"}
    assert run.classify(_agg(), us) == ("candidate", "brand matches seller")
    assert run.classify(_agg(), {**us, "country": "CN"})[0] == "skip_non_us"
    assert run.classify(_agg(), {**us, "business_name": "Shenzhen Foo Technology Co., Ltd"})[0] == "skip_non_us"
    assert run.classify(_agg(brands=["A", "B", "C"]), us)[0] == "skip_reseller"
    assert run.classify(_agg(rev=2_000_000), us)[0] == "skip_size"
    assert run.classify(_agg(reviews=200_000), us)[0] == "skip_size"
    assert run.classify(_agg(brand="Foo", seller="Bar"), {**us, "business_name": "BAR LLC"})[0] == "candidate"
    assert run.classify(_agg(brand="Foo", seller="Bar", brands=["Foo", "Baz"]), {**us, "business_name": "BAR LLC"})[0] == "skip_reseller"
    assert run.classify(_agg(), None)[0] == "candidate"  # profile unavailable: still worth enriching


def _crawl_pages():
    return {amazon.category_url("kitchen"): BESTSELLER_PAGE,
            f"{amazon.BASE}/dp/B0CQVWT2NH": PRODUCT_3P,
            f"{amazon.BASE}/dp/B09B8V1LZ3": PRODUCT_AMZ,
            amazon.seller_url("AXSP4G6IQFYIQ"): SELLER_PAGE}


def test_crawl_writes_products_and_one_candidate_seller(tmp_path):
    db, f = FakeDB(), FakeFetcher(_crawl_pages())
    s = run.crawl(db, f, ["kitchen"], max_products=10, cache=Cache(tmp_path), log=quiet)
    assert s["products_fetched"] == 2 and s["sellers_seen"] == 1 and s["sellers_new"] == 1
    assert {r["asin"] for r in db.store["harvest_products"]} == {"B0CQVWT2NH", "B09B8V1LZ3"}
    (row,) = db.store["harvest_sellers"]
    assert row["seller_id"] == "AXSP4G6IQFYIQ" and row["status"] == "candidate"
    assert row["brand"] == "HydroJug" and row["business_name"] == "HYDROJUG LLC" and row["country"] == "US"
    assert row["est_monthly_revenue"] > 0 and row["asins"][0]["asin"] == "B0CQVWT2NH"
    assert db.store["funnel_events"][0]["kind"] == "harvest"
    # second pass: everything parsed last time comes from the cache, Amazon is not asked again
    f2 = FakeFetcher(_crawl_pages())
    s2 = run.crawl(db, f2, ["kitchen"], max_products=10, cache=Cache(tmp_path), log=quiet)
    assert s2["products_cached"] == 2 and s2["sellers_new"] == 0
    assert not any("/dp/" in c or "/sp?" in c for c in f2.calls)


def test_crawl_stops_cleanly_when_amazon_blocks(tmp_path):
    class Blocker(FakeFetcher):
        def get(self, url, headers=None):
            if "/dp/" in url:
                raise Blocked("captcha")
            return super().get(url, headers)

    db = FakeDB()
    s = run.crawl(db, Blocker(_crawl_pages()), ["kitchen"], max_products=10, cache=Cache(tmp_path), log=quiet)
    assert s["blocked"] and s["products_fetched"] == 1 and not db.store.get("harvest_sellers")


def test_enrich_updates_rows_in_revenue_order(tmp_path):
    db = FakeDB()
    db.store["harvest_sellers"] = [
        {"seller_id": "S1", "brand": "HydroJug", "business_name": "HYDROJUG LLC", "status": "candidate", "est_monthly_revenue": 95000},
        {"seller_id": "S2", "brand": "Nowhere Brand", "business_name": None, "status": "candidate", "est_monthly_revenue": 5000},
    ]
    f = FakeFetcher({"https://hydrojug.com/": '<html><title>HydroJug</title><a href="mailto:hello@hydrojug.com">x</a></html>'})
    counts = run.enrich(db, f, limit=10, resolver=lambda d: True, log=quiet)
    assert counts == {"enriched": 1, "no_website": 1}
    s1, s2 = db.store["harvest_sellers"]
    assert s1["status"] == "enriched" and s1["email"] == "hello@hydrojug.com" and s1["website"] == "https://hydrojug.com/"
    assert s2["status"] == "no_website"


def _enriched_rows():
    return [
        {"seller_id": "A", "brand": "A Brand", "status": "enriched", "email": "hello@a.com", "est_monthly_revenue": 50000,
         "website": "https://a.com/", "business_name": "A LLC", "email_confidence": "published"},
        {"seller_id": "B", "brand": "B Brand", "status": "enriched", "email": "hello@b.com", "est_monthly_revenue": 1000},
        {"seller_id": "C", "brand": "C Brand", "status": "enriched", "email": "hagen.hds@gmail.com", "est_monthly_revenue": 20000},
        {"seller_id": "D", "brand": "D Brand", "status": "candidate", "email": None, "est_monthly_revenue": 90000},
    ]


def test_push_creates_the_list_batches_leads_and_marks_rows():
    db, api = FakeDB(), FakeApi()
    db.store["harvest_sellers"] = _enriched_rows()
    assert run.push(db, api, limit=40, log=quiet) == 1
    assert api.created == [run.LIST_NAME] and "hubricon" in run.LIST_NAME.lower()  # the operator enrolls it
    list_id, leads = api.added[0]
    assert list_id == "L1" and [l["email"] for l in leads] == ["hello@a.com"]
    lead = leads[0]
    assert lead["first_name"] == "A Brand team" and lead["company_name"] == "A Brand"  # "Hi {{firstName}}" never renders empty
    assert lead["custom_variables"]["source"] == "harvest" and lead["custom_variables"]["person_found"] is False
    by_id = {r["seller_id"]: r for r in db.store["harvest_sellers"]}
    assert by_id["A"]["status"] == "pushed" and by_id["A"]["pushed_at"]
    assert by_id["B"]["status"] == "enriched"  # below the revenue floor, waits
    assert by_id["C"]["status"] == "enriched"  # internal address, never pushed
    assert run.push(db, api, limit=40, log=quiet) == 0  # idempotent


def test_push_dry_run_and_no_api_touch_nothing():
    db = FakeDB()
    db.store["harvest_sellers"] = _enriched_rows()
    api = FakeApi()
    assert run.push(db, api, dry=True, log=quiet) == 1 and not api.added and not api.created
    assert run.push(db, None, log=quiet) == 0
    assert all(r["status"] != "pushed" for r in db.store["harvest_sellers"])


def test_lead_payload_prefers_a_found_person():
    lead = run.lead_payload({"seller_id": "S", "brand": "X", "email": "jane@x.com", "first_name": "Jane", "last_name": "Doe"})
    assert (lead["first_name"], lead["last_name"]) == ("Jane", "Doe") and lead["custom_variables"]["person_found"]


def test_fee_cliff_edges():
    assert amazon.fee_cliff(16.8) == (16, 0.8)   # 0.8 oz of packaging away from the 14–16 oz band
    assert amazon.fee_cliff(20.8) == (20, 0.8)
    assert amazon.fee_cliff(50.0) == (48, 2.0)
    assert amazon.fee_cliff(100.0) == (96, 4.0)
    assert amazon.fee_cliff(2.0) is None and amazon.fee_cliff(None) is None


def test_fee_cliff_report_counts_listings_near_a_lighter_band():
    db = FakeDB()
    db.store["harvest_products"] = [
        {"asin": "A1", "brand": "A", "category": "Kitchen & Dining", "weight_oz": 16.8, "est_monthly_units": 900},
        {"asin": "A2", "brand": "B", "category": "Kitchen & Dining", "weight_oz": 9.5, "est_monthly_units": 100},
        {"asin": "A3", "brand": "C", "category": "Pet Supplies", "weight_oz": 32.5, "est_monthly_units": 50},
        {"asin": "A4", "brand": "D", "category": "Pet Supplies", "weight_oz": None},
    ]
    r = run.fee_cliff_report(db, within_oz=1.0)
    assert (r["products"], r["with_weight"], r["near_cliff"]) == (4, 3, 2)
    assert r["by_category"][0] == {"category": "Pet Supplies", "near": 1, "total": 1, "share": 1.0}
    assert r["examples"][0]["asin"] == "A1" and r["examples"][0]["over_by_oz"] == 0.8
    text = run.fee_cliff_text(db)
    assert "2 listings (67%)" in text and "Pet Supplies" in text and "estimate" in text
    assert "no product weights" in run.fee_cliff_text(FakeDB())


def test_status_text_and_launchd_plist():
    db = FakeDB()
    db.store["harvest_sellers"] = _enriched_rows()
    text = run.status_text(db)
    assert "4 sellers on file" in text and "enriched 3" in text and "A Brand" in text
    plist = run.launchd_plist(Path("/x/engine"), "/opt/homebrew/bin/uv", 6, 10)
    assert plist["ProgramArguments"] == ["/opt/homebrew/bin/uv", "run", "hubricon", "harvest", "all"]
    assert plist["StartCalendarInterval"] == {"Hour": 6, "Minute": 10} and plist["WorkingDirectory"] == "/x/engine"
