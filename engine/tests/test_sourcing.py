"""Shopify lead sourcing: discovery, qualification, contact, and the fences.

The fence tests are the ones that matter most. `outbound.enroll_from_lists`
enrols any Instantly list whose name contains INSTANTLY_LIST_MATCH into the
live campaign, and the hourly operator runs with COLD_DRY_RUN=false — so a
mistake in `push.py` is not a bug, it is cold email going to strangers nobody
approved. Four of these tests exist to make that impossible to do by accident.
"""

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from hubricon_engine import outbound
from hubricon_engine.cold import findings
from hubricon_engine.cold.snapshot import Item, Observation, ProspectSnapshot
from hubricon_engine.sourcing import catalog, contact, discover, push, score, sheet, stack
from hubricon_engine.sourcing import run as sourcing
from hubricon_engine.sourcing.fetch import DualFetcher

from test_harvest import FakeApi, FakeDB, FakeFetcher, quiet  # noqa: F401


# -- doubles -----------------------------------------------------------------------

class CountingFetcher:
    """A Fetcher stand-in that tracks `missing` the way the real one does."""

    def __init__(self, pages=None, missing=(), ok=True):
        self.pages = pages or {}
        self.missing = set(missing)
        self.calls = []
        self.stats = {"requests": 0, "ok": 0, "missing": 0, "errors": 0}

    def get(self, url, headers=None):
        self.calls.append(url)
        self.stats["requests"] += 1
        if url in self.pages:
            self.stats["ok"] += 1
            return self.pages[url]
        if url in self.missing:
            self.stats["missing"] += 1      # a 404
            return None
        self.stats["errors"] += 1           # a 403/429/timeout
        return None


class RecordingApi(FakeApi):
    """FakeApi, but it remembers whether campaign_id was ever passed."""

    def __init__(self, lists=None):
        super().__init__(lists)
        self.campaign_ids = []

    def add_leads(self, list_id=None, campaign_id=None, leads=None):
        self.campaign_ids.append(campaign_id)
        return super().add_leads(list_id=list_id, campaign_id=campaign_id, leads=leads)


def resolver_for(records):
    """dig double: {(name, kind): [values]}."""
    return lambda name, kind: records.get((name, kind), [])


def catalog_json(products):
    return json.dumps({"products": products})


def product(handle, price, compare_at=None, days_old=400, updated_days=10, grams=200):
    made = datetime.now(timezone.utc) - timedelta(days=days_old)
    touched = datetime.now(timezone.utc) - timedelta(days=updated_days)
    return {
        "handle": handle, "title": handle.replace("-", " ").title(), "vendor": "Riverbend",
        "product_type": "Bags", "created_at": made.isoformat(), "updated_at": touched.isoformat(),
        "variants": [{"price": str(price), "compare_at_price": (str(compare_at) if compare_at else None),
                      "grams": grams, "sku": handle.upper(), "available": True}],
    }


# -- fence 1: the list cannot be auto-enrolled --------------------------------------

def test_the_holding_pen_is_named_so_the_operator_cannot_enrol_it():
    """outbound.enroll_from_lists matches on a substring of the list name. If
    the holding pen ever contains that token, the hourly operator starts
    cold-emailing everything in it."""
    assert outbound.LIST_MATCH
    assert outbound.LIST_MATCH not in push.LIST_NAME.lower()


def test_a_list_renamed_to_something_enrollable_is_refused():
    """Fence 2. Somebody renames the list in Instantly at eleven at night; the
    next push must raise rather than fill a list the operator will enrol."""
    api = RecordingApi(lists=[{"id": "L9", "name": "Hubricon sourcing"}])
    with pytest.raises(push.WouldEnroll) as err:
        push.ensure_list(api, "Hubricon sourcing")
    assert "enrol" in str(err.value)
    assert push.LIST_NAME in str(err.value)   # says what to rename it back to


