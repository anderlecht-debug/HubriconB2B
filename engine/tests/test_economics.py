"""The unit-economics report: its arithmetic on a synthetic month, what it says
with no clients, the founder's log, the calendar's automatic minutes, and the
two things held in step with files outside the engine (the migration's seed,
the workflows' schedule)."""

import math
import re
import sys
import types
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from hubricon_engine import economics, meter
from econdb import EconDB

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
OCT = date(2026, 10, 1)


@pytest.fixture(autouse=True)
def _unbound():
    meter.unbind()
    yield
    meter.unbind()


def _client(cid, name, email, status="active", **kw):
    return {"id": cid, "company_name": name, "contact_email": email, "contact_name": name.split()[0],
            "status": status, "retainer_started_at": None, "exit_trued_up_at": None,
            "updated_at": "2026-11-01T00:00:00+00:00", **kw}


def _ev(n, at, service, unit, q, client=None, prospect=None, item=None, component=None,
        runner="github_actions", detail=None):
    return {"id": n, "occurred_at": at, "client_id": client, "prospect_id": prospect, "service": service,
            "unit": unit, "quantity": q, "item": item, "component": component, "job": None, "runner": runner,
            "detail": detail or {}}


def _job(n, at, command, seconds, run_id=None, job=None, runner="github_actions"):
    detail = {"outcome": "ok"}
    if runner == "github_actions":
        detail.update(github_run_id=run_id, github_run_attempt="1", github_job=job)
    return _ev(n, at, "engine", "seconds", seconds, item=command, component="job", runner=runner, detail=detail)


def _t(n, on, minutes, client=None, prospect=None, source="logged", basis="logged", what="work", ref=None):
    return {"id": f"t{n}", "occurred_on": on, "minutes": minutes, "client_id": client, "prospect_id": prospect,
            "source": source, "basis": basis, "what": what, "ref": ref}


def _founder(key, v):
    return {"key": key, "value": v, "unit": "", "basis": "founder", "note": "set in the test"}


