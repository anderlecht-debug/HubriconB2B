"""The meter: every cost driver counted where it is incurred, and never fatally.

What one more account costs cannot be managed until it is measured, and until
2026-09-25 the only record was model_runs' two timestamps. Four things cost
money per unit of work, and each is counted at the one place the engine pays
for it:

  Anthropic   tokens, as the API's own `usage` reports them (narrate.py,
              triage.py). When a server-side fallback served the reply, each
              attempt is counted at its own model, from `usage.iterations`.
  ElevenLabs  characters sent for speech (tts.py)
  Resend      emails the API accepted (notify.py)
  the engine  wall seconds: each scheduled command (operator, sweep, issue,
              watch, calibrate) as a whole, and each account's part of it

Attribution is a scope, not a parameter threaded through pure functions. The
code that knows whose work it is says so once — `@meter.metered("issue")` on a
function whose second argument is the client row, or `with meter.account(...)`
— and everything counted inside is that account's (or that prospect's).
Counted outside any scope, it is the machine's own. The database is bound
once, by `db.connect()`, so a command run by hand is counted too.

Never fatal, and cheap. A capture function cannot raise into its caller. A
failed write is dropped with one line on stderr, and after three in a row the
meter goes quiet for the rest of the process rather than pay a failing round
trip per email. The work — a brief, an email, a sweep — never waits on it.

What it cannot tell you:
- A price. It records quantities; economics.py multiplies them by cost_config.
- Runner time before `hubricon` starts (checkout, dependency install): the
  report adds an allowance per job, and says it is one.
- Anything, when the database is unreachable or the migration is not applied:
  the work goes on uncounted, and the report's coverage line shows the gap.
"""

from __future__ import annotations

import contextlib
import contextvars
import functools
import math
import os
import sys
import time
from datetime import datetime, timezone

MIGRATION ="supabase/migrations/20260925000004_unit_economics.sql"
TABLE = "usage_events"
ANTHROPIC, ELEVENLABS, RESEND, ENGINE = "anthropic", "elevenlabs", "resend", "engine"
# The commands .github/workflows runs on a schedule. Each one's wall time is an
# event of its own when it ends; the runner-minute estimate is built from them.
SCHEDULED = ("operator", "sweep", "issue", "watch", "calibrate")
QUIET_AFTER = 3
# usage_events.unit <- the attribute the Anthropic SDK reports it under
TOKEN_UNITS = (("input_tokens", "input_tokens"), ("output_tokens", "output_tokens"),
               ("cache_write_tokens", "cache_creation_input_tokens"),
               ("cache_read_tokens", "cache_read_input_tokens"))
GITHUB = (("github_run_id", "GITHUB_RUN_ID"), ("github_run_attempt", "GITHUB_RUN_ATTEMPT"),
          ("github_job", "GITHUB_JOB"), ("github_workflow", "GITHUB_WORKFLOW"))

_state = {"db": None, "failures": 0, "quiet": False, "said": False}
_scopes: contextvars.ContextVar[tuple] = contextvars.ContextVar("hubricon_meter_scopes", default=())
_job: contextvars.ContextVar[str | None] = contextvars.ContextVar("hubricon_meter_job", default=None)


def bind(db) -> None:
    """Where the meter writes: the engine's own database, bound by db.connect()."""
    _state.update(db=db, failures=0, quiet=False, said=False)


def unbind() -> None:
    _state.update(db=None, failures=0, quiet=False, said=False)


def runner() -> str:
    return "github_actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"


def _never_raises(fn):
    """Metering is bookkeeping. Whatever goes wrong in it stays in it."""
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return None
    return inner


def _say(line: str) -> None:
    try:
        print(line, file=sys.stderr)
    except Exception:
        pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _here() -> dict:
    stack = _scopes.get()
    return stack[-1] if stack else {}