def test_ensure_list_checks_the_name_instantly_reports_not_the_one_we_asked_for():
    api = RecordingApi(lists=[{"id": "L9", "name": "hubricon holding pen"}])
    # We ask for the safe name, but Instantly hands back a list whose real name
    # would be enrolled. Matching on our own constant would miss this.
    api.lists[0]["name"] = push.LIST_NAME
    assert push.ensure_list(api) == "L9"


# -- fence 3: never a campaign ------------------------------------------------------

def test_push_never_passes_a_campaign_id():
    db = FakeDB()
    rows = [{"domain": "riverbend.com", "brand": "Riverbend", "email": "dana@riverbend.com",
             "email_confidence": "published", "role_inbox": False, "first_name": "Dana"}]
    api = RecordingApi()
    push.push(db, api, rows, log=quiet)
    assert api.campaign_ids == [None]
    assert api.added[0][0] == "L1"            # into the list, by id


def test_the_package_never_calls_create_lead():
    """`create_lead` is the per-prospect teardown dispatch path — the one that
    actually sends. Nothing in sourcing/ may reach it."""
    import pathlib

    root = pathlib.Path(push.__file__).parent
    for path in root.glob("*.py"):
        assert "create_lead(" not in path.read_text(), path.name


# -- fence 4: only published, non-role addresses ------------------------------------

def test_push_refuses_a_pattern_address():
    """A guessed address passes every free check because Shopify merchants run
    catch-all, and hard-bounces. There is no paid verification in this build."""
    rows = [{"domain": "riverbend.com", "email": "dana@riverbend.com",
             "email_confidence": "pattern", "role_inbox": False}]
    keep, refused = push.eligible(rows)
    assert keep == []
    assert "pattern" in refused[0][1]


def test_push_refuses_a_role_inbox():
    """The founder's decision on 2026-09-03: role inboxes reach a support queue
    and are never cold-emailed. They stay on the sheet for the founder lane."""
    rows = [{"domain": "riverbend.com", "email": "hello@riverbend.com",
             "email_confidence": "published", "role_inbox": True}]
    keep, refused = push.eligible(rows)
    assert keep == []
    assert "role inbox" in refused[0][1]


def test_push_refuses_an_address_at_someone_elses_domain():
    rows = [{"domain": "riverbend.com", "email": "dana@someagency.com",
             "email_confidence": "published", "role_inbox": False}]
    keep, refused = push.eligible(rows)
    assert keep == []
    assert "own domain" in refused[0][1]


def test_push_accepts_a_published_named_address():
    rows = [{"domain": "riverbend.com", "email": "dana@riverbend.com",
             "email_confidence": "published", "role_inbox": False}]
    keep, refused = push.eligible(rows)
    assert [r["email"] for r in keep] == ["dana@riverbend.com"]
    assert refused == []


def test_a_dry_push_writes_nothing_anywhere():
    db = FakeDB()
    api = RecordingApi()
    rows = [{"domain": "riverbend.com", "email": "dana@riverbend.com",
             "email_confidence": "published", "role_inbox": False}]
    got = push.push(db, api, rows, dry=True, log=quiet)
    assert got["pushed"] == 0 and api.added == [] and db.store == {}


# -- promote: the status the auto-push does not select ------------------------------

def test_promote_lands_a_row_at_candidate_not_enriched(monkeypatch):
    """harvest/run.py::push selects `enriched` rows and pushes them into the
    auto-enrolled list. A promoted row at `enriched` would be cold-emailed by
    the hourly operator with nobody having approved it."""
    db = FakeDB()
    db.store["sourcing_prospects"] = [{
        "domain": "riverbend.com", "myshopify_handle": "riverbend", "status": "contacted_found",
        "score": 80, "email": "dana@riverbend.com", "email_confidence": "published",
        "first_name": "Dana", "last_name": "Okafor", "contact_source": "site/pages/about",
    }]
    from hubricon_engine.harvest import shopify as shopify_harvest

    monkeypatch.setattr(shopify_harvest, "read_store", lambda *a, **k: {
        "meta": {"name": "Riverbend", "country": "US", "currency": "USD", "domain": "riverbend.com"},
        # `read_store` decided `enriched`; promote must overrule it.
        "status": "enriched", "note": "published contact address",
        "products": [], "sampled": [], "vendors": {"vendors": ["Riverbend"], "dominant": "Riverbend"},
        "est_annual": 2_000_000, "contact": {"email": "hello@riverbend.com"},
    })
    monkeypatch.setattr(sourcing, "_with_compare_at", lambda *a, **k: [])
    got = sourcing.promote(db, FakeFetcher({}), log=quiet)
    assert got["promoted"] == 1
    seller = db.store["harvest_sellers"][0]
    assert seller["status"] == "candidate"
    assert seller["source"] == "sourcing"
    # The published address the contact pass found beats the re-read's guess.
    assert seller["email"] == "dana@riverbend.com"
    assert seller["first_name"] == "Dana"


