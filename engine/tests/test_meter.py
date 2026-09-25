"""The meter: every cost driver counted where it is incurred, attributed to the
account whose work it was, and never able to break the work it counts."""

import io
import types
import urllib.error

import pytest

from hubricon_engine import meter, narrate, notify, triage, tts
from econdb import EconDB

GITHUB_ENV = ("GITHUB_ACTIONS", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "GITHUB_WORKFLOW")


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    for k in GITHUB_ENV:
        monkeypatch.delenv(k, raising=False)
    meter.unbind()
    yield
    meter.unbind()


def _usage(**kw):
    base = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0, "iterations": None}
    base.update(kw)
    return types.SimpleNamespace(**base)


def _events(db, **match):
    return [r for r in db.rows("usage_events") if all(r.get(k) == v for k, v in match.items())]


class _Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_anthropic(monkeypatch, text, model, usage):
    """The SDK client, answering on both the plain and the beta surface."""
    import anthropic

    class Messages:
        def create(self, **kw):
            return types.SimpleNamespace(stop_reason="end_turn", model=model, usage=usage,
                                         content=[types.SimpleNamespace(type="text", text=text)])

    class Client:
        def __init__(self, **kw):
            self.messages = Messages()
            self.beta = types.SimpleNamespace(messages=Messages())

    monkeypatch.setattr(anthropic, "Anthropic", Client)


def test_tokens_come_from_the_responses_own_usage_and_belong_to_the_account_in_scope():
    db = EconDB()
    meter.bind(db)
    reply = types.SimpleNamespace(model="claude-fable-5-1",
                                  usage=_usage(input_tokens=1200, output_tokens=340, cache_read_input_tokens=None))
    with meter.account(client_id="c1", component="issue", timed=False):
        meter.anthropic(reply, "narrate", requested_model="claude-fable-5-1")
    rows = _events(db)
    assert [(r["unit"], r["quantity"]) for r in rows] == [("input_tokens", 1200), ("output_tokens", 340)]
    assert {(r["service"], r["item"], r["client_id"], r["component"], r["runner"]) for r in rows} == \
        {("anthropic", "claude-fable-5-1", "c1", "narrate", "local")}
    assert all(r["detail"] == {"attempt": "served"} for r in rows)
    # Counted outside any scope, it is the machine's own.
    meter.anthropic(reply, "narrate")
    assert _events(db)[-1]["client_id"] is None and _events(db)[-1]["prospect_id"] is None
    # A cache write and a cache read are their own units.
    meter.anthropic(types.SimpleNamespace(model="claude-opus-5", usage=_usage(
        input_tokens=10, cache_creation_input_tokens=4000, cache_read_input_tokens=9000)), "triage")
    assert [(r["unit"], r["quantity"]) for r in _events(db, item="claude-opus-5")] == \
        [("input_tokens", 10), ("cache_write_tokens", 4000), ("cache_read_tokens", 9000)]


def test_a_fallback_reply_is_counted_once_per_attempt_at_the_model_that_ran_it():
    db = EconDB()
    meter.bind(db)
    declined = types.SimpleNamespace(type="message", model="claude-fable-5-1", input_tokens=800, output_tokens=0,
                                     cache_creation_input_tokens=0, cache_read_input_tokens=0)
    served = types.SimpleNamespace(type="fallback_message", model="claude-opus-4-8", input_tokens=900,
                                   output_tokens=300, cache_creation_input_tokens=0, cache_read_input_tokens=0)
    reply = types.SimpleNamespace(model="claude-opus-4-8",
                                  usage=_usage(input_tokens=900, output_tokens=300, iterations=[declined, served]))
    meter.anthropic(reply, "narrate", requested_model="claude-fable-5-1")
    got = [(r["item"], r["unit"], r["quantity"], r["detail"]["attempt"]) for r in _events(db)]
    assert got == [("claude-fable-5-1", "input_tokens", 800, "declined"),
                   ("claude-opus-4-8", "input_tokens", 900, "served"),
                   ("claude-opus-4-8", "output_tokens", 300, "served")]
    # The top-level usage is the served attempt again, and is not added twice.
    assert sum(r["quantity"] for r in _events(db, unit="input_tokens")) == 1700
    assert _events(db)[-1]["detail"]["requested"] == "claude-fable-5-1"