def _october(**override):
    """Three accounts in October 2026, one pending, one gone, one internal."""
    tables = dict(
        clients=[
            _client("c1", "Acme Co", "dana@acmeco.co", retainer_started_at="2026-09-01T00:00:00+00:00"),
            _client("c2", "Beta Brands", "ops@betabrands.co"),               # kickoff on 10 Oct, by the mandate
            _client("c3", "Gamma Goods", "hi@gammagoods.co", status="pending"),   # never said yes
            _client("c4", "Delta Home", "d@deltahome.co", status="churned",
                    retainer_started_at="2026-06-01T00:00:00+00:00", exit_trued_up_at="2026-09-20T10:00:00+00:00"),
            _client("c5", "Echo Co", "e@echoco.co", retainer_started_at="2026-08-01T00:00:00+00:00"),
            _client("c9", "Test", "hagen@hubricon.com", retainer_started_at="2026-01-01T00:00:00+00:00"),
        ],
        invoices=[
            {"id": "i1", "client_id": "c1", "stripe_invoice_id": "in_1", "status": "paid", "amount_due": 6000,
             "amount_paid": 6000, "refunded_usd": 0, "period_start": "2026-10-01"},
            {"id": "i2", "client_id": "c5", "stripe_invoice_id": "in_2", "status": "void", "amount_due": 6000,
             "amount_paid": 0, "refunded_usd": 0, "period_start": "2026-10-01"},
            {"id": "i3", "client_id": "c9", "stripe_invoice_id": "in_3", "status": "paid", "amount_due": 6000,
             "amount_paid": 6000, "refunded_usd": 0, "period_start": "2026-10-01"},      # internal: nobody's revenue
        ],
        usage_events=[
            _ev(1, "2026-10-05T11:00:00+00:00", "engine", "seconds", 300, client="c1", component="sweep",
                detail={"started_at": "2026-10-05T10:55:00+00:00"}),
            _ev(2, "2026-10-14T14:10:00+00:00", "engine", "seconds", 120, client="c1", component="issue",
                detail={"started_at": "2026-10-14T14:08:00+00:00"}),
            _ev(3, "2026-10-16T14:10:00+00:00", "engine", "seconds", 180, client="c2", component="issue",
                detail={"started_at": "2026-10-16T14:07:00+00:00"}),
            _ev(4, "2026-10-08T13:00:00+00:00", "engine", "seconds", 240, client="c3", component="teardown",
                detail={"started_at": "2026-10-08T12:56:00+00:00"}),
            _ev(5, "2026-10-14T14:09:00+00:00", "anthropic", "input_tokens", 100000, client="c1",
                item="claude-fable-5-1", component="narrate"),
            _ev(6, "2026-10-14T14:09:00+00:00", "anthropic", "output_tokens", 20000, client="c1",
                item="claude-fable-5-1", component="narrate"),
            _ev(7, "2026-10-15T14:09:00+00:00", "anthropic", "input_tokens", 200000, client="c2",
                item="claude-opus-4-8", component="narrate"),
            _ev(8, "2026-10-15T14:09:00+00:00", "anthropic", "output_tokens", 40000, client="c2",
                item="claude-opus-4-8", component="narrate"),
            _ev(9, "2026-10-08T09:00:00+00:00", "anthropic", "input_tokens", 10000, prospect="p1",
                item="claude-opus-5", component="triage"),
            _ev(10, "2026-10-08T09:00:00+00:00", "anthropic", "output_tokens", 2000, prospect="p1",
                item="claude-opus-5", component="triage"),
            _ev(11, "2026-10-09T09:00:00+00:00", "anthropic", "input_tokens", 20000, item="claude-opus-5",
                component="narrate", runner="local"),                              # by hand: nobody's
            _ev(12, "2026-10-14T14:09:30+00:00", "elevenlabs", "characters", 2000, client="c1", component="tts"),
            _ev(13, "2026-10-20T14:09:30+00:00", "elevenlabs", "characters", 1000, client="c5", component="tts"),
            _ev(14, "2026-10-14T14:10:00+00:00", "resend", "emails", 3, client="c1", component="email"),
            _ev(15, "2026-10-08T13:00:00+00:00", "resend", "emails", 2, client="c3", component="onboarding"),
            _ev(16, "2026-10-12T13:17:00+00:00", "resend", "emails", 30, component="email"),
            _ev(17, "2026-10-12T13:17:00+00:00", "resend", "emails", 1, client="c9", component="email"),
            _job(18, "2026-10-05T11:16:00+00:00", "sweep", 900, "1001", "sweep"),
            _job(19, "2026-10-05T11:17:00+00:00", "calibrate", 60, "1001", "sweep"),
            _job(20, "2026-10-14T14:07:00+00:00", "issue", 400, "1002", "issue"),
            _job(21, "2026-10-14T14:07:30+00:00", "watch", 20, "1002", "issue"),
            _job(22, "2026-10-01T00:18:00+00:00", "operator", 50, "2001", "operator"),
            _job(23, "2026-10-01T01:18:00+00:00", "operator", 50, "2002", "operator"),
            _job(24, "2026-10-01T02:18:00+00:00", "operator", 50, "2003", "operator"),
            _job(25, "2026-10-03T09:00:00+00:00", "operator", 45, runner="local"),
        ],
        model_runs=[
            {"id": "r1", "client_id": "c1", "status": "succeeded", "started_at": "2026-10-05T10:56:00+00:00",
             "finished_at": "2026-10-05T10:58:00+00:00"},        # inside the sweep's section: counted there
            {"id": "r2", "client_id": "c5", "status": "succeeded", "started_at": "2026-10-12T15:00:00+00:00",
             "finished_at": "2026-10-12T15:10:00+00:00"},        # by hand on the Mac: 600 s, no runner minute
        ],
        founder_time=[
            _t(1, "2026-10-05", 90, client="c1", what="pricing review"),
            _t(2, "2026-10-20", 30, client="c1", what="claims"),
            _t(3, "2026-10-10", 45, client="c2", source="kickoff", basis="stated", what="Kickoff", ref="kickoff:c2"),
            _t(4, "2026-10-02", 20, client="c2", source="booking", basis="stated", what="Margin audit (booked)",
               ref="booking:b0"),                                   # before the kickoff: winning them
            _t(5, "2026-10-06", 60, what="Monday review of every account"),
            _t(6, "2026-10-08", 15, prospect="p1", what="answered a fee question"),
            _t(7, "2026-10-09", 25, client="c3", what="teardown walkthrough"),
        ],
        mandates=[{"id": "m1", "client_id": "c2", "agreed_at": "2026-10-10T15:00:00+00:00"}],
        bookings=[],
        cost_config=[_founder("founder.hourly_rate_usd", 120), _founder("founder.working_hours_per_week", 45),
                     _founder("rate.github_actions.usd_per_minute", 0.01),
                     _founder("rate.github_actions.included_minutes", 0),
                     _founder("rate.github_actions.setup_seconds_per_job", 30),
                     _founder("rate.elevenlabs.included_characters", 1000)],
        prospects=[{"id": "p1", "email": "lee@zetabrand.co"}],
    )
    tables.update(override)
    return EconDB(**tables)