def test_nothing_in_the_package_approves_a_teardown():
    import pathlib

    root = pathlib.Path(push.__file__).parent
    for path in root.glob("*.py"):
        text = path.read_text()
        assert '"approved"' not in text and "'approved'" not in text, path.name


# -- the fetcher: plain first, Chrome only on a refusal -----------------------------

def test_a_404_does_not_spend_a_chrome_launch():
    """A headless storefront answers /products.json with a 404. Chrome will not
    conjure the endpoint, so escalating costs six seconds for nothing."""
    plain = CountingFetcher(missing={"https://x.com/products.json"})
    chrome = CountingFetcher()
    dual = DualFetcher(plain=plain, chrome=chrome)
    assert dual.get("https://x.com/products.json") is None
    assert chrome.calls == []
    assert dual.stats["escalations"] == 0


def test_a_403_escalates_to_chrome():
    plain = CountingFetcher()                       # neither a page nor a 404 -> refused
    chrome = CountingFetcher(pages={"https://ridge.com/meta.json": '{"name": "Ridge"}'})
    dual = DualFetcher(plain=plain, chrome=chrome)
    assert dual.get("https://ridge.com/meta.json") == '{"name": "Ridge"}'
    assert dual.stats["escalations"] == 1 and dual.stats["chrome_ok"] == 1


def test_a_store_that_answers_plainly_never_touches_chrome():
    """Measured 2026-09-05: allbirds, brooklinen and drinkolipop all answer
    plain HTTP with full JSON, whatever user agent is used."""
    plain = CountingFetcher(pages={"https://allbirds.com/meta.json": '{"name": "Allbirds"}'})
    chrome = CountingFetcher()
    dual = DualFetcher(plain=plain, chrome=chrome)
    assert dual.get_json("https://allbirds.com/meta.json") == {"name": "Allbirds"}
    assert chrome.calls == [] and dual.stats["plain_ok"] == 1


def test_html_where_json_was_expected_escalates():
    """An interstitial or a challenge page is a 200 that is not the payload."""
    plain = CountingFetcher(pages={"https://x.com/products.json": "<html>just a moment</html>"})
    chrome = CountingFetcher(pages={"https://x.com/products.json": '{"products": []}'})
    dual = DualFetcher(plain=plain, chrome=chrome)
    assert dual.get_json("https://x.com/products.json") == {"products": []}
    assert dual.stats["escalations"] == 1


def test_no_chrome_on_the_machine_is_not_an_error():
    plain = CountingFetcher()
    dual = DualFetcher(plain=plain, chrome=None)
    assert dual.get("https://x.com/") is None
    assert dual.stats["refused"] == 1


# -- discovery ---------------------------------------------------------------------

def test_an_a_record_in_shopifys_block_is_a_store():
    """Verified live 2026-09-05: allbirds.com -> 23.227.38.32."""
    ok, why = discover.is_shopify_dns(
        "allbirds.com", resolver_for({("allbirds.com", "A"): ["23.227.38.32"]}))
    assert ok and why == "A 23.227.38.32"


def test_a_cname_at_www_is_a_store():
    ok, why = discover.is_shopify_dns("allbirds.com", resolver_for({
        ("allbirds.com", "A"): ["76.76.21.21"],
        ("www.allbirds.com", "CNAME"): ["shops.myshopify.com"]}))
    assert ok and "shops.myshopify.com" in why