def test_the_narrator_and_the_triage_record_what_the_api_reported_and_return_what_they_always_did(monkeypatch):
    db = EconDB()
    meter.bind(db)
    _fake_anthropic(monkeypatch, "Dear {{first_name}},", "claude-fable-5-1",
                    _usage(input_tokens=5000, output_tokens=700))
    with meter.account(client_id="c1", component="issue", timed=False):
        assert narrate._call_claude("system", "prompt", "claude-fable-5-1") == "Dear {{first_name}},"
    assert [(r["unit"], r["quantity"], r["client_id"], r["component"]) for r in _events(db, service="anthropic")] == \
        [("input_tokens", 5000, "c1", "narrate"), ("output_tokens", 700, "c1", "narrate")]

    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    _fake_anthropic(monkeypatch, '{"category": "question", "reply": "Short.\\n\\nHagen", "reason": "asked"}',
                    "claude-opus-5", _usage(input_tokens=2100, output_tokens=90))
    with meter.account(prospect_id="p1", component="triage", timed=False):
        verdict = triage.classify_claude("Re:", "How long does it take?", "Lee")
    assert verdict == {"category": "question", "reply": "Short.\n\nHagen", "reason": "asked"}
    mine = _events(db, item="claude-opus-5")
    assert [(r["unit"], r["quantity"], r["prospect_id"], r["client_id"], r["component"]) for r in mine] == \
        [("input_tokens", 2100, "p1", None, "triage"), ("output_tokens", 90, "p1", None, "triage")]


def test_speech_is_counted_by_the_character_and_mail_by_the_email_and_only_when_paid_for(monkeypatch, tmp_path):
    db = EconDB()
    meter.bind(db)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "xi")
    monkeypatch.setattr(tts.urllib.request, "urlopen", lambda req, timeout=None: _Response(b"ID3 audio"))
    with meter.account(client_id="c1", component="issue", timed=False):
        tts._elevenlabs("Your record, in one line.", tmp_path / "a.mp3")
    assert (tmp_path / "a.mp3").read_bytes() == b"ID3 audio"

    def refused(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"bad key"))

    monkeypatch.setattr(tts.urllib.request, "urlopen", refused)
    with pytest.raises(tts.TTSUnavailable):
        tts._elevenlabs("A refused request costs nothing.", tmp_path / "b.mp3")
    chars = _events(db, service="elevenlabs")
    assert [(r["unit"], r["quantity"], r["client_id"], r["item"]) for r in chars] == \
        [("characters", len("Your record, in one line."), "c1", tts.ELEVEN_MODEL)]

    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda req, timeout=None: _Response(b'{"id":"x"}'))
    with meter.account(client_id="c2", component="onboarding", timed=False):
        assert notify.send_email("dana@acmeco.co", "Welcome", "text") is True
    monkeypatch.setattr(notify.urllib.request, "urlopen", refused)
    assert notify.send_email("dana@acmeco.co", "Bounced", "text") is False
    mail = _events(db, service="resend")
    assert [(r["unit"], r["quantity"], r["client_id"], r["component"], r["item"]) for r in mail] == \
        [("emails", 1, "c2", "onboarding", None)]
    assert "dana@acmeco.co" not in str(db.rows("usage_events"))     # a count, never a recipient


