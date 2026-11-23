"""Shadow mode: the engine makes its calls every week, seals them, and acts on
none of them.

A brand that has just installed has no reason to let anything touch its prices.
What it can be shown instead is the engine being right, or wrong, in public:
each weekly run writes down, before the week starts,

  * per SKU, the units it expects next week and the profit they carry, each
    with a 90% range; and
  * every move the engine WOULD make (directives.draft_directives on the
    store's own rows), with the expected dollars it would have promised;

and seals every one of those calls on the client's Record chain through
seal.seal_called, exactly as an issued move is sealed. A shadow call is a
directive-shaped dict (module "shadow", mandate "shadow", status "shadow",
evidence.executed False) so the Seal needs no change and its export shows
plainly what was a shadow call. Nothing here writes to the store, and nothing
here writes to the directives table: a shadow call is never a move.

grade() then sets the sealed calls against the week as it happened. The units
call is a hit when the week's actual units land inside its 90% range; the gap
is actual less expected, summed. The profit calls go through
replay.score, the same harness that scores every issued move (realisation ratio
and band coverage). calibration.py is not used: it pools consenting clients'
accounts into the cold engine's priors, which is a different question from
whether one store's calls came true. With a database, each graded call gets
its measured entry sealed (seal.seal_measured), answering its called leaf, so
the grade is on the chain beside the call.

The 90% range. models/forecast.py fits a daily rate and the spread of its own
out-of-sample errors (details.error_sd, moderated across the catalogue). Next
week's units are that rate times seven, and the range is the point plus or
minus 1.645 error sds times seven, floored at zero: forecast.py's own
documented simplification of scaling a one-step rate band by the horizon.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta

from . import directives as directives_mod
from . import seal as sealmod
from .lookback import _safe, complete, unit_margins
from .models import elasticity, forecast, margin, shopify_findings
from .models.common import num
from .replay import score

MODULE = "shadow"
FORECAST_KIND = "shadow_forecast"
MOVE_PREFIX = "shadow_"
HORIZON_DAYS = 7
Z90 = 1.6448536269514722            # scipy.stats.norm.ppf(0.95): the edges of a central 90%
NAMESPACE = uuid.UUID("6f1c3a52-6b0e-4d55-9a57-2f7d1c9b0a11")   # shadow call ids, stable per week and subject
NOT_EXECUTED = "Shadow call, not executed."


def call_id(client_id: str, week_start: date, kind: str, subject: str) -> str:
    """The same call on a re-run is the same id, so the Seal's entry key
    (called:<id>) refuses to seal it twice."""
    return str(uuid.uuid5(NAMESPACE, f"{client_id}|{week_start.isoformat()}|{kind}|{subject}"))


def _jsonable(v):
    return json.loads(json.dumps(v, default=lambda x: float(x) if hasattr(x, "__float__") else str(x)))


def _call(client_id, week_start, kind, subject, expected, action, evidence, issued_at) -> dict:
    week_end = week_start + timedelta(days=HORIZON_DAYS - 1)
    return {
        "id": call_id(client_id, week_start, kind, subject),
        "client_id": client_id,
        "channel": "shopify",
        "module": MODULE,
        "kind": kind,
        "status": "shadow",
        "mandate": "shadow",
        "issued_at": issued_at,
        "expected_impact_usd": None if expected is None else num(expected),
        "action_text": f"{NOT_EXECUTED} {action}",
        "dedupe_key": directives_mod.dedupe_key(MODULE, kind, [subject, week_start.isoformat()]),
        "evidence": _jsonable({**evidence, "week_start": week_start.isoformat(), "week_end": week_end.isoformat(),
                               "executed": False}),
    }


def forecast_calls(data: dict, client_id: str, week_start: date, issued_at: str,
                   forecasts: list[dict], margins: list[dict]) -> list[dict]:
    per_unit = unit_margins(margins)
    out = []
    for f in forecasts:
        if f.get("level") != "sku" or f.get("status") != "ok":
            continue
        sku = f["item_id"]
        rate = float(f["daily_rate_point"])
        sd = (f.get("details") or {}).get("error_sd")
        if sd is None:
            sd = (float(f["daily_rate_p90"]) - float(f["daily_rate_p10"])) / forecast.NORMAL_P10_P90_WIDTH
        units = rate * HORIZON_DAYS
        lo, hi = max(0.0, (rate - Z90 * float(sd)) * HORIZON_DAYS), (rate + Z90 * float(sd)) * HORIZON_DAYS
        m = per_unit.get(sku)
        ev = {"sku": sku, "units_p50": num(units, 2), "units_p5": num(lo, 2), "units_p95": num(hi, 2),
              "method": f.get("method"), "daily_rate": num(rate, 4), "error_sd": num(float(sd), 4),
              "unit_margin": None if m is None else num(m, 4), "horizon_days": HORIZON_DAYS}
        profit = None
        if m is not None:
            profit = units * m
            p = sorted((lo * m, hi * m))
            ev.update({"delta_p5": num(p[0]), "delta_p50": num(profit), "delta_p95": num(p[1])})
        text = (f"{sku} sells {units:,.0f} units in the week of {week_start.isoformat()} "
                f"(90% range {lo:,.0f} to {hi:,.0f})"
                + (f", ${profit:,.0f} profit (90% range ${ev['delta_p5']:,.0f} to ${ev['delta_p95']:,.0f})."
                   if profit is not None else "; no unit cost on file, so no profit call."))
        out.append(_call(client_id, week_start, FORECAST_KIND, sku, profit, text, ev, issued_at))
    return out


def move_calls(data: dict, client_id: str, week_start: date, issued_at: str,
               fits: list[dict], margins: list[dict]) -> list[dict]:
    """What the engine would draft this week, priced, executed never."""
    drafts = _safe(directives_mod.draft_directives, [], [], fits, margins, channel="shopify",
                   client_id=client_id, shopify_findings=_safe(shopify_findings.run, data), default=[]) or []
    out = []
    for d in drafts:
        if d.get("expected_impact_usd") is None:
            continue
        ev = d.get("evidence") or {}
        subject = d.get("dedupe_key") or ev.get("sku") or d.get("kind")
        out.append(_call(client_id, week_start, MOVE_PREFIX + str(d.get("kind")), subject,
                         float(d["expected_impact_usd"]), f"Would do: {d.get('action_text')}",
                         {**ev, "would_be_kind": d.get("kind"), "would_be_mandate": d.get("mandate")}, issued_at))
    return out


def calls(data: dict, client_id: str, week_start: date, issued_at=None) -> list[dict]:
    """This week's shadow calls from the store's rows (weekly sku_economics,
    the cost sheet, the stock snapshot). Pure."""
    issued_at = sealmod.stamp(issued_at or datetime.now(UTC))
    data = complete(data)
    margins = _safe(margin.run, data, default=[])
    fits = _safe(elasticity.run, data, default=[])
    forecasts = _safe(forecast.run, data, horizon_days=HORIZON_DAYS, elasticity_rows=fits, default=[])
    return (forecast_calls(data, client_id, week_start, issued_at, forecasts, margins)
            + move_calls(data, client_id, week_start, issued_at, fits, margins))


def seal_calls(db, client_id: str, shadow_calls: list[dict], sealed_at=None) -> dict:
    """Seal each call before its week starts. Never raises (seal.seal_called)."""
    return sealmod.seal_called(db, client_id, shadow_calls, sealed_at=sealed_at)


def run(db, data: dict, client_id: str, week_start: date, issued_at=None) -> dict:
    out = calls(data, client_id, week_start, issued_at)
    return {"calls": out, "seal": seal_calls(db, client_id, out, sealed_at=issued_at)}


# ── grading ──────────────────────────────────────────────────────────────────

def actuals(econ_rows: list[dict], cogs_rows: list[dict], week_start: date) -> dict[str, dict]:
    """{sku: {units, profit}} for the week, from its sku_economics rows (a week
    crossing a month end is two rows) and models/margin.run's net margin."""
    end = (week_start + timedelta(days=HORIZON_DAYS - 1)).isoformat()
    rows = [r for r in econ_rows if week_start.isoformat() <= str(r["period_start"])[:10] <= end]
    out: dict[str, dict] = {}
    for r in rows:
        a = out.setdefault(r["sku"], {"units": 0.0, "profit": 0.0, "costed": None})
        a["units"] += float(r.get("units_sold") or 0)
    for m in _safe(margin.run, complete({"sku_economics": rows, "cogs_inputs": cogs_rows}), default=[]):
        a = out[m["sku"]]
        a["profit"] += float(m["net_margin"] or 0)
        a["costed"] = a["costed"] is not False and m.get("cogs") is not None
    return {s: {**a, "costed": bool(a["costed"])} for s, a in out.items()}