def test_a_proxied_store_is_not_settled_by_dns():
    """bombas.com -> 76.76.21.21 (Vercel) and ridge.com -> Cloudflare. Both are
    Shopify stores; DNS cannot say so, which is why the HTTP pass exists."""
    ok, _ = discover.is_shopify_dns("bombas.com", resolver_for({("bombas.com", "A"): ["76.76.21.21"]}))
    assert not ok


def test_obvious_non_stores_are_never_probed():
    for domain in ("google.com", "www.linkedin.com", "harvard.edu", "irs.gov",
                   # Shopify's own hosts sit in Shopify's own IP block, so the
                   # DNS pass says yes to them every time. myshopify.com is
                   # ranked in Tranco and was "discovered" on the first run.
                   "myshopify.com", "shopify.com", "riverbend.myshopify.com",
                   # a store somewhere we are not allowed to write to
                   "scotch-soda.eu", "invicta.com.pe", "courtorder.co.za"):
        assert not discover.worth_probing(domain), domain
    for domain in ("allbirds.com", "riverbend.co", "drinkolipop.com"):
        assert discover.worth_probing(domain), domain


def test_the_http_fingerprint_reads_the_handle_out_of_meta():
    fetcher = FakeFetcher({"https://riverbend.com/meta.json":
                           '{"name": "Riverbend", "myshopify_domain": "riverbend.myshopify.com"}'})
    handle, meta = discover.fingerprint_http(fetcher, "riverbend.com")
    assert handle == "riverbend" and meta["name"] == "Riverbend"


def test_a_headless_storefront_is_recorded_as_platform_only():
    """thehydrojug.com served a React app at its own domain on 2026-09-04. It is
    a Shopify store; it just will not say so in JSON."""
    fetcher = FakeFetcher({"https://hydro.com/": '<script src="https://cdn.shopify.com/x.js">'})
    handle, meta = discover.fingerprint_http(fetcher, "hydro.com")
    assert handle is None and meta["platform_only"] is True


def test_a_domain_that_is_not_shopify_at_all_returns_nothing():
    fetcher = FakeFetcher({"https://plain.com/": "<html>a wordpress blog</html>"})
    assert discover.fingerprint_http(fetcher, "plain.com") == (None, None)


# -- the catalogue -----------------------------------------------------------------

def test_the_catalogue_keeps_the_compare_at_price_the_harvest_drops():
    got = catalog.parse_catalog(catalog_json([product("tote", 32.0, compare_at=45.0)]))
    assert got[0]["price"] == 32.0 and got[0]["compare_at"] == 45.0


def test_compare_at_below_the_price_is_not_a_discount():
    got = catalog.parse_catalog(catalog_json([product("tote", 45.0, compare_at=32.0)]))
    assert catalog.discount_profile(got)["share"] == 0.0


def test_the_price_ladder_finds_the_widest_step():
    products = catalog.parse_catalog(catalog_json([
        product("a", 12.0), product("b", 14.0), product("c", 16.0), product("d", 89.0)]))
    ladder = catalog.price_ladder(products)
    assert ladder["gap_at"] == (16.0, 89.0)
    assert ladder["gap_ratio"] == pytest.approx(5.56, abs=0.01)
    assert ladder["median"] == 15.0


def test_a_catalogue_too_short_to_have_a_ladder_reports_no_gap():
    products = catalog.parse_catalog(catalog_json([product("a", 12.0), product("b", 90.0)]))
    assert catalog.price_ladder(products)["gap_ratio"] is None


def test_a_dead_store_shows_it_in_the_dates():
    products = catalog.parse_catalog(catalog_json([product("a", 30.0, days_old=1200, updated_days=700)]))
    assert catalog.velocity(products)["days_since_update"] > 600
    assert catalog.velocity(products)["new_last_year"] == 0


# -- the stack ---------------------------------------------------------------------