def _view(db, month=OCT, now=NOW):
    return economics.month_view(economics.load(db, economics._add_months(month, -11), now), month, now)


def test_a_synthetic_month_adds_up():
    v = _view(_october())
    assert [r["name"] for r in v["accounts"]] == ["Acme Co", "Beta Brands", "Echo Co"]
    acme, beta, echo = v["accounts"]
    # Revenue as Stripe mirrored it; the internal client's invoice is nobody's revenue.
    assert (acme["stood"], echo["voided"], v["total"]["stood"], v["total"]["voided"]) == (6000, 6000, 6000, 6000)
    # Minutes on each account, plus an even share of the 60 logged to all of them.
    assert (acme["minutes"], beta["minutes"], echo["minutes"]) == (140, 65, 20)
    assert v["minutes_per_account"] == 75 and v["logged_accounts"] == 1
    assert (acme["founder_usd"], beta["founder_usd"], echo["founder_usd"]) == (280, 130, 40)
    # Engine seconds: the model run inside the sweep's timed section is not counted twice; the one by hand is.
    assert (acme["seconds"], beta["seconds"], echo["seconds"]) == (420, 180, 600)
    # Runner minutes: two commands in one GitHub job are one billed job, rounded up once with its setup.
    r = v["runner"]
    assert r["billed_minutes"] == 17 + 8 + 3 * 2 and r["jobs"] == 5 and r["local_seconds"] == 45
    assert r["bill"] == pytest.approx(0.31)
    assert (r["account_minutes"], r["acquisition_minutes"], r["machine_minutes"]) == (10, 4, 17)
    assert (acme["compute"], beta["compute"], echo["compute"]) == pytest.approx((0.07, 0.03, 0.0))
    # Third-party: tokens at each model's rate, characters past the quota spread by use, Stripe's fees.
    assert acme["third_party"] == pytest.approx(1.00 + 1.00 + 0.40 + 29.00)
    assert beta["third_party"] == pytest.approx(2.00) and echo["third_party"] == pytest.approx(0.20)
    # Cost to serve, contribution, and the book.
    assert (acme["cost_to_serve"], beta["cost_to_serve"], echo["cost_to_serve"]) == \
        pytest.approx((311.47, 132.03, 40.20))
    assert acme["contribution"] == pytest.approx(5688.53) and beta["contribution"] == pytest.approx(-132.03)
    assert v["total"]["contribution"] == pytest.approx(6000 - 483.70)
    assert v["cost_per_account"] == pytest.approx(483.70 / 3)
    # The fixed base: the platform's placeholders, runner minutes nobody's, usage nobody's.
    assert v["platform"] == 127 and v["fixed_total"] == pytest.approx(127 + 0.17 + 0.10)
    assert v["fixed_per_account"] == pytest.approx(127.27 / 3)
    assert v["after_fixed"] == pytest.approx(6000 - 483.70 - 127.27)
    # Capacity: a 45-hour week is 11,700 minutes a month; at 75 an account, 156 accounts.
    assert v["available_minutes"] == pytest.approx(11700) and v["capacity"] == 156
    assert v["capacity_status"] == "ok"
    # Winning accounts stays out of cost to serve.
    a = v["acquisition"]
    assert (a["minutes"], a["founder_usd"]) == (60, 120)
    assert (a["usage_usd"], a["compute_usd"]) == pytest.approx((0.10, 0.04))
    assert a["new_accounts"] == ["Beta Brands"] and a["per_account_won"] == pytest.approx(120.14)
    assert v["unpriced"] == {} and v["warnings"] == []


