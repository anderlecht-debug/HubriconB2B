"""One world, scored: the engine's promises, the truth behind each, what the
Profit Record would bank, and the facts the rubric reads. Pure bookkeeping —
every judgement lives in rubric.py."""
from datetime import timedelta

import numpy as np

from hubricon_engine import measurement
from hubricon_engine.models.cashflow import cash_from_components

from . import truth as truthmod
from .worlds import TODAY

SIMULATED_KINDS = ("price_step", "markdown", "budget_reallocation", "campaign_trim", "ad_bleed_terms")


def world_report(name: str, data: dict, truth: dict, out: dict, seed: int) -> dict:
    after = truthmod.simulate(data, truth, out, seed)
    drafts = [{**d, "id": f"d{i}", "status": "approved", "issued_at": f"{TODAY.isoformat()}T00:00:00+00:00"}
              for i, d in enumerate(out["drafts"])]
    is_stretch = lambda d: d["kind"] == "price_step" and d["evidence"].get("reason") == "stretch"
    due = [d for d in drafts if d["kind"] in SIMULATED_KINDS and not is_stretch(d)]
    verdicts = measurement.measure(due, after["after_data"], out["margins"] + after["after_margins"],
                                   after["ads_after"], [], today=TODAY + timedelta(days=30), inv_econ=out["ie"])
    by_id = {d["id"]: d for d in due}

    # ── the truth of each simulated directive ──
    def truth_of(d):
        k, ev = d["kind"], d["evidence"]
        if k in ("price_step", "markdown"):
            t = after["step_truth"].get(ev.get("sku"))
            return None if t is None else t["full"]
        if k == "budget_reallocation":
            return after["realloc_truth"]
        if k == "campaign_trim":
            return after["trim_truth"].get(ev.get("campaign_name"))
        if k == "ad_bleed_terms":
            return after["bleed_truth"]
        return None

    record = {}
    for v in verdicts:
        d = by_id[v["directive_id"]]
        k = d["kind"]
        r = record.setdefault(k, {"n": 0, "n_measured": 0, "promised": 0.0, "banked": 0.0, "truth": 0.0,
                                  "verdicts": {}})
        r["n"] += 1
        r["verdicts"][v["verdict"]] = r["verdicts"].get(v["verdict"], 0) + 1
        t = truth_of(d)
        if v["verdict"] == "measured" and v.get("measured_impact_usd") is not None and d.get("expected_impact_usd") \
                and t is not None:
            r["n_measured"] += 1
            r["promised"] += float(d["expected_impact_usd"])
            r["banked"] += float(v["measured_impact_usd"])
            r["truth"] += float(t)

    steps = []
    for d in out["drafts"]:
        if d["kind"] not in ("price_step", "markdown") or d.get("expected_impact_usd") is None:
            continue
        ev = d["evidence"]
        t = after["step_truth"].get(ev.get("sku"))
        if t is None:
            continue
        steps.append({"sku": ev["sku"], "kind": d["kind"], "reason": ev.get("reason"),
                      "p50": float(d["expected_impact_usd"]),
                      "p5": ev.get("delta_p5"), "p95": ev.get("delta_p95"), "p_loss": ev.get("p_loss"),
                      "risk_budget": ((ev.get("policy") or {}).get("risk_budget")),
                      "step_fraction": ev.get("step_fraction"), "truth": t["full"], "truth_half": t["half"]})

    # ── elasticity against the truth (pre-drift) ──
    el = [r for r in out["el"] if r["level"] == "sku"]
    ok = [r for r in el if r["status"] == "ok"]
    eps_true = {s: t["eps"] for s, t in truth["skus"].items()}
    err = [float(r["elasticity"]) - eps_true[r["item_id"]] for r in ok if r["item_id"] in eps_true]
    cover = [r["details"]["ci95"][0] <= eps_true[r["item_id"]] <= r["details"]["ci95"][1]
             for r in ok if r["item_id"] in eps_true]

    # ── the whole sweep's cash moves on the engine's own cone, at once ──
    ruin = combined_ruin(out)

    # ── the catalogue's monthly contribution, the yardstick for "immaterial" ──
    latest = max(m["period_start"] for m in out["margins"])
    contribution = sum(float(m["revenue"]) - float(m.get("amazon_fees") or 0) - float(m["cogs"])
                       for m in out["margins"] if m["period_start"] == latest and m.get("cogs") is not None)

    realloc = next((d for d in out["drafts"] if d["kind"] == "budget_reallocation"), None)
    trims = [{"campaign": d["evidence"]["campaign_name"], "promised": d.get("expected_impact_usd"),
              "truth": after["trim_truth"].get(d["evidence"]["campaign_name"])}
             for d in out["drafts"] if d["kind"] == "campaign_trim"]

    # ── data quality against what was planted ──
    dq = out["dq"]
    flags_text = " ".join(f for fl in (dq.get("flags") or {}).values() for f in fl)
    planted = truth["pathologies"]
    detected = {cls: (_detected(cls, dq, flags_text) if members else None) for cls, members in planted.items()}
    no_cogs_steps = [s["sku"] for s in steps if s["sku"] in set(planted["no_cogs"])]

    book = out.get("book")
    book_truth = None
    if book and book.get("status") == "ok":
        book_truth = {}
        for g, members in (book.get("members") or {}).items():
            vals = []
            for key in members:
                d = next((x for x in out["drafts"] if _key(x) == key), None)
                if d is None:
                    vals = None
                    break
                t = truth_of(d)
                if t is None:
                    vals = None
                    break
                vals.append(float(t))
            book_truth[g] = None if vals is None else float(sum(vals))

    return {
        "world": name, "seed": seed,
        "elasticity": {"n_fit": len(el), "n_ok": len(ok), "median_error": float(np.median(err)) if err else None,
                       "coverage95": float(np.mean(cover)) if cover else None,
                       "raw_se_median": float(np.median([float(r["details"].get("std_err_raw") or r["std_err"])
                                                         for r in ok])) if ok else None,
                       "pool_se": next((float(r["details"]["pooled_epsilon_se"]) for r in ok
                                        if r["details"].get("pooled_epsilon_se") is not None), None),
                       "common_se": (float(np.median([float(r["details"]["common_se"]) for r in ok
                                                      if r["details"].get("common_se") is not None]))
                                     if any(r["details"].get("common_se") is not None for r in ok) else None)},
        "steps": steps,
        "realloc": None if realloc is None else {"p50": realloc.get("expected_impact_usd"),
                                                 "p5": realloc["evidence"].get("delta_p5"),
                                                 "p95": realloc["evidence"].get("delta_p95"),
                                                 "truth": after["realloc_truth"]},
        "trims": trims,
        "bleed": {"promised": sum(float(d.get("expected_impact_usd") or 0) for d in out["drafts"]
                                  if d["kind"] == "ad_bleed_terms"), "truth": after["bleed_truth"]},
        "record": record,
        "inventory": {k: v for k, v in after["inventory"].items() if k != "rows"},
        "ruin": ruin,
        "monthly_contribution": contribution,
        "dq": {"status": dq.get("status"), "flags": dq.get("flags"), "detected": detected,
               "no_cogs_steps": no_cogs_steps},
        "book": None if not book else {k: v for k, v in book.items() if k not in ("members",)},
        "book_truth": book_truth,
        "kinds": _count(out["drafts"]),
    }


