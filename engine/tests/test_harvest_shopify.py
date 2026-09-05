"""The Shopify half of the harvest: the JSON every store publishes, parsed.

Fixtures are shaped like the real payloads (/meta.json, /products.json?limit=250,
a product page with a review app's JSON-LD, the /policies/contact-information
page Shopify makes every store publish). The doubles are the ones the Amazon
tests use. No network anywhere in here.
"""

import json

from hubricon_engine import outreach
from hubricon_engine.harvest import enrich, run, shopify
from hubricon_engine.harvest.fetch import Cache

from test_harvest import FakeDB, FakeFetcher, quiet, seller_page  # noqa: F401

# -- fixtures modeled on the live payloads (2026-09-04) --------------------------

META_JSON = json.dumps({
    "name": "Riverbend Goods", "city": "Burlington", "province": "Vermont", "country": "US",
    "currency": "USD", "domain": "riverbendgoods.com",
    "myshopify_domain": "riverbend-goods.myshopify.com",
    "description": "Waxed canvas bags, made in Vermont.", "published_products_count": 8,
    "money_format": "${{amount}}",
})

META_CA = json.dumps({"name": "Maple Mercantile", "city": "Toronto", "province": "Ontario",
                      "country": "CA", "currency": "CAD", "domain": "maplemercantile.ca",
                      "myshopify_domain": "maple-mercantile.myshopify.com"})


def _product(pid, title, handle, vendor, ptype, created, variants):
    return {"id": pid, "title": title, "handle": handle, "vendor": vendor, "product_type": ptype,
            "created_at": created, "updated_at": "2026-08-01T10:00:00-04:00", "tags": ["canvas"],
            "variants": variants, "images": [{"src": f"https://cdn.shopify.com/{handle}.jpg"}]}


def _variant(vid, title, sku, price, grams):
    return {"id": vid, "title": title, "sku": sku, "price": price, "grams": grams,
            "available": True, "compare_at_price": None}


PRODUCTS_JSON = json.dumps({"products": [
    _product(1, "Harbor Tote", "harbor-tote", "Riverbend Goods", "Bags", "2021-03-08T09:12:44-05:00",
             [_variant(11, "Default Title", "RB-HT", "48.00", 510)]),
    _product(2, "Cedar Caddy", "cedar-caddy", "Riverbend Goods", "Bags", "2022-06-10T09:00:00-04:00",
             [_variant(21, "Default Title", "RB-CC", "32.00", 900)]),
    # two variants: the cheapest is the price a first order is likeliest to pay,
    # the first variant carries the shipping weight
    _product(3, "Harbor Mug", "harbor-mug", "Riverbend Goods", "Drinkware", "2023-01-05T09:00:00-05:00",
             [_variant(31, "12 oz", "RB-MG-12", "26.00", 340), _variant(32, "8 oz", "RB-MG-8", "22.00", 300)]),
    _product(4, "Guest Candle", "guest-candle", "Northfield Candle Co", "Home", "2023-03-03T09:00:00-05:00",
             [_variant(41, "Default Title", "NC-GC", "18.00", 0)]),  # grams 0 = never entered, not weightless
    _product(5, "Field Apron", "field-apron", "Riverbend Goods", "Apparel", "2023-05-01T09:00:00-04:00",
             [_variant(51, "Default Title", "RB-FA", "58.00", 620)]),
    _product(6, "Rope Leash", "rope-leash", "Riverbend Goods", "Pet", "2024-02-11T09:00:00-05:00",
             [_variant(61, "Default Title", "RB-RL", "34.00", 210)]),
    _product(7, "Trail Pouch", "trail-pouch", "Riverbend Goods", "Bags", "2024-09-19T09:00:00-04:00",
             [_variant(71, "Default Title", "RB-TP", "24.00", 130)]),
    _product(8, "Balsam Candle", "balsam-candle", "Northfield Candle Co", "Home", "2025-01-20T09:00:00-05:00",
             [_variant(81, "Default Title", "NC-BC", "26.00", 400)]),
]})

# Judge.me: two JSON-LD blocks, the count quoted with a thousands separator.
PRODUCT_PAGE_REVIEWS = """<html><head><title>Harbor Tote &mdash; Riverbend Goods</title>
<script type="application/ld+json">{"@context":"https://schema.org/","@type":"Organization",
 "name":"Riverbend Goods","url":"https://riverbendgoods.com"}</script>
<script type="application/ld+json">{"@context":"https://schema.org/","@type":"Product",
 "name":"Harbor Tote","sku":"RB-HT","offers":{"@type":"Offer","price":"48.00","priceCurrency":"USD"},
 "aggregateRating":{"@type":"AggregateRating","ratingValue":"4.8","reviewCount":"1,204"}}</script>
</head><body><div class="jdgm-widget jdgm-rev-widg" data-id="1"></div></body></html>"""

# Loox: one block, the count as a bare number.
PRODUCT_PAGE_BARE = """<html><head><title>Cedar Caddy</title>
<script type="application/ld+json">{"@type":"Product","name":"Cedar Caddy",
 "aggregateRating":{"@type":"AggregateRating","ratingValue":4.6,"reviewCount":96}}</script>
</head><body><script src="https://loox.io/widget/loox.js"></script></body></html>"""

# A product nobody has reviewed yet, and no review app on the page at all.
PRODUCT_PAGE_NO_REVIEWS = """<html><head><title>Harbor Mug</title>
<script type="application/ld+json">{"@type":"Product","name":"Harbor Mug",
 "offers":{"@type":"Offer","price":"22.00"}}</script></head><body>Harbor Mug</body></html>"""

CONTACT_POLICY = """<html><head><title>Contact information</title></head><body><main>
<h1>Contact information</h1>
<p>Trade name: Riverbend Goods LLC</p>
<p>Riverbend Goods, 412 Harbor View Rd, Suite 3, Burlington, VT 05401, United States</p>
<p>Phone number: +1 802-555-0134</p>
<p>Email: <a href="mailto:hello@riverbendgoods.com">hello@riverbendgoods.com</a></p>
<p>Founded by Nora Fielding in 2021, we sew every bag in Vermont.</p>
</main></body></html>"""

PASSWORD_PAGE = """<html><head><title>Riverbend Goods &mdash; Opening Soon</title></head><body>
<h1>Opening soon</h1><form method="post" action="/password">
<input type="password" name="password" placeholder="Enter store password"></form></body></html>"""

