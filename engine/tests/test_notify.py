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
