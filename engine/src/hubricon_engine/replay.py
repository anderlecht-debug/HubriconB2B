"""Did the promises come true? The harness that scores the engine against itself.

Every directive the engine issues carries a dollar figure and, for a price step,
a whole distribution. The measurement pass already compares each one with the
client's own later exports. What was missing is the pass ABOVE that: over all
directives ever measured, was the promise calibrated? Did the measured delta land
inside the range we published? Did we systematically over-promise?

That question cannot be answered by a model. It can only be answered by replay,
and replay needs two things from every directive: that its evidence blob carries
everything required to rebuild the counterfactual, and that the range it is
scored against is the range it actually promised. `completeness` checks the
first; `score` answers the second.

The harness runs in two modes.

  replay(directives, ...)  re-runs the measurement pass over a set of historical
                           directives and current exports and returns a scorecard.
                           This is what `hubricon replay <client>` does.
  score(directives)        scores directives that already carry a measured
                           impact, without re-measuring — for a client whose
                           history was measured on earlier runs.

Both report `status: "pending"` rather than a number when there is not yet a
measured directive to score, because a backtest with no history is a harness, not
a result, and calling it anything else would be the failure this engine exists to
avoid.
"""

from datetime import date

from .models.common import num

# Below this many scored directives the calibration statistics are noise. The
# harness reports them anyway, labelled, because a client with four measured
# moves is entitled to see their four — but `calibrated` stays None.
MIN_SCORED_FOR_CALIBRATION = 8

# What realisation ratio a CORRECT engine should show, and why it is not 1.
#
# measurement.py banks the 25th percentile of the measured-delta distribution and
# caps the claim at what the SKU's profit actually rose, so an engine whose
# forecasts are exactly right still books less than it promised. On simulated
# sellers whose demand responded exactly as the fitted curve said, the ratio comes
# out near 0.6. Below MIN_REALISATION the engine is over-promising in a way the
# deliberate conservatism cannot explain; above MAX_REALISATION it is banking more
# than it forecast, which means the promise was too small and is also worth
# knowing.
MIN_REALISATION = 0.30
MAX_REALISATION = 1.30
# And the published 90% band should contain the measured outcome about 90% of the
# time. A little over is fine — the band is conservative by construction.
MIN_BAND_COVERAGE = 0.80

# What a price-step evidence blob must carry for its counterfactual to be
# rebuildable from scratch. Anything missing means the promise cannot be audited,
# which is a defect in the directive and not in the replay.
PRICE_STEP_REQUIRED = (
    "sku", "p0", "p_new", "elasticity", "ci95",
    "baseline_units", "baseline_revenue", "baseline_period",
)
# And what it must carry for the promise to be scored against the range it made,
# rather than against two endpoints reconstructed later.
PRICE_STEP_DISTRIBUTION = ("delta_p5", "delta_p50", "delta_p95", "p_loss", "mc_inputs")

BANKABLE_REQUIRED = {
    "price_step": PRICE_STEP_REQUIRED,
    "fee_anomaly": ("scope", "item_id", "metric", "baseline", "current", "since"),
    "referral_anomaly": ("scope", "item_id", "metric", "baseline", "current", "since"),
    "spend_step": ("scope", "item_id", "metric", "baseline", "current", "since"),
    "ad_bleed_terms": ("terms", "baseline_spend", "campaign_baseline_spend"),
    "campaign_trim": ("campaign_name", "current_spend", "breakeven_spend", "horizon_days"),
    "branded_pause": ("brand_terms", "baseline_spend", "n_terms", "incrementality_mid"),
    "negative_margin_sku": ("sku", "baseline_period", "baseline_units", "baseline_revenue",
                            "baseline_net"),
    "recovery_filing": ("claim_keys", "face_value", "expected_value"),
    "low_inventory_fee": ("skus", "monthly_fee", "per_sku"),
    "aged_surcharge": ("skus", "monthly_surcharge", "per_sku"),
    "budget_reallocation": ("campaigns", "total_spend", "lambda", "avg_margin", "horizon_days",
                            "delta_p5", "delta_p50", "delta_p95", "mc_inputs"),
    "markdown": ("sku", "p0", "p_new", "depth", "elasticity", "ci95", "baseline_units", "baseline_revenue",
                 "baseline_period", "carry_saving_p50"),
}
# Every kind that promised a DISTRIBUTION, and the fields that distribution is.
DISTRIBUTION_FIELDS = {
    "price_step": PRICE_STEP_DISTRIBUTION,
    "budget_reallocation": ("delta_p5", "delta_p50", "delta_p95", "p_loss", "mc_inputs"),
    "markdown": PRICE_STEP_DISTRIBUTION,
}