CDX_TEXT = """https://riverbend-goods.myshopify.com/ 20260701000000
https://admin.myshopify.com/ 20260801000000
https://riverbend-goods.myshopify.com/ 20250101000000
https://cdn.myshopify.com/ 20260101000000
https://shop.myshopify.com/ 20260101000000
https://northfield-candle.myshopify.com/ 20260801120000
https://a.b.myshopify.com/ 20260801000000
https://www.myshopify.com/ 20260101000000
https://big-timber-supply.myshopify.com 20240401000000
garbage line
"""


class StoreFetcher(FakeFetcher):
    """FakeFetcher plus the sleep() the crawl uses to pace itself between stores."""

    def __init__(self, pages):
        super().__init__(pages)
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)


def store_pages(**extra):
    # The catalogue and product pages come off the myshopify host (always the
    # classic storefront); the contact pages come off the brand's own domain.
    return {
        "https://riverbend-goods.myshopify.com/meta.json": META_JSON,
        "https://riverbend-goods.myshopify.com/products.json?limit=250": PRODUCTS_JSON,
        "https://riverbend-goods.myshopify.com/products/harbor-tote": PRODUCT_PAGE_REVIEWS,
        "https://riverbend-goods.myshopify.com/products/cedar-caddy": PRODUCT_PAGE_BARE,
        "https://riverbend-goods.myshopify.com/products/harbor-mug": PRODUCT_PAGE_NO_REVIEWS,
        "https://riverbendgoods.com/policies/contact-information": CONTACT_POLICY,
        **extra,
    }


# Chrome's JSON viewer: --dump-dom hands back the DOM, not the bytes, so the
# payload arrives inside a <pre> with its entities escaped. Observed against
# the live endpoint on 2026-09-04.
CHROME_WRAPPED = ('<html><head><meta name="color-scheme" content="light dark"><meta charset="utf-8">'
                  '</head><body><pre style="white-space:pre-wrap">'
                  '{&quot;name&quot;:&quot;Riverbend Goods&quot;,&quot;country&quot;:&quot;US&quot;,'
                  '&quot;currency&quot;:&quot;USD&quot;,&quot;domain&quot;:&quot;riverbendgoods.com&quot;}'
                  '</pre></body></html>')

# A headless storefront (Hydrogen/Oxygen) serves its React app at the custom
# domain, so /products.json there is HTML. thehydrojug.com did exactly this.
HEADLESS_APP = ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
                '<link rel="stylesheet" href="https://cdn.shopify.com/oxygen-v2/assets/app.css">'
                '</head><body><div id="root"></div></body></html>')


# -- discovery ---------------------------------------------------------------------

def test_json_arrives_bare_or_inside_chromes_viewer():
    assert shopify.parse_meta(META_JSON)["name"] == "Riverbend Goods"
    wrapped = shopify.parse_meta(CHROME_WRAPPED)
    assert wrapped["name"] == "Riverbend Goods" and wrapped["country"] == "US"
    assert wrapped["domain"] == "riverbendgoods.com"
    # a store's own HTML is not a payload, however it arrives
    assert shopify.parse_meta(PASSWORD_PAGE) is None
    assert shopify.parse_meta(HEADLESS_APP) is None
    assert shopify.parse_products(HEADLESS_APP) == []
    assert shopify.json_payload(None) is None and shopify.json_payload("nonsense") is None
    assert shopify.json_payload("<pre>not json</pre>") is None


def test_the_catalog_is_read_from_the_myshopify_host_with_the_custom_domain_as_fallback():
    # The myshopify host is always the classic storefront; a headless store's
    # custom domain answers /products.json with its React app.
    pages = store_pages()
    del pages["https://riverbend-goods.myshopify.com/products.json?limit=250"]
    pages["https://riverbend-goods.myshopify.com/products.json?limit=250"] = HEADLESS_APP
    pages["https://riverbendgoods.com/products.json?limit=250"] = PRODUCTS_JSON
    f = StoreFetcher(pages)
    out = shopify.read_store(f, "riverbend-goods", resolver=lambda d: True)
    assert len(out["products"]) == 8              # the fallback found the catalogue
    assert out["status"] == "enriched"
    # the myshopify host is tried first, the brand's own domain only after
    catalog = [c for c in f.calls if "products.json" in c]
    assert catalog[0].startswith("https://riverbend-goods.myshopify.com")
    assert catalog[1].startswith("https://riverbendgoods.com")


def test_the_checkout_host_is_never_the_storefront():
    # hydrojug.myshopify.com reports its primary domain as checkout.thehydrojug.com;
    # the row's website and the contact pages must use the brand's own host.
    assert shopify.store_domain("hydrojug", {"domain": "checkout.thehydrojug.com"}) == "thehydrojug.com"
    assert shopify.store_domain("x", {"domain": "www.riverbendgoods.com"}) == "www.riverbendgoods.com"
    assert shopify.store_domain("x", {}) == "x.myshopify.com"
    assert shopify.store_domain("x", None) == "x.myshopify.com"


def test_parse_cdx_keeps_store_handles_newest_first_and_drops_shopifys_own_hosts():
    handles = shopify.parse_cdx(CDX_TEXT)
    assert handles == ["northfield-candle", "riverbend-goods", "big-timber-supply"]
    for own in ("admin", "cdn", "shop", "www"):
        assert own not in handles          # Shopify's own subdomains are not stores
    assert not any("." in h for h in handles)  # a.b.myshopify.com is a sub-subdomain, not a store
    assert shopify.parse_cdx("") == []


def test_load_handles_downloads_once_and_reuses_the_file(tmp_path):
    lines = CDX_TEXT.splitlines()
    f = FakeFetcher({shopify.CDX_COUNT: "2\n",
                     shopify.CDX + "&page=0": lines[0] + "\n",
                     shopify.CDX + "&page=1": lines[5] + "\n"})
    path = tmp_path / "shopify-stores.cdx"
    handles = shopify.load_handles(f, path, log=quiet)
    assert handles == ["northfield-candle", "riverbend-goods"] and path.exists()
    f2 = FakeFetcher({})
    assert shopify.load_handles(f2, path, log=quiet) == handles and not f2.calls
    assert "myshopify.com" in shopify.CDX and "%5E" in shopify.CDX  # the regex filter is URL-encoded
    # the count is asked for on its own: the live API answers "- -" instead of
    # a number when fl= or collapse= ride along (checked 2026-09-04)
    assert "showNumPages" in shopify.CDX_COUNT
    assert "fl=" not in shopify.CDX_COUNT and "collapse=" not in shopify.CDX_COUNT