def test_the_page_labels_every_figure_and_draws_the_scale_curve():
    text = economics.report(_october(), OCT, NOW)
    assert "[m] measured" in text and "[a] assumed" in text
    assert "22 of 30 prices and rates are placeholders" in text
    assert "3 accounts served [m]" in text
    assert re.search(r"Acme Co\s+\$6,000\.00\s+\$0\.00\s+\$0\.07\s+\$31\.40\s+140\s+\$280\.00\s+\$311\.47\s+"
                     r"\$5,688\.53", text)
    assert re.search(r"Echo Co\s+\$0\.00\s+\$6,000\.00\s+\$0\.00\s+\$0\.20\s+20\s+\$40\.00\s+\$40\.20\s+-\$40\.20",
                     text)
    assert "Minutes include 20 each of the 60 logged to all accounts" in text
    assert "Founder time at $120 an hour (founder's figure)" in text
    assert re.search(r"Founder minutes per account-month\s+75 \[m\]\s+\(225 over 3 accounts; 1 of 3 carry "
                     r"hand-logged time\)", text)
    assert re.search(r"Cost to serve per account\s+\$161\.23 \[a\]\n", text)
    assert re.search(r"Capacity\s+156 accounts \[a\]  \(a 45-hour week, founder's figure: 11,700 minutes a month "
                     r"÷ 75 per account\)", text)
    assert "No invoice this month for Beta Brands [m]: a Proving Month, or billing not started." in text
    assert re.search(r"supabase\s+\$25\.00\s+placeholder", text)
    assert "GitHub runner minutes  31 billed [a]: 5 job runs recorded [m]" in text
    assert "only 5 of the 779 scheduled runs were recorded [m], so these minutes are a floor" in text
    assert "by hand on the Mac: 0.8 minutes [m], not billed" in text
    assert re.search(r"elevenlabs characters\s+3,000\s+\$0\.60\s+3,000 of 1,000 included \(founder's figure\), "
                     r"past the quota", text)
    assert re.search(r"anthropic claude-fable-5-1 output_tokens\s+20,000\s+\$1\.00\s+placeholder rate", text)
    assert "1 account began service (Beta Brands): $120.14 per account won [a]" in text
    # The curve starts where the data does (Delta Home's June) and ends on the month.
    assert [line.split()[0] for line in text.split("Scale curve")[1].splitlines()[3:8]] == \
        ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    assert re.search(r"2026-10\s+3\s+75\s+\$161\.23\s+\$42\.42\s+\$203\.66", text)
    # Before anything was recorded a month is blank, never a zero that looks measured.
    assert re.search(r"2026-06\s+1\s+—\s+—\s+\$127\.00\s+—\n", text)
    assert "— nothing recorded on that month's accounts" in text