def test_a_failed_write_never_reaches_the_caller_and_the_meter_goes_quiet_after_three(monkeypatch, capsys, tmp_path):
    db = EconDB(missing={"usage_events"})                            # the migration is not applied
    meter.bind(db)
    tried = []
    real_table = db.table
    monkeypatch.setattr(db, "table", lambda name: tried.append(name) or real_table(name))
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda req, timeout=None: _Response(b"{}"))
    for _ in range(5):
        assert notify.send_email("dana@acmeco.co", "Profit Brief", "text") is True
    assert tried.count("usage_events") == 3
    err = capsys.readouterr().err
    assert err.count("usage not recorded") == 1 and meter.MIGRATION in err
    meter.anthropic(types.SimpleNamespace(model="m", usage=_usage(input_tokens=5)), "narrate")
    assert tried.count("usage_events") == 3                          # quiet: no fourth round trip

    # The same missing table under the narrator and the voice: the letter and the audio still arrive.
    meter.bind(EconDB(missing={"usage_events"}))
    _fake_anthropic(monkeypatch, "Dear {{first_name}},", "claude-fable-5-1", _usage(input_tokens=5, output_tokens=5))
    with meter.account(client_id="c1", component="issue"):
        assert narrate._call_claude("system", "prompt", "claude-fable-5-1") == "Dear {{first_name}},"
    monkeypatch.setenv("ELEVENLABS_API_KEY", "xi")
    monkeypatch.setattr(tts.urllib.request, "urlopen", lambda req, timeout=None: _Response(b"ID3"))
    tts._elevenlabs("Still spoken.", tmp_path / "c.mp3")
    assert (tmp_path / "c.mp3").read_bytes() == b"ID3"


class _Exploding:
    def __getattr__(self, name):
        raise RuntimeError(f"no {name}")


def test_nothing_in_the_capture_path_can_raise_into_the_caller(monkeypatch):
    class Hostile:
        def table(self, name):
            raise TypeError("a client in a state nobody expected")

    meter.bind(Hostile())
    weird = [None, object(), _Exploding(), types.SimpleNamespace(usage=_Exploding()),
             types.SimpleNamespace(model=7, usage=_usage(input_tokens="12", output_tokens=float("nan"),
                                                          iterations=[_Exploding()])),
             types.SimpleNamespace(usage=types.SimpleNamespace(input_tokens=-5, output_tokens=True,
                                                               iterations="not a list"))]
    for reply in weird:
        assert meter.anthropic(reply, "narrate", requested_model="claude-opus-5") is None
    assert meter.characters("elevenlabs", "many", "tts") is None
    assert meter.characters("elevenlabs", 10 ** 12, "tts") is None
    assert meter.email() is None
    # And a quantity that is not a finite count never becomes a row.
    counted = EconDB()
    meter.bind(counted)
    meter.characters("elevenlabs", float("inf"), "tts")
    meter.anthropic(types.SimpleNamespace(model="m", usage=_usage(input_tokens=float("inf"), output_tokens=-3)),
                    "narrate")
    assert counted.rows("usage_events") == []
    meter.bind(Hostile())

    # The meter's own parts failing outright, one by one.
    for part in ("_row", "_write", "_enter", "_leave", "_start_job", "_end_job"):
        monkeypatch.setattr(meter, part, lambda *a, **k: 1 / 0)
    assert meter.anthropic(types.SimpleNamespace(model="m", usage=_usage(input_tokens=5)), "narrate") is None
    assert meter.email() is None
    with meter.account(client_id="c1", component="issue"):
        pass
    with meter.job("sweep"):
        pass
    assert meter.metered("issue")(lambda db, client: "published")(None, {"id": "c1"}) == "published"
    # ...while the work's own failure is still its own, untouched.
    with pytest.raises(KeyError, match="the work's own error"):
        with meter.account(client_id="c1"):
            raise KeyError("the work's own error")