def test_index_pages_are_sampled_across_the_whole_listing_not_swept_from_the_front():
    # The CDX index is sorted by URL key, so its pages run alphabetically: page 0
    # is "0-5-yas-kiz-…", page 200 is "0c2e44-cb". Reading the first N pages of
    # 42,897 returns only handles starting with a digit — Shopify's own dev
    # stores. Spreading the same N pages over the index samples the alphabet.
    picks = shopify.sample_pages(42897, 12)
    assert picks[0] == 0 and len(picks) == 12
    assert picks[-1] > 39000                      # the far end of the alphabet is reached
    assert picks == sorted(set(picks))            # no page fetched twice
    assert max(b - a for a, b in zip(picks, picks[1:])) < 42897 // 8  # evenly spread
    # a listing smaller than the budget is read whole, and nothing is asked of an empty one
    assert shopify.sample_pages(3, 12) == [0, 1, 2]
    assert shopify.sample_pages(0, 12) == [] and shopify.sample_pages(42897, 0) == []


def test_generated_dev_store_handles_are_dropped_and_real_names_survive():
    # Sampled live from the archive's listing on 2026-09-04: the left column is
    # what Shopify names an unclaimed development store, the right is a shop.
    for blob in ("0003bd-ca", "0c2e44-cb", "00006e", "000235", "00dze5-yu",
                 "00ipv9-52", "ctq2ua-gn", "00xb5e-17", "0c32da"):
        assert shopify.looks_like_a_dev_store(blob), blob
    for name in ("sundrashop", "ruggit-collars", "ctrlgear", "metropolisvintage", "hamarushop",
                 "rugitdown", "0-waste-eco", "hydrojug", "riverbend-goods", "hamade-law",
                 "metrolix1", "ctpremierwpc-1081", "tens-towels"):
        assert not shopify.looks_like_a_dev_store(name), name
    # and the listing itself drops them
    assert shopify.parse_cdx("https://0c2e44-cb.myshopify.com/ 20260801000000\n"
                             "https://ruggit-collars.myshopify.com/ 20260801000000\n") == ["ruggit-collars"]


# -- the three public payloads ------------------------------------------------------

def test_meta_json_is_the_shopify_seller_profile():
    m = shopify.parse_meta(META_JSON)
    assert m["name"] == "Riverbend Goods" and m["domain"] == "riverbendgoods.com"
    assert (m["city"], m["province"], m["country"], m["currency"]) == ("Burlington", "Vermont", "US", "USD")
    assert m["myshopify_domain"] == "riverbend-goods.myshopify.com" and m["published_products_count"] == 8
    assert shopify.parse_meta(PASSWORD_PAGE) is None and shopify.parse_meta(None) is None
    assert shopify.parse_meta('{"published_products_count": 3}') is None  # no name = no shop record
    assert shopify.looks_password_page(PASSWORD_PAGE) and not shopify.looks_password_page(META_JSON)
    assert shopify.store_domain("riverbend-goods", m) == "riverbendgoods.com"
    assert shopify.store_domain("riverbend-goods", None) == "riverbend-goods.myshopify.com"


def test_products_json_gives_vendors_prices_and_shipping_weights():
    ps = shopify.parse_products(PRODUCTS_JSON)
    assert len(ps) == 8 and [p["handle"] for p in ps][:2] == ["harbor-tote", "cedar-caddy"]
    tote = ps[0]
    assert tote["vendor"] == "Riverbend Goods" and tote["product_type"] == "Bags" and tote["sku"] == "RB-HT"
    assert tote["price"] == 48.0 and tote["weight_oz"] == 17.99          # 510 g
    assert ps[2]["price"] == 22.0 and ps[2]["weight_oz"] == 11.993       # cheapest variant, first variant's grams
    assert ps[3]["weight_oz"] is None                                     # grams 0 = unknown, not weightless
    v = shopify.vendor_profile(ps)
    assert v["dominant"] == "Riverbend Goods" and v["share"] == 0.75 and len(v["vendors"]) == 2
    assert v["category"] == "Bags"
    assert shopify.vendor_profile([])["dominant"] is None
    assert shopify.parse_products(PASSWORD_PAGE) == [] and shopify.parse_products(None) == []
    assert shopify.grams_to_oz(0) is None and shopify.grams_to_oz(None) is None


def test_review_count_reads_every_shape_the_apps_publish():
    assert shopify.review_count(PRODUCT_PAGE_REVIEWS) == 1204   # "1,204": quoted, with a separator
    assert shopify.review_count(PRODUCT_PAGE_BARE) == 96        # a bare number
    assert shopify.review_count(PRODUCT_PAGE_NO_REVIEWS) is None  # no aggregateRating: unknown, not zero
    assert shopify.review_count(None) is None
    assert shopify.rating_value(PRODUCT_PAGE_REVIEWS) == 4.8
    # the widget is on the page even when the count is rendered client-side
    assert shopify.has_reviews(PRODUCT_PAGE_REVIEWS) and shopify.has_reviews(PRODUCT_PAGE_BARE)
    assert not shopify.has_reviews(PRODUCT_PAGE_NO_REVIEWS)


def test_store_age_and_the_revenue_estimate_are_arithmetic_we_can_check():
    ps = shopify.parse_products(PRODUCTS_JSON)
    from datetime import datetime, timezone
    age = shopify.store_age_years(ps, now=datetime(2026, 3, 8, tzinfo=timezone.utc))
    assert abs(age - 5.0) < 0.01                       # oldest product published 2021-03-08
    assert shopify.store_age_years([]) == 0.5          # a store with no dates is treated as new
    # 1300 reviews over 3 sampled products, scaled to 8, at 50 orders a review and a $34 ASP,
    # over five years:  1300 × (8/3) × 50 × 34 / 5
    assert shopify.estimate_annual([1204, 96, None], 8, 34.0, 5.0) == 1178666.67
    assert shopify.estimate_annual([None, None, None], 8, 34.0, 5.0) is None   # unknown stays unknown
    assert shopify.estimate_annual([1204], 8, None, 5.0) is None               # no price, no estimate
    assert shopify.estimate_annual([1204, 96, None], 8, 34.0, 0.1) == \
        shopify.estimate_annual([1204, 96, None], 8, 34.0, 0.5)               # age is floored at half a year


# -- the hook ------------------------------------------------------------------------