def test_with_no_clients_it_says_so_and_shows_only_the_fixed_base():
    db = EconDB(clients=[], invoices=[], usage_events=[], model_runs=[], founder_time=[], bookings=[],
                mandates=[], cost_config=[], prospects=[])
    now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    text = economics.report(db, date(2026, 9, 1), now)
    assert "Unit economics — 2026-09, month to date (day 25 of 30)" in text
    assert "No accounts were served in 2026-09" in text and "no capacity figure" in text
    assert "Fixed base  $127.00 a month [a], carried by no account" in text
    assert "28 of 30 prices and rates are placeholders" in text
    assert re.search(r"instantly\s+\$37\.00\s+placeholder", text)
    # No figure that needs an account to divide by is printed at all.
    for absent in ("accounts served", "Cost to serve per account", "Capacity ", "Contribution",
                   "per account won [a]", "After the fixed base"):
        assert absent not in text, absent
    # The runner minutes it cannot measure are a floor from the schedule, not a guess.
    assert "not measured: no scheduled job recorded this month. The schedule fired 615 times" in text
    assert "no account began service this month" in text
    assert re.search(r"2026-09\s+0\s+—\s+—\s+—\s+—\s+month to date", text)


def test_a_missing_table_is_a_named_status_and_never_a_crash():
    db = EconDB(missing={"usage_events", "founder_time", "cost_config"},
                clients=[_client("c1", "Acme Co", "dana@acmeco.co", retainer_started_at="2026-09-01T00:00:00+00:00")],
                invoices=[{"id": "i1", "client_id": "c1", "status": "paid", "amount_due": 6000, "amount_paid": 6000,
                           "period_start": "2026-10-01"}],
                model_runs=[], bookings=[], mandates=[], prospects=[])
    text = economics.report(db, OCT, NOW)
    for table in ("usage_events", "founder_time", "cost_config"):
        assert f"{table} is not there" in text
    assert meter.MIGRATION in text
    assert re.search(r"Founder minutes per account-month\s+not measured", text)
    assert "(without compute, third-party usage, founder time: not measured)" in text
    assert re.search(r"Acme Co\s+\$6,000\.00\s+\$0\.00\s+—\s+\$29\.00\s+—\s+—", text)


def test_tokens_without_a_rate_are_shown_unpriced_until_the_founder_sets_one():
    acme = _client("c1", "Acme Co", "dana@acmeco.co", retainer_started_at="2026-09-01T00:00:00+00:00")
    usage = [_ev(1, "2026-10-05T10:00:00+00:00", "anthropic", "input_tokens", 50000, client="c1",
                 item="claude-next-9", component="narrate")]
    db = EconDB(clients=[acme], invoices=[], usage_events=usage, model_runs=[], founder_time=[], bookings=[],
                mandates=[], cost_config=[], prospects=[])
    v = _view(db)
    assert v["accounts"][0]["third_party"] == 0
    assert v["unpriced"] == {("anthropic", "claude-next-9", "input_tokens"): 50000}
    text = economics.render(v, [economics.curve_row(v)])
    assert "no rate: hubricon economics --set rate.anthropic.claude-next-9.input_usd_per_mtok <usd>" in text
    assert economics.set_config(db, "rate.anthropic.claude-next-9.input_usd_per_mtok", "8") == \
        "rate.anthropic.claude-next-9.input_usd_per_mtok = 8 usd/1M tokens (founder's figure)."
    v = _view(db)
    assert v["accounts"][0]["third_party"] == pytest.approx(0.40) and v["unpriced"] == {}
    assert re.search(r"claude-next-9 input_tokens\s+50,000\s+\$0\.40\s+founder's figure rate",
                     economics.render(v, [economics.curve_row(v)]))


