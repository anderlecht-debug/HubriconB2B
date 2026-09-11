import io
import json
import urllib.error

from hubricon_engine import notify


class _Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_send_email_names_its_client_and_posts_the_full_payload(monkeypatch):
    # Cloudflare (error 1010) refuses Python's default user agent at api.resend.com;
    # found 2026-09-02 when the teardown_ready email silently failed.
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        seen["body"] = json.loads(req.data)
        return _Response(b'{"id":"x"}')

    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    ok = notify.send_email("to@x.com", "Subj", "plain", html="<p>h</p>",
                           sender="Hagen <h@hubricon.com>", reply_to="h@hubricon.com")
    assert ok
    assert seen["headers"]["user-agent"].startswith("Hubricon-engine/")
    assert seen["headers"]["authorization"] == "Bearer re_test"
    assert seen["body"] == {"from": "Hagen <h@hubricon.com>", "to": ["to@x.com"], "subject": "Subj",
                            "text": "plain", "html": "<p>h</p>", "reply_to": "h@hubricon.com"}


def test_send_email_reports_http_failures_and_is_a_noop_without_a_key(monkeypatch, capsys):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    assert notify.send_email("to@x.com", "s", "t") is False

    def blocked(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b"error code: 1010"))

    monkeypatch.setattr(notify.urllib.request, "urlopen", blocked)
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    assert notify.send_email("to@x.com", "s", "t") is False
    assert "HTTP 403 error code: 1010" in capsys.readouterr().err


def test_the_watch_and_the_veto_notice_close_on_the_record_line_when_given():
    """Every client email ends on the Profit Record. The line is optional so
    a footer failure can never hold a notice hostage."""
    line = "Your Profit Record: $5,415 proven since day one · $2,400 found and filed, not yet banked · $0 billed to date."
    text, html = notify.alert_email_body("Acme", [{"severity": "warning", "message": "SKU-1 stockout in 9 days."}],
                                         "Dana", "https://x/portal", record_line=line)
    assert text.rstrip().endswith(line) or line in text.split("SKU-1")[1]
    assert line in html
    plain, _ = notify.alert_email_body("Acme", [{"severity": "warning", "message": "SKU-1 stockout in 9 days."}], "Dana")
    assert "Your Profit Record:" not in plain

    from datetime import datetime
    d = [{"action_text": "Raise SKU-1 by 3%.", "expected_impact_usd": 400, "mandate": "standing"}]
    text, html = notify.directive_email_body({"contact_name": "Dana"}, d, datetime(2026, 9, 14, 9),
                                             "https://x/portal", record_line=line)
    assert line in text and line in html
    assert text.index("nothing would move") < text.index(line)      # the record is the last word
    plain, _ = notify.directive_email_body({"contact_name": "Dana"}, d, datetime(2026, 9, 14, 9), "https://x/portal")
    assert "Your Profit Record:" not in plain


def test_the_veto_notice_says_an_unanswered_explicit_move_lapses():
    """issue.lapse_unanswered retires an explicit-mandate move after three
    weeks of silence, so the notice must say that, not 'however long that
    takes': silence is not consent, and it is not an open-ended wait either."""
    from datetime import datetime
    from hubricon_engine.issue import EXPLICIT_LAPSE_DAYS
    d = [{"action_text": "Reorder 400 units of SKU-1.", "expected_impact_usd": 900, "mandate": "explicit"}]
    text, html = notify.directive_email_body({"contact_name": "Dana"}, d, datetime(2026, 9, 14, 9), "https://x/portal")
    line = ("Outside your mandate — these wait for your explicit yes; after three weeks "
            "without an answer they lapse and nothing happens:")
    assert line in text and line in html
    assert "however long that takes" not in text
    assert EXPLICIT_LAPSE_DAYS == 21                          # 'three weeks' is the engine's number
