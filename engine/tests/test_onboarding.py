import hashlib
from datetime import date, datetime, timedelta, timezone

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


CALL = datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc)
AGREED = {"start": date(2026, 10, 1), "end": date(2026, 10, 31), "free_end": date(2026, 10, 31), "fee": 6000.0,
          "first_read": False, "has_files": False, "drafts": 0, "next_sweep": datetime(2026, 10, 5, 11, tzinfo=timezone.utc),
          "kickoff_at": None, "veto_hours": 72}


def test_the_proving_month_is_dated_the_way_the_billing_gate_dates_it():
    """`hubricon retainer` used to print start + 30 days; the gate bills calendar
    months from the day of the yes. One arithmetic now, the gate's own."""
    from hubricon_engine import monthly
    for started, free in (("2026-10-01", 1), ("2027-01-31", 1), ("2026-02-15", 2), ("2028-01-30", 1)):
        c = {"retainer_started_at": f"{started}T00:00:00+00:00", "free_months": free}
        pm = onboarding.proving_month(c)
        months = monthly.billing_months(c, date(2030, 1, 1))
        assert (pm["start"], pm["end"]) == (months[0]["start"], months[0]["end"])
        assert pm["free_end"] == months[free - 1]["end"] and months[free - 1]["free"] and not months[free]["free"]
    jan31 = onboarding.proving_month({"retainer_started_at": "2027-01-31T00:00:00+00:00"})
    assert jan31["end"] == date(2027, 2, 27)          # Feb 28 is month 1's first day, not +30 (Mar 2)
    assert onboarding.proving_month({"status": "pending"}) is None


def test_the_agreed_letter_confirms_the_yes_with_dates_and_what_happens_next():
    spec = email_spec("agreed", "Priya Patel", "https://x/intake?t=up", "https://x/portal", platform="amazon",
                      **AGREED)
    text = render_text(spec)
    assert spec["subject"] == "Confirmed: your Proving Month runs October 1 to October 31, 2026"
    assert "This confirms your yes. Managed Profit started on Thursday, October 1, 2026." in text
    assert "from October 1 to October 31, 2026, and it is free whatever it measures" in text
    assert "cleared the $6,000 fee" in text
    assert "the first of those Mondays is October 5" in text
    assert "72 hours after the notice unless you reply no" in text and "nothing in it goes live" in text
    assert "https://x/intake?t=up" in text and "https://x/portal" in text
    assert "Book it on your welcome page" in text
    for retired in ("retainer", "Teardown", "directive", "desk", "ledger", "!", "within the hour"):
        assert retired not in text, retired


def test_the_agreed_letter_says_what_is_true_at_each_point():
    out = lambda **kw: render_text(email_spec("agreed", "Sam", "", "p", **{**AGREED, **kw}))
    sent_files = out(has_files=True)
    assert "written from the files you sent" in sent_files and "upload page" not in sent_files.split("What")[1].split("welcome")[0]
    read_out = out(first_read=True, has_files=True, drafts=3)
    assert "already in Hubricon" in read_out and "sent separately after this letter" in read_out
    nothing = out(first_read=True, has_files=True, drafts=0)
    assert "It found no move to make yet." in nothing and "sent separately" not in nothing
    booked = out(kickoff_at=datetime(2026, 10, 8, 16, tzinfo=timezone.utc))
    assert "Your kickoff is booked for Thursday, October 8 at 16:00 UTC" in booked and "Book it" not in booked
    referred = out(free_end=date(2026, 11, 30))
    assert "your free months run to November 30, 2026" in referred