def test_the_founders_figure_replaces_a_placeholder_and_says_whose_it_is():
    db = EconDB(cost_config=[])
    assert economics.set_config(db, "founder.hourly_rate_usd", "200") == "founder.hourly_rate_usd = 200 usd/hour (founder's figure)."
    assert economics.set_config(db, "fixed.domains", "3.5").endswith("usd/month (founder's figure).")
    for key, raw in (("founder.shoe_size", "11"), ("fixed.supabase", "-1"), ("fixed.supabase", "lots")):
        with pytest.raises(ValueError):
            economics.set_config(db, key, raw)
    cfg, status = economics.load_config(db)
    assert status == "ok" and cfg["founder.hourly_rate_usd"]["value"] == 200
    assert cfg["founder.hourly_rate_usd"]["basis"] == "founder" and cfg["fixed.supabase"]["basis"] == "placeholder"
    listing = economics.render_config(cfg, status)
    assert listing.startswith("cost_config: 31 inputs, 27 of them placeholders")
    assert re.search(r"fixed\.domains\s+3\.5\s+usd/month\s+founder", listing)
    # A row the founder deletes falls back to its placeholder, and says so.
    cfg, status = economics.load_config(EconDB(missing={"cost_config"}))
    assert status == "missing" and cfg["founder.hourly_rate_usd"] == {
        "value": 150.0, "unit": "usd/hour", "basis": "placeholder",
        "note": "the shadow price of one founder hour in cost to serve; set your own"}
    assert "the table is not there" in economics.render_config(cfg, status)


def test_capacity_is_an_upper_bound_when_only_the_calendar_speaks_and_absent_with_no_minutes():
    acme = _client("c1", "Acme Co", "dana@acmeco.co", retainer_started_at="2026-09-01T00:00:00+00:00")
    base = dict(clients=[acme], invoices=[], usage_events=[], model_runs=[], bookings=[], mandates=[],
                cost_config=[], prospects=[])
    v = _view(EconDB(founder_time=[_t(1, "2026-10-09", 45, client="c1", source="kickoff", basis="stated")], **base))
    assert v["capacity_status"] == "calendar_only" and v["logged_accounts"] == 0
    assert v["capacity"] == math.floor(v["available_minutes"] / 45)
    assert "an upper bound: only the calendar's minutes" in economics.render(v, [economics.curve_row(v)])
    v = _view(EconDB(founder_time=[], **base))
    assert v["capacity"] is None and v["capacity_status"] == "no_minutes"
    assert "not computable: no founder minutes on any account this month" in \
        economics.render(v, [economics.curve_row(v)])


def test_a_month_to_date_paces_its_minutes_to_the_whole_month():
    acme = _client("c1", "Acme Co", "dana@acmeco.co", retainer_started_at="2026-09-01T00:00:00+00:00")
    db = EconDB(clients=[acme], invoices=[], usage_events=[], model_runs=[], bookings=[], mandates=[],
                cost_config=[], prospects=[], founder_time=[_t(1, "2026-10-05", 60, client="c1")])
    now = datetime(2026, 10, 16, tzinfo=timezone.utc)          # 15 of 31 days gone
    v = _view(db, OCT, now)
    assert v["elapsed"] == pytest.approx(15 / 31)
    assert v["minutes_per_account"] == 60 and v["minutes_paced"] == pytest.approx(60 * 31 / 15)
    assert v["capacity"] == math.floor(v["available_minutes"] / (60 * 31 / 15))
    assert re.search(r"124 at this month's pace \[a\]", economics.render(v, [economics.curve_row(v)]))
    with pytest.raises(ValueError, match="has not started"):
        economics.report(db, date(2026, 11, 1), now)