def test_the_stack_reads_the_apps_a_store_pays_for():
    """Measured on allbirds.com, 2026-09-05."""
    got = stack.detect("<script src='//elevar.com/x.js'></script> "
                       "<script src='//cdn.attentivemobile.com/t.js'></script> yotpo tiktok")
    assert "elevar" in got["apps"] and "attentive" in got["apps"]
    assert "attribution" in got["tiers"] and got["weight"] >= 5.0


def test_a_bare_theme_scores_nothing():
    got = stack.detect("<html><body>a shop</body></html>")
    assert got["apps"] == [] and got["weight"] == 0.0


def test_one_tier_counts_once_however_many_apps_are_in_it():
    """Three review apps is one operation mid-migration, not three."""
    one = stack.detect("okendo")
    three = stack.detect("okendo yotpo stamped.io")
    assert three["weight"] == one["weight"]
    assert len(three["apps"]) == 3


# -- the score ---------------------------------------------------------------------

def test_a_real_brand_clears_the_bar():
    total, parts = score.score({
        "tranco_rank": 90_000, "products": 60, "ladder": {"median": 68.0},
        "velocity": {"days_since_update": 3, "new_last_year": 12},
        "stack": {"weight": 8.0, "apps": ["elevar", "attentive"], "plus": True},
        "vendors": {"dominant": "Riverbend", "share": 0.95, "vendors": ["Riverbend"]},
        "est_annual": 4_000_000,
    })
    assert total >= score.MIN_SCORE
    assert parts["rank"]["points"] > 0


def test_a_dropshipper_is_thrown_out_on_the_catalogue():
    total, parts = score.score({
        "tranco_rank": 400_000, "products": 1400, "ladder": {"median": 9.0},
        "velocity": {"days_since_update": 40, "new_last_year": 200},
        "stack": {"weight": 0.5, "apps": ["meta_pixel"], "plus": False},
        "vendors": {"dominant": None, "share": 0.1, "vendors": ["A", "B", "C", "D"]},
        "est_annual": None,
    })
    assert total < score.MIN_SCORE
    assert parts["catalog"]["points"] < 0 and parts["price"]["points"] < 0


def test_an_unknown_size_never_disqualifies_on_its_own():
    """Many stores render reviews client-side and publish no count. The harvest
    applies the same rule: unknown is not a verdict."""
    points, why = score._size_points(None)
    assert points == 0.0 and "no review" in why


def test_the_verdict_names_the_signal_that_sank_it():
    status, note, total, _ = score.verdict({
        "tranco_rank": 900_000, "products": 1400, "ladder": {"median": 4.0},
        "velocity": {"days_since_update": 900}, "stack": {}, "vendors": {},
        "est_annual": None})
    assert status == "disqualified"
    assert "score" in note and str(int(total)) in note.replace(",", "")


def test_calibrate_reports_precision_and_recall():
    rows = [{"domain": f"d{i}.com", "score": s, "good": g} for i, (s, g) in enumerate(
        [(80, True), (75, True), (60, True), (50, False), (30, False)])]
    out = score.calibrate(rows, thresholds=(55, 70))
    assert "precision" in out and "3 in-ICP" in out


# -- contact -----------------------------------------------------------------------

def test_only_an_address_at_the_brands_own_domain_counts_as_published():
    """A contact page often carries a supplier's or an agency's address, and
    writing to them reaches the wrong company."""
    assert contact.published_email(["dana@supplier.com", "dana@riverbend.com"],
                                   "riverbend.com") == "dana@riverbend.com"
    assert contact.published_email(["dana@supplier.com"], "riverbend.com") is None


def test_a_store_with_no_custom_domain_is_refused_at_the_source():
    """myshopify.com has an MX record, so a guess there resolves and
    hard-bounces — the one cost a warmed domain cannot absorb."""
    got = contact.resolve(FakeFetcher({}), "beantones.myshopify.com", "Beantones")
    assert got["status"] == "no_contact" and got["email"] is None
    assert "no inbox" in got["note"]


def test_a_linkedin_url_is_captured_not_crawled():
    url = contact.linkedin_url({"/pages/about": 'follow us <a href="https://www.linkedin.com/company/riverbend">'})
    assert url == "https://www.linkedin.com/company/riverbend"