def completeness(directive: dict) -> dict:
    """Can this directive's promise be rebuilt and audited from its own evidence?

    Promise integrity is not a property of the measurement code — it is a
    property of what the draft wrote down at the moment it made the promise. A
    directive missing a field here cannot be scored honestly later, whatever the
    measurement pass does."""
    kind = directive.get("kind")
    evidence = directive.get("evidence") or {}
    required = BANKABLE_REQUIRED.get(kind)
    if required is None:
        return {"kind": kind, "checked": False,
                "reason": "no rebuild contract for this kind — nothing is banked on it"}
    missing = [f for f in required if evidence.get(f) is None]
    out = {"kind": kind, "checked": True, "complete": not missing, "missing": missing}
    if kind in DISTRIBUTION_FIELDS:
        # A price step (or a reallocation) promised a DISTRIBUTION, not two
        # endpoints. If the blob carries only the endpoints, the range it is
        # scored against is not the range it made.
        dist_missing = [f for f in DISTRIBUTION_FIELDS[kind] if evidence.get(f) is None]
        out["distribution_complete"] = not dist_missing
        out["distribution_missing"] = dist_missing
        # and the promise itself must be the one the distribution describes
        promised = directive.get("expected_impact_usd")
        out["promise_matches_distribution"] = (
            promised is None or evidence.get("delta_p50") is None
            or abs(float(promised) - float(evidence["delta_p50"])) < 0.02
        )
    return out


def _promise_band(directive: dict) -> tuple[float, float] | None:
    evidence = directive.get("evidence") or {}
    lo, hi = evidence.get("delta_p5"), evidence.get("delta_p95")
    if lo is None or hi is None:
        return None
    return float(lo), float(hi)


def score(directives: list[dict]) -> dict:
    """Promise against outcome, over every directive already measured.

    Three numbers matter. The realisation ratio — measured dollars over promised
    dollars — says whether the engine over-promises. The band coverage says
    whether the published range meant anything. The count of directives whose
    evidence could not be audited at all says whether the rest can be trusted."""
    scored, bandable = [], []
    audit = {"complete": 0, "incomplete": 0, "unchecked": 0, "missing_fields": {}}
    for d in directives:
        check = completeness(d)
        if not check.get("checked"):
            audit["unchecked"] += 1
        elif check.get("complete"):
            audit["complete"] += 1
        else:
            audit["incomplete"] += 1
            for field in check.get("missing", []):
                key = f"{d.get('kind')}.{field}"
                audit["missing_fields"][key] = audit["missing_fields"].get(key, 0) + 1

        measured = d.get("measured_impact_usd")
        promised = d.get("expected_impact_usd")
        if measured is None:
            continue
        scored.append({
            "kind": d.get("kind"), "dedupe_key": d.get("dedupe_key"),
            "promised": None if promised is None else float(promised),
            "measured": float(measured),
        })
        band = _promise_band(d)
        if band is not None:
            lo, hi = band
            bandable.append({"kind": d.get("kind"), "measured": float(measured),
                             "p5": lo, "p95": hi, "inside": lo <= float(measured) <= hi})

    with_promise = [s for s in scored if s["promised"] is not None]
    promised_total = sum(s["promised"] for s in with_promise)
    measured_total = sum(s["measured"] for s in with_promise)
    out = {
        "n_directives": len(directives),
        "n_scored": len(scored),
        "n_with_promise": len(with_promise),
        "promised_total": num(promised_total),
        "measured_total": num(measured_total),
        "realisation_ratio": num(measured_total / promised_total, 4) if promised_total else None,
        "n_banded": len(bandable),
        "band_coverage": num(sum(b["inside"] for b in bandable) / len(bandable), 4)
        if bandable else None,
        "evidence_audit": audit,
        "scored": scored,
        "banded": bandable,
    }
    if len(scored) < MIN_SCORED_FOR_CALIBRATION:
        out["status"] = "pending"
        out["calibrated"] = None
        out["note"] = (
            f"{len(scored)} measured directive(s) on file; calibration needs "
            f"{MIN_SCORED_FOR_CALIBRATION}. The harness runs and reports what exists — "
            f"it does not report a ratio computed on too little to mean anything."
        )
    else:
        out["status"] = "ok"
        ratio = out["realisation_ratio"]
        coverage = out["band_coverage"]
        # Two independent things have to hold. The ratio says whether the dollar
        # figure was honest; the band coverage says whether the range around it
        # meant anything. A ratio near target achieved by large errors cancelling
        # would pass the first and fail the second.
        out["over_promising"] = bool(ratio is not None and ratio < MIN_REALISATION)
        out["under_promising"] = bool(ratio is not None and ratio > MAX_REALISATION)
        out["calibrated"] = bool(
            ratio is not None and MIN_REALISATION <= ratio <= MAX_REALISATION
            and (coverage is None or coverage >= MIN_BAND_COVERAGE)
        )
        verdict = ("calibrated" if out["calibrated"]
                   else "OVER-PROMISING" if out["over_promising"]
                   else "under-promising" if out["under_promising"]
                   else "the published range is not holding")
        out["note"] = (
            f"{len(scored)} measured directives: {out['measured_total']} banked against "
            f"{out['promised_total']} promised"
            + (f", and {coverage:.0%} of measured outcomes landed inside the published range"
               if coverage is not None else "")
            + f" — {verdict}. A correct engine books less than it promises here: the Record "
              f"banks the 25th percentile of the fitted range and caps each claim at what the "
              f"SKU's profit actually rose, so the target band is "
              f"{MIN_REALISATION:.2f}–{MAX_REALISATION:.2f}, not 1.00."
        )
    return out