def test_the_first_read_waits_for_the_core_files_or_a_day_after_the_last_one():
    now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    up = lambda kind, hours_ago, status="parsed": {"report_type": kind, "status": status,
                                                     "uploaded_at": (now - timedelta(hours=hours_ago)).isoformat()}
    r = onboarding.first_read_ready([up("business_report", 2)], "amazon", now)
    assert not r["ready"] and r["missing"] == ["sku_economics"]
    assert r["publish_by"] == now + timedelta(hours=22)
    r = onboarding.first_read_ready([up("business_report", 2), up("sku_economics", 1)], "amazon", now)
    assert r["ready"] and r["missing"] == [] and r["why"] == "core"
    r = onboarding.first_read_ready([up("business_report", 25)], "amazon", now)
    assert r["ready"] and r["missing"] == ["sku_economics"] and r["why"] == "waited"
    # a file that has landed but is not parsed yet holds the clock open
    r = onboarding.first_read_ready([up("business_report", 30), up("cogs", 1, "uploaded")], "amazon", now)
    assert not r["ready"]
    r = onboarding.first_read_ready([up("shopify_orders", 1), up("shopify_products", 1)], "shopify", now)
    assert r["ready"] and r["why"] == "core"
    # data that came through the seat has no uploads and nothing to wait for
    assert onboarding.first_read_ready([], "amazon", now)["ready"]


def test_the_next_sweep_is_the_next_monday_at_eleven_utc():
    assert onboarding.next_sweep(datetime(2026, 10, 1, 9, tzinfo=timezone.utc)) == \
        datetime(2026, 10, 5, 11, tzinfo=timezone.utc)
    assert onboarding.next_sweep(datetime(2026, 10, 5, 10, 59, tzinfo=timezone.utc)) == \
        datetime(2026, 10, 5, 11, tzinfo=timezone.utc)
    assert onboarding.next_sweep(datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc)) == \
        datetime(2026, 10, 12, 11, tzinfo=timezone.utc)


def test_the_call_prep_says_what_the_call_is_and_the_one_thing_to_do_first():
    """On booking, before any yes: no "You're in", no exports homework the call
    does not read, no offer to book the call they just booked. The upload page
    is there, second and optional."""
    link = "https://www.hubricon.com/intake?t=abc"
    spec = email_spec("call_prep", "Priya Patel", link, platform="amazon", call_at=CALL)
    text, html = render_text(spec), render_html(spec)
    assert text.startswith("Hi Priya,")
    assert spec["subject"] == "Your call on Friday, October 2: the one thing to do first"
    assert "Friday, October 2 at 15:00 UTC" in text
    assert "twenty minutes" in text and "Nothing is uploaded" in text
    assert "Fee Preview" in text and "Manage Inventory Health" in text and "Amazon builds them on request" in text
    assert "landed cost as a percentage of price" in text and "ACoS" in text
    # the upload link is the last thing, and optional
    assert text.index("Fee Preview") < text.index(link) and "optional" in text.lower()
    assert "first full read" in text and "Profit Brief No. 001" in text
    for retired in ("You're in", "Welcome aboard", "calendly.com", "Book 20 minutes", "Teardown", "!"):
        assert retired not in text, retired
    assert link in html and "<ol" in html


def test_the_call_prep_follows_the_platform():
    shopify = render_text(email_spec("call_prep", "Sam", "l", platform="shopify", call_at=CALL))
    both = render_text(email_spec("call_prep", "Sam", "l", platform="both", call_at=CALL))
    assert "Shopify admin" in shopify and "Products export" in shopify and "landed cost" in shopify
    assert "Seller Central" not in shopify and "Fee Preview" not in shopify and "ACoS" not in shopify
    assert "Fee Preview" in both and "Shopify admin" in both
    # the Shopify leaks are named the way apply.html's Shopify panel names them,
    # where until 2026-10-01 a Shopify seller read "the costs only your own data shows"
    for body in (shopify, both):
        assert "compare-at" in body and "USPS pound line" in body and "Nothing is uploaded" in body
    assert "aged stock" not in shopify and "low-inventory" not in shopify
    # no time on the booking: the email says where the time is rather than inventing one
    untimed = email_spec("call_prep", "Sam", "l", platform="amazon")
    assert untimed["subject"] == "Your call: the one thing to do first"
    assert "Calendly's invitation has the time" in render_text(untimed)