def test_the_sub_pound_ounce_tiers_are_gone_and_cannot_be_quoted():
    """USPS collapsed the 4 / 8 / 12 / 15.99 oz tiers into one flat sub-pound
    rate at published Commercial prices on 2026-07-12.

    This test is the guard on a claim that used to be true and stopped being so.
    Every ounce-tier sentence the founder lane and the cold engine can compose
    is built from these edges, so an edge that no longer exists here cannot
    reach a stranger's inbox from anywhere.
    """
    for weight in (4.5, 8.5, 12.5, 15.9):
        assert shopify.shipping_cliff(weight) is None, \
            f"{weight} oz has no cheaper band to drop into: under a pound the rate is flat"
    assert shopify.MIN_HOOK_WEIGHT_OZ == 16.0


def test_shipping_cliff_edges_follow_the_carrier_rate_card():
    assert shopify.shipping_cliff(3.9) is None
    assert shopify.shipping_cliff(17.2) == (16, 1.2)      # over a pound: rounds up to the 2 lb rate
    assert shopify.shipping_cliff(33.0) == (32, 1.0)
    assert shopify.shipping_cliff(None) is None and shopify.shipping_cliff(0) is None


def test_the_band_names_account_for_the_round_up():
    # A parcel over a pound bills at two, so what a 17 oz product is really
    # choosing between is the 2 lb rate and the flat sub-pound rate — not the
    # 1 lb rate, which only an exactly-16.000 oz parcel ever pays. Naming the
    # 1 lb rate here would understate the saving by about half.
    assert shopify.band_names(16) == ("under a pound", "2 lb")
    assert shopify.band_names(32) == ("2 lb", "3 lb")


# -- classification --------------------------------------------------------------------

def _meta(**over):
    return {**shopify.parse_meta(META_JSON), **over}


def test_classification_keeps_us_private_label_and_names_every_skip():
    ps = shopify.parse_products(PRODUCTS_JSON)
    status, note = shopify.classify(_meta(), ps, est_annual=3_000_000)
    assert status == "candidate" and "Riverbend Goods" in note and "est. $3,000,000/yr" in note

    assert shopify.classify(shopify.parse_meta(META_CA), ps)[0] == "skip_non_us"
    ca = shopify.classify(shopify.parse_meta(META_CA), ps)[1]
    assert "CA" in ca and "CAD" in ca                       # both values are recorded
    assert shopify.classify(_meta(currency="GBP"), ps)[0] == "skip_non_us"

    assert shopify.classify(_meta(), [])[0] == "no_website"
    assert shopify.classify(_meta(), ps[:2])[0] == "skip_size"          # a catalog of two is a hobby
    assert "too small" in shopify.classify(_meta(), ps[:2])[1]
    big = [dict(p, handle=f"h{i}") for i in range(2001) for p in ps[:1]]
    assert shopify.classify(_meta(), big)[0] == "skip_size"             # a marketplace, not a brand

    # a boutique: many vendors, none of them the store's own
    boutique = [dict(ps[0], vendor=f"Vendor {i}", handle=f"v{i}") for i in range(6)]
    status, note = shopify.classify(_meta(name="Corner Shop Collective"), boutique)
    assert status == "skip_reseller" and "multi-brand" in note

    assert shopify.classify(_meta(name="Fellow Products"), ps)[0] == "skip_size"   # a household name
    assert shopify.classify(_meta(name="Bellavix"), ps)[0] == "skip_reseller"      # icp: an agency

    # the revenue band, and the rule that an unknown never disqualifies
    assert shopify.classify(_meta(), ps, est_annual=90_000_000)[0] == "skip_size"
    assert shopify.classify(_meta(), ps, est_annual=90_000)[0] == "skip_size"
    assert shopify.classify(_meta(), ps, est_annual=None)[0] == "candidate"
    assert "no review count" in shopify.classify(_meta(), ps, est_annual=None)[1]


def test_contact_pages_give_the_legal_name_the_address_and_the_person():
    assert shopify.parse_business_name(CONTACT_POLICY) == "Riverbend Goods LLC"
    addr = shopify.parse_us_address(CONTACT_POLICY)
    assert addr == {"address": "412 Harbor View Rd, Suite 3, Burlington, VT 05401",
                    "city": "Burlington", "state": "VT", "zip": "05401"}
    assert shopify.parse_us_address("Unit 4, Toronto, Ontario M5V 2T6") is None  # not US-shaped
    assert shopify.parse_business_name("<p>We are a small team.</p>") is None    # no entity, no legal name
    f = FakeFetcher({"https://riverbendgoods.com/policies/contact-information": CONTACT_POLICY})
    c = shopify.store_contact(f, "https://riverbendgoods.com/", "Riverbend Goods")
    assert c["status"] == "enriched" and c["email"] == "hello@riverbendgoods.com"
    assert c["email_confidence"] == "published" and (c["first_name"], c["last_name"]) == ("Nora", "Fielding")
    assert c["business_name"] == "Riverbend Goods LLC" and c["state"] == "VT"
    assert f.calls[0].endswith("/policies/contact-information")  # Shopify's own page is read first
    # no published address, but the domain takes mail: the pattern guess, flagged as one
    bare = FakeFetcher({"https://riverbendgoods.com/": "<html><title>Riverbend</title>no mail</html>"})
    p = shopify.store_contact(bare, "https://riverbendgoods.com/", "Riverbend Goods", resolver=lambda d: True)
    assert p["email"] == "hello@riverbendgoods.com" and p["email_confidence"] == "pattern"
    assert shopify.store_contact(bare, "https://riverbendgoods.com/", "R", resolver=lambda d: False)["status"] \
        == "candidate"


# -- the crawl --------------------------------------------------------------------------