def test_sendable_is_the_single_gate_and_it_explains_itself():
    ok, why = contact.sendable({"email": None})
    assert not ok and why == "no address"
    ok, why = contact.sendable({"email": "dana@riverbend.com", "email_confidence": "published",
                                "domain": "riverbend.com"})
    assert ok and why == ""


# -- the sheet ---------------------------------------------------------------------

def test_the_sheet_says_why_a_row_is_not_sendable():
    row = sheet.as_row({"domain": "riverbend.com", "email": "hello@riverbend.com",
                        "email_confidence": "published", "role_inbox": True, "score": 71})
    assert row["sendable"] == "no" and "role inbox" in row["not_sendable_why"]
    assert row["role_inbox"] == "yes"


def test_the_sheet_carries_a_role_inbox_row_at_all():
    """Sheet yes, Instantly never: a qualified brand is worth a human's ninety
    seconds even when the crawler could not find its owner."""
    db = FakeDB()
    db.store["sourcing_prospects"] = [
        {"domain": "riverbend.com", "status": "contacted_found", "score": 71,
         "email": "hello@riverbend.com", "email_confidence": "published", "role_inbox": True},
    ]
    got = sourcing.sheet(db, dry=True, log=quiet)
    assert got["rows"] == 1


def test_every_sheet_column_is_produced_by_as_row():
    """The Apps Script writes COLUMNS as its header and keys updates on them,
    so a column the writer never fills is a silently empty column."""
    row = sheet.as_row({"domain": "riverbend.com"})
    assert set(row) == set(sheet.COLUMNS)


def test_the_csv_is_written_even_with_no_webhook_configured(tmp_path, monkeypatch):
    monkeypatch.delenv(sheet.SHEET_URL, raising=False)
    monkeypatch.delenv(sheet.SHEET_SECRET, raising=False)
    out = tmp_path / "leads.csv"
    got = sheet.sync([{"domain": "riverbend.com", "score": 71}], log=quiet, csv_path=out)
    assert got["sheet"] == "not configured"
    assert "riverbend.com" in out.read_text()


# -- the detector ------------------------------------------------------------------

def snapshot_with(items, platform="shopify"):
    return ProspectSnapshot(key="riverbend.myshopify.com", platform=platform, provider="sourcing",
                            brand="Riverbend", items=tuple(items),
                            captured_at=datetime.now(timezone.utc))


def discounted(ref, price, compare_at, history=()):
    return Item(ref=ref, url=f"https://riverbend.com/products/{ref}", title=ref.title(),
                price=price, compare_at_price=compare_at, history=tuple(history))


def test_permanent_discount_fires_on_a_shelf_priced_below_its_own_anchor():
    items = [discounted("tote", 32.0, 45.0), discounted("belt", 20.0, 30.0),
             discounted("cap", 15.0, 22.0)]
    got = findings.permanent_discount(items[0], snapshot_with(items), date.today())
    assert got is not None
    assert got.kind == "permanent_discount"
    assert got.per_unit_low == 13.0            # 45 - 32, arithmetic not estimate
    assert got.evidence["catalogue_discount_share"] == 1.0


def test_permanent_discount_is_silent_when_one_product_is_on_sale():
    """One discounted product is marketing. It is the shelf that makes it a price."""
    items = [discounted("tote", 32.0, 45.0)] + [
        Item(ref=f"p{i}", url="u", price=30.0) for i in range(9)]
    assert findings.permanent_discount(items[0], snapshot_with(items), date.today()) is None


def test_permanent_discount_is_silent_on_a_clean_catalogue():
    items = [Item(ref="tote", url="u", price=32.0), Item(ref="belt", url="u", price=20.0)]
    assert findings.permanent_discount(items[0], snapshot_with(items), date.today()) is None


