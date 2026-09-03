from hubricon_engine import triage
from hubricon_engine.triage import (
    CALENDLY_URL,
    EXEC_EMAIL,
    SILENT,
    classify_rules,
    draft_for,
    strip_quoted,
)

OUR_EMAIL = (
    "\n\nOn Tue, Sep 2, 2026 at 9:01 AM Hagen Simmons <hagen@gethubricon.com> wrote:\n"
    "> Want one? Reply TEARDOWN and I'll send the upload page\n> Hagen"
)


def test_strip_quoted_removes_history_so_our_keyword_never_classifies():
    body = "Thanks, not the right time for us." + OUR_EMAIL
    assert strip_quoted(body) == "Thanks, not the right time for us."
    assert classify_rules("Re: margin", body) != "wants_teardown"


def test_teardown_keyword_in_the_reply_itself_wins():
    assert classify_rules("Re: margin", "TEARDOWN" + OUR_EMAIL) == "wants_teardown"
    assert classify_rules("Re:", "sure, send me the teardown link") == "wants_teardown"


def test_silent_categories_get_no_draft():
    cases = {
        "bounce": ("Delivery Status Notification (Failure)", "address not found", "mailer-daemon@google.com"),
        "ooo": ("Automatic reply: margin", "I am out of the office until Monday", "x@y.com"),
        "unsubscribe": ("Re:", "Please remove me from your list", "x@y.com"),
        "not_interested": ("Re:", "No thanks.", "x@y.com"),
    }
    for expected, (subject, body, sender) in cases.items():
        cat = classify_rules(subject, body, sender)
        assert cat == expected, (subject, body, cat)
        assert cat in SILENT and draft_for(cat, "Sam") is None


def test_plain_no_is_a_decline_but_no_problem_is_not():
    assert classify_rules("Re:", "No") == "not_interested"
    assert classify_rules("Re:", "no thanks, we're good") == "not_interested"
    assert classify_rules("Re:", "No problem, happy to chat next week?") != "not_interested"


def test_interested_and_not_now_have_templates_with_the_right_links():
    assert classify_rules("Re:", "Interested. How does this work?") == "interested"
    d = draft_for("interested", "Priya Patel")
    assert d.startswith("Great, Priya.") and CALENDLY_URL in d and "TEARDOWN" in d
    assert classify_rules("Re:", "Not right now, circle back in Q1") == "not_now"
    assert "90 days" in draft_for("not_now", None) and "Hi there" not in draft_for("not_now", None)
    d = draft_for("wants_teardown", "Sam")
    assert EXEC_EMAIL in d and "24 hours" in d


def test_questions_are_left_for_a_writer_when_claude_is_off(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    v = triage.triage("Re: margin", "What reports do you need exactly?", "Sam")
    assert v["category"] == "question" and v["draft"] is None and v["reply_status"] == "pending_review"


def test_triage_statuses(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert triage.triage("Re:", "unsubscribe", "Sam")["reply_status"] == "skipped"
    assert triage.triage("Re:", "yes let's talk", "Sam")["reply_status"] == "approved"
    assert triage.triage("Re:", "hmm", "Sam")["category"] == "other"


def test_claude_verdict_is_guarded(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(triage, "classify_claude",
                        lambda s, b, n: {"category": "question", "reply": "Answer " * 200, "reason": ""})
    v = triage.triage("Re:", "Do you work with wholesale sellers?", "Sam")
    # an over-long model reply is discarded, so the message waits for review
    assert v["category"] == "question" and v["reply_status"] == "pending_review"
    monkeypatch.setattr(triage, "classify_claude",
                        lambda s, b, n: {"category": "question", "reply": "Short answer.\n\nHagen", "reason": ""})
    v = triage.triage("Re:", "Do you work with wholesale sellers?", "Sam")
    assert v["reply_status"] == "approved" and v["by"] == "claude"


def test_a_question_that_mentions_the_teardown_is_still_a_question():
    # Found in the 2026-09-02 funnel test: the bare keyword match promised an
    # upload page to someone who only asked how long the teardown takes.
    asks = [
        "Do you need a login to my Seller Central for this, and how long does the teardown take once I send the files?",
        "What does the teardown actually look like? Is it a PDF?",
        "Is the teardown really free or is there a catch?",
    ]
    for body in asks:
        assert classify_rules("Re: margin", body + OUR_EMAIL) == "question", body
    # …while every way of actually asking for it still works
    wants = ["TEARDOWN", "teardown", "Teardown please!", "Sure, send me the teardown link",
             "Yes — I'd like the teardown. Send the upload page.", "let's do the teardown"]
    for body in wants:
        assert classify_rules("Re: margin", body + OUR_EMAIL) == "wants_teardown", body


def test_bare_later_is_not_now_as_step_three_invites():
    assert classify_rules("Re: margin", "later" + OUR_EMAIL) == "not_now"
    assert classify_rules("Re: margin", "Later, thanks." + OUR_EMAIL) == "not_now"
    assert classify_rules("Re: margin", "Later this week I'll send the files — TEARDOWN" + OUR_EMAIL) == "wants_teardown"


def test_claude_tier_names_the_workspace_and_reports_why_it_passed(monkeypatch):
    import types
    import anthropic

    captured = {}

    class FakeMessages:
        def create(self, **kw):
            captured.update(kw)
            return types.SimpleNamespace(stop_reason="end_turn", content=[
                types.SimpleNamespace(type="text", text='{"category": "question", "reply": "Short.\\n\\nHagen", "reason": "asked"}')])

    class FakeClient:
        def __init__(self, **kw):
            captured["client"] = kw
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_test")
    v = triage.classify_claude("Re:", "How long does it take?", "Lee")
    assert captured["client"]["default_headers"] == {"anthropic-workspace-id": "wrkspc_test"}
    assert captured["model"] == triage.MODEL and captured["output_config"] == {"effort": "low"}
    assert v == {"category": "question", "reply": "Short.\n\nHagen", "reason": "asked"}

    # when the model tier fails, triage() says why instead of failing silently
    monkeypatch.setattr(triage, "classify_claude",
                        lambda s, b, n: {"category": None, "reply": None, "reason": "claude failed: 400"})
    v = triage.triage("Re:", "How long does it take?", "Lee")
    assert v["reply_status"] == "pending_review" and v["reason"] == "claude failed: 400"
