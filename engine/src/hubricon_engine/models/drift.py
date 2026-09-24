"""Model decay: has the world moved since the last fit, and are the promises
still coming true?

A model tuned last quarter quietly decays. Two things say so. The PROMISES:
the replay harness scores every measured directive against what it promised,
and until 2026-09-23 it pooled them all into one realisation ratio — a ratio
that was calibrated on last year's directives and is not on this quarter's
would still read fine. replay.score now also scores by 90-day cohort of the
measurement date, with a block-bootstrap band per cohort, a Mann–Kendall trend
test across cohorts, and a `decaying` flag when the latest cohort sits below
the floor the pooled figure clears. The PARAMETERS: every elasticity and every
ad curve is re-fitted each run, and this module compares each new fit with
the previous run's on the same item:

    z = (θ_new − θ_old) / sqrt(se_new² + se_old²)

with Benjamini–Hochberg across every item in the sweep (the anomaly pass's
false-discovery control, reused), so a catalogue of four hundred SKUs does not
produce twenty "drifted" elasticities by chance every fortnight. A drifted fit
carries `details.drift` and the pricing engine halves its risk tolerance for
the cycle — a stated rule: a fit that just moved walks half as far until the
next run says it has settled.

The two fits share most of their data (last month's periods plus one more), so
z overstates independence and understates the standard error of the change;
that is the conservative direction for a drift flag (fewer false calms, more
false alarms, and the alarms only shorten a step). Stated, not corrected.

WHAT IT CANNOT TELL YOU. Why a parameter moved. A drifted elasticity may be a
new competitor, a season, or the estimator seeing one more period of the same
reactive history; the flag halves the step and the next run decides.
"""

import numpy as np
from scipy import stats

from .common import num
from .null_calibration import benjamini_hochberg

DRIFT_Q = 0.05
TOLERANCE_SCALE_ON_DRIFT = 0.5


def _pairs_elasticity(new_rows, old_rows):
    old = {(r["level"], r["item_id"]): r for r in old_rows or [] if r.get("status") == "ok" and r.get("std_err")}
    for r in new_rows or []:
        if r.get("status") != "ok" or not r.get("std_err"):
            continue
        o = old.get((r["level"], r["item_id"]))
        if o is None:
            continue
        yield {"kind": "elasticity", "level": r["level"], "item_id": r["item_id"],
               "new": float(r["elasticity"]), "old": float(o["elasticity"]),
               "se_new": float(r["std_err"]), "se_old": float(o["std_err"])}


def _pairs_ads(new_rows, old_rows):
    old = {r["campaign_name"]: r for r in old_rows or [] if r.get("status") == "ok"}
    for r in new_rows or []:
        if r.get("status") != "ok":
            continue
        o = old.get(r["campaign_name"])
        if o is None:
            continue
        un, uo = (r.get("details") or {}).get("uncertainty") or {}, (o.get("details") or {}).get("uncertainty") or {}
        if un.get("basis") != "parameter_covariance" or uo.get("basis") != "parameter_covariance":
            continue
        # marginal ROAS at current spend, its se read off the published band
        se_new = (float(un["marginal_roas_p95"]) - float(un["marginal_roas_p5"])) / (2 * 1.645)
        se_old = (float(uo["marginal_roas_p95"]) - float(uo["marginal_roas_p5"])) / (2 * 1.645)
        if se_new <= 0 or se_old <= 0 or r.get("marginal_roas") is None or o.get("marginal_roas") is None:
            continue
        yield {"kind": "ad_curve", "level": "campaign", "item_id": r["campaign_name"],
               "new": float(r["marginal_roas"]), "old": float(o["marginal_roas"]), "se_new": se_new, "se_old": se_old}


def compare_runs(new_elasticity, old_elasticity, new_ads, old_ads, q: float = DRIFT_Q) -> dict:
    pairs = list(_pairs_elasticity(new_elasticity, old_elasticity)) + list(_pairs_ads(new_ads, old_ads))
    if not pairs:
        return {"status": "insufficient_data", "n_pairs": 0, "drifted": [],
                "basis": "no item fitted on both this run and the previous one"}
    for p in pairs:
        se = float(np.sqrt(p["se_new"] ** 2 + p["se_old"] ** 2))
        p["z"] = (p["new"] - p["old"]) / se if se > 0 else 0.0
        p["p_value"] = float(2 * stats.norm.sf(abs(p["z"])))
    flags, q_values, _ = benjamini_hochberg([p["p_value"] for p in pairs], q)
    drifted = []
    for p, flag, qv in zip(pairs, flags, q_values):
        p["drifted"] = bool(flag)
        p["z"] = num(p["z"], 3)
        p["p_value"] = num(p["p_value"], 5)
        p["q_value"] = num(qv, 5)
        if p["drifted"]:
            drifted.append({"kind": p["kind"], "level": p["level"], "item_id": p["item_id"], "old": num(p["old"], 4),
                            "new": num(p["new"], 4), "z": p["z"]})
    return {"status": "ok", "n_pairs": len(pairs), "n_drifted": len(drifted), "drifted": drifted,
            "fdr_q": q, "pairs": pairs,
            "basis": (f"{len(pairs)} items fitted on both runs; z on the change against both standard errors; "
                      f"Benjamini–Hochberg at q = {q}; a drifted fit walks half as far this cycle")}


def apply_to_elasticity(rows: list[dict], drift_out: dict | None) -> list[dict]:
    """Mark drifted elasticity rows so the pricing engine can halve their
    tolerance. In place; returns the rows."""
    flagged = {(d["level"], d["item_id"]) for d in (drift_out or {}).get("drifted", []) if d["kind"] == "elasticity"}
    for r in rows or []:
        if (r.get("level"), r.get("item_id")) in flagged:
            r.setdefault("details", {})["drift"] = {"flagged": True, "tolerance_scale": TOLERANCE_SCALE_ON_DRIFT}
    return rows