def replay(directives: list[dict], data: dict, margins: list[dict], ads_rows: list[dict],
           claims: list[dict], today: date | None = None,
           inv_econ: dict | None = None, switchbacks: list[dict] | None = None,
           experiments: list[dict] | None = None) -> dict:
    """Re-measure a set of historical directives against current exports, then
    score the promises. Returns the scorecard plus the verdicts that produced it,
    so a disagreement with the live ledger is visible rather than silent.

    Import is deferred: measurement imports models, models import this module's
    siblings, and a top-level import would make the cycle."""
    from . import measurement

    verdicts = measurement.measure(
        [{**d, "measured_at": None} for d in directives],
        data, margins, ads_rows, claims, today=today, inv_econ=inv_econ, switchbacks=switchbacks,
        experiments=experiments,
    )
    by_id = {d.get("id") or d.get("dedupe_key"): d for d in directives}
    replayed = []
    for v in verdicts:
        original = by_id.get(v.get("directive_id")) or {}
        replayed.append({
            **original,
            "measured_impact_usd": v.get("measured_impact_usd"),
            "replay_verdict": v.get("verdict"),
            "replay_note": v.get("note"),
        })
    out = score(replayed)
    out["verdicts"] = verdicts
    # Where the live ledger already holds a measurement, replay must agree with
    # it. A disagreement means the measurement code changed under a promise that
    # was already banked, which is the one thing a Profit Record cannot do.
    drift = []
    for d in directives:
        live = d.get("measured_impact_usd")
        if live is None:
            continue
        again = next((r["measured_impact_usd"] for r in replayed
                      if (r.get("id") or r.get("dedupe_key")) == (d.get("id") or d.get("dedupe_key"))),
                     None)
        if again is not None and abs(float(again) - float(live)) > 0.01:
            drift.append({"dedupe_key": d.get("dedupe_key"), "kind": d.get("kind"),
                          "banked": float(live), "replayed": float(again)})
    out["drift"] = drift
    out["drift_free"] = not drift
    return out


def render(scorecard: dict) -> str:
    """The scorecard as a few lines of plain text, for the CLI and the operator
    log."""
    lines = [f"Replay: {scorecard['n_directives']} directive(s), "
             f"{scorecard['n_scored']} with a measured outcome"]
    lines.append(f"  status: {scorecard['status']}")
    if scorecard.get("note"):
        lines.append(f"  {scorecard['note']}")
    if scorecard.get("realisation_ratio") is not None:
        lines.append(f"  realisation: {scorecard['realisation_ratio']:.2f}x promised "
                     f"({scorecard['measured_total']} of {scorecard['promised_total']})")
    if scorecard.get("band_coverage") is not None:
        lines.append(f"  published range contained the outcome "
                     f"{scorecard['band_coverage']:.0%} of the time "
                     f"({scorecard['n_banded']} scored against a range)")
    audit = scorecard["evidence_audit"]
    lines.append(f"  evidence rebuildable: {audit['complete']} complete, "
                 f"{audit['incomplete']} incomplete, {audit['unchecked']} not banked on")
    for key, count in sorted(audit["missing_fields"].items(), key=lambda kv: -kv[1])[:5]:
        lines.append(f"    missing {key} on {count} directive(s)")
    if "drift_free" in scorecard:
        lines.append("  replay agrees with the banked ledger"
                     if scorecard["drift_free"] else
                     f"  DRIFT: {len(scorecard['drift'])} banked measurement(s) "
                     f"no longer reproduce")
    return "\n".join(lines)
