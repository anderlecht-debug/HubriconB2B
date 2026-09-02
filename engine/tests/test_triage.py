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