def test_the_calendar_writes_each_fact_once_and_never_over_a_correction():
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    bookings = [
        {"id": "b1", "client_id": "c1", "invitee_email": "dana@acmeco.co", "event_type": "20 Minute Meeting",
         "starts_at": "2026-10-01T15:00:00+00:00", "is_test": False},
        {"id": "b2", "client_id": "c1", "invitee_email": "dana@acmeco.co", "event_type": "Kickoff",
         "starts_at": "2026-10-09T15:00:00+00:00", "is_test": False},
        {"id": "b3", "client_id": None, "invitee_email": "Lee@ZetaBrand.co", "event_type": "Margin audit",
         "starts_at": "2026-10-03T15:00:00+00:00", "is_test": False},
        {"id": "b4", "client_id": "c1", "invitee_email": "dana@acmeco.co", "event_type": "Kickoff",
         "starts_at": "2026-10-30T15:00:00+00:00", "is_test": False},                 # has not happened yet
        {"id": "b5", "client_id": None, "invitee_email": "john@brand.co", "event_type": "20 min",
         "starts_at": "2026-10-02T15:00:00+00:00", "is_test": True},                  # a test booking
        {"id": "b6", "client_id": "c9", "invitee_email": "hagen@hubricon.com", "event_type": "20 min",
         "starts_at": "2026-10-02T15:00:00+00:00", "is_test": False},                 # the founder's own
    ]
    mandates = [{"id": "m1", "client_id": "c1", "agreed_at": "2026-10-09T16:00:00+00:00"},  # the booking covers it
                {"id": "m2", "client_id": "c2", "agreed_at": "2026-10-12T16:00:00+00:00"}]  # no Kickoff booked
    db = EconDB(clients=[_client("c1", "Acme Co", "dana@acmeco.co"), _client("c2", "Beta Brands", "ops@betabrands.co"),
                         _client("c9", "Test", "hagen@hubricon.com")],
                bookings=bookings, mandates=mandates, founder_time=[], cost_config=[],
                prospects=[{"id": "p1", "email": "lee@zetabrand.co"}])
    assert economics.sync_calendar(db, now) == (4, "ok")
    got = sorted((r["ref"], r["minutes"], r["basis"], r["source"], r["client_id"], r["prospect_id"], r["occurred_on"])
                 for r in db.rows("founder_time"))
    assert got == [("booking:b1", 20.0, "scheduled", "booking", "c1", None, "2026-10-01"),
                   ("booking:b2", 45.0, "stated", "kickoff", "c1", None, "2026-10-09"),
                   ("booking:b3", 20.0, "stated", "booking", None, "p1", "2026-10-03"),
                   ("kickoff:c2", 45.0, "stated", "kickoff", "c2", None, "2026-10-12")]
    assert economics.sync_calendar(db, now) == (0, "ok")                  # twice is once
    no_show = next(r for r in db.rows("founder_time") if r["ref"] == "booking:b3")
    no_show["minutes"] = 0                                                # the founder marks a no-show
    assert economics.sync_calendar(db, now) == (0, "ok") and no_show["minutes"] == 0
    assert economics.sync_calendar(EconDB(missing={"founder_time"}), now) == (0, "missing")
    # The kickoff is where service begins.
    book = economics.load(db, date(2025, 11, 1), now)
    assert book["start"] == {"c1": date(2026, 10, 9), "c2": date(2026, 10, 12)}


def _log(target, minutes, *what, on="2026-10-05"):
    return types.SimpleNamespace(target=target, minutes=str(minutes), what=list(what), on=on)


