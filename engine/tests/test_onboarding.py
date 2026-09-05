import hashlib

from hubricon_engine import onboarding
from hubricon_engine.onboarding import email_spec, guess_name_parts, is_internal, render_html, render_text


def test_internal_addresses_never_become_prospects_or_clients():
    assert is_internal("hagen.hds@gmail.com")
    assert is_internal("HAGEND.S25@gmail.com")
    assert is_internal("dryrun@hubricon.internal")
    assert is_internal("anyone@gethubricon.com")
    assert is_internal("someone@example.com")
    assert is_internal("real@brand.com", "John Doe")
    assert not is_internal("real@brand.com", "Priya Patel")
    assert is_internal("")


def test_mint_token_stores_only_the_hash():
    calls = []

    class RPC:
        def __init__(self, name, params):
            calls.append((name, params))

        def execute(self):
            return None

    class DB:
        def rpc(self, name, params):
            return RPC(name, params)

    token = onboarding.mint_token(DB(), "client-1", "audit intake")
    assert 40 <= len(token) <= 60
    names = [c[0] for c in calls]
    assert names == ["revoke_intake_tokens", "create_intake_token"]
    stored = calls[1][1]["p_token_hash"]
    assert stored == hashlib.sha256(token.encode()).hexdigest()
    assert token not in str(calls[1][1])


def test_welcome_email_leads_with_the_upload_page():
    link = "https://www.hubricon.com/intake?t=abc"
    spec = email_spec("welcome", "Priya Patel", link)
    text = render_text(spec)
    html = render_html(spec)
    assert text.startswith("Hi Priya,")
    assert text.index(link) < text.index("Prefer to grant a seat")  # upload path first, seat second
    assert "24 hours" in text and "first month is free" in text
    assert link in html and "<ol" in html and "Hubricon" in html


def test_all_kinds_render_and_greet_unknown_names():
    for kind in ("welcome", "files", "nudge", "teardown_ready"):
        spec = email_spec(kind, None, "https://x/intake?t=1", "https://x/portal")
        assert render_text(spec).startswith("Hi there,")
        assert spec["subject"]
    assert "https://x/portal" in render_text(email_spec("teardown_ready", "Sam", "l", "https://x/portal"))


def test_name_split():
    assert guess_name_parts("Priya Patel") == ("Priya", "Patel")
    assert guess_name_parts("Cher") == ("Cher", None)
    assert guess_name_parts("") == (None, None)


def test_the_export_list_follows_the_platform():
    amazon = render_text(email_spec("files", "Sam", "https://x/intake?t=1", platform="amazon"))
    shopify = render_text(email_spec("files", "Sam", "https://x/intake?t=1", platform="shopify"))
    both = render_text(email_spec("files", "Sam", "https://x/intake?t=1", platform="both"))
    assert "SKU Economics" in amazon and "Shopify admin" not in amazon
    assert "Shopify admin" in shopify and "Seller Central" not in shopify
    assert "SKU Economics" not in shopify and "Meta Ads Manager" in shopify
    # both platforms: every line says which one it belongs to, and the shared
    # cost template is asked for once, not twice
    assert "Amazon — " in both and "Shopify — " in both
    assert both.count("one-row-per-SKU template") == 1
    # the seat instructions follow too
    assert "Seller Central" in render_text(email_spec("welcome", "Sam", "l", platform="amazon"))
    assert "collaborator request" in render_text(email_spec("welcome", "Sam", "l", platform="shopify"))
    # no platform stated is the column default: Amazon, exactly as before
    assert render_text(email_spec("files", "Sam", "l")) == amazon.replace("https://x/intake?t=1", "l")


def test_the_shopify_email_warns_about_the_two_exports_that_catch_people_out():
    """A filtered export ships a slice, and a dated export never downloads —
    Shopify emails it. Both are why an intake stalls; Amazon has neither."""
    shopify = render_text(email_spec("files", "Sam", "l", platform="shopify"))
    both = render_text(email_spec("welcome", "Sam", "l", platform="both"))
    amazon = render_text(email_spec("files", "Sam", "l", platform="amazon"))
    for body in (shopify, both):
        assert "clear any filter" in body
        assert "emailed to you and to the store owner" in body
    assert "emailed to you" not in amazon
    # a multi-location store is told why the products file has no quantities
    assert "Products → Inventory → Export" in shopify


def test_the_welcome_link_carries_the_platform():
    """/welcome leads with the seat the client actually has to grant."""
    link = lambda platform: [b for b in email_spec("welcome", "Sam", "l", platform=platform)["blocks"]
                             if b.get("button") == "Open your welcome page"][0]["url"]
    assert link("shopify").endswith("/welcome?p=shopify")
    assert link("both").endswith("/welcome?p=both")
    assert link("amazon").endswith("/welcome")   # the page's own default shows both seats
    assert link(None).endswith("/welcome")


def test_platform_read_from_the_application_gate():
    from hubricon_engine.onboarding import platform_from_answers as p

    # the gate's own utm_content string, however the routine stored it
    assert p({"utm_content": "rev:$1M–$5M|model:Private label|skus:10–50 SKUs|fit:core|channel:Shopify"}) == "shopify"
    assert p({"notes": "channel: Both"}) == "both"
    assert p({"channel": "Amazon"}) == "amazon"
    assert p({"platform": "shopify"}) == "shopify"
    # nothing recognisable leaves the column default alone rather than guessing
    assert p({"rev": "$1M–$5M"}) is None
    assert p({"channel": "Walmart"}) is None
    assert p({}) is None and p(None) is None