def test_metered_work_keeps_its_own_result_and_its_own_errors_and_is_timed_once():
    db = EconDB()
    meter.bind(db)

    @meter.metered("issue")
    def publish(db_, client, n):
        with meter.account(client_id=client["id"], component="letter"):   # same account: no second clock
            return n * 2

    @meter.metered("sweep")
    def sweep(db_, client):
        raise ValueError("the sweep's own failure")

    assert publish(None, {"id": "c1"}, 21) == 42 and publish.__name__ == "publish"
    with pytest.raises(ValueError, match="own failure"):
        sweep(None, {"id": "c2"})
    secs = _events(db, unit="seconds")
    assert [(r["client_id"], r["component"], r["service"]) for r in secs] == \
        [("c1", "issue", "engine"), ("c2", "sweep", "engine")]
    assert all(r["quantity"] >= 0 and r["detail"]["started_at"] for r in secs)
    # A second argument that is not a client row is nobody's, and the work still runs.
    assert meter.metered("x")(lambda db_, c: "ran")(None, "not-a-row") == "ran"
    assert len(_events(db, unit="seconds")) == 2                         # untimed: no account to time


def test_the_work_that_serves_an_account_is_metered_to_it():
    """The wiring, pinned: each function whose second argument is the client
    it works for carries the meter, so its usage and seconds are that client's."""
    from hubricon_engine import cli, operator
    for fn in (cli._publish_issue, cli._sweep_client, cli._send_client_email,
               operator.Pass._touch, operator.Pass._publish_first_issue):
        assert hasattr(fn, "__wrapped__"), fn.__name__


def test_a_scheduled_command_is_one_job_event_carrying_its_github_run(monkeypatch):
    db = EconDB()
    meter.bind(db)
    env = {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "991", "GITHUB_RUN_ATTEMPT": "1",
           "GITHUB_JOB": "issue", "GITHUB_WORKFLOW": "Fortnightly issue"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with meter.job("issue"):
        meter.email()
    jobs = _events(db, component="job")
    assert len(jobs) == 1 and jobs[0]["item"] == "issue" and jobs[0]["runner"] == "github_actions"
    assert jobs[0]["client_id"] is None and jobs[0]["unit"] == "seconds"
    assert jobs[0]["detail"] == {"outcome": "ok", "github_run_id": "991", "github_run_attempt": "1",
                                 "github_job": "issue", "github_workflow": "Fortnightly issue"}
    assert _events(db, unit="emails")[0]["job"] == "issue"
    # A command that exits non-zero is counted, and still exits.
    with pytest.raises(SystemExit):
        with meter.job("watch"):
            raise SystemExit("a Buy Box reading is missing")
    assert _events(db)[-1]["item"] == "watch" and _events(db)[-1]["detail"]["outcome"] == "exit"
    # A command nobody schedules is no job event, though what it does is named for it.
    with meter.job("script"):
        meter.email()
    assert _events(db)[-1]["unit"] == "emails" and _events(db)[-1]["job"] == "script"
    assert not _events(db, item="script")
    meter.email()
    assert _events(db)[-1]["job"] is None                                # the name ends with the command


def test_connecting_to_the_database_is_what_binds_the_meter(monkeypatch):
    from hubricon_engine import db as dbmod
    bound = EconDB()
    monkeypatch.setattr(dbmod.config, "load", lambda: {"supabase_url": "https://x", "service_role_key": "k"})
    monkeypatch.setattr(dbmod, "create_client", lambda url, key: bound)
    assert dbmod.connect() is bound
    meter.email()
    assert len(bound.rows("usage_events")) == 1


def test_with_no_database_bound_nothing_is_written_and_nothing_is_left_behind():
    reply = types.SimpleNamespace(model="m", usage=_usage(input_tokens=5))
    meter.anthropic(reply, "narrate")
    meter.email()
    meter.characters("elevenlabs", 5, "tts")
    with meter.account(client_id="c1"):
        meter.email()
    with meter.job("operator"):
        pass
    assert meter._scopes.get() == () and meter._job.get() is None
