from hubricon_engine import outbound
from hubricon_engine.outbound import CAMPAIGN_NAME, campaign_spec


def test_campaign_spec_is_three_plain_text_steps_with_compliance_footer():
    spec = campaign_spec(["hagen@gethubricon.com", "h@gethubricon.com"], "123 Main St, Dallas, TX 75201")
    assert spec["name"] == CAMPAIGN_NAME
    steps = spec["sequences"][0]["steps"]
    assert len(steps) == 3 and all(s["type"] == "email" for s in steps)
    for s in steps:
        body = s["variants"][0]["body"]
        assert "123 Main St" in body and "stop emailing" in body
        assert "{{firstName}}" in body
        assert "TEARDOWN" in body
        assert "<br/>" in body and "\n" not in body  # Instantly wants <br/> line breaks
    assert steps[0]["variants"][0]["subject"]  # first step opens the thread
    assert steps[1]["variants"][0]["subject"] == ""  # follow-ups stay in-thread
    assert spec["text_only"] and spec["insert_unsubscribe_header"] and spec["stop_on_reply"]
    assert not spec["open_tracking"] and not spec["link_tracking"]
    assert spec["email_list"] == ["hagen@gethubricon.com", "h@gethubricon.com"]


def test_daily_limit_scales_with_mailboxes_but_is_capped():
    assert campaign_spec(["a@x.com"], "addr")["daily_limit"] == outbound.PER_MAILBOX_DAILY
    assert campaign_spec(["a@x.com"] * 10, "addr")["daily_limit"] == outbound.CAMPAIGN_DAILY_CAP
    assert campaign_spec([], "addr")["daily_limit"] == outbound.PER_MAILBOX_DAILY


def test_schedule_is_us_business_hours_on_weekdays():
    sched = campaign_spec(["a@x.com"], "addr")["campaign_schedule"]["schedules"][0]
    assert sched["timezone"] == "America/Chicago"
    assert set(sched["days"]) == {"1", "2", "3", "4", "5"}
    assert sched["timing"] == {"from": "08:00", "to": "17:00"}


def test_every_step_word_count_stays_short():
    spec = campaign_spec(["a@x.com"], "addr")
    for s in spec["sequences"][0]["steps"]:
        words = s["variants"][0]["body"].replace("<br/>", " ").split()
        assert len(words) <= 130, len(words)
