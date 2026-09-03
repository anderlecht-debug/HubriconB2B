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
<div class="a-box"><div class="a-box-inner"><!-- Detailed Seller Information --> <div class="a-row a-spacing-small"><h3>Detailed Seller Information</h3></div><div class="a-row a-spacing-none"><span class="a-text-bold">Business Name: </span><span>HYDROJUG LLC</span></div><div class="a-row a-spacing-none"><span class="a-text-bold">Business Address: </span></div><div class="a-row a-spacing-none indent-left"><span>1 MAIN ST</span></div><div class="a-row a-spacing-none indent-left"><span>STE 2</span></div><div class="a-row a-spacing-none indent-left"><span>OGDEN</span></div><div class="a-row a-spacing-none indent-left"><span>UT</span></div><div class="a-row a-spacing-none indent-left"><span>84401</span></div><div class="a-row a-spacing-none indent-left"><span>US</span></div></div></div>
<a class="a-link-normal feedback-detail-description" href="#"><i class="a-icon a-icon-star a-star-5"><span class="a-icon-alt">5 out of 5 stars</span></i><b>98% positive</b> in the last 12 months (1,139 ratings)</a>
<div id="rating-lifetime-num" class="a-row a-spacing-none"><span class="ratings-reviews-count">50,819</span><span class="ratings-reviews-word">ratings</span></div>
</body></html>"""


def seller_page(name="HydroJug", business="HYDROJUG LLC", country="US", r12="1,139", life="50,819"):
    return (SELLER_PAGE.replace("HydroJug", name).replace("HYDROJUG LLC", business)
            .replace("<span>US</span>", f"<span>{country}</span>").replace("(1,139 ratings)", f"({r12} ratings)")
            .replace('ratings-reviews-count">50,819', f'ratings-reviews-count">{life}'))

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

    def in_(self, k, values):
        self._filters.append(lambda r: r.get(k) in values)
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

    def leads_by_email(self, email):
        return [l for l in getattr(self, "by_email", {}).get(email.lower(), [])]

    def delete_lead(self, lead_id):
        self.deleted = getattr(self, "deleted", []) + [lead_id]
        if lead_id == "gone":
            from hubricon_engine.instantly import InstantlyError
            raise InstantlyError(404, f"/leads/{lead_id}", "not found")
        return {}

    def supersearch_count(self, filters):
        self.counted = filters
        return {"number_of_leads": 7}

    def supersearch_enrich(self, list_id, filters, limit, search_name):
        self.enriched = (list_id, filters, limit, search_name)
        return {"background_job_id": "job-1"}

    def add_leads(self, list_id=None, campaign_id=None, leads=None):
        self.added.append((list_id, leads))
        return self.reply if hasattr(self, "reply") else {
            "status": "success", "total_sent": len(leads), "leads_uploaded": len(leads), "invalid_email_count": 0,
            "skipped_count": 0, "duplicated_leads": 0, "in_blocklist": 0,
            "created_leads": [{"index": i, "id": f"lead-{i}", "email": l["email"]} for i, l in enumerate(leads)]}


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
    assert s["ratings_12mo"] == 1139 and s["ratings_lifetime"] == 50819
    bare = amazon.seller("<html><h1 id='seller-name'>New Shop</h1></html>")
    assert bare["ratings_12mo"] is None and bare["ratings_lifetime"] is None


def test_seller_feedback_band_sizes_the_account():
    assert amazon.seller_size(8703, 211_667)[0] == "too_big"      # Gorilla Grip, $100M+
    assert amazon.seller_size(10_609, 107_044)[0] == "too_big"    # MED PRIDE
    assert amazon.seller_size(2_195, 63_297) == (None, "")         # Comfy Package stays
    assert amazon.seller_size(208, 836) == (None, "")              # KITESSENSU, ~$2M
    assert amazon.seller_size(40, 90)[0] == "too_small"
    assert amazon.seller_size(None, None) == (None, "")            # unknown never disqualifies
    assert amazon.seller_size(500, 90_000)[0] == "too_big"         # lifetime cap alone
    assert amazon.revenue_from_ratings(1200) == round(1200 * amazon.REVENUE_PER_RATING_YEAR / 12, 2)
    assert amazon.revenue_from_ratings(None) is None


def test_classify_uses_the_feedback_band_and_tolerates_profile_only_rows():
    agg = {"seller_id": "S", "seller_name": "Gorilla Grip", "brand": "GORILLA GRIP", "brands": ["GORILLA GRIP"],
           "asins": [{"asin": "A", "est_monthly_revenue": 40000, "price": 20}], "reviews_max": 30000}
    prof = {"business_name": "Some Industries, LLC", "country": "US", "ratings_12mo": 8703, "ratings_lifetime": 211667}
    status, note = run.classify(agg, prof)
    assert status == "skip_size" and "8,703" in note
    prof["ratings_12mo"], prof["ratings_lifetime"] = 900, 4000
    assert run.classify(agg, prof)[0] == "candidate"
    assert run.classify({**agg, "asins": []}, prof)[0] == "candidate"  # no listings known: still classifiable


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


def test_chrome_transport_builds_a_headless_dump_dom_command(monkeypatch, tmp_path):
    from hubricon_engine.harvest import fetch as fetchmod
    seen = {}

    def runner(cmd):
        seen["cmd"] = cmd
        return 200, "<html>dom</html>"
    t = fetchmod._chrome_transport("/fake/chrome", profile_dir=str(tmp_path / "prof"), runner=runner)
    assert t("https://www.amazon.com/dp/X", {"User-Agent": "UA/1"}, 40) == (200, "<html>dom</html>")
    cmd = seen["cmd"]
    assert cmd[0] == "/fake/chrome" and "--headless" in cmd and "--dump-dom" in cmd and cmd[-1] == "https://www.amazon.com/dp/X"
    assert "--user-agent=UA/1" in cmd and f"--user-data-dir={tmp_path / 'prof'}" in cmd and "--timeout=30000" in cmd
    monkeypatch.setenv("HARVEST_AMAZON_CLIENT", "urllib")
    assert fetchmod.chrome_binary() is None  # the switch back to plain HTTP
    monkeypatch.setenv("HARVEST_AMAZON_CLIENT", "chrome")
    monkeypatch.setenv("HARVEST_CHROME", str(tmp_path / "nope"))
    monkeypatch.setattr(fetchmod, "CHROME_CANDIDATES", (str(tmp_path / "nope"),))
    assert fetchmod.chrome_binary() is None
    (tmp_path / "chrome").write_text("")
    monkeypatch.setattr(fetchmod, "CHROME_CANDIDATES", (str(tmp_path / "chrome"),))
    assert fetchmod.chrome_binary() == str(tmp_path / "chrome")
    f = Fetcher(transport=lambda u, h, t: (200, "x"))  # an injected transport is used for every host
    assert f.amazon_transport is None and f.client == "urllib"


# -- enrichment -----------------------------------------------------------------------

def test_candidate_domains_start_with_the_obvious_one():
    d = enrich.candidate_domains("Alpha Grillers")
    assert d[0] == "alphagrillers.com" and "alpha-grillers.com" in d
    assert enrich.candidate_domains("Ab") == []
    # a long name: its first two words are tried as a domain and accepted in a title
    d = enrich.candidate_domains("MIND BODHI HEALTH & WELLNESS")
    assert d[:4] == ["mindbodhihealthwellness.com", "mindbodhihealthwellness.com", "mind-bodhi-health-wellness.com", "mindbodhi.com"] or "mindbodhi.com" in d[:4]
    assert enrich.short_token("MIND BODHI HEALTH & WELLNESS") == "mindbodhi" and enrich.short_token("Alpha Grillers") is None
    assert enrich.site_matches("<html><head><title>Mind Bodhi | Supplements</title></head></html>", "MIND BODHI HEALTH & WELLNESS")


def test_bing_links_are_unwrapped():
    assert enrich.bing_results(bing_page("https://www.anker.com/", "https://www.amazon.com/x")) == \
        ["https://www.anker.com/", "https://www.amazon.com/x"]
    assert enrich.bing_results(None) == []


def test_site_matches_requires_the_brand_and_rejects_parked_domains():
    assert enrich.site_matches("<html><head><title>Anker | Official</title></head></html>", "Anker")
    assert not enrich.site_matches("<html><title>Anker</title>This domain is for sale</html>", "Anker")
    assert not enrich.site_matches("<html><title>Something else</title></html>", "Anker")


def test_offshore_domains_disqualify_site_and_inbox():
    assert enrich.offshore_domain("akacompany.com.vn") == ".vn"
    assert enrich.offshore_domain("bellavita@akacompany.com.vn") == ".vn"
    assert enrich.offshore_domain("shop.example.co.uk") == ".co.uk"
    assert enrich.offshore_domain("hydrojug.com") is None and enrich.offshore_domain(None) is None
    f = FakeFetcher({"https://bellavita.com/": '<html><title>Bella Vita</title><a href="mailto:bellavita@akacompany.com.vn">x</a></html>'})
    upd = enrich.enrich_seller(f, {"brand": "Bella Vita", "business_name": None}, resolver=lambda d: True)
    assert upd["status"] == "skip_non_us" and ".vn" in upd["notes"]


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

def test_fetcher_backs_off_and_keeps_going_by_default():
    sleeps, pages = [], iter(["<html>Robot Check</html>", "<html>Robot Check</html>", "<html>Robot Check</html>", "<html>fine</html>"])

    def transport(url, headers, timeout):
        return 200, next(pages)

    f = Fetcher(min_interval=8, jitter=0, transport=transport, sleep=sleeps.append, clock=lambda: 0.0,
                block_pause=600, block_pause_cap=1500)
    assert f.get("https://www.amazon.com/dp/A") is None
    assert f.get("https://www.amazon.com/dp/B") is None
    assert f.get("https://www.amazon.com/dp/C") is None
    assert f.get("https://www.amazon.com/dp/D") == "<html>fine</html>"  # no Blocked, the run continues
    assert [x for x in sleeps if x >= 60] == [600, 1200, 1500]  # 10, 20, then the cap (shorter sleeps are pacing)
    assert f.min_interval == 27 and f.block_streak == 0 and f.stats["blocked"] == 3


def test_fetcher_can_still_give_up_when_asked():
    sleeps = []

    def transport(url, headers, timeout):
        return 200, "<html>Robot Check</html>" if "amazon." in url else "<html>ok</html>"

    f = Fetcher(min_interval=0, jitter=0, transport=transport, sleep=sleeps.append, clock=lambda: 0.0, block_pause=5,
                give_up=True)
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

def test_categories_rotate_by_half_day():
    a, b = run.pick_categories(3, date(2026, 9, 3), slot=0), run.pick_categories(3, date(2026, 9, 4), slot=0)
    assert len(a) == 3 and set(a) <= set(amazon.CATEGORIES) and a != b
    assert run.pick_categories(3, date(2026, 9, 3), slot=1) != a  # the evening run reads a different slice


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


def test_big_parents_and_aggregators_are_skipped():
    us = {"country": "US", "address": "1 MAIN ST, OGDEN, UT 84401, US"}
    assert run.classify(_agg(brand="Vital Proteins", seller="Vital Proteins"),
                        {**us, "business_name": "Nestle Healthcare Nutrition Inc"})[0] == "skip_size"
    assert run.classify(_agg(brand="Pure Encapsulations", seller="Pattern."),
                        {**us, "business_name": "Pattern Inc"})[0] == "skip_size"
    assert run.classify(_agg(rev=350_000), {**us, "business_name": "HYDROJUG LLC"})[0] == "skip_size"
    assert run.classify(_agg(rev=200_000), {**us, "business_name": "HYDROJUG LLC"})[0] == "candidate"


def test_category_asins_reads_child_lists_before_the_giants():
    root = ('<a href="/x/dp/B0ROOT0001/ref=a">r</a>'
            '<a href="/Best-Sellers-Kitchen-Dining-Bakeware/zgbs/kitchen/289668/ref=n">sub</a>'
            '<a href="/Best-Sellers-Kitchen-Dining/zgbs/kitchen/ref=zg_bs_pg_2_kitchen?_encoding=UTF8&amp;pg=2">n</a>')
    f = FakeFetcher({
        amazon.category_url("kitchen"): root,
        "https://www.amazon.com/Best-Sellers-Kitchen-Dining-Bakeware/zgbs/kitchen/289668": '<a href="/y/dp/B0SUBC0001/ref=a">s</a>',
        "https://www.amazon.com/Best-Sellers-Kitchen-Dining/zgbs/kitchen/ref=zg_bs_pg_2_kitchen?_encoding=UTF8&pg=2":
            '<a href="/z/dp/B0PAGE2001/ref=a">p</a><a href="/z/dp/B0ROOT0001/ref=dup">d</a>',
    })
    assert run.category_asins(f, "kitchen", subcats=6) == ["B0SUBC0001", "B0PAGE2001", "B0ROOT0001"]


def test_category_asins_goes_two_levels_down_and_reads_the_deepest_first():
    sub = "https://www.amazon.com/Best-Sellers-Kitchen-Dining-Bakeware/zgbs/kitchen/289668"
    grand = "https://www.amazon.com/Best-Sellers-Bakeware-Muffin-Pans/zgbs/kitchen/289675"
    f = FakeFetcher({
        amazon.category_url("kitchen"): ('<a href="/x/dp/B0ROOT0001/ref=a">r</a>'
                                         '<a href="/Best-Sellers-Kitchen-Dining-Bakeware/zgbs/kitchen/289668/ref=n">sub</a>'),
        sub: ('<a href="/y/dp/B0SUBC0001/ref=a">s</a>'
              '<a href="/Best-Sellers-Kitchen-Dining-Bakeware/zgbs/kitchen/289668/ref=self">me</a>'  # nav repeats the current node
              '<a href="/Best-Sellers-Bakeware-Muffin-Pans/zgbs/kitchen/289675/ref=n">grand</a>'),
        grand: '<a href="/z/dp/B0GRAND001/ref=a">g</a>',
    })
    assert run.category_asins(f, "kitchen", subcats=6, depth=2) == ["B0GRAND001", "B0SUBC0001", "B0ROOT0001"]
    assert f.calls.count(sub) == 1  # the node's own link in its nav is not re-fetched
    f2 = FakeFetcher(dict(f.pages))
    assert run.category_asins(f2, "kitchen", subcats=6, depth=1) == ["B0SUBC0001", "B0ROOT0001"]


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
        {"seller_id": "S1", "brand": "HydroJug", "business_name": "HYDROJUG LLC", "status": "candidate", "est_monthly_revenue": 95000, "country": "US"},
        {"seller_id": "S2", "brand": "Nowhere Brand", "business_name": None, "status": "candidate", "est_monthly_revenue": 5000, "country": "US"},
        {"seller_id": "S3", "brand": "Unknown Land", "business_name": None, "status": "candidate", "est_monthly_revenue": 80000, "country": None},
    ]
    f = FakeFetcher({"https://hydrojug.com/": '<html><title>HydroJug</title><a href="mailto:hello@hydrojug.com">x</a></html>'})
    counts = run.enrich(db, f, limit=10, resolver=lambda d: True, log=quiet)
    assert counts == {"enriched": 1, "no_website": 1}  # S3 has no country yet and is left alone
    s1, s2, s3 = db.store["harvest_sellers"]
    assert s3["status"] == "candidate"
    assert s1["status"] == "enriched" and s1["email"] == "hello@hydrojug.com" and s1["website"] == "https://hydrojug.com/"
    assert s2["status"] == "no_website"


def _enriched_rows():
    return [
        {"seller_id": "A", "brand": "A Brand", "status": "enriched", "email": "hello@a.com", "est_monthly_revenue": 50000,
         "website": "https://a.com/", "business_name": "A LLC", "email_confidence": "published", "country": "US"},
        {"seller_id": "B", "brand": "B Brand", "status": "enriched", "email": "hello@b.com", "est_monthly_revenue": 1000, "country": "US"},
        {"seller_id": "C", "brand": "C Brand", "status": "enriched", "email": "hagen.hds@gmail.com", "est_monthly_revenue": 20000, "country": "US"},
        {"seller_id": "D", "brand": "D Brand", "status": "candidate", "email": None, "est_monthly_revenue": 90000, "country": "US"},
        {"seller_id": "E", "brand": "E Brand", "status": "enriched", "email": "hello@e.com", "est_monthly_revenue": 70000, "country": None},
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
    assert by_id["E"]["status"] == "enriched"  # no country on file (profile unread): waits, never emailed blind
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
    assert "5 sellers on file" in text and "enriched 4" in text and "A Brand" in text
    plist = run.launchd_plist(Path("/x/engine"), "/opt/homebrew/bin/uv", (6, 18), 10)
    assert plist["ProgramArguments"] == ["/opt/homebrew/bin/uv", "run", "hubricon", "harvest", "all"]
    assert plist["StartCalendarInterval"] == [{"Hour": 6, "Minute": 10}, {"Hour": 18, "Minute": 10}]
    assert plist["WorkingDirectory"] == "/x/engine" and plist["EnvironmentVariables"]["PYTHONUNBUFFERED"] == "1"


def test_page_budget_is_split_across_categories_and_unused_pages_roll_over(tmp_path):
    seen_budgets = []

    def fake_category(db, fetcher, slug, budget, subcats, depth, cache, log):
        seen_budgets.append((slug, budget))
        used = 10 if slug == "kitchen" else budget  # kitchen has few listings; the rest are deep
        return {"products_fetched": used, "products_cached": 0, "sellers_seen": 0, "sellers_new": 0,
                "statuses": {}, "blocked": False}

    original = run._crawl_category
    run._crawl_category = fake_category
    try:
        s = run.crawl(FakeDB(), FakeFetcher({}), ["kitchen", "beauty", "hpc"], max_products=90,
                      cache=Cache(tmp_path), log=quiet)
    finally:
        run._crawl_category = original
    assert seen_budgets == [("kitchen", 30), ("beauty", 50), ("hpc", 30)]  # 20 unused pages rolled once
    assert s["products_fetched"] == 90


def test_category_asins_stops_reading_lists_once_it_has_enough():
    root = ('<a href="/Best-Sellers-A/zgbs/kitchen/1/ref=n">a</a><a href="/Best-Sellers-B/zgbs/kitchen/2/ref=n">b</a>'
            '<a href="/Best-Sellers-C/zgbs/kitchen/3/ref=n">c</a>')
    lists = {f"https://www.amazon.com/Best-Sellers-{n}/zgbs/kitchen/{i}":
             "".join(f'<a href="/x/dp/B0{n}{j:07d}/ref=a">p</a>' for j in range(31))
             for i, n in ((1, "A"), (2, "B"), (3, "C"))}
    f = FakeFetcher({amazon.category_url("kitchen"): root, **lists})
    got = run.category_asins(f, "kitchen", subcats=6, depth=2, enough=40)
    assert len(got) == 62 and sum(1 for c in f.calls if "/zgbs/kitchen/" in c) == 2  # two lists, not three


def test_push_records_instantly_counts_and_drops_a_rejected_batch():
    db, api = FakeDB(), FakeApi()
    db.store["harvest_sellers"] = _enriched_rows()
    run.push(db, api, limit=40, log=quiet)
    a = next(r for r in db.store["harvest_sellers"] if r["seller_id"] == "A")
    assert a["status"] == "pushed" and "leads_uploaded 1" in a["notes"] and a["instantly_lead_id"] == "lead-0"
    assert db.store["funnel_events"][-1]["payload"]["instantly"][0]["leads_uploaded"] == 1
    # a batch Instantly refuses outright (all invalid) is parked, not retried every hour
    db2, api2 = FakeDB(), FakeApi()
    api2.reply = {"status": "success", "total_sent": 1, "leads_uploaded": 0, "invalid_email_count": 1, "skipped_count": 0}
    db2.store["harvest_sellers"] = _enriched_rows()
    assert run.push(db2, api2, limit=40, log=quiet) == 0
    a2 = next(r for r in db2.store["harvest_sellers"] if r["seller_id"] == "A")
    assert a2["status"] == "no_email" and "invalid_email_count 1" in a2["notes"]


def test_one_harvest_at_a_time(tmp_path):
    lock = tmp_path / "run.lock"
    lock.write_text("999999")  # a pid that is not running
    assert run.acquire_lock(lock) == lock and lock.read_text() == str(run.os.getpid())
    assert run.acquire_lock(lock) is None  # this process holds it
    assert run.run_all(FakeDB(), FakeFetcher({}), lock=lock, log=quiet) == {"skipped": "locked"}
    lock.unlink()
    out = run.run_all(FakeDB(), FakeFetcher({}), categories=["kitchen"], max_products=1, lock=lock, log=quiet)
    assert "crawl" in out and not lock.exists()  # released even though nothing was found


# -- requalify / prune ---------------------------------------------------------------

def _pushed_rows():
    return [
        {"seller_id": "G", "seller_name": "Gorilla Grip", "brand": "GORILLA GRIP", "brands": ["GORILLA GRIP"], "asins": [],
         "reviews_max": 0, "status": "pushed", "email": "hello@gorillagrip.com", "instantly_lead_id": "lead-g",
         "est_monthly_revenue": 236000, "country": "US", "notes": "brand matches seller"},
        {"seller_id": "K", "seller_name": "KITESSENSU", "brand": "KITESSENSU", "brands": ["KITESSENSU"], "asins": [],
         "reviews_max": 0, "status": "pushed", "email": "support@kitessensu.com", "instantly_lead_id": "lead-k",
         "est_monthly_revenue": 26000, "country": "US", "notes": "brand matches seller"},
    ]


def test_requalify_rereads_profiles_and_demotes_giants(tmp_path):
    db = FakeDB()
    db.store["harvest_sellers"] = _pushed_rows()
    f = FakeFetcher({amazon.seller_url("G"): seller_page("Gorilla Grip", "Hillspoint Industries, LLC", r12="8,703", life="211,667"),
                     amazon.seller_url("K"): seller_page("KITESSENSU", "KITESSENSU LLC", r12="208", life="836")})
    db.store["harvest_sellers"].append({"seller_id": "V", "seller_name": "Bella Vita", "brand": "Bella Vita", "brands": ["Bella Vita"],
                                        "asins": [], "reviews_max": 0, "status": "enriched", "email": "bellavita@akacompany.com.vn",
                                        "est_monthly_revenue": 89000, "country": "US"})
    f.pages[amazon.seller_url("V")] = seller_page("Bella Vita", "BELLA VITA INC", r12="3,057", life="5,266")
    db.store["harvest_sellers"].append({"seller_id": "W", "seller_name": "-Bookworm-", "brand": "-Bookworm-", "brands": ["-Bookworm-"],
                                        "asins": [], "reviews_max": 0, "status": "candidate", "source": "wayback",
                                        "est_monthly_revenue": 1000, "country": "US"})
    f.pages[amazon.seller_url("W")] = seller_page("-Bookworm-", "Page Turners LLC", r12="3,177", life="21,535")
    counts = run.requalify(db, f, limit=10, cache=Cache(tmp_path), log=quiet)
    assert counts == {"skip_size": 1, "kept": 1, "skip_non_us": 1, "skip_reseller": 1}
    assert db.store["harvest_sellers"][3]["status"] == "skip_reseller"  # a wayback row keeps the profile-only rules
    assert db.store["harvest_sellers"][2]["status"] == "skip_non_us"  # a .vn inbox outranks the profile's "US"
    g, k = db.store["harvest_sellers"][:2]
    assert g["status"] == "skip_size" and g["ratings_12mo"] == 8703 and g["instantly_lead_id"] == "lead-g"  # prune needs the id
    assert k["status"] == "pushed" and k["ratings_12mo"] == 208
    assert Cache(tmp_path).get("seller", "G")["ratings_12mo"] == 8703  # the crawl's cache learns the counts too


def test_prune_deletes_list_and_campaign_leads_and_dqs_the_prospect():
    db, api = FakeDB(), FakeApi()
    rows = _pushed_rows()
    rows[0]["status"], rows[0]["notes"] = "skip_size", "requalified: 8,703 seller ratings"
    db.store["harvest_sellers"] = rows
    db.store["prospects"] = [{"id": "p1", "email": "hello@gorillagrip.com", "instantly_lead_id": "camp-g", "status": "queued"},
                             {"id": "p2", "email": "support@kitessensu.com", "instantly_lead_id": "camp-k", "status": "queued"}]
    assert run.prune(db, api, dry=True, log=quiet) == 1 and not getattr(api, "deleted", [])
    api.by_email = {"hello@gorillagrip.com": [{"id": "camp-g", "email": "hello@gorillagrip.com"}, {"id": "list-g2", "email": "hello@gorillagrip.com"}]}
    assert run.prune(db, api, log=quiet) == 1
    assert sorted(api.deleted) == ["camp-g", "lead-g", "list-g2"]  # stored ids plus whatever Instantly holds under the address; never KITESSENSU
    g = db.store["harvest_sellers"][0]
    assert g["instantly_lead_id"] is None and g["pushed_at"] is None and "removed from Instantly (3 lead object(s))" in g["notes"]
    assert db.store["prospects"][0]["status"] == "dq" and db.store["prospects"][1]["status"] == "queued"
    assert run.prune(db, api, log=quiet) == 0  # idempotent
    assert db.store["funnel_events"][-1]["note"].startswith("prune: 1 lead")


def test_prune_treats_an_already_deleted_lead_as_done():
    db, api = FakeDB(), FakeApi()
    rows = _pushed_rows()[:1]
    rows[0].update(status="skip_size", instantly_lead_id="gone")
    db.store["harvest_sellers"] = rows
    assert run.prune(db, api, log=quiet) == 1
    assert db.store["harvest_sellers"][0]["instantly_lead_id"] is None


def test_prune_finds_a_pushed_row_without_a_stored_id_by_its_address():
    db, api = FakeDB(), FakeApi()
    rows = _pushed_rows()[:2]
    rows[0].update(status="skip_non_us", instantly_lead_id=None, pushed_at=None)  # pushed_at was lost, address remains
    rows[1].update(status="skip_size", instantly_lead_id=None, pushed_at=None)    # never actually reached Instantly
    db.store["harvest_sellers"] = rows
    api.by_email = {"hello@gorillagrip.com": [{"id": "found-1", "email": "hello@gorillagrip.com"}]}
    assert run.prune(db, api, log=quiet) == 1 and api.deleted == ["found-1"]
    g, k = db.store["harvest_sellers"]
    assert "removed from Instantly (1 lead object(s))" in g["notes"]
    assert k["notes"].endswith("not in Instantly")
    assert run.prune(db, api, log=quiet) == 0 and api.deleted == ["found-1"]  # both are settled; no lookups repeat


# -- wayback: archived seller profiles ----------------------------------------------------

from hubricon_engine.harvest import wayback  # noqa: E402

CDX_TEXT = """https://www.amazon.com/sp?seller=A1AAAAAAAAAAAA 20220101000000 82000
https://www.amazon.com/sp?seller=A1AAAAAAAAAAAA&sshmPath=shipping-rates 20250301000000 90000
https://www.amazon.com/sp?seller=A1AAAAAAAAAAAA 20240601000000 91000
https://www.amazon.com/sp?seller=A2BBBBBBBBBBBB 20250215032444 2053
https://www.amazon.com/sp?seller=A3CCCCCCCCCCCC 20190101000000 88000
https://www.amazon.com/sp?seller=a4dddddddddddd 20230505050505 77000
garbage line
"""


def test_parse_cdx_keeps_the_newest_plain_capture_per_seller_and_drops_stubs():
    caps = wayback.parse_cdx(CDX_TEXT)
    assert caps["A1AAAAAAAAAAAA"] == ("20240601000000", "https://www.amazon.com/sp?seller=A1AAAAAAAAAAAA")  # plain beats the newer tab
    assert "A2BBBBBBBBBBBB" not in caps  # 2 KB = Amazon's captcha stub
    assert "A3CCCCCCCCCCCC" not in caps  # pre-2021: no business address on the page
    assert caps["A4DDDDDDDDDDDD"][0] == "20230505050505"


def _snap(caps, sid):
    ts, url = caps[sid]
    return wayback.SNAPSHOT.format(ts=ts, url=url)


def test_wayback_crawl_writes_profile_only_rows_sized_by_feedback():
    db = FakeDB()
    db.store["harvest_sellers"] = [{"seller_id": "A0ONFILE00000", "status": "pushed"}]
    caps = {
        "A0ONFILE00000": ("20250101000000", "https://www.amazon.com/sp?seller=A0ONFILE00000"),   # already on file: untouched
        "A1HYDRO000000": ("20240601000000", "https://www.amazon.com/sp?seller=A1HYDRO000000"),   # US, in band
        "A2GIANT000000": ("20240701000000", "https://www.amazon.com/sp?seller=A2GIANT000000"),   # US, too big
        "A3CHINA000000": ("20240801000000", "https://www.amazon.com/sp?seller=A3CHINA000000"),   # offshore
        "A4STUB0000000": ("20240901000000", "https://www.amazon.com/sp?seller=A4STUB0000000"),   # captcha capture
        "A5NOFEEDBACK0": ("20241001000000", "https://www.amazon.com/sp?seller=A5NOFEEDBACK0"),   # no ratings line
    }
    pages = {
        _snap(caps, "A1HYDRO000000"): seller_page(),
        _snap(caps, "A2GIANT000000"): seller_page("Mega Store", "MEGA CORP LLC", r12="12,000", life="300,000"),
        _snap(caps, "A3CHINA000000"): seller_page("Foo Direct", "Shenzhen Foo Technology Co., Ltd", country="CN"),
        _snap(caps, "A4STUB0000000"): "<html>Type the characters you see in this image</html>",
        _snap(caps, "A5NOFEEDBACK0"): SELLER_PAGE.split("<a class=\"a-link-normal feedback")[0] + "</body></html>",
    }
    fake = FakeFetcher(pages)
    s = wayback.crawl(db, caps, limit=10, workers=2, fetcher_factory=lambda: fake, log=quiet)
    assert s["read"] == 4 and s["unreadable"] == 1
    assert not any("A0ONFILE00000" in c for c in fake.calls)
    by_id = {r["seller_id"]: r for r in db.store["harvest_sellers"]}
    hydro = by_id["A1HYDRO000000"]
    assert hydro["status"] == "candidate" and hydro["source"] == "wayback" and hydro["brand"] == "HydroJug"
    assert hydro["business_name"] == "HYDROJUG LLC" and hydro["country"] == "US" and hydro["ratings_12mo"] == 1139
    assert hydro["est_monthly_revenue"] == amazon.revenue_from_ratings(1139) and "archived profile 20240601" in hydro["notes"]
    assert by_id["A2GIANT000000"]["status"] == "skip_size"
    assert by_id["A3CHINA000000"]["status"] == "skip_non_us"
    assert by_id["A5NOFEEDBACK0"]["status"] == "skip_size" and "no feedback" in by_id["A5NOFEEDBACK0"]["notes"]
    assert db.store["funnel_events"][-1]["note"].startswith("wayback: 4 archived profiles")
    # the enrich step picks the candidate up like any live-crawled row
    f2 = FakeFetcher({"https://hydrojug.com/": '<html><title>HydroJug</title><a href="mailto:hello@hydrojug.com">x</a></html>'})
    assert run.enrich(db, f2, limit=10, resolver=lambda d: True, log=quiet) == {"enriched": 1}


def test_profile_only_rows_keep_brands_and_drop_resellers_individuals_and_handles():
    def verdict(name, business, r12=900):
        prof = {"seller_name": name, "business_name": business, "country": "US", "ratings_12mo": r12, "ratings_lifetime": 5000}
        return wayback.classify_profile("S", prof)[0]
    assert verdict("HydroJug", "HYDROJUG LLC") == "candidate"
    assert verdict("Tens Towels", "Tens Home") == "candidate"          # brand-ish two-word legal name, not a person
    assert verdict("Blue Vase Books", "Blue Vase Markeplace LLC") == "skip_reseller"
    assert verdict("-Bookworm-", "Page Turners LLC") == "skip_reseller"   # punctuation around the word
    assert verdict("UPSW Auto Parts", "Time Auto Parts Inc.") == "skip_reseller"
    assert verdict("SSA Cards", "Super Special Awesome Cards") == "skip_reseller"
    assert verdict("LuxuryMerchandise", "Lorenzo Juan Ramos Jr") == "skip_reseller"   # individual
    assert verdict("webdelicollc", "Aruna sampath Wijesinghe") == "skip_reseller"
    assert verdict("greatgirls321", "GREAT GIRLS LLC") == "skip_reseller"            # handle
    assert verdict("KITESSENSU", "KITESSENSU LLC", r12=150) == "skip_size"           # under the profile-only floor
    assert verdict("KITESSENSU", "KITESSENSU LLC", r12=None) == "skip_size"
    assert wayback.looks_like_a_person("sherry savoy") and not wayback.looks_like_a_person("Gerbi Direct, Inc.")
    assert not wayback.looks_like_a_person("Hillspoint Industries")


def test_load_captures_downloads_once_and_reuses_the_file(tmp_path):
    f = FakeFetcher({wayback.CDX + "&showNumPages=true": "2\n",
                     wayback.CDX + "&page=0": CDX_TEXT.splitlines()[0] + "\n",
                     wayback.CDX + "&page=1": CDX_TEXT.splitlines()[5] + "\n"})
    path = tmp_path / "sellers.cdx"
    caps = wayback.load_captures(f, path, log=quiet)
    assert set(caps) == {"A1AAAAAAAAAAAA", "A4DDDDDDDDDDDD"} and path.exists()
    f2 = FakeFetcher({})
    assert wayback.load_captures(f2, path, log=quiet) == caps and not f2.calls


# -- owners ---------------------------------------------------------------------------

def test_owners_asks_supersearch_for_the_founder_at_each_pushed_domain_once():
    db, api = FakeDB(), FakeApi()
    db.store["harvest_sellers"] = [
        {"seller_id": "A", "brand": "A Brand", "status": "pushed", "website": "https://www.abrand.com/", "first_name": None},
        {"seller_id": "B", "brand": "B Brand", "status": "enriched", "website": "https://bbrand.com/", "first_name": None},
        {"seller_id": "C", "brand": "C Brand", "status": "pushed", "website": "https://cbrand.com/", "first_name": "Cara"},  # named already
        {"seller_id": "D", "brand": "D Brand", "status": "candidate", "website": None, "first_name": None},
    ]
    assert run.owners(db, api, dry=True, log=quiet, today="2026-09-03") == 2 and not hasattr(api, "enriched")
    assert run.owners(db, api, log=quiet, today="2026-09-03") == 2
    list_id, filters, limit, name = api.enriched
    assert list_id == "L1" and api.created == [run.OWNERS_LIST_NAME] and "hubricon" in run.OWNERS_LIST_NAME.lower()
    assert filters["domains"] == ["abrand.com", "bbrand.com"] and "Founder" in filters["title"]["include"] and limit == 2
    by_id = {r["seller_id"]: r for r in db.store["harvest_sellers"]}
    assert by_id["A"]["person_source"] == "supersearch:requested" and by_id["C"].get("person_source") is None
    assert db.store["operator_state"][0]["value"]["count"] == 2
    assert run.owners(db, api, log=quiet, today="2026-09-03") == 0  # nothing left to ask
    db.store["harvest_sellers"].append({"seller_id": "E", "brand": "E", "status": "pushed", "website": "https://e.com/", "first_name": None})
    assert run.owners(db, api, daily=2, log=quiet, today="2026-09-03") == 0  # the daily cap holds
    assert run.owners(db, api, daily=2, log=quiet, today="2026-09-04") == 1  # a new day
    assert db.store["funnel_events"][-1]["note"].startswith("owners: asked SuperSearch")


# -- listings for profile-only sellers -----------------------------------------------

def test_listings_pairs_an_archived_seller_with_its_live_products(tmp_path):
    db = FakeDB()
    db.store["harvest_sellers"] = [
        {"seller_id": "AXSP4G6IQFYIQ", "seller_name": "HydroJug", "brand": "HydroJug", "brands": ["HydroJug"], "asins": [],
         "status": "pushed", "country": "US", "source": "wayback", "est_monthly_revenue": 50000, "notes": "archived profile"},
        {"seller_id": "AOTHER000000", "seller_name": "Other", "brand": "Other", "brands": ["Other"], "asins": [{"asin": "X"}],
         "status": "pushed", "country": "US", "source": "bestsellers", "est_monthly_revenue": 90000},
    ]
    storefront = '<html><a href="/HydroJug-Traveler/dp/B0CQVWT2NH/ref=sr_1_1">a</a><a href="/Echo/dp/B09B8V1LZ3/ref=sr_1_2">b</a></html>'
    f = FakeFetcher({run.storefront_url("AXSP4G6IQFYIQ"): storefront,
                     f"{amazon.BASE}/dp/B0CQVWT2NH": PRODUCT_3P, f"{amazon.BASE}/dp/B09B8V1LZ3": PRODUCT_AMZ})
    counts = run.listings(db, f, limit=10, per_seller=2, cache=Cache(tmp_path), log=quiet)
    assert counts == {"paired": 1}
    row = db.store["harvest_sellers"][0]
    assert row["asins"][0]["asin"] == "B0CQVWT2NH" and row["top_bsr"] == 400 and row["top_category"] == "Kitchen & Dining"
    assert row["brand"] == "HydroJug" and "1 live listing(s)" in row["notes"]  # the Echo is Amazon's own offer, not this seller's
    assert {r["asin"] for r in db.store["harvest_products"]} == {"B0CQVWT2NH"}
    assert not any("AOTHER" in c for c in f.calls)  # rows that already carry a listing are left alone
    assert run.listings(db, FakeFetcher({}), limit=10, cache=Cache(tmp_path), log=quiet) == {}
