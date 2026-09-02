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