def test_all_kinds_render_and_greet_unknown_names():
    for kind in ("call_prep", "files", "nudge", "teardown_ready", "downsell", "recovery_welcome"):
        spec = email_spec(kind, None, "https://x/intake?t=1", "https://x/portal")
        assert render_text(spec).startswith("Hi there,")
        assert spec["subject"]
        assert "$3M" not in render_text(spec) and "Teardown" not in render_text(spec)
    assert "https://x/portal" in render_text(email_spec("teardown_ready", "Sam", "l", "https://x/portal"))
    # "You're in" is gone with the email that said it before anyone had said yes
    import pytest
    with pytest.raises(ValueError):
        email_spec("welcome", "Sam", "l")


def test_the_first_read_email_ends_where_the_client_stands():
    booked = render_text(email_spec("teardown_ready", "Sam", "l", "p", stage="booked", call_at=CALL))
    agreed = render_text(email_spec("teardown_ready", "Sam", "l", "p", stage="agreed"))
    called = render_text(email_spec("teardown_ready", "Sam", "l", "p", stage="called"))
    assert "on your call, Friday, October 2 at 15:00 UTC" in booked
    # before a yes there is a baseline, not a Profit Record
    assert "Your Profit Record starts today" not in booked and "if you go ahead" in booked
    assert "Your Profit Record starts today at $0" in agreed
    assert "own notice" in agreed and "before anything in your account changes" in agreed
    assert "own notice" not in called and "calendly" not in called.lower()
    # what the read could not see, in plain words
    short = render_text(email_spec("teardown_ready", "Sam", "l", "p", stage="called",
                                   missing=["sku_economics"]))
    assert "One file was not in when this read was written." in short
    assert "SKU Economics (fees by SKU): without it, Amazon's fees are not split by SKU" in short
    assert "Your upload page stays open for it." in short


def test_the_teardown_email_opens_the_record_at_zero_before_anything_is_touched():
    """Day 0 is the baseline. The client hears that the Record starts at $0
    and that every later move is measured against today, so a number on it
    later is never mistaken for one that was already there."""
    spec = email_spec("teardown_ready", "Sam", "l", "https://x/portal")
    paras = [b["p"] for b in spec["blocks"] if "p" in b]
    baseline = ("Your Profit Record starts today at $0: the baseline is recorded before anything is "
                "touched, so every later move is measured against it.")
    assert baseline in paras
    signin = next(p for p in paras if p.startswith("Sign in with this email address"))
    assert paras.index(baseline) == paras.index(signin) + 1
    assert baseline in render_text(spec)


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
    # the seat instructions in the agreed letter follow too
    assert "Seller Central" in render_text(email_spec("agreed", "Sam", "l", platform="amazon", **AGREED))
    assert "staff account" in render_text(email_spec("agreed", "Sam", "l", platform="shopify", **AGREED))
    # no platform stated is the column default: Amazon, exactly as before
    assert render_text(email_spec("files", "Sam", "l")) == amazon.replace("https://x/intake?t=1", "l")


def test_the_shopify_email_warns_about_the_two_exports_that_catch_people_out():
    """A filtered export ships a slice, and a dated export never downloads —
    Shopify emails it. Both are why an intake stalls; Amazon has neither."""
    shopify = render_text(email_spec("files", "Sam", "l", platform="shopify"))
    both = render_text(email_spec("files", "Sam", "l", platform="both"))
    amazon = render_text(email_spec("files", "Sam", "l", platform="amazon"))
    for body in (shopify, both):
        assert "clear any filter" in body
        assert "emailed to you and to the store owner" in body
    assert "emailed to you" not in amazon
    # a multi-location store is told why the products file has no quantities
    assert "Products → Inventory → Export" in shopify


