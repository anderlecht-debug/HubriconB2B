"""Unit economics: what one more account costs, and whether that falls.

Hubricon is one founder serving every account for a flat fee, so whether it
scales is arithmetic rather than opinion: what an account-month costs in
compute, in third-party usage and above all in the founder's minutes, and
whether that falls as the engine automates more. Carnegie's rule — know the
cost of every unit, every week — needs the units recorded first, and until
2026-09-25 only model_runs' two timestamps were.

`meter.py` counts usage where it is incurred, `hubricon log` records the
founder's minutes, and this module prices them:

    hubricon economics [--month YYYY-MM]   the month per account and in total, and the scale curve
    hubricon economics --config            every price, plan fee and rate it uses, and whose each is
    hubricon economics --set KEY VALUE     the founder's figure replaces a placeholder
    hubricon log <client|prospect|all> <minutes> <what...> [--on YYYY-MM-DD]

Every figure says what it is. [m] is measured: read from the engine's own
records (invoices as Stripe mirrored them, usage the meter wrote, minutes
logged, a booking's scheduled length). [a] is assumed: a measured quantity at a
price or rate from cost_config, which names its basis: a placeholder nobody has
checked, the length the site states, or the founder's own figure.

An account is a client in service: from the yes (retainer_started_at) or the
kickoff, whichever came first, until they leave; and any client an invoice
bills that month. Time and usage before that are what winning them cost, and
are reported apart from cost to serve.

What it cannot tell you:
- Minutes nobody logged. Unlogged work is invisible, so the report says how
  many accounts carry hand-logged time, and calls capacity an upper bound when
  only the calendar speaks.
- Whether a booked call happened. It counts at its scheduled length; correct a
  no-show or an overrun by editing the row's minutes (0 for a no-show; a
  deleted row is written again on the next run).
- The day a client left. It is not recorded; the exit true-up (or the row's
  last update) stands in for it.
- Runner time the engine does not see. Checkout and dependency install are an
  allowance per job, and GitHub rounds each job up to the minute.
- Anything outside the engine: the cloud routine runs on the founder's
  claude.ai plan and the harvest on his Mac. The site's own mail (the
  60-second Teardown's copy from api/quick.js, the portal's sign-in links)
  reaches Resend without passing the engine, so the Resend line is the
  engine's share. Add such costs to cost_config as fixed if they should count.
- A price. Every rate and plan fee is an input, and ships as a placeholder.
"""

from __future__ import annotations

import math
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import billing, meter, onboarding

MIGRATION = meter.MIGRATION
FOUNDER_TZ = ZoneInfo("America/Chicago")   # Dallas; the digest already runs on Chicago time
WEEKS_PER_MONTH = 52 / 12
CURVE_MONTHS = 12
COVER_TOLERANCE_S = 5                       # the runner's clock against the database's
MAX_MINUTES = 1440

# The three workflows' schedules, as .github/workflows states them (UTC).
# tests/test_economics.py holds this in step with the files.
SCHEDULE = {"operator": "17 * * * *", "issue": "0 14 * * *", "sweep": "0 11 * * 1"}

# Every input the arithmetic multiplies by, exactly as the migration seeds it.
# `placeholder` means nobody has checked it; `site` is what the site tells a
# client; `founder` is his own figure. A test holds this and the seed in step.
DEFAULTS = (
    ("founder.hourly_rate_usd", 150, "usd/hour", "placeholder",
     "the shadow price of one founder hour in cost to serve; set your own"),
    ("founder.working_hours_per_week", 50, "hours/week", "placeholder",
     "the working week the capacity figure is computed in"),
    ("founder.booked_call_minutes", 20, "minutes", "site",
     "a booked call whose event names no length: the 20-minute call apply.html offers"),
    ("founder.kickoff_minutes", 45, "minutes", "site",
     "the Kickoff: 45 minutes on welcome.html and method.html"),
    ("fixed.supabase", 25, "usd/month", "placeholder", "Supabase Pro list price, unverified; use the invoice"),
    ("fixed.vercel", 20, "usd/month", "placeholder", "Vercel Pro, one seat, unverified"),
    ("fixed.github", 4, "usd/month", "placeholder", "GitHub Pro, unverified; 0 on the free plan"),
    ("fixed.google_workspace", 7, "usd/month", "placeholder", "Workspace Business Starter, one user, unverified"),
    ("fixed.calendly", 12, "usd/month", "placeholder", "Calendly Standard billed monthly, unverified"),
    ("fixed.instantly", 37, "usd/month", "placeholder", "Instantly Growth billed monthly, unverified"),
    ("fixed.elevenlabs", 22, "usd/month", "placeholder", "ElevenLabs Creator, unverified"),
    ("fixed.resend", 0, "usd/month", "placeholder", "Resend free tier, unverified"),
    ("rate.github_actions.usd_per_minute", 0.008, "usd/minute", "placeholder",
     "a hosted Linux runner on a private repo, unverified; 0 if the repo is public"),
    ("rate.github_actions.included_minutes", 2000, "minutes/month", "placeholder",
     "runner minutes the plan includes before any are billed, unverified"),
    ("rate.github_actions.setup_seconds_per_job", 60, "seconds/job", "placeholder",
     "checkout and dependency install before hubricon starts, which the engine cannot see"),
    ("rate.anthropic.claude-fable-5-1.input_usd_per_mtok", 10, "usd/1M tokens", "placeholder",
     "list price in mid-2026, unverified"),
    ("rate.anthropic.claude-fable-5-1.output_usd_per_mtok", 50, "usd/1M tokens", "placeholder",
     "list price in mid-2026, unverified"),
    ("rate.anthropic.claude-opus-5.input_usd_per_mtok", 5, "usd/1M tokens", "placeholder",
     "list price in mid-2026, unverified"),
    ("rate.anthropic.claude-opus-5.output_usd_per_mtok", 25, "usd/1M tokens", "placeholder",
     "list price in mid-2026, unverified"),
    ("rate.anthropic.claude-opus-4-8.input_usd_per_mtok", 5, "usd/1M tokens", "placeholder",
     "list price in mid-2026, unverified"),
    ("rate.anthropic.claude-opus-4-8.output_usd_per_mtok", 25, "usd/1M tokens", "placeholder",
     "list price in mid-2026, unverified"),
    ("rate.anthropic.cache_write_multiplier", 1.25, "x input rate", "placeholder",
     "a cache write, as a multiple of the input rate, unverified"),
    ("rate.anthropic.cache_read_multiplier", 0.1, "x input rate", "placeholder",
     "a cache read, as a multiple of the input rate, unverified"),
    ("rate.elevenlabs.usd_per_1k_characters", 0.3, "usd/1k characters", "placeholder",
     "characters past the plan quota, unverified"),
    ("rate.elevenlabs.included_characters", 100000, "characters/month", "placeholder",
     "the plan quota, unverified"),
    ("rate.resend.usd_per_email", 0.0009, "usd/email", "placeholder", "emails past the plan quota, unverified"),
    ("rate.resend.included_emails", 3000, "emails/month", "placeholder", "the plan quota, unverified"),
    ("rate.stripe.invoicing_pct", 0.004, "share of a paid invoice", "placeholder", "Stripe Invoicing, unverified"),
    ("rate.stripe.ach_pct", 0.008, "share of a paid invoice", "placeholder", "ACH Direct Debit, unverified"),
    ("rate.stripe.ach_cap_usd", 5, "usd/payment", "placeholder", "the ACH fee cap, unverified"),
)
BASIS = {"placeholder": "placeholder", "site": "as the site states", "founder": "founder's figure"}
# Metered services a plan includes a quota of: past it, a rate per `per` units.
QUOTAS = {("elevenlabs", "characters"): ("rate.elevenlabs.usd_per_1k_characters", 1000,
                                         "rate.elevenlabs.included_characters"),
          ("resend", "emails"): ("rate.resend.usd_per_email", 1, "rate.resend.included_emails")}