def test_crawl_writes_a_shopify_seller_and_its_sampled_products():
    db = FakeDB()
    db.store["harvest_sellers"] = [{"seller_id": "onfile-store.myshopify.com", "status": "pushed"}]
    f = StoreFetcher(store_pages(**{
        "https://maple-mercantile.myshopify.com/meta.json": META_CA,
        "https://closed-store.myshopify.com/meta.json": PASSWORD_PAGE,
    }))
    s = shopify.crawl(db, f, ["riverbend-goods", "onfile-store", "maple-mercantile", "closed-store"],
                      limit=10, log=quiet, resolver=lambda d: True)
    assert s["read"] == 3 and s["statuses"] == {"enriched": 1, "skip_non_us": 1, "no_website": 1}
    assert not any("onfile-store" in c for c in f.calls)   # already on file, never fetched
    assert f.sleeps == [shopify.PAUSE_BETWEEN_STORES] * 2  # ~1 s between stores, none before the first

    by_id = {r["seller_id"]: r for r in db.store["harvest_sellers"]}
    row = by_id["riverbend-goods.myshopify.com"]
    assert row["platform"] == "shopify" and row["source"] == "shopify" and row["status"] == "enriched"
    assert row["seller_name"] == "Riverbend Goods" and row["brand"] == "Riverbend Goods"
    assert row["brands"] == ["Riverbend Goods", "Northfield Candle Co"]
    assert row["business_name"] == "Riverbend Goods LLC" and row["country"] == "US"
    assert (row["city"], row["state"]) == ("Burlington", "Vermont")
    assert row["address"] == "412 Harbor View Rd, Suite 3, Burlington, VT 05401"
    assert row["website"] == "https://riverbendgoods.com/"
    assert row["email"] == "hello@riverbendgoods.com" and row["email_confidence"] == "published"
    assert (row["first_name"], row["last_name"]) == ("Nora", "Fielding")
    assert [a["asin"] for a in row["asins"]] == ["harbor-tote", "cedar-caddy", "harbor-mug"]
    assert row["asins"][0]["reviews"] == 1204 and row["reviews_max"] == 1204
    assert row["top_category"] == "Bags" and row["top_bsr"] is None
    assert row["ratings_12mo"] is None and row["est_monthly_units"] is None
    assert row["est_monthly_revenue"] > 0
    assert "shopify store, 8 products, 2 vendors, est $" in row["notes"] and "/yr from reviews" in row["notes"]

    # the Canadian store cost one request; the closed one cost one and is not an error
    assert by_id["maple-mercantile.myshopify.com"]["status"] == "skip_non_us"
    assert by_id["maple-mercantile.myshopify.com"]["country"] == "CA"  # the country that disqualified it
    assert by_id["closed-store.myshopify.com"]["status"] == "no_website"
    assert "password-protected" in by_id["closed-store.myshopify.com"]["notes"]
    assert not any("maple-mercantile.myshopify.com/products" in c for c in f.calls)

    # The whole catalogue is kept, not the three products we also fetched HTML
    # pages for. /products.json returned all eight in one request; writing only
    # the sampled three parsed the other five and threw them away, which cost
    # the teardown its shelf and the benchmark its sample for nothing.
    prods = {p["asin"]: p for p in db.store["harvest_products"]}
    assert len(prods) == 8
    assert "riverbendgoods.com/products/harbor-tote" in prods
    assert all(p["seller_id"] == "riverbend-goods.myshopify.com" for p in prods.values())
    # Only a sampled product can carry a review count, and only when its page
    # published one. The rest say None rather than borrowing a number from a
    # sibling, which is what would make the shelf table lie.
    sampled = {"harbor-tote", "cedar-caddy", "harbor-mug"}
    reviewed = {p["asin"].rsplit("/", 1)[-1] for p in prods.values() if p["reviews"] is not None}
    assert reviewed and reviewed <= sampled
    tote = prods["riverbendgoods.com/products/harbor-tote"]
    assert tote["platform"] == "shopify" and tote["fulfilled_by_amazon"] is False
    assert tote["weight_oz"] == 17.99 and tote["price"] == 48.0 and tote["reviews"] == 1204
    assert tote["brand"] == "Riverbend Goods" and tote["category"] == "Bags" and tote["bsr"] is None
    assert tote["seller_id"] == "riverbend-goods.myshopify.com"
    assert db.store["funnel_events"][-1]["note"].startswith("shopify: 3 store(s) read")

    # a second pass reads nothing: every handle is on file now
    f2 = StoreFetcher(store_pages())
    assert shopify.crawl(db, f2, ["riverbend-goods"], log=quiet)["read"] == 0 and not f2.calls


def test_a_recheck_refreshes_the_catalog_but_keeps_the_verdict():
    """A store re-read after it was pushed keeps its verdict, exactly as a
    re-crawled Amazon seller does in run._crawl_category — a fresh 'candidate'
    must not reset a row that is already through the pipeline."""
    db = FakeDB()
    shopify.crawl(db, StoreFetcher(store_pages()), ["riverbend-goods"], log=quiet, resolver=lambda d: True)
    db.store["harvest_sellers"][0].update(status="pushed", top_category=None)
    f = StoreFetcher(store_pages())
    assert shopify.crawl(db, f, ["riverbend-goods"], log=quiet)["read"] == 0   # skipped by default
    s = shopify.crawl(db, f, ["riverbend-goods"], log=quiet, resolver=lambda d: True, recheck=True)
    row = db.store["harvest_sellers"][0]
    assert s["read"] == 1 and row["status"] == "pushed"      # the verdict survives
    assert row["top_category"] == "Bags"                      # the catalog facts are refreshed
    # a store that has since gone out of band is demoted, verdict or not
    db.store["harvest_sellers"][0]["status"] = "pushed"
    tiny = store_pages()
    tiny["https://riverbend-goods.myshopify.com/products.json?limit=250"] = json.dumps(
        {"products": json.loads(PRODUCTS_JSON)["products"][:2]})
    shopify.crawl(db, StoreFetcher(tiny), ["riverbend-goods"], log=quiet, recheck=True)
    assert db.store["harvest_sellers"][0]["status"] == "skip_size"
    # the rule itself
    assert shopify.keep_verdict("pushed", "enriched") == "pushed"
    assert shopify.keep_verdict("pushed", "skip_size") == "skip_size"   # fresh evidence wins
    assert shopify.keep_verdict("skip_internal", "candidate") == "skip_internal"
    assert shopify.keep_verdict("candidate", "enriched") == "enriched"
    assert shopify.keep_verdict(None, "candidate") == "candidate"


def test_a_store_with_no_review_counts_is_still_a_candidate():
    db = FakeDB()
    pages = store_pages()
    for handle in ("harbor-tote", "cedar-caddy"):
        pages[f"https://riverbend-goods.myshopify.com/products/{handle}"] = PRODUCT_PAGE_NO_REVIEWS
    f = StoreFetcher(pages)
    shopify.crawl(db, f, ["riverbend-goods"], log=quiet, resolver=lambda d: True)
    (row,) = db.store["harvest_sellers"]
    # enriched because the contact page published an address; no estimate, so the
    # push's revenue floor leaves it in the founder lane rather than the campaign
    assert row["status"] == "enriched" and row["est_monthly_revenue"] is None
    assert "no review count on the sampled product pages" in row["notes"]


# -- wiring ------------------------------------------------------------------------------