def _key(d):
    ev = d.get("evidence") or {}
    return f"{d['kind']}|{ev.get('sku') or ev.get('campaign_name') or ''}|{ev.get('reason') or ''}"


def _count(drafts):
    out = {}
    for d in drafts:
        out[d["kind"]] = out.get(d["kind"], 0) + 1
    return out


DETECT_PATTERNS = {"stockout": ("stockout",), "deal": ("promotion", "deal"), "duplicate": ("duplicate",),
                   "no_cogs": ("no_landed_cost", "landed cost", "no_cogs"), "short_period": ("irregular_period", "short_period")}


def _detected(cls, dq, flags_text):
    return any(p in flags_text for p in DETECT_PATTERNS[cls])


def combined_ruin(out: dict) -> dict | None:
    """Every cash-moving directive of the sweep applied to the cone's own
    paths at once: P(cash under the floor at any day) before and after."""
    paths = out.get("cash_paths")
    if not paths:
        return None
    base = cash_from_components(paths, paths["sales_net"], paths["ad_daily_total"], paths["outflow"],
                                paths["payout_days"], 0)
    floor = float(paths.get("ruin_floor") or 0.0)
    days = base.shape[1]
    flows = np.zeros(days)
    n, deferred = 0, 0
    for d in out["drafts"]:
        rd = (d.get("evidence") or {}).get("ruin_delta")
        if not rd or rd.get("amount") is None:
            continue
        # a move the engine itself defers ("asked for, not wired") is not in
        # the sweep it recommends executing now; counted, so a sweep that
        # defers everything is visible in the evidence
        if ((d.get("evidence") or {}).get("book") or {}).get("deferred_for_cash"):
            deferred += 1
            continue
        day = int(max(0, min(days - 1, int(rd.get("day") or 0))))
        flows[day] += float(rd["amount"])
        n += 1
    after = base - np.cumsum(flows)[None, :]
    p_before = float(np.mean(base.min(axis=1) < floor))
    p_after = float(np.mean(after.min(axis=1) < floor))
    return {"n_moves": n, "n_deferred": deferred, "p_before": p_before, "p_after": p_after,
            "total_outflow": float(flows.sum()),
            "starting_cash": float(paths["starting_cash"]), "trough_before": float(base.min(axis=1).mean()),
            "trough_after": float(after.min(axis=1).mean())}