KICKOFF = re.compile(r"kick\s*-?\s*off", re.I)
LENGTH = re.compile(r"(\d{1,3})\s*-?\s*min", re.I)


# -- small things ------------------------------------------------------------------

def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _ts(v) -> datetime | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _day(v) -> date | None:
    """A date column, or the UTC day of a timestamp."""
    if not v:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    s = str(v)
    if len(s) == 10:
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None
    t = _ts(s)
    return t.date() if t else None


def _local_day(v) -> date | None:
    """The founder's calendar day of a timestamp."""
    t = _ts(v)
    return t.astimezone(FOUNDER_TZ).date() if t else None


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _next_month(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def _add_months(d: date, k: int) -> date:
    n = d.year * 12 + d.month - 1 + k
    return date(n // 12, n % 12 + 1, 1)


def _midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _usd(x) -> str:
    if x is None:
        return "—"
    return ("-" if x < 0 else "") + f"${abs(x):,.2f}"


def _n(x, digits: int = 0) -> str:
    if x is None:
        return "—"
    return f"{x:,.{digits}f}"


def _name(c: dict) -> str:
    return c.get("company_name") or c.get("contact_email") or str(c.get("id"))[:8]


# -- the inputs: cost_config ------------------------------------------------------

def load_config(db) -> tuple[dict, str]:
    """key -> {value, unit, basis, note}: the table's rows over the defaults, so
    a row the founder deleted falls back to its placeholder and says so.
    Status 'ok', or 'missing' when the table is not there yet."""
    cfg = {k: {"value": float(v), "unit": u, "basis": b, "note": n} for k, v, u, b, n in DEFAULTS}
    try:
        rows = db.table("cost_config").select("*").execute().data or []
    except Exception:
        return cfg, "missing"
    for r in rows:
        try:
            v = float(r["value"])
        except (KeyError, TypeError, ValueError):
            continue
        prior = cfg.get(r.get("key"), {})
        cfg[r["key"]] = {"value": v, "unit": r.get("unit") or prior.get("unit") or "",
                         "basis": r.get("basis") if r.get("basis") in BASIS else "placeholder",
                         "note": r.get("note") or prior.get("note") or ""}
    return cfg, "ok"


def value(cfg: dict, key: str) -> float:
    return float((cfg.get(key) or {}).get("value") or 0.0)


def basis(cfg: dict, key: str) -> str:
    return BASIS.get((cfg.get(key) or {}).get("basis"), "placeholder")


def _unit_for(key: str) -> str | None:
    for k, _v, unit, _b, _n in DEFAULTS:
        if k == key:
            return unit
    if re.fullmatch(r"fixed\.[a-z0-9_]+", key):
        return "usd/month"
    if re.fullmatch(r"rate\.anthropic\.[a-z0-9.\-]+\.(input|output)_usd_per_mtok", key):
        return "usd/1M tokens"
    return None


def set_config(db, key: str, raw: str) -> str:
    """The founder's figure replaces a placeholder. A known key, a new fixed
    cost (fixed.<name>, dollars a month) or a rate for a new model."""
    unit = _unit_for(key)
    if unit is None:
        raise ValueError(f"{key!r} is not an input the report reads. Use a key from `hubricon economics "
                         f"--config`, fixed.<name> for another monthly cost, or "
                         f"rate.anthropic.<model>.input_usd_per_mtok / output_usd_per_mtok.")
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"{raw!r} is not a number.") from None
    if v < 0:
        raise ValueError("A price is not negative.")
    db.table("cost_config").upsert({"key": key, "value": v, "unit": unit, "basis": "founder",
                                    "note": f"set by the founder on {date.today().isoformat()}"},
                                   on_conflict="key").execute()
    return f"{key} = {v:g} {unit} (founder's figure)."


def render_config(cfg: dict, status: str) -> str:
    keys = sorted(cfg)
    held = sum(1 for k in keys if cfg[k]["basis"] == "placeholder")
    out = [f"cost_config: {len(keys)} inputs, {held} of them placeholders"
           + ("" if status == "ok" else f" (the table is not there: these are the defaults; apply {MIGRATION})")]
    for k in keys:
        c = cfg[k]
        out.append(f"  {k:<54} {c['value']:>10g}  {c['unit']:<24} {c['basis']:<12} {c['note']}")
    out.append("Replace one: hubricon economics --set founder.hourly_rate_usd 200 "
               "(or edit the row in Supabase; either makes it the founder's figure).")
    return "\n".join(out)


# -- the data ------------------------------------------------------------------------

def _rows(db, table: str, columns: str = "*", since_col: str | None = None, since: str | None = None,
          page: int = 1000) -> list[dict] | None:
    """Every row, paged (PostgREST caps a response at 1,000 and says nothing),
    or None when the table is not there."""
    out, start = [], 0
    try:
        while True:
            q = db.table(table).select(columns)
            if since_col and since is not None:
                q = q.gte(since_col, since)
            rows = q.order("id").range(start, start + page - 1).execute().data or []
            out.extend(rows)
            if len(rows) < page:
                return out
            start += page
    except Exception:
        return None


def service_start(client: dict, kickoff: date | None) -> date | None:
    """The yes or the kickoff, whichever came first."""
    found = [d for d in (_day(client.get("retainer_started_at")), kickoff) if d]
    return min(found) if found else None


def service_end(client: dict) -> date | None:
    """The day they left. Not recorded anywhere: the exit true-up, else the
    row's last update, stands in for it."""
    if client.get("status") != "churned":
        return None
    return _day(client.get("exit_trued_up_at")) or _day(client.get("updated_at"))


def kickoff_dates(bookings: list[dict], mandates: list[dict], now: datetime) -> dict[str, date]:
    """The day each client's service began in the founder's calendar: a Kickoff
    booking that has happened, else the first standing mandate agreed, which
    is set on that call."""
    out: dict[str, date] = {}
    for b in bookings:
        at = _ts(b.get("starts_at"))
        cid = b.get("client_id")
        if b.get("is_test") or not cid or not at or at > now or not KICKOFF.search(b.get("event_type") or ""):
            continue
        d = at.astimezone(FOUNDER_TZ).date()
        out[cid] = min(out.get(cid, d), d)
    agreed: dict[str, date] = {}
    for m in mandates:
        d, cid = _local_day(m.get("agreed_at")), m.get("client_id")
        if d and cid:
            agreed[cid] = min(agreed.get(cid, d), d)
    for cid, d in agreed.items():
        out.setdefault(cid, d)
    return out


def _sections(usage: list[dict]) -> dict[str, list[tuple[datetime, datetime]]]:
    """Each account's timed stretches of engine work, for telling a model run
    inside one (already counted) from one run by hand."""
    out: dict[str, list] = defaultdict(list)
    for e in usage:
        if e.get("service") != meter.ENGINE or e.get("component") == "job" or not e.get("client_id"):
            continue
        end = _ts(e.get("occurred_at"))
        if not end:
            continue
        begin = _ts((e.get("detail") or {}).get("started_at")) or end - timedelta(seconds=_f(e.get("quantity")))
        out[e["client_id"]].append((begin, end))
    return out


def _covered(s: datetime, f: datetime, windows) -> bool:
    tol = timedelta(seconds=COVER_TOLERANCE_S)
    return any(a - tol <= s and f <= b + tol for a, b in windows)


def load(db, since: date, now: datetime) -> dict:
    """Everything the arithmetic reads, from `since` on (invoices and clients
    whole). A table that is not there is a status, never a crash."""
    status = {}
    cfg, status["config"] = load_config(db)
    everyone = _rows(db, "clients") or []
    internal = {c["id"] for c in everyone if onboarding.is_internal(c.get("contact_email"), c.get("contact_name"))}
    clients = {c["id"]: c for c in everyone if c["id"] not in internal}
    invoices = _rows(db, "invoices")
    status["invoices"] = "ok" if invoices is not None else "missing"
    stamp = _midnight(since).isoformat()
    runs = _rows(db, "model_runs", "id, client_id, status, started_at, finished_at", "started_at", stamp)
    usage = _rows(db, "usage_events", "*", "occurred_at", stamp)
    status["usage"] = "ok" if usage is not None else "missing"
    time_rows = _rows(db, "founder_time", "*", "occurred_on", since.isoformat())
    status["time"] = "ok" if time_rows is not None else "missing"
    bookings = _rows(db, "bookings", "id, client_id, invitee_email, event_type, starts_at, is_test") or []
    mandates = _rows(db, "mandates", "id, client_id, agreed_at") or []
    kick = kickoff_dates(bookings, mandates, now)
    return {"config": cfg, "status": status, "clients": clients, "internal": internal,
            "invoices": [i for i in (invoices or []) if i.get("client_id") not in internal],
            "runs": runs or [], "usage": usage or [], "time": time_rows or [], "kickoffs": kick,
            "start": {cid: service_start(c, kick.get(cid)) for cid, c in clients.items()},
            "end": {cid: service_end(c) for cid, c in clients.items()},
            "sections": _sections(usage or [])}


# -- what the calendar already says --------------------------------------------------

def calendar_entries(bookings: list[dict], mandates: list[dict], cfg: dict, now: datetime,
                     prospect_ids: dict[str, str] | None = None) -> list[dict]:
    """founder_time rows the data already vouches for, one per fact: every
    booked call that has happened, at the length its event names (else the
    site's), and each client's kickoff — a Kickoff booking, or failing one the
    day the standing mandate was agreed. Nothing is guessed beyond that."""
    prospect_ids = prospect_ids or {}
    rows, kickoff_booked = [], set()
    for b in bookings:
        at = _ts(b.get("starts_at"))
        if b.get("is_test") or not at or at > now:
            continue
        name = (b.get("event_type") or "").strip()
        kickoff = bool(KICKOFF.search(name))
        m = LENGTH.search(name)
        if m and 0 < int(m.group(1)) <= 480:
            minutes, how = float(m.group(1)), "scheduled"
        else:
            minutes = value(cfg, "founder.kickoff_minutes" if kickoff else "founder.booked_call_minutes")
            how = "stated"
        cid = b.get("client_id")
        if kickoff and cid:
            kickoff_booked.add(cid)
        rows.append({"ref": f"booking:{b['id']}", "source": "kickoff" if kickoff else "booking", "basis": how,
                     "minutes": minutes, "occurred_on": at.astimezone(FOUNDER_TZ).date().isoformat(),
                     "client_id": cid, "prospect_id": None if cid else prospect_ids.get(
                         (b.get("invitee_email") or "").strip().lower()),
                     "what": f"{name or 'booked call'} (booked)"})
    agreed: dict[str, date] = {}
    for m in mandates:
        d, cid = _local_day(m.get("agreed_at")), m.get("client_id")
        if d and cid:
            agreed[cid] = min(agreed.get(cid, d), d)
    for cid, d in sorted(agreed.items()):
        if cid in kickoff_booked:
            continue
        rows.append({"ref": f"kickoff:{cid}", "source": "kickoff", "basis": "stated",
                     "minutes": value(cfg, "founder.kickoff_minutes"), "occurred_on": d.isoformat(),
                     "client_id": cid, "prospect_id": None,
                     "what": "Kickoff (the standing mandate was agreed on it)"})
    return rows


def sync_calendar(db, now: datetime | None = None) -> tuple[int, str]:
    """Write the calendar's entries, once each. A row already there is never
    touched, so a corrected minute count stands. Returns (written, status)."""
    now = now or datetime.now(timezone.utc)
    existing = _rows(db, "founder_time", "id, ref")
    if existing is None:
        return 0, "missing"
    try:
        have = {r.get("ref") for r in existing if r.get("ref")}
        clients = _rows(db, "clients", "id, contact_email, contact_name") or []
        internal = {c["id"] for c in clients if onboarding.is_internal(c.get("contact_email"), c.get("contact_name"))}
        bookings = [b for b in (_rows(db, "bookings", "id, client_id, invitee_email, event_type, starts_at, is_test")
                                or [])
                    if b.get("client_id") not in internal
                    and not onboarding.is_internal(b.get("invitee_email"))]
        mandates = [m for m in (_rows(db, "mandates", "id, client_id, agreed_at") or [])
                    if m.get("client_id") not in internal]
        cfg, _ = load_config(db)
        prospect_ids = {}
        for email in {(b.get("invitee_email") or "").strip().lower() for b in bookings if not b.get("client_id")}:
            if email:
                hit = db.table("prospects").select("id, email").eq("email", email).limit(1).execute().data
                if hit:
                    prospect_ids[email] = hit[0]["id"]
        new = [r for r in calendar_entries(bookings, mandates, cfg, now, prospect_ids) if r["ref"] not in have]
        if new:
            db.table("founder_time").insert(new).execute()
        return len(new), "ok"
    except Exception as err:
        return 0, f"failed: {str(err)[:120]}"


# -- hubricon log ----------------------------------------------------------------------

def resolve_target(db, ident: str) -> tuple[str, dict | None]:
    """'all', a client (uuid, uuid prefix, contact email, or company name, whole
    or a part only one company has) or a prospect (by email). Raises
    LookupError with the reason."""
    s = (ident or "").strip()
    low = s.lower()
    if low == "all":
        return "all", None
    clients = [c for c in (_rows(db, "clients", "id, company_name, contact_email, contact_name") or [])]
    if "@" in low:
        hit = [c for c in clients if (c.get("contact_email") or "").lower() == low]
        if hit:
            return "client", hit[0]
        found = (db.table("prospects").select("id, email, company_name").eq("email", low).limit(1).execute().data)
        if found:
            return "prospect", found[0]
        raise LookupError(f"No client or prospect has the address {s!r}.")
    named = lambda c: (c.get("company_name") or "").strip().lower()
    hit = ([c for c in clients if len(low) >= 4 and str(c["id"]).startswith(low)]
           or [c for c in clients if named(c) == low]
           or [c for c in clients if len(low) >= 3 and low in named(c)])     # "acme" for Acme Co, if only one
    if len(hit) > 1:
        raise LookupError(f"{s!r} is ambiguous: " + ", ".join(f"{str(c['id'])[:8]} ({_name(c)})" for c in hit))
    if hit:
        return "client", hit[0]
    raise LookupError(f"No client matches {s!r}. Name a client (uuid, prefix, email or company name), "
                      f"a prospect by email, or 'all'.")


def log_entry(kind: str, row: dict | None, minutes: float, what: str, on: date) -> dict:
    return {"occurred_on": on.isoformat(), "minutes": round(float(minutes), 1), "what": what[:500],
            "source": "logged", "basis": "logged",
            "client_id": row["id"] if kind == "client" else None,
            "prospect_id": row["id"] if kind == "prospect" else None}


def cmd_log(args):
    """hubricon log <client|prospect|all> <minutes> <what...>"""
    from . import db as dbmod
    try:
        minutes = float(args.minutes)
    except ValueError:
        sys.exit(f"{args.minutes!r} is not a number of minutes.")
    if not 0 < minutes <= MAX_MINUTES:
        sys.exit(f"Minutes are more than 0 and at most {MAX_MINUTES:,} (a day) per entry.")
    what = " ".join(args.what).strip()
    if not what:
        sys.exit("Say what the minutes were for.")
    try:
        on = date.fromisoformat(args.on) if args.on else datetime.now(FOUNDER_TZ).date()
    except ValueError:
        sys.exit(f"--on takes a date, YYYY-MM-DD, not {args.on!r}.")
    db = dbmod.connect()
    try:
        kind, row = resolve_target(db, args.target)
    except LookupError as err:
        sys.exit(str(err))
    try:
        db.table("founder_time").insert(log_entry(kind, row, minutes, what, on)).execute()
    except Exception as err:
        sys.exit(f"Not logged: {str(err)[:200]}. If founder_time is missing, apply {MIGRATION}.")
    label = "all accounts" if kind == "all" else _name(row) if kind == "client" else f"prospect {row.get('email')}"
    print(f"Logged {minutes:g} min on {label} ({on.isoformat()}): {what}")
    month = _month_start(on)
    rows = _rows(db, "founder_time", "id, client_id, prospect_id, minutes, occurred_on", "occurred_on",
                 month.isoformat()) or []
    entry = log_entry(kind, row, minutes, what, on)
    mine = [r for r in rows if (_day(r.get("occurred_on")) or month) < _next_month(month)
            and r.get("client_id") == entry["client_id"] and r.get("prospect_id") == entry["prospect_id"]]
    if mine:
        print(f"  {month:%Y-%m} so far: {sum(_f(r.get('minutes')) for r in mine):,.0f} min on {label}.")


# -- the schedule ----------------------------------------------------------------------

def _fires(cron: str, start: datetime, end: datetime) -> int:
    """How often a `minute hour * * dow` cron fired in [start, end), UTC."""
    minute, hour, _dom, _mon, dow = cron.split()
    n, t = 0, start.replace(minute=0, second=0, microsecond=0)
    while t < end:
        fire = t.replace(minute=int(minute))
        if (start <= fire < end and (hour == "*" or t.hour == int(hour))
                and (dow == "*" or t.isoweekday() % 7 == int(dow))):
            n += 1
        t += timedelta(hours=1)
    return n


def scheduled_runs(ms: date, me: date, now: datetime) -> dict[str, int]:
    end = min(_midnight(me), now)
    return {name: _fires(cron, _midnight(ms), end) for name, cron in SCHEDULE.items()}


# -- the month --------------------------------------------------------------------------

def _invoice_day(inv: dict) -> date | None:
    """The month an invoice bills for (the webhook stores the line's service
    period), else the day it was issued."""
    return _day(inv.get("period_start")) or _day(inv.get("issued_at")) or _day(inv.get("created_at"))


def _anthropic_key(model, unit: str) -> str:
    """The rate a token unit is priced from: output at its own rate, the rest
    (input, cache writes and reads) off the model's input rate."""
    return f"rate.anthropic.{model}.{'output' if unit == 'output_tokens' else 'input'}_usd_per_mtok"


def _anthropic_usd(cfg: dict, model, unit: str, quantity: float) -> float | None:
    """Dollars for a token count, or None when there is no rate for the model:
    the tokens are still shown, unpriced, rather than priced at a guess."""
    rate = cfg.get(_anthropic_key(model, unit))
    multiplier = {"input_tokens": 1.0, "output_tokens": 1.0,
                  "cache_write_tokens": value(cfg, "rate.anthropic.cache_write_multiplier"),
                  "cache_read_tokens": value(cfg, "rate.anthropic.cache_read_multiplier")}.get(unit)
    if rate is None or multiplier is None:
        return None
    return quantity / 1e6 * rate["value"] * multiplier


def _stripe_fee(cfg: dict, inv: dict) -> float:
    paid = _f(inv.get("amount_paid"))
    if paid <= 0:
        return 0.0
    return (paid * value(cfg, "rate.stripe.invoicing_pct")
            + min(paid * value(cfg, "rate.stripe.ach_pct"), value(cfg, "rate.stripe.ach_cap_usd")))


def _elapsed(ms: date, me: date, now: datetime) -> float:
    a, b = _midnight(ms), _midnight(me)
    if now >= b:
        return 1.0
    return max(0.0, (now - a) / (b - a))


def month_view(book: dict, ms: date, now: datetime) -> dict:
    """One month's arithmetic, from rows already loaded. Pure: no database."""
    me = _next_month(ms)
    cfg, clients, start, end = book["config"], book["clients"], book["start"], book["end"]
    measured = {k: book["status"].get(k) == "ok" for k in ("usage", "time", "invoices")}

    def in_month(d) -> bool:
        return d is not None and ms <= d < me

    invoices = [i for i in book["invoices"] if in_month(_invoice_day(i))]
    invoiced = {i.get("client_id") for i in invoices} & set(clients)
    accounts = sorted((cid for cid in clients if cid in invoiced or (
        start[cid] is not None and start[cid] < me and (end[cid] is None or end[cid] >= ms))),
        key=lambda cid: _name(clients[cid]).lower())
    acct, n = set(accounts), len(accounts)

    def where(cid, pid, d: date) -> str:
        """Whose cost a day's work is: an account's, winning one, or the machine's."""
        if cid in clients:
            s = start[cid]
            if s is not None and d >= s:
                return "account" if cid in acct else "machine"   # after they left: the book's overhead
            return "account" if (s is None and cid in acct) else "acquisition"
        return "acquisition" if pid else "machine"

    # revenue, as Stripe mirrored it
    blank = lambda: {"stood": 0.0, "voided": 0.0, "held": 0.0, "fees": 0.0, "paid_invoices": 0}
    rev = {cid: blank() for cid in accounts}
    loose = blank()
    for i in invoices:
        b = rev.get(i.get("client_id"), loose)
        st, amount = i.get("status"), _f(i.get("amount_due"))
        if st in billing.BILLED_STATUSES:
            b["stood"] += billing.still_billed(i)
            b["voided"] += min(_f(i.get("refunded_usd")), amount)
        elif st == "void":
            b["voided"] += amount
        elif st == "draft":
            b["held"] += amount
        if _f(i.get("amount_paid")) > 0:
            b["fees"] += _stripe_fee(cfg, i)
            b["paid_invoices"] += 1

    # the founder's minutes
    minutes = {cid: 0.0 for cid in accounts}
    logged, shared, won = set(), 0.0, 0.0
    for t in book["time"]:
        d = _day(t.get("occurred_on"))
        if not in_month(d):
            continue
        m, cid, pid = _f(t.get("minutes")), t.get("client_id"), t.get("prospect_id")
        w = where(cid, pid, d) if (cid or pid) else "machine"
        if w == "account":
            minutes[cid] += m
            if (t.get("source") or "logged") == "logged":
                logged.add(cid)
        elif w == "acquisition":
            won += m
        else:
            shared += m          # 'all', or a former account: work for the book

    # usage: engine seconds and third-party quantities
    seconds = {cid: 0.0 for cid in accounts}
    on_github = {cid: 0.0 for cid in accounts}
    won_seconds = won_github = 0.0
    events = {"account": {cid: [] for cid in accounts}, "acquisition": [], "machine": []}
    jobs = []
    for e in book["usage"]:
        at = _ts(e.get("occurred_at"))
        if not at or not in_month(at.date()):
            continue
        cid, pid = e.get("client_id"), e.get("prospect_id")
        if e.get("service") == meter.ENGINE:
            if e.get("component") == "job":
                jobs.append(e)
                continue
            secs, gh = _f(e.get("quantity")), e.get("runner") == "github_actions"
            w = where(cid, pid, at.date())
            if w == "account":
                seconds[cid] += secs
                on_github[cid] += secs if gh else 0.0
            elif w == "acquisition":
                won_seconds += secs
                won_github += secs if gh else 0.0
            continue
        w = where(cid, pid, at.date())
        (events["account"][cid] if w == "account" else events[w]).append(e)
    for r in book["runs"]:
        s, f = _ts(r.get("started_at")), _ts(r.get("finished_at"))
        if not s or not f or f < s or not in_month(s.date()):
            continue
        cid = r.get("client_id")
        if _covered(s, f, book["sections"].get(cid, ())):
            continue                     # inside a timed section, already counted
        w = where(cid, None, s.date())
        if w == "account":
            seconds[cid] += (f - s).total_seconds()
        elif w == "acquisition":
            won_seconds += (f - s).total_seconds()

    # GitHub's runner minutes: one billed job per (run, attempt, job), rounded up
    setup = value(cfg, "rate.github_actions.setup_seconds_per_job")
    per_job: dict[tuple, float] = defaultdict(float)
    local_seconds = 0.0
    for j in jobs:
        if j.get("runner") != "github_actions":
            local_seconds += _f(j.get("quantity"))
            continue
        det = j.get("detail") or {}
        key = (det.get("github_run_id") or f"row:{j.get('id')}", det.get("github_run_attempt") or "1",
               det.get("github_job") or j.get("item"))
        per_job[key] += _f(j.get("quantity"))
    rate = value(cfg, "rate.github_actions.usd_per_minute")
    included = value(cfg, "rate.github_actions.included_minutes")
    fired = scheduled_runs(ms, me, now)
    runner = {"measured": bool(per_job), "jobs": len(per_job), "fired": fired, "local_seconds": local_seconds,
              "account_minutes": sum(on_github.values()) / 60, "acquisition_minutes": won_github / 60}
    compute: dict[str, float | None]
    if per_job:
        billed = sum(math.ceil((s + setup) / 60) for s in per_job.values())
        bill = max(0.0, billed - included) * rate
        per_minute = bill / billed if billed else 0.0
        machine_minutes = max(0.0, billed - runner["account_minutes"] - runner["acquisition_minutes"])
        compute = {cid: on_github[cid] / 60 * per_minute for cid in accounts}
        runner.update(billed_minutes=billed, bill=bill, machine_minutes=machine_minutes,
                      machine_usd=machine_minutes * per_minute,
                      acquisition_usd=runner["acquisition_minutes"] * per_minute)
    else:
        floor = sum(fired.values())       # each run bills at least one minute
        compute = {cid: None for cid in accounts}
        runner.update(billed_minutes=None, bill=None, floor_minutes=floor,
                      floor_usd=max(0.0, floor - included) * rate, machine_usd=0.0, acquisition_usd=0.0)

    # third-party prices
    everything = [e for es in events["account"].values() for e in es] + events["acquisition"] + events["machine"]
    totals: dict[tuple, float] = defaultdict(float)
    for e in everything:
        totals[(e.get("service"), e.get("unit"))] += _f(e.get("quantity"))
    unit_price = {}
    for key, (rate_key, per, included_key) in QUOTAS.items():
        total = totals.get(key, 0.0)
        bill = max(0.0, total - value(cfg, included_key)) * value(cfg, rate_key) / per
        unit_price[key] = bill / total if total else 0.0
    unpriced: dict[tuple, float] = defaultdict(float)
    lines: dict[tuple, dict] = {}

    def price(e) -> float:
        svc, unit, q = e.get("service"), e.get("unit"), _f(e.get("quantity"))
        item = e.get("item") if svc == meter.ANTHROPIC else None
        usd = (_anthropic_usd(cfg, item, unit, q) if svc == meter.ANTHROPIC
               else q * unit_price[(svc, unit)] if (svc, unit) in unit_price else None)
        line = lines.setdefault((svc, item, unit), {"quantity": 0.0, "usd": 0.0, "priced": True})
        line["quantity"] += q
        if usd is None:
            unpriced[(svc, item, unit)] += q
            line["priced"] = False
            return 0.0
        line["usd"] += usd
        return usd

    third = {cid: sum(price(e) for e in events["account"][cid]) + rev[cid]["fees"] for cid in accounts}
    won_usage = sum(price(e) for e in events["acquisition"])
    machine_usage = sum(price(e) for e in events["machine"])

    # per account, and the book
    hourly = value(cfg, "founder.hourly_rate_usd")
    shared_each = shared / n if n else 0.0
    rows = []
    for cid in accounts:
        mins = minutes[cid] + shared_each
        founder_usd = mins / 60 * hourly if measured["time"] else None
        cost = (founder_usd or 0.0) + third[cid] + (compute[cid] or 0.0)
        rows.append({"client_id": cid, "name": _name(clients[cid]), **{k: rev[cid][k] for k in ("stood", "voided", "held")},
                     "compute": compute[cid], "seconds": seconds[cid], "third_party": third[cid],
                     "fees": rev[cid]["fees"], "minutes": mins if measured["time"] else None,
                     "direct_minutes": minutes[cid], "founder_usd": founder_usd,
                     "cost_to_serve": cost, "contribution": rev[cid]["stood"] - cost, "logged": cid in logged})
    total = {k: sum(r[k] or 0.0 for r in rows) for k in ("stood", "voided", "held", "third_party", "cost_to_serve",
                                                        "contribution", "seconds", "fees")}
    total["compute"] = sum(r["compute"] for r in rows) if runner["measured"] else None
    total["minutes"] = (sum(minutes.values()) + (shared if n else 0.0)) if measured["time"] else None
    total["founder_usd"] = total["minutes"] / 60 * hourly if total["minutes"] is not None else None

    fixed_items = [(k.split(".", 1)[1], cfg[k]) for k in sorted(cfg) if k.startswith("fixed.")]
    platform = sum(c["value"] for _, c in fixed_items)
    fixed_total = platform + (runner.get("machine_usd") or 0.0) + machine_usage

    # the three numbers
    elapsed = _elapsed(ms, me, now)
    mpa = total["minutes"] / n if (n and total["minutes"] is not None) else None
    paced = mpa / elapsed if (mpa is not None and 0 < elapsed < 1) else mpa
    available = value(cfg, "founder.working_hours_per_week") * 60 * WEEKS_PER_MONTH
    if not n:
        capacity, cap_status = None, "no_accounts"
    elif not measured["time"]:
        capacity, cap_status = None, "not_measured"
    elif not paced:
        capacity, cap_status = None, "no_minutes"
    else:
        capacity = math.floor(available / paced)
        cap_status = "ok" if logged else "calendar_only"

    new_accounts = [cid for cid in accounts if start[cid] is not None and ms <= start[cid] < me]
    won_founder = won / 60 * hourly
    won_total = won_founder + won_usage + (runner.get("acquisition_usd") or 0.0)
    warnings = []
    if not measured["usage"]:
        warnings.append(f"usage_events is not there, so compute and third-party usage are not measured: apply {MIGRATION}.")
    if not measured["time"]:
        warnings.append(f"founder_time is not there, so founder minutes are not measured: apply {MIGRATION}.")
    if book["status"].get("config") != "ok":
        warnings.append(f"cost_config is not there: every price below is the code's placeholder ({MIGRATION}).")
    if not measured["invoices"]:
        warnings.append("invoices could not be read, so revenue reads zero.")
    held = sum(1 for c in cfg.values() if c["basis"] == "placeholder")
    runner["fired_total"] = sum(fired.values())
    # Anything at all on this month's accounts? A month before the meter and
    # the log began reads "not recorded", never a measured-looking zero.
    recorded = bool(sum(minutes.values()) or any(events["account"].values()) or any(seconds.values()))
    billed_ids = {i.get("client_id") for i in invoices}
    return {
        "month": ms, "label": f"{ms:%Y-%m}", "elapsed": elapsed, "day": now.day, "days": (me - ms).days,
        "recorded": recorded, "uninvoiced": [_name(clients[c]) for c in accounts if c not in billed_ids],
        "accounts": rows, "n": n, "total": total, "loose": loose, "shared": shared, "shared_each": shared_each,
        "hourly": hourly, "measured": measured, "runner": runner, "setup": setup,
        "fixed_items": fixed_items, "platform": platform, "machine_usage": machine_usage, "fixed_total": fixed_total,
        "fixed_per_account": fixed_total / n if n else None,
        "after_fixed": total["contribution"] - fixed_total if n else None,
        "minutes_per_account": mpa, "minutes_paced": paced, "available_minutes": available,
        "capacity": capacity, "capacity_status": cap_status, "logged_accounts": len(logged),
        "cost_per_account": total["cost_to_serve"] / n if n else None,
        "acquisition": {"minutes": won if measured["time"] else None, "founder_usd": won_founder,
                        "usage_usd": won_usage, "compute_usd": runner.get("acquisition_usd") or 0.0,
                        "total_usd": won_total, "new_accounts": [_name(clients[c]) for c in new_accounts],
                        "per_account_won": won_total / len(new_accounts) if new_accounts else None},
        "lines": lines, "unpriced": dict(unpriced), "unit_price": unit_price, "totals": dict(totals),
        "warnings": warnings, "placeholders": held, "inputs": len(cfg), "config": cfg,
    }


def curve_months(book: dict, month: date) -> list[date]:
    """From the first month anything happened (at most a year back) to `month`."""
    floor = _add_months(month, -(CURVE_MONTHS - 1))
    seen = [d for d in book["start"].values() if d]
    seen += [d for d in (_invoice_day(i) for i in book["invoices"]) if d]
    seen += [d for d in (_day(e.get("occurred_at")) for e in book["usage"]) if d]
    seen += [d for d in (_day(t.get("occurred_on")) for t in book["time"]) if d]
    seen += [d for d in (_day(r.get("started_at")) for r in book["runs"]) if d]
    first = max(floor, _month_start(min(seen))) if seen else month
    first = min(first, month)
    out, m = [], first
    while m <= month:
        out.append(m)
        m = _next_month(m)
    return out


# -- the page ------------------------------------------------------------------------------

def _cap_line(v: dict) -> str:
    cfg = v["config"]
    week = (f"a {value(cfg, 'founder.working_hours_per_week'):g}-hour week, "
            f"{basis(cfg, 'founder.working_hours_per_week')}: {v['available_minutes']:,.0f} minutes a month")
    status = v["capacity_status"]
    if status == "no_accounts":
        return "not computable: no account was served"
    if status == "not_measured":
        return "not measured: founder_time is not there"
    if status == "no_minutes":
        return ("not computable: no founder minutes on any account this month. "
                "Log them: hubricon log <client> <minutes> <what>")
    per = v["minutes_paced"]
    line = f"{v['capacity']:,} accounts [a]  ({week} ÷ {per:,.0f} per account)"
    if status == "calendar_only":
        line += "\n" + " " * 38 + "an upper bound: only the calendar's minutes (calls, kickoffs); nothing logged by hand"
    return line


def render(v: dict, curve: list[dict], notes: list[str] = ()) -> str:
    cfg = v["config"]
    title = f"Unit economics — {v['label']}"
    if v["elapsed"] < 1:
        title += f", month to date (day {v['day']} of {v['days']})"
    out = [title,
           "  [m] measured: read from the engine's own records.  "
           "[a] assumed: a measured quantity at a price or rate from cost_config.",
           f"  {v['placeholders']} of {v['inputs']} prices and rates are placeholders, not facts: "
           "`hubricon economics --config` lists them."]
    out += [f"  {x}" for x in notes]
    out += [f"  ! {w}" for w in v["warnings"]]
    out.append("")
    hourly_note = f"${v['hourly']:,.0f} an hour ({basis(cfg, 'founder.hourly_rate_usd')})"

    if not v["n"]:
        out.append(f"No accounts were served in {v['label']}. With no account to divide by there is no cost to serve, "
                   "no contribution margin and no capacity figure;")
        out.append("what follows is what the machine costs to stand up, and what winning accounts has cost.")
    else:
        out.append(f"{v['n']} account{'s' if v['n'] != 1 else ''} served [m]")
        head = (f"  {'Account':<18}{'Stood':>12}{'Voided':>11}{'Compute':>10}{'Third-party':>13}"
                f"{'Minutes':>9}{'Founder':>11}{'Cost to serve':>15}{'Contribution':>14}")
        tags = f"  {'':<18}{'[m]':>12}{'[m]':>11}{'[a]':>10}{'[a]':>13}{'[m]':>9}{'[a]':>11}{'[a]':>15}{'[a]':>14}"
        out += [head, tags]

        def row(name, r):
            return (f"  {name[:18]:<18}{_usd(r['stood']):>12}{_usd(r['voided']):>11}{_usd(r['compute']):>10}"
                    f"{_usd(r['third_party']):>13}{_n(r['minutes']):>9}{_usd(r['founder_usd']):>11}"
                    f"{_usd(r['cost_to_serve']):>15}{_usd(r['contribution']):>14}")

        out += [row(r["name"], r) for r in v["accounts"]]
        out.append(row("Total", v["total"]))
        t = v["total"]
        if v["shared"]:
            out.append(f"  Minutes include {v['shared_each']:,.0f} each of the {v['shared']:,.0f} logged to all "
                       f"accounts [m, spread evenly]. Founder time at {hourly_note}.")
        else:
            out.append(f"  Founder time at {hourly_note}.")
        if t["stood"] > 0:
            out.append(f"  Contribution margin {t['contribution'] / t['stood']:.1%} of revenue that stood [a]. "
                       f"Third-party includes {_usd(t['fees'])} of payment fees [a].")
        if t["held"]:
            out.append(f"  Held at draft for the gate, not yet revenue: {_usd(t['held'])} [m].")
        if v["uninvoiced"]:
            out.append(f"  No invoice this month for {', '.join(v['uninvoiced'])} [m]: a Proving Month, "
                       "or billing not started.")
        if v["loose"]["stood"] or v["loose"]["voided"]:
            out.append(f"  Invoices no account carries: {_usd(v['loose']['stood'])} stood, "
                       f"{_usd(v['loose']['voided'])} voided [m].")
        if not v["runner"]["measured"]:
            out.append("  Compute is not measured this month: no scheduled job was recorded (see runner minutes).")
        out.append("")
        out.append("The three numbers")
        mpa = v["minutes_per_account"]
        if mpa is None:
            out.append(f"  {'Founder minutes per account-month':<36}not measured")
        else:
            out.append(f"  {'Founder minutes per account-month':<36}{mpa:,.0f} [m]  ({t['minutes']:,.0f} over "
                       f"{v['n']} account{'s' if v['n'] != 1 else ''}; {v['logged_accounts']} of {v['n']} "
                       f"carry hand-logged time)")
            if v["minutes_paced"] != mpa:
                out.append(f"  {'':<36}{v['minutes_paced']:,.0f} at this month's pace [a]")
        missing = [part for part, ok in (("compute", v["runner"]["measured"]),
                                         ("third-party usage", v["measured"]["usage"]),
                                         ("founder time", v["measured"]["time"])) if not ok]
        out.append(f"  {'Cost to serve per account':<36}{_usd(v['cost_per_account'])} [a]"
                   + (f"  (without {', '.join(missing)}: not measured)" if missing else ""))
        out.append(f"  {'Capacity':<36}{_cap_line(v)}")
    out.append("")

    per = f"; {_usd(v['fixed_per_account'])} per account" if v["n"] else ", carried by no account"
    out.append(f"Fixed base  {_usd(v['fixed_total'])} a month [a]{per}")
    for name, c in v["fixed_items"]:
        out.append(f"  {name:<24}{_usd(c['value']):>10}  {BASIS.get(c['basis'], c['basis'])}")
    r = v["runner"]
    if r["measured"]:
        out.append(f"  {'runner, the machine':<24}{_usd(r['machine_usd']):>10}  {r['machine_minutes']:,.0f} minutes "
                   "that were no account's [a]")
    out.append(f"  {'usage no account carried':<24}{_usd(v['machine_usage']):>10}  [a]")
    if not v["n"] and v["shared"]:
        out.append(f"  founder minutes logged to all accounts, with none served: {v['shared']:,.0f} [m]")
    if v["n"]:
        out.append(f"After the fixed base  {_usd(v['after_fixed'])} [a] across {v['n']} account"
                   f"{'s' if v['n'] != 1 else ''}")
    out.append("")

    fired = sum(r["fired"].values())
    setup = f"{v['setup']:g} s of setup ({basis(cfg, 'rate.github_actions.setup_seconds_per_job')})"
    price = (f"{value(cfg, 'rate.github_actions.included_minutes'):,.0f} minutes included "
             f"({basis(cfg, 'rate.github_actions.included_minutes')}), "
             f"${value(cfg, 'rate.github_actions.usd_per_minute'):g} a minute beyond "
             f"({basis(cfg, 'rate.github_actions.usd_per_minute')})")
    if r["measured"]:
        out.append(f"GitHub runner minutes  {r['billed_minutes']:,} billed [a]: {r['jobs']:,} job runs recorded [m] "
                   f"(the schedule fired {fired:,} times), each rounded up to the minute with {setup}")
        out.append(f"  on accounts {r['account_minutes']:,.1f} [m] · winning accounts {r['acquisition_minutes']:,.1f} [m]"
                   f" · the machine {r['machine_minutes']:,.1f} [a]")
        out.append(f"  bill {_usd(r['bill'])} [a]: {price}")
        if r["jobs"] < r["fired_total"]:
            out.append(f"  only {r['jobs']:,} of the {r['fired_total']:,} scheduled runs were recorded [m], "
                       "so these minutes are a floor, not the month")
    else:
        out.append(f"GitHub runner minutes  not measured: no scheduled job recorded this month. The schedule fired "
                   f"{fired:,} times, so at least {r['floor_minutes']:,} billed minutes [a]")
        out.append(f"  and a bill of at least {_usd(r['floor_usd'])} [a]: {price}")
    if r["local_seconds"]:
        out.append(f"  by hand on the Mac: {r['local_seconds'] / 60:,.1f} minutes [m], not billed")
    out.append("")

    out.append(f"{'Third-party usage':<48}{'quantity [m]':>14}{'cost [a]':>12}")
    for (svc, item, unit), line in sorted(v["lines"].items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        label = " ".join(str(x) for x in (svc, item, unit) if x)
        if not line["priced"]:
            how = (f"no rate: hubricon economics --set {_anthropic_key(item, unit)} <usd>"
                   if svc == meter.ANTHROPIC else "no rate for this service")
        elif svc == meter.ANTHROPIC:
            how = f"{basis(cfg, _anthropic_key(item, unit))} rate"
        else:
            how = _quota_note(v, svc, unit) or "priced at 0"
        out.append(f"  {label[:46]:<46}{line['quantity']:>14,.0f}{_usd(line['usd'] if line['priced'] else None):>12}"
                   f"  {how}")
    fees = v["total"]["fees"] + v["loose"]["fees"]
    if fees:
        out.append(f"  {'stripe fees on paid invoices':<46}{'':>14}{_usd(fees):>12}  "
                   f"{basis(cfg, 'rate.stripe.ach_pct')} rates")
    if not v["lines"] and not fees:
        out.append("  nothing recorded this month" + ("" if v["measured"]["usage"] else " (not measured)"))
    out.append("")

    a = v["acquisition"]
    out.append("Winning accounts (kept out of cost to serve)")
    out.append(f"  founder minutes {_n(a['minutes'])} [m] -> {_usd(a['founder_usd'])} [a]; usage "
               f"{_usd(a['usage_usd'])} [a]; runner {_usd(a['compute_usd'])} [a]")
    if a["new_accounts"]:
        out.append(f"  {len(a['new_accounts'])} account{'s' if len(a['new_accounts']) != 1 else ''} began service "
                   f"({', '.join(a['new_accounts'])}): {_usd(a['per_account_won'])} per account won [a]")
    else:
        out.append("  no account began service this month, so there is no cost per account won")
    out.append("")

    out.append("Scale curve: cost to serve per account, month over month")
    out.append(f"  {'Month':<9}{'Accounts':>9}{'Min/acct':>10}{'Cost to serve':>15}{'Fixed':>11}{'All-in':>11}")
    out.append(f"  {'':<9}{'[m]':>9}{'[m]':>10}{'[a]':>15}{'[a]':>11}{'[a]':>11}")
    blank = False
    for c in curve:
        mpa = c["minutes_per_account"] if c["minutes_per_account"] else None
        cost = c["cost_per_account"] if c["recorded"] else None
        allin = cost + c["fixed_per_account"] if (c["n"] and cost is not None) else None
        blank = blank or bool(c["n"] and (mpa is None or cost is None))
        out.append(f"  {c['label']:<9}{c['n']:>9}{_n(mpa):>10}{_usd(cost):>15}{_usd(c['fixed_per_account']):>11}"
                   f"{_usd(allin):>11}" + ("   month to date" if c["elapsed"] < 1 else ""))
    if blank:
        out.append("  — nothing recorded on that month's accounts: before the meter and the log began, "
                   "or not logged. Never read as zero.")
    return "\n".join(out)


def _quota_note(v: dict, svc: str, unit: str) -> str | None:
    spec = QUOTAS.get((svc, unit))
    if not spec:
        return None
    cfg = v["config"]
    included = value(cfg, spec[2])
    used = v["totals"].get((svc, unit), 0.0)
    where = "inside" if used <= included else "past"
    return f"{used:,.0f} of {included:,.0f} included ({basis(cfg, spec[2])}), {where} the quota"


def curve_row(v: dict) -> dict:
    return {k: v[k] for k in ("label", "n", "minutes_per_account", "cost_per_account", "fixed_per_account",
                              "elapsed", "recorded")}


# -- the commands ----------------------------------------------------------------------------

def report(db, month: date | None = None, now: datetime | None = None) -> str:
    """Sync what the calendar says, load a year at most, and print the month."""
    now = now or datetime.now(timezone.utc)
    month = month or _month_start(now.date())
    if _midnight(month) > now:
        raise ValueError(f"{month:%Y-%m} has not started.")
    written, sync = sync_calendar(db, now)
    notes = []
    if written:
        notes.append(f"Calendar: {written} entr{'y' if written == 1 else 'ies'} written to founder_time "
                     "(booked calls at their scheduled length, kickoffs) [m].")
    if sync.startswith("failed"):
        notes.append(f"Calendar entries not written ({sync}); the report reads what is there.")
    book = load(db, _add_months(month, -(CURVE_MONTHS - 1)), now)
    views = [month_view(book, m, now) for m in curve_months(book, month)]
    return render(views[-1], [curve_row(x) for x in views], notes)


def _parse_month(s: str) -> date:
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", (s or "").strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise ValueError(f"--month takes YYYY-MM, not {s!r}.")
    return date(int(m.group(1)), int(m.group(2)), 1)


def cmd_economics(args):
    from . import db as dbmod
    db = dbmod.connect()
    if args.set:
        try:
            print(set_config(db, *args.set))
        except ValueError as err:
            sys.exit(str(err))
        return
    if args.config:
        print(render_config(*load_config(db)))
        return
    try:
        month = _parse_month(args.month) if args.month else None
        print(report(db, month))
    except ValueError as err:
        sys.exit(str(err))


def register(sub) -> None:
    """Add `economics` and `log` to the CLI (cli.main)."""
    about = ("unit economics: what an account-month costs in compute, third-party usage and founder minutes, "
             "per account and in total, with the scale curve")
    p = sub.add_parser("economics", help=about, description=about[0].upper() + about[1:] + ".")
    p.add_argument("--month", help="YYYY-MM (default: this month, to date)")
    p.add_argument("--config", action="store_true", help="every price, plan fee and rate the report uses, and whose")
    p.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="replace a placeholder with your own figure")
    p.set_defaults(fn=cmd_economics)

    about = "log founder minutes: hubricon log <client|prospect|all> <minutes> <what>"
    p = sub.add_parser("log", help=about, description=about[0].upper() + about[1:] + ". Time before a client's "
                       "yes or kickoff counts as winning them; 'all' is work for every account at once.")
    p.add_argument("target", help="a client (uuid, prefix, email or company name), a prospect's email, or 'all'")
    p.add_argument("minutes", help="minutes spent, e.g. 30")
    p.add_argument("what", nargs="+", help="what they were for")
    p.add_argument("--on", help="YYYY-MM-DD (default: today, Chicago)")
    p.set_defaults(fn=cmd_log)