def test_the_founders_log_lands_on_the_account_the_prospect_or_all(monkeypatch, capsys):
    from hubricon_engine import db as dbmod
    acme = _client("4f1c2a9e-0000-4000-8000-000000000001", "Acme Co", "dana@acmeco.co")
    db = EconDB(clients=[acme], prospects=[{"id": "p1", "email": "lee@zetabrand.co"}], founder_time=[])
    monkeypatch.setattr(dbmod, "connect", lambda: db)
    economics.cmd_log(_log("acme", 30, "pricing", "review"))
    economics.cmd_log(_log("4f1c", "12.5", "claims", "filed", on="2026-10-07"))
    economics.cmd_log(_log("Lee@ZetaBrand.co", 15, "answered", "the", "fee", "question"))
    economics.cmd_log(_log("ALL", 60, "Monday", "review"))
    got = [(r["client_id"], r["prospect_id"], r["minutes"], r["what"], r["source"], r["basis"], r["occurred_on"])
           for r in db.rows("founder_time")]
    assert got == [(acme["id"], None, 30.0, "pricing review", "logged", "logged", "2026-10-05"),
                   (acme["id"], None, 12.5, "claims filed", "logged", "logged", "2026-10-07"),
                   (None, "p1", 15.0, "answered the fee question", "logged", "logged", "2026-10-05"),
                   (None, None, 60.0, "Monday review", "logged", "logged", "2026-10-05")]
    out = capsys.readouterr().out
    assert "Logged 30 min on Acme Co (2026-10-05): pricing review" in out
    assert "2026-10 so far: 42 min on Acme Co." in out
    assert "Logged 15 min on prospect lee@zetabrand.co" in out and "Logged 60 min on all accounts" in out

    for args, why in ((_log("acme co", 0, "nothing"), "more than 0"), (_log("acme co", "abc", "x"), "not a number"),
                      (_log("nobody", 5, "x"), "No client matches"),
                      (_log("who@else.co", 5, "x"), "No client or prospect has the address"),
                      (_log("acme co", 5, "x", on="5 Oct"), "--on takes a date")):
        with pytest.raises(SystemExit) as stop:
            economics.cmd_log(args)
        assert why in str(stop.value.code)
    twins = EconDB(clients=[acme, _client("4f1c2a9e-0000-4000-8000-000000000002", "Acme Home", "h@acmehome.co")],
                   prospects=[], founder_time=[])
    monkeypatch.setattr(dbmod, "connect", lambda: twins)
    with pytest.raises(SystemExit) as stop:
        economics.cmd_log(_log("acme", 5, "x"))                   # two companies say acme: name one
    assert "ambiguous" in str(stop.value.code) and not twins.rows("founder_time")
    economics.cmd_log(_log("acme co", 5, "the whole name still wins"))
    assert twins.rows("founder_time")[0]["client_id"] == acme["id"]
    missing = EconDB(missing={"founder_time"}, clients=[acme], prospects=[])
    monkeypatch.setattr(dbmod, "connect", lambda: missing)
    with pytest.raises(SystemExit) as stop:
        economics.cmd_log(_log("acme co", 5, "x"))
    assert meter.MIGRATION in str(stop.value.code)


def test_the_commands_are_on_the_cli(monkeypatch, capsys):
    from hubricon_engine import cli
    for argv in (["hubricon", "economics", "--help"], ["hubricon", "log", "--help"]):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as stop:
            cli.main()
        assert stop.value.code == 0
    out = capsys.readouterr().out
    assert "--month" in out and "<client|prospect|all> <minutes> <what>" in out


SEED = re.compile(r"\('([^']+)', ([0-9.]+), '([^']*)', '(placeholder|site|founder)', '([^']*)'\)")


def test_the_migration_seeds_exactly_the_codes_defaults_and_is_service_role_only():
    sql = (REPO / "supabase/migrations/20260925000004_unit_economics.sql").read_text()
    seeded = [(k, float(v), u, b, n) for k, v, u, b, n in SEED.findall(sql)]
    assert seeded == [(k, float(v), u, b, n) for k, v, u, b, n in economics.DEFAULTS]
    for table in ("usage_events", "founder_time", "cost_config"):
        assert f"alter table public.{table} enable row level security;   -- service role only" in sql
    assert "create policy" not in sql and "on conflict (key) do nothing" in sql


def test_the_schedule_and_the_scheduled_commands_are_the_workflows():
    crons, commands = {}, set()
    for f in sorted((REPO / ".github/workflows").glob("*.yml")):
        text = f.read_text()
        found = re.search(r'cron:\s*"([^"]+)"', text)
        if found:
            crons[f.stem] = found.group(1)
        commands |= set(re.findall(r"uv run hubricon ([a-z-]+)", text))
    assert crons == economics.SCHEDULE
    assert commands == set(meter.SCHEDULED)
    fired = economics.scheduled_runs(date(2026, 9, 1), date(2026, 10, 1), datetime(2026, 10, 5, tzinfo=timezone.utc))
    assert fired == {"operator": 720, "issue": 30, "sweep": 4}