def _count(v) -> float:
    """A quantity the SDK reported, or 0 for anything that is not a finite,
    positive number."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return 0
    return v if v > 0 else 0


def _row(service: str, unit: str, quantity: float, item=None, component: str | None = None,
         detail: dict | None = None, scope: dict | None = None) -> dict:
    s = _here() if scope is None else scope
    return {"occurred_at": _now(), "client_id": s.get("client_id"), "prospect_id": s.get("prospect_id"),
            "service": service, "unit": unit, "quantity": round(float(quantity), 3),
            "item": None if item is None else str(item)[:120],
            "component": component or s.get("component"), "job": _job.get(), "runner": runner(),
            "detail": detail or {}}


def _write(rows: list[dict]) -> bool:
    db = _state["db"]
    if db is None or _state["quiet"] or not rows:
        return False
    try:
        db.table(TABLE).insert(rows).execute()
    except Exception as err:
        _state["failures"] += 1
        if not _state["said"]:
            _state["said"] = True
            _say(f"  usage not recorded ({type(err).__name__}: {str(err)[:160]}); the work goes on. "
                 f"If usage_events is missing, apply {MIGRATION}.")
        if _state["failures"] >= QUIET_AFTER:
            _state["quiet"] = True
        return False
    _state["failures"] = 0
    return True


# -- what is counted ---------------------------------------------------------------

@_never_raises
def anthropic(response, component: str, requested_model: str | None = None) -> None:
    """Tokens, from the response's own `usage`. A reply a server-side fallback
    served carries every attempt in `usage.iterations`, each with its model;
    the top-level usage then covers only the attempt that answered, so the
    iterations are the record. A declined attempt is written as reported."""
    if _state["db"] is None or _state["quiet"]:
        return
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    served = getattr(response, "model", None)
    served = served if isinstance(served, str) and served else requested_model
    tries = [it for it in (getattr(usage, "iterations", None) or [])
             if getattr(it, "type", None) in ("message", "fallback_message")]
    if any(getattr(it, "type", None) == "fallback_message" for it in tries):
        attempts = []
        for it in tries:
            answered = it.type == "fallback_message"
            model = getattr(it, "model", None) or (served if answered else requested_model)
            attempts.append((model, "served" if answered else "declined", it))
    else:
        attempts = [(served, "served", usage)]
    rows = []
    for model, outcome, u in attempts:
        detail = {"attempt": outcome}
        if requested_model and model != requested_model:
            detail["requested"] = requested_model
        for unit, attr in TOKEN_UNITS:
            n = _count(getattr(u, attr, None))
            if n:
                rows.append(_row(ANTHROPIC, unit, n, item=model or "unknown", component=component, detail=detail))
    _write(rows)


@_never_raises
def characters(service: str, n, component: str, item: str | None = None) -> None:
    """Characters a speech vendor was paid to voice."""
    n = _count(n)
    if n:
        _write([_row(service, "characters", n, item=item, component=component)])


@_never_raises
def email(service: str = RESEND) -> None:
    """One email the provider accepted. No recipient and no subject: a count."""
    _write([_row(service, "emails", 1, component=_here().get("component") or "email")])


# -- whose it is --------------------------------------------------------------------

@_never_raises
def _enter(client_id, prospect_id, component, timed):
    outer = _scopes.get()
    cid = str(client_id) if client_id else None
    pid = str(prospect_id) if prospect_id else None
    # A timed scope inside another for the same account adds no seconds of its
    # own: the outer one is already counting them.
    already = any(s.get("timed") and s.get("client_id") == cid and s.get("prospect_id") == pid for s in outer)
    scope = {"client_id": cid, "prospect_id": pid, "component": component,
             "timed": bool(timed and (cid or pid) and not already),
             "t0": time.monotonic(), "started_at": _now()}
    return scope, _scopes.set(outer + (scope,))


@_never_raises
def _leave(entered) -> None:
    if not entered:
        return
    scope, token = entered
    _scopes.reset(token)
    if scope["timed"]:
        _write([_row(ENGINE, "seconds", time.monotonic() - scope["t0"], component=scope["component"],
                     detail={"started_at": scope["started_at"]}, scope=scope)])


@contextlib.contextmanager
def account(client_id=None, prospect_id=None, component: str | None = None, timed: bool = True):
    """Everything inside is this account's. Timed, its wall seconds are too.
    The body's own exceptions pass through untouched."""
    try:
        entered = _enter(client_id, prospect_id, component, timed)
    except Exception:
        entered = None
    try:
        yield
    finally:
        try:
            _leave(entered)
        except Exception:
            pass


def metered(component: str, timed: bool = True):
    """Decorate a function whose second positional argument is the client row —
    (db, client, ...) or (self, client, ...) — so its work is that account's."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            try:
                client = args[1] if len(args) > 1 else kwargs.get("client")
                cid = client.get("id") if isinstance(client, dict) else None
            except Exception:
                cid = None
            with account(client_id=cid, component=component, timed=timed):
                return fn(*args, **kwargs)
        return inner
    return wrap


# -- the scheduled job ----------------------------------------------------------------

@_never_raises
def _start_job(command):
    return _job.set(command)


@_never_raises
def _end_job(command, seconds: float, outcome: str, token) -> None:
    try:
        if command in SCHEDULED:
            gh = {k: os.environ[v] for k, v in GITHUB if os.environ.get(v)}
            _write([_row(ENGINE, "seconds", seconds, item=command, component="job",
                         detail={"outcome": outcome, **gh}, scope={})])
    finally:
        if token is not None:
            _job.reset(token)


@contextlib.contextmanager
def job(command: str | None):
    """A CLI command's wall time. Every event inside carries its name; a
    scheduled one (SCHEDULED) is itself an event when it ends, whatever way it
    ends, and its exit passes through untouched."""
    try:
        token = _start_job(command)
    except Exception:
        token = None
    t0, outcome = time.monotonic(), "ok"
    try:
        yield
    except SystemExit as err:
        outcome = "ok" if err.code in (None, 0) else "exit"
        raise
    except BaseException:
        outcome = "error"
        raise
    finally:
        try:
            _end_job(command, time.monotonic() - t0, outcome, token)
        except Exception:
            pass