def test_permanent_is_not_claimed_until_the_price_history_earns_it():
    """The arithmetic is certain from day one; the word "permanent" is a claim
    about time, and one snapshot cannot see time. Below COLD_MIN_CONFIDENCE
    until it can, so `select` will not send it."""
    items = [discounted("tote", 32.0, 45.0), discounted("belt", 20.0, 30.0)]
    got = findings.permanent_discount(items[0], snapshot_with(items), date.today())
    assert got.confidence < 0.70
    assert got.evidence["settled"] is False
    assert "not yet watched" in " ".join(got.assumptions)


def test_a_fortnight_of_the_same_price_earns_the_claim():
    today = date.today()
    history = [Observation(seen_on=today - timedelta(days=d), price=32.0) for d in (0, 10, 20)]
    items = [discounted("tote", 32.0, 45.0, history), discounted("belt", 20.0, 30.0)]
    got = findings.permanent_discount(items[0], snapshot_with(items), today)
    assert got.confidence >= 0.70
    assert got.evidence["settled"] is True and got.evidence["days_observed"] == 20


def test_a_price_that_moved_is_not_settled():
    today = date.today()
    history = [Observation(seen_on=today - timedelta(days=d), price=p)
               for d, p in ((0, 32.0), (10, 39.0), (20, 32.0))]
    items = [discounted("tote", 32.0, 45.0, history), discounted("belt", 20.0, 30.0)]
    got = findings.permanent_discount(items[0], snapshot_with(items), today)
    assert got.evidence["settled"] is False


def test_an_amazon_item_carries_no_anchor_so_the_detector_stays_out_of_its_way():
    items = [Item(ref="B01", url="u", price=32.0)]
    assert findings.permanent_discount(items[0], snapshot_with(items, "amazon"), date.today()) is None


def test_the_detector_is_registered_for_shopify_only():
    assert findings.permanent_discount in findings.SHOPIFY_DETECTORS
    assert findings.permanent_discount not in findings.AMAZON_DETECTORS


def test_the_email_hook_renders_from_the_stores_own_two_numbers():
    from hubricon_engine.cold import copy

    items = [discounted("tote", 32.0, 45.0), discounted("belt", 20.0, 30.0)]
    got = findings.permanent_discount(items[0], snapshot_with(items), date.today())
    subject, body = copy.hook(got, "Riverbend")
    assert "Riverbend" in subject
    assert "$45.00" in body and "$32.00" in body
    assert "no access to your store" in body


def test_a_store_can_rank_too_well_for_the_band():
    """The ICP is $1M-$20M, so the rank is a window and not a ladder. The first
    live qualify pass scored barnesandnoble.com (Tranco #2,197) at 73 and passed
    it, because the bands then read "higher is better"."""
    giant, parts = score.score({
        "tranco_rank": 2_197, "products": 120, "ladder": {"median": 25.0},
        "velocity": {"days_since_update": 2, "new_last_year": 40},
        "stack": {"weight": 4.0, "apps": ["klaviyo"], "plus": False},
        "vendors": {"dominant": None, "share": 0.2, "vendors": ["A", "B"]},
        "est_annual": None,
    })
    assert parts["rank"]["points"] < 0
    assert "too big" in parts["rank"]["why"]
    assert giant < score.MIN_SCORE

    in_band = score.score({**{
        "tranco_rank": 180_000, "products": 120, "ladder": {"median": 25.0},
        "velocity": {"days_since_update": 2, "new_last_year": 40},
        "stack": {"weight": 4.0, "apps": ["klaviyo"], "plus": False},
        "vendors": {"dominant": None, "share": 0.2, "vendors": ["A", "B"]},
        "est_annual": None}})[0]
    assert in_band > giant


def test_every_field_a_contact_pass_writes_is_a_column_it_can_write():
    """The first live contact pass died mid-batch writing `address` to a table
    that had no such column. resolve() and CONTACT_FIELDS have to agree."""
    got = contact.resolve(FakeFetcher({}), "beantones.myshopify.com", "Beantones")
    assert set(sourcing.CONTACT_FIELDS) <= set(got), set(sourcing.CONTACT_FIELDS) - set(got)