def test_the_welcome_link_carries_the_platform():
    """/welcome leads with the seat the client actually has to grant. Since
    2026-10-01 it is linked from the agreed letter, after the yes."""
    link = lambda platform: [b for b in email_spec("agreed", "Sam", "l", platform=platform, **AGREED)["blocks"]
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


def test_every_email_says_when_the_first_read_is_written_as_the_schedule_writes_it():
    """The operator writes the first read on its next pass after the core files
    are in, or 24 hours after the last upload (first_read_ready), and GitHub runs
    that pass late. No email may promise it "the moment" a file lands."""
    when = "on our next pass after your core files are in, or 24 hours after your last upload"
    prep = render_text(email_spec("call_prep", "Sam", "https://x/intake?t=1", platform="amazon", call_at=CALL))
    files = render_text(email_spec("files", "Sam", "https://x/intake?t=1"))
    agreed = render_text(email_spec("agreed", "Sam", "https://x/intake?t=1", "p", **AGREED))
    for text in (prep, files, agreed):
        assert when in text
    for kind in ("call_prep", "files", "nudge", "teardown_ready", "downsell", "recovery_welcome"):
        text = render_text(email_spec(kind, "Sam", "https://x/intake?t=1", "https://x/portal", call_at=CALL))
        for promise in ("the moment", "as soon as", "within the hour", "within an hour", "written once"):
            assert promise not in text, (kind, promise)


def test_every_client_email_is_set_in_the_one_look():
    """Inter on white, ink #0a0e17, #3b4250 for what is secondary, one hairline
    rule, the button in ink: the sign-in email's look (supabase/templates/
    magic-link.html), never the old Georgia serif. Blue is for money alone, so a
    letter of prose carries none. The words are unchanged."""
    spec = email_spec("call_prep", "Sam", "https://x/intake?t=1", platform="amazon", call_at=CALL)
    html = render_html(spec)
    assert "font-family:Inter,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif" in html
    for gone in ("Georgia", "Times New Roman", "#1a1a1a", "#555", "#8a8a8a", "Menlo", "#0b5fff"):
        assert gone not in html, gone
    assert "color:#0a0e17" in html and "color:#3b4250" in html
    assert html.count("<hr ") == 1 and "border-top:1px solid #e4e7ec" in html
    assert "background:#0a0e17;color:#ffffff" in html and "border-radius:10px" in html
    assert "Hagen Simmons" in html and ">Hubricon</p>" in html
    path = render_html({"greeting": "Hi,", "blocks": [{"path": "Settings → User Permissions"}]})
    assert "Settings → User Permissions" in path and "monospace" not in path


def test_the_shopify_seat_is_a_staff_account_with_the_ad_accounts_asked_for_apart():
    """A collaborator request needs a Shopify Partner organisation on our side;
    a staff account is the route the owner takes alone. The seat reaches no ad
    account and never Finances (finding 6, 2026-10-01)."""
    from hubricon_engine.onboarding import EXEC_EMAIL, seat_hint
    shop = seat_hint("shopify")
    assert shop.startswith(f"Add {EXEC_EMAIL} as a staff account under Settings → Users → Add users")
    assert "Orders, Analytics, Reports and Marketing to view; Products and Discounts to edit" in shop
    assert "Finances and Settings off" in shop
    # the collaborator route is an alternative the client asks for, never a request we say we send
    assert "if you would rather approve a collaborator request instead, reply and say so" in shop
    assert "we send a collaborator request" not in shop and "Partner" not in shop.replace("Partners)", "")
    # the ad accounts, each on its own
    assert "partner access to your Meta ad account" in shop and "user access to your Google Ads account" in shop
    both = seat_hint("both")
    assert both.startswith(f"Add {EXEC_EMAIL} under Seller Central") and "On Shopify: add " in both
    assert seat_hint("amazon") == seat_hint(None) and "staff account" not in seat_hint("amazon")