def test_enrich_uses_a_website_the_row_already_has():
    """A Shopify row knows its own site, so the guess-and-Bing search is skipped."""
    f = FakeFetcher({"https://riverbendgoods.com/policies/contact-information": CONTACT_POLICY})
    upd = enrich.enrich_seller(f, {"brand": "Riverbend Goods", "website": "https://riverbendgoods.com/"},
                               resolver=lambda d: True)
    assert upd["status"] == "enriched" and upd["website"] == "https://riverbendgoods.com/"
    assert upd["email"] == "hello@riverbendgoods.com" and upd["notes"] == "site via known"
    assert not any("bing.com" in c for c in f.calls)
    assert "/policies/contact-information" in enrich.CONTACT_PATHS


def test_run_all_runs_the_shopify_step_and_survives_it_failing(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(run, "crawl", lambda *a, **k: calls.append("crawl") or {})
    monkeypatch.setattr(run, "listings", lambda *a, **k: calls.append("listings") or {})
    monkeypatch.setattr(run, "enrich", lambda *a, **k: calls.append("enrich") or {})
    monkeypatch.setattr(run, "push", lambda *a, **k: calls.append("push") or 0)
    monkeypatch.setattr(shopify, "store_fetcher", lambda: FakeFetcher({}))
    monkeypatch.setattr(shopify, "archive_fetcher", lambda: FakeFetcher({}))
    monkeypatch.setattr(shopify, "discover", lambda *a, **k: (["riverbend-goods"], {}))
    monkeypatch.setattr(shopify, "crawl", lambda *a, **k: calls.append("shopify") or {"read": 1})

    out = run.run_all(FakeDB(), FakeFetcher({}), lock=tmp_path / "run.lock", log=quiet)
    assert calls == ["crawl", "listings", "shopify", "enrich", "push"]  # after listings, before enrich
    assert out["shopify"] == {"read": 1}

    # the archive is down: the Shopify pass is skipped and the Amazon steps still run
    calls.clear()

    def boom(*a, **k):
        raise RuntimeError("web.archive.org refused the connection")

    monkeypatch.setattr(shopify, "discover", boom)
    out = run.run_all(FakeDB(), FakeFetcher({}), lock=tmp_path / "run2.lock", log=quiet)
    assert calls == ["crawl", "listings", "enrich", "push"]
    assert "refused" in out["shopify"]["error"]


def test_status_and_lead_payload_carry_the_platform():
    db = FakeDB()
    db.store["harvest_sellers"] = [
        {"seller_id": "A", "status": "pushed", "platform": "amazon", "source": "bestsellers"},
        {"seller_id": "riverbend-goods.myshopify.com", "status": "enriched", "platform": "shopify",
         "source": "shopify", "brand": "Riverbend Goods", "email": "hello@riverbendgoods.com"},
        {"seller_id": "C", "status": "candidate"},  # written before 2026-09-04: no platform column
    ]
    s = run.status(db)
    assert s["by_platform"] == {"amazon": 2, "shopify": 1}
    assert "shopify 1" in run.status_text(db) and "3 sellers on file" in run.status_text(db)
    lead = run.lead_payload(db.store["harvest_sellers"][1])
    assert lead["custom_variables"]["platform"] == "shopify"
    assert run.lead_payload({"seller_id": "A", "brand": "A", "email": "a@a.com"})["custom_variables"]["platform"] \
        == "amazon"


def test_requalify_leaves_shopify_rows_alone(tmp_path):
    """There is no Amazon seller profile to re-read for a store."""
    db = FakeDB()
    db.store["harvest_sellers"] = [
        {"seller_id": "G", "seller_name": "Gorilla Grip", "brand": "GORILLA GRIP", "brands": ["GORILLA GRIP"],
         "asins": [], "reviews_max": 0, "status": "pushed", "platform": "amazon", "country": "US",
         "est_monthly_revenue": 236000},
        {"seller_id": "riverbend-goods.myshopify.com", "brand": "Riverbend Goods", "brands": [], "asins": [],
         "reviews_max": 0, "status": "pushed", "platform": "shopify", "country": "US",
         "est_monthly_revenue": 89000, "notes": "shopify store, 8 products"},
    ]
    from hubricon_engine.harvest import amazon
    f = FakeFetcher({amazon.seller_url("G"): seller_page("Gorilla Grip", "Hillspoint Industries, LLC",
                                                         r12="8,703", life="211,667")})
    counts = run.requalify(db, f, limit=10, cache=Cache(tmp_path), log=quiet)
    assert counts == {"skip_size": 1}
    assert not any("riverbend" in c for c in f.calls)
    assert db.store["harvest_sellers"][1]["status"] == "pushed"
    # `listings` reads an Amazon storefront, which a store does not have
    assert run.listings(db, f, limit=10, cache=Cache(tmp_path), log=quiet) == {}
    assert not any("riverbend" in c for c in f.calls)


def test_fee_cliff_report_stays_an_amazon_post():
    db = FakeDB()
    db.store["harvest_products"] = [
        {"asin": "A1", "brand": "A", "category": "Kitchen & Dining", "weight_oz": 16.8, "platform": "amazon"},
        {"asin": "riverbendgoods.com/products/harbor-tote", "brand": "Riverbend Goods", "category": "Bags",
         "weight_oz": 17.99, "platform": "shopify"},
    ]
    r = run.fee_cliff_report(db, within_oz=1.0)
    assert r["products"] == 1 and r["near_cliff"] == 1   # the Shopify product pays a carrier, not Amazon
    assert all(e["asin"] == "A1" for e in r["examples"])


# -- the founder lane -----------------------------------------------------------------------

def _shopify_db():
    db = FakeDB()
    db.store["harvest_sellers"] = [{
        "seller_id": "riverbend-goods.myshopify.com", "platform": "shopify", "source": "shopify",
        "seller_name": "Riverbend Goods", "brand": "Riverbend Goods", "brands": ["Riverbend Goods"],
        "business_name": "Riverbend Goods LLC", "city": "Burlington", "state": "Vermont", "country": "US",
        "website": "https://riverbendgoods.com/", "email": "hello@riverbendgoods.com",
        "email_confidence": "published", "first_name": "Nora", "last_name": "Fielding",
        "status": "enriched", "est_monthly_revenue": 89000, "reviews_max": 1204, "top_category": "Bags",
    }]
    db.store["harvest_products"] = [{
        "asin": "riverbendgoods.com/products/harbor-tote", "seller_id": "riverbend-goods.myshopify.com",
        "brand": "Riverbend Goods", "title": "Harbor Tote, waxed canvas everyday bag", "category": "Bags",
        "bsr": None, "price": 48.0, "reviews": 1204, "weight_oz": 17.2, "platform": "shopify",
        "fulfilled_by_amazon": False,
    }]
    return db


def test_the_founder_lane_hook_for_a_shopify_row_is_the_shipping_band():
    db = _shopify_db()
    facts = outreach.seller_facts(db, "riverbend-goods.myshopify.com")
    assert facts["platform"] == "shopify"
    assert (facts["items"][0]["band_edge"], facts["items"][0]["over_by"]) == (16, 1.2)

    brief = outreach.brief_text(facts)
    assert "ships at 17.2 oz. USPS rounds anything over 16 oz up to 2 lb, so trimming 1.2 oz " \
           "drops every parcel to the under a pound rate." in brief
    # And it says what that is worth, from the one rate card both lanes read.
    assert "$0.96 to $4.47 a parcel" in brief
    assert "platform      Shopify" in brief and "FBA" not in brief
    assert "https://riverbendgoods.com/policies/contact-information" in brief
    assert "Amazon storefront" not in brief

    draft = outreach.founder_email(facts, "Nora", "https://cal.com/hubricon")
    assert draft["complete"] and draft["to"] == "hello@riverbendgoods.com"
    # The subject carries the number and what it costs, and never the word
    # "FBA" — the whole point of the Shopify lane.
    assert draft["subject"] == "1.2 oz is costing Riverbend Goods on every parcel"
    assert "FBA" not in draft["subject"]
    assert "onto the 2 lb rate instead of the under a pound rate" in draft["body"]
    assert "$0.96 to $4.47 each" in draft["body"]
    assert "Shopify admin" in draft["body"] and "Seller Central" not in draft["body"]
    assert "no access to your store" in draft["body"]

    partner = outreach.partner_email(facts, "Dana", "20% of the first year")
    assert "16 oz mark USPS rounds up from" in partner["body"] and "FBA" not in partner["body"]
    assert "the 2 lb rate rather than the under a pound one" in partner["body"]

    rows = outreach.targets(db, limit=5)
    assert rows[0]["seller_id"] == "riverbend-goods.myshopify.com" and rows[0]["has_hook"]
    assert outreach.target_label(rows[0]) == "READY"


def test_an_amazon_row_still_talks_about_the_fba_band():
    db = _shopify_db()
    db.store["harvest_sellers"][0].update(platform="amazon", seller_id="AXSP4G6IQFYIQ")
    db.store["harvest_products"][0].update(platform="amazon", seller_id="AXSP4G6IQFYIQ",
                                           asin="B0CQVWT2NH", weight_oz=20.8)
    facts = outreach.seller_facts(db, "AXSP4G6IQFYIQ")
    assert facts["platform"] == "amazon" and facts["items"][0]["band_edge"] == 20
    assert "next fee band" in outreach.brief_text(facts)
    assert "FBA weight band" in outreach.founder_email(facts, "Nora", "https://cal.com/x")["body"]
    assert "Seller Central" in outreach.founder_email(facts, "Nora", "https://cal.com/x")["body"]


def test_the_archive_is_read_with_plain_http_not_through_chrome():
    # store_fetcher routes every host through Chrome because Shopify 429s a
    # plain client. web.archive.org is not Shopify: Chrome answers its
    # plain-text page count with the JSON viewer, which read as zero pages and
    # made the first live run list nothing at all (2026-09-04).
    assert shopify.store_fetcher().chrome_hosts == ("",)
    assert shopify.archive_fetcher().chrome_hosts == ("amazon.",)
    # the count survives either shape, and anything that is not a number is zero
    assert shopify.page_count("42897\n") == 42897
    assert shopify.page_count("<html><body><pre>42897</pre></body></html>") == 42897
    assert shopify.page_count("- -\n") == 0          # what the API says when fl=/collapse= ride along
    assert shopify.page_count(None) == 0 and shopify.page_count("") == 0


def test_load_handles_lists_with_its_own_fetcher_when_none_is_given(tmp_path, monkeypatch):
    built = []

    def fake_archive_fetcher():
        f = FakeFetcher({shopify.CDX_COUNT: "1\n", shopify.CDX + "&page=0": CDX_TEXT})
        built.append(f)
        return f

    monkeypatch.setattr(shopify, "archive_fetcher", fake_archive_fetcher)
    handles = shopify.load_handles(cdx_file=tmp_path / "s.cdx", log=quiet)
    assert built and handles == ["northfield-candle", "riverbend-goods", "big-timber-supply"]


def test_a_store_with_no_custom_domain_never_gets_a_guessed_address():
    # myshopify.com has an MX, so `hello@beantones.myshopify.com` passes every
    # cheap check and hard-bounces. Two of the first five stores read live on
    # 2026-09-04 were exactly this, and a bounce on a two-month-old sending
    # domain is the one cost the founder lane cannot absorb.
    assert shopify.is_shopify_host("beantones.myshopify.com")
    assert shopify.is_shopify_host("myshopify.com")
    assert not shopify.is_shopify_host("riverbendgoods.com")
    assert not shopify.is_shopify_host("notmyshopify.com")
    assert not shopify.is_shopify_host(None)

    bare = FakeFetcher({"https://beantones.myshopify.com/": "<html><title>Bean Tones</title>no mail</html>"})
    c = shopify.store_contact(bare, "https://beantones.myshopify.com/", "The Bean Tones",
                              resolver=lambda d: True)          # even with MX saying yes
    assert c["status"] == "no_email" and c["email"] is None
    assert "no custom domain" in c["note"]
    # a brand that owns a domain still gets the pattern guess
    own = FakeFetcher({"https://riverbendgoods.com/": "<html><title>Riverbend Goods</title>no mail</html>"})
    p = shopify.store_contact(own, "https://riverbendgoods.com/", "Riverbend Goods", resolver=lambda d: True)
    assert p["email"] == "hello@riverbendgoods.com" and p["email_confidence"] == "pattern"


# -- discovery through Shopify's own marketplace ---------------------------------

SEARCH_PAGE = """<html><body><ol>
<li class="b_algo"><h2><a href="https://shop.app/store/corgi-candle">Corgi Candle</a></h2></li>
<li class="b_algo"><h2><a href="https://corgicandle.com/">Corgi Candle</a></h2></li>
<li class="b_algo"><h2><a href="https://www.britannica.com/topic/candle">Candle</a></h2></li>
<li class="b_algo"><h2><a href="https://www.amazon.com/candles">Amazon</a></h2></li>
<li class="b_algo"><h2><a href="https://thefoggydog.com/collections/all">The Foggy Dog</a></h2></li>
<li class="b_algo"><h2><a href="https://example.co.uk/">A British shop</a></h2></li>
</ol></body></html>"""


def test_search_results_become_candidate_brand_domains():
    doms = shopify.search_domains(SEARCH_PAGE)
    assert doms == ["corgicandle.com", "thefoggydog.com"]
    # shop.app itself, the retailers, the publishers and the non-US domains are all out
    for junk in ("shop.app", "britannica.com", "amazon.com", "example.co.uk"):
        assert junk not in doms
    assert shopify.search_domains(None) == []
    assert "site%3Ashop.app" in shopify.search_url("candles")
    assert "candles" in shopify.search_url("candles")


def test_search_terms_rotate_by_half_day_like_the_amazon_categories():
    import datetime as _dt
    day = _dt.date(2026, 9, 4)
    morning = shopify.search_terms(4, today=day, slot=0)
    evening = shopify.search_terms(4, today=day, slot=1)
    assert len(morning) == 4 and not set(morning) & set(evening)
    assert all(t in shopify.SEARCH_CATEGORIES for t in morning + evening)


def test_discover_probes_each_domain_and_keys_stores_by_their_myshopify_handle():
    # the row key must be the handle, so a store found by search and the same
    # store found in the archive are one row rather than two
    assert shopify.handle_from_meta({"myshopify_domain": "corgi-candle.myshopify.com"}) == "corgi-candle"
    assert shopify.handle_from_meta({"myshopify_domain": ""}) is None
    assert shopify.handle_from_meta(None) is None

    search = FakeFetcher({shopify.search_url("candles"): SEARCH_PAGE})
    corgi = json.dumps({"name": "Corgi Candle", "country": "US", "currency": "USD",
                        "domain": "corgicandle.com", "myshopify_domain": "corgi-candle.myshopify.com"})
    stores = FakeFetcher({"https://corgicandle.com/meta.json": corgi})  # the foggy dog does not answer
    handles, metas = shopify.discover(search, stores, terms=["candles"], log=quiet)
    assert handles == ["corgi-candle"]
    assert metas["corgi-candle"]["name"] == "Corgi Candle"
    # both candidates were probed; the miss costs one request and nothing else
    assert sorted(c for c in stores.calls) == ["https://corgicandle.com/meta.json",
                                               "https://thefoggydog.com/meta.json"]


def test_a_discovered_meta_is_not_fetched_twice():
    meta = json.loads(META_JSON)
    f = StoreFetcher(store_pages())
    out = shopify.read_store(f, "riverbend-goods", resolver=lambda d: True, meta=meta)
    assert out["status"] == "enriched" and len(out["products"]) == 8
    assert not any(c.endswith("/meta.json") for c in f.calls)   # the search already paid for it


def test_domains_that_can_never_be_a_store_are_dropped_before_the_probe():
    # Measured across all 27 category searches on 2026-09-04: publishers were
    # a fifth of the candidates, and each costs a six-second Chrome probe to
    # learn nothing. A government or university host is never a shop.
    page = "<html><body><ol>" + "".join(
        f'<li class="b_algo"><h2><a href="https://{d}/">x</a></h2></li>' for d in (
            "tea.texas.gov", "cs.stanford.edu", "www.nytimes.com", "www.forbes.com",
            "stackoverflow.com", "seriouseats.com", "corgicandle.com", "bombas.com")
    ) + "</ol></body></html>"
    kept = shopify.search_domains(page)
    # the two real stores survive; the retailer is left for the classifier to
    # size out, because guessing at that verdict is what a name list would be
    assert kept == ["corgicandle.com", "bombas.com"]


def test_a_search_term_that_returns_nothing_says_so():
    # A barren term and a broken one look identical from here — the Amazon side
    # lost five Best Sellers slugs to exactly that silence.
    lines = []
    empty = FakeFetcher({})
    shopify.discover(empty, FakeFetcher({}), terms=["nonsense term"], log=lines.append)
    assert any("nothing; check the term" in l for l in lines)
    # and a term that works is not flagged
    lines.clear()
    ok = FakeFetcher({shopify.search_url("candles"): SEARCH_PAGE})
    shopify.discover(ok, FakeFetcher({}), terms=["candles"], log=lines.append)
    assert not any("nothing; check the term" in l for l in lines)


def test_a_skip_that_came_off_a_name_list_says_so():
    # A name list is a cost optimisation: it saves the pages a real measurement
    # would cost. It must never read like a finding, or a wrong skip is
    # indistinguishable from a right one when someone reviews the row later.
    status, note = shopify.classify_catalog(
        {"name": "Thrasio Home", "domain": "thrasiohome.com"},
        [{"vendor": "Thrasio Home"}] * 5)
    assert status == "skip_size"
    assert "name on the conglomerate list" in note and "'thrasio'" in note
    assert "not a measured size" in note

    # a skip on the store's own numbers still reads as the finding it is
    multi, note2 = shopify.classify_catalog(
        {"name": "Big Retailer", "domain": "bigretailer.com"},
        [{"vendor": v} for v in ("A", "B", "C", "D")] * 2)
    assert multi == "skip_reseller" and "multi-brand catalog" in note2 and "vendors" in note2

    assert shopify.big_parent_word("Nestle Purina", None) == "nestle"
    assert shopify.big_parent_word("Riverbend Goods", "Riverbend Goods") is None


def test_only_the_stores_own_domain_counts_as_a_published_address():
    # A contact page often carries a supplier's or an agency's address. Writing
    # to it reaches the wrong company, which reads worse to the recipient than a
    # guess at the right one. Same rule enrich.py applies on the Amazon side.
    page = ('<html><title>Riverbend Goods</title><body>'
            'Fulfilment by <a href="mailto:contact@somesupplier.com">our partner</a>'
            '</body></html>')
    f = FakeFetcher({"https://riverbendgoods.com/": page})
    c = shopify.store_contact(f, "https://riverbendgoods.com/", "Riverbend Goods",
                              resolver=lambda d: True)
    assert c["email"] != "contact@somesupplier.com"
    assert c["email"] == "hello@riverbendgoods.com" and c["email_confidence"] == "pattern"

    # an offshore address anywhere on the page is a fact about the company,
    # even when the store also publishes one at its own domain
    off = ('<html><title>Riverbend Goods</title><body>'
           '<a href="mailto:hello@riverbendgoods.com">us</a>'
           '<a href="mailto:sales@riverbend.cn">factory</a></body></html>')
    f2 = FakeFetcher({"https://riverbendgoods.com/": off})
    c2 = shopify.store_contact(f2, "https://riverbendgoods.com/", "Riverbend Goods",
                               resolver=lambda d: True)
    assert c2["status"] == "skip_non_us" and ".cn" in c2["note"]