def grade(shadow_calls: list[dict], econ_rows: list[dict], cogs_rows: list[dict] | None = None,
          db=None, client_id: str | None = None, measured_at=None) -> dict:
    """Sealed calls against the week as it happened.

    hit_rate   share of the units calls whose actual units fell inside the 90% range
    gap_units  sum of (actual - expected) units over those calls
    gap_usd    sum of (actual - expected) profit over the profit calls
    replay     replay.score over the profit calls: realisation ratio, band coverage
    A SKU with no rows in the week sold nothing, so it grades as zero units."""
    measured_at = sealmod.stamp(measured_at or datetime.now(UTC))
    by_week: dict[str, dict] = {}
    graded, scored = [], []
    for c in shadow_calls:
        if c.get("kind") != FORECAST_KIND:
            continue                      # a move's outcome is never observed: it was not made
        ev = c["evidence"]
        wk = ev["week_start"]
        if wk not in by_week:
            by_week[wk] = actuals(econ_rows, cogs_rows or [], date.fromisoformat(wk))
        a = by_week[wk].get(ev["sku"], {"units": 0.0, "profit": 0.0, "costed": True})
        hit = float(ev["units_p5"]) <= a["units"] <= float(ev["units_p95"])
        row = {"id": c["id"], "sku": ev["sku"], "week_start": wk, "expected_units": ev["units_p50"],
               "range_units": [ev["units_p5"], ev["units_p95"]], "actual_units": a["units"],
               "hit": hit, "gap_units": num(a["units"] - float(ev["units_p50"]), 2)}
        if c.get("expected_impact_usd") is not None and a["costed"]:
            row.update({"expected_usd": c["expected_impact_usd"], "actual_usd": num(a["profit"]),
                        "gap_usd": num(a["profit"] - float(c["expected_impact_usd"]))})
            scored.append({**c, "status": "measured", "attribution": "direct",
                           "measured_impact_usd": num(a["profit"]), "measured_at": measured_at,
                           "evidence": {**ev, "after": {"units": a["units"], "profit": num(a["profit"])}}})
        graded.append(row)
    n = len(graded)
    out = {
        "n_graded": n,
        "hits": sum(r["hit"] for r in graded),
        "hit_rate": num(sum(r["hit"] for r in graded) / n, 4) if n else None,
        "target_hit_rate": 0.90,
        "gap_units": num(sum(r["gap_units"] for r in graded), 2),
        "gap_usd": num(sum(r["gap_usd"] for r in graded if "gap_usd" in r)),
        "rows": graded,
        "replay": score(scored) if scored else None,
    }
    if db is not None and client_id and scored:
        out["seal"] = sealmod.seal_measured(db, client_id, scored, sealed_at=measured_at)
    return out