def test_the_catalogue_reads_past_the_first_page():
    """Shopify caps /products.json at 250. Reading one page made every large
    catalogue look like exactly 250 items, which meant score.py's 800-SKU
    dropshipper filter could never fire."""
    page1 = catalog_json([product(f"p{i}", 20.0 + i) for i in range(250)])
    page2 = catalog_json([product(f"q{i}", 20.0 + i) for i in range(250)])
    page3 = catalog_json([product(f"r{i}", 20.0 + i) for i in range(30)])
    fetcher = FakeFetcher({
        "https://riverbend.myshopify.com/products.json?limit=250": page1,
        "https://riverbend.myshopify.com/products.json?limit=250&page=2": page2,
        "https://riverbend.myshopify.com/products.json?limit=250&page=3": page3,
    })
    got = catalog.read(fetcher, "riverbend.com", "riverbend")
    assert got["count"] == 530
    assert got["truncated"] is False


def test_a_short_catalogue_costs_one_request():
    fetcher = FakeFetcher({"https://riverbend.myshopify.com/products.json?limit=250":
                           catalog_json([product("a", 30.0), product("b", 40.0)])})
    got = catalog.read(fetcher, "riverbend.com", "riverbend")
    assert got["count"] == 2 and len(fetcher.calls) == 1


def test_a_dropshipper_sized_catalogue_is_reported_as_a_floor():
    pages = {f"https://x.myshopify.com/products.json?limit=250{'' if i == 1 else f'&page={i}'}":
             catalog_json([product(f"p{i}-{j}", 9.0) for j in range(250)]) for i in range(1, 5)}
    got = catalog.read(FakeFetcher(pages), "x.com", "x", max_pages=4)
    assert got["count"] == 1000 and got["truncated"] is True
    # And that count is what makes the junk filter fire at all.
    points, why = score._catalog_points(got["count"], {"vendors": ["A", "B", "C"], "dominant": None})
    assert points < 0 and "supplier feed" in why


def test_promote_does_not_launder_a_store_read_store_rejected(monkeypatch):
    """The first live promote wrote `candidate` unconditionally and promoted
    Boston Scally, which read_store had just rejected as a multi-brand
    catalogue. A skip is a verdict, not a status to overwrite."""
    db = FakeDB()
    db.store["sourcing_prospects"] = [{
        "domain": "bostonscally.com", "myshopify_handle": "boston-scally-co",
        "status": "contacted_found", "score": 77,
    }]
    from hubricon_engine.harvest import shopify as shopify_harvest

    monkeypatch.setattr(shopify_harvest, "read_store", lambda *a, **k: {
        "meta": {"name": "Boston Scally", "country": "US", "currency": "USD"},
        "status": "skip_reseller", "note": "multi-brand catalog (6 vendors, top 61%)",
        "products": [], "sampled": [], "vendors": {}, "est_annual": None, "contact": None,
    })
    got = sourcing.promote(db, FakeFetcher({}), log=quiet)
    assert got["promoted"] == 0 and got["skipped"] == 1
    assert "harvest_sellers" not in db.store
    assert db.store["sourcing_prospects"][0]["status"] == "disqualified"
    assert "skip_reseller" in db.store["sourcing_prospects"][0]["note"]


def test_qualify_drops_a_non_us_store_before_reading_its_catalogue():
    """The country is the cheapest disqualifier there is. Without this gate the
    scorer put oglmove.com — a Hong Kong store — at 76 and a whole contact pass
    was spent on a company we can never write to."""
    db = FakeDB()
    db.store["sourcing_prospects"] = [{
        "domain": "oglmove.com", "myshopify_handle": "oglmove", "status": "discovered",
        "tranco_rank": 150_063, "country": "HK", "currency": "USD",
    }]
    fetcher = FakeFetcher({})           # never asked for a page
    got = sourcing.qualify(db, fetcher, log=quiet)
    assert got["disqualified"] == 1 and got["qualified"] == 0
    assert fetcher.calls == []
    assert db.store["sourcing_prospects"][0]["status"] == "disqualified"
    assert "HK" in db.store["sourcing_prospects"][0]["note"]
