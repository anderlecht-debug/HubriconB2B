"""The Simons–Thorp–Griffin test: ten pass/fail criteria, three lenses.

The lenses are principles associated with each man's public work, stated in
our own words — none of this is a quotation.

  SIMONS   Is the signal real, and is the stated uncertainty honest? Trust
           only what holds out of sample; a model that finds edge in noise
           is worse than none; a probability you quote must come true at
           the rate you quoted it.
  THORP    Know the edge before you bet, size the bet to the edge, and never
           risk ruin. Under-betting costs a little; over-betting and ruin
           cost everything.
  GRIFFIN  Manage the book, not the trade. Small correlated errors compound
           across a portfolio; bad data is a risk like any other; execution
           and accounting must be as rigorous as the model.

Each criterion names the client problem it answers. The thresholds were
fixed on 2026-09-24 before the engine was changed to meet them, and each is
set where an engine that knew the truth would pass with room for sampling
noise — never where the current engine happens to sit. A test is one seed:
six worlds; a test scores 10/10 only if every criterion passes. Three tests,
three seeds.
"""
import numpy as np
from scipy import stats

CRITERIA = [
    # id, lens, name, client problem
    ("S1", "Simons", "Estimator honesty",
     "Does the seller's elasticity say what the data can support — no more, no less?"),
    ("S2", "Simons", "Promise calibration",
     "When the engine says a price step lands between $a and $b nine times in ten, does it?"),
    ("S3", "Simons", "No edge where there is none",
     "Does a confident promise come true, and does a catalogue already at its best prices get left alone?"),
    ("S4", "Simons", "Stability and reproducibility",
     "Would the same data give the same advice, and would one month more or less reverse it?"),
    ("T1", "Thorp", "The edge is real",
     "Do price steps, budget moves, trims and negations deliver what they promised, in truth?"),
    ("T2", "Thorp", "Never over-bet",
     "Are price steps and purchase orders sized to the edge — never bigger than the evidence pays for?"),
    ("T3", "Thorp", "Survive",
     "Can the whole sweep, executed at once, run the business out of cash, or lose more than it said it could?"),
    ("G1", "Griffin", "Manage the book",
     "Is the sweep's total promise honest as a portfolio, and is its downside inside the client's budget?"),
    ("G2", "Griffin", "Garbage in, flagged and neutralised",
     "Do stockouts, deals, duplicates and missing costs in the exports get caught before they become advice?"),
    ("G3", "Griffin", "The Profit Record is honest",
     "Does the Record bank what the engine really delivered — never more, and not so little it is useless?"),
]

# ── thresholds (pre-registered; see the module docstring) ──
S1_COVERAGE = 0.90                # 95% intervals, 160 SKUs: sd of coverage ≈ 0.017. Over-coverage is
                                  # not dishonesty; what it costs shows up in T1 and T2
S1_BIAS = 0.15                    # median error, where the fits can resolve it (median raw se ≤ 1)
S1_INFORMATIVE_SE = 1.0
S1_BIAS_Z = 3.0                   # elsewhere: within three of the engine's own stated pool-mean errors
S2_POOLED = (0.82, 0.98)          # 90% bands, ~250 steps: sd ≈ 0.02; 0.98 = tails twice too wide
S2_WORLD_ALPHA = 0.005            # a world fails if its coverage is that improbable under a true 90%
S2_MIN_STEPS = 10
S3_CONFIDENT_PLOSS = 0.20         # the confident subset: rated at most a one-in-five chance of loss
S3_OVERCONFIDENCE_Z = 3.0         # realised losses may not exceed the sum of quoted P(loss) by 3 sd
S3_MIN_CONFIDENT = 20
S3_OPTIMAL_DAMAGE = 0.001         # of the catalogue's monthly contribution, in the no-edge world
S4_MAX_FLIP_SHARE = 0.10
S4_MAX_FLIP_DOLLARS = 0.05
S4_MAX_DRIFT_ALARMS = 0.01
T1_POOLED = (0.80, 1.25)          # true $ / promised $, worlds whose future resembles their past
T1_WORLD = (0.60, 1.50)
T1_MIN_PROMISED = 500.0
T1_BAND_MISSES = 2                # of up to six reallocations per test (P(≥3 | calibrated) ≈ 0.016)
T2_HALF_TOLERANCE = 0.05          # half-size may not beat full size by more than 5%
T2_INVENTORY_EXCESS = 0.15        # expected newsvendor cost at most 15% above the true optimum
T2_MIN_REORDERS = 20
T3_TAIL_SHARE = 0.05              # steps whose true loss exceeds their own stated risk budget
T3_RUIN_WARNING = 0.05
G1_MIN_INSIDE = 7                 # of 10 (world × group) book checks outside the drift world
G3_RATIO = (0.30, 1.30)
G3_OVERCLAIM = 0.05               # banked may exceed truth by at most 5% of the promise, pooled per kind
G3_MIN_MEASURED = 3

CALIBRATED_WORLDS = ("clean", "reactive", "thin", "dirty", "optimal")
REALISED_WORLDS = ("clean", "reactive", "thin", "dirty")


def _ordinary(steps):
    return [s for s in steps if s.get("reason") != "stretch"]


def _in_band(s):
    return s["p5"] is not None and s["p95"] is not None and s["p5"] <= s["truth"] <= s["p95"]


def s1(reports, stab):
    rows, ok = [], True
    for r in reports:
        e = r["elasticity"]
        informative = (e.get("raw_se_median") or 0) <= S1_INFORMATIVE_SE
        limit = S1_BIAS if informative else max(S1_BIAS, S1_BIAS_Z * float(e.get("pool_se") or 0))
        good = (e["coverage95"] is not None and e["coverage95"] >= S1_COVERAGE
                and e["median_error"] is not None and abs(e["median_error"]) <= limit)
        ok &= good
        rows.append(f"{r['world']}: coverage {e['coverage95']:.3f}, median error {e['median_error']:+.3f} "
                    f"(limit ±{limit:.2f}{'' if informative else ', fits uninformative'})" + ("" if good else "  ✗"))
    return ok, rows


def s2(reports, stab):
    pooled, rows, ok = [], [], True
    for r in reports:
        if r["world"] not in CALIBRATED_WORLDS:
            continue
        st = _ordinary(r["steps"])
        inside = [_in_band(s) for s in st]
        pooled += inside
        frac = float(np.mean(inside)) if inside else None
        bad = len(st) >= S2_MIN_STEPS and stats.binom.cdf(sum(inside), len(st), 0.90) < S2_WORLD_ALPHA
        ok &= not bad
        rows.append(f"{r['world']}: {sum(inside)}/{len(st)} inside" + (f" ({frac:.2f})" if frac is not None else "")
                    + ("  ✗" if bad else ""))
    p = float(np.mean(pooled)) if pooled else 0.0
    good = S2_POOLED[0] <= p <= S2_POOLED[1]
    ok &= good
    rows.insert(0, f"pooled {p:.3f} over {len(pooled)} steps (target {S2_POOLED[0]}–{S2_POOLED[1]})" + ("" if good else "  ✗"))
    return ok, rows


def _loss_z(steps):
    """Realised losses against the Poisson-binomial the quoted P(loss) implies."""
    p = np.array([float(s["p_loss"]) for s in steps])
    losses = sum(s["truth"] < 0 for s in steps)
    sd = float(np.sqrt(max((p * (1 - p)).sum(), 1e-9)))
    return losses, float(p.sum()), (losses - float(p.sum())) / sd


def s3(reports, stab):
    rows, ok = [], True
    quoted = [s for r in reports if r["world"] in CALIBRATED_WORLDS for s in _ordinary(r["steps"])
              if s["p_loss"] is not None]
    for label, subset in (("all steps", quoted),
                          (f"steps rated P(loss) ≤ {S3_CONFIDENT_PLOSS:.0%}",
                           [s for s in quoted if s["p_loss"] <= S3_CONFIDENT_PLOSS])):
        if len(subset) < S3_MIN_CONFIDENT:
            rows.append(f"{label}: only {len(subset)}; the frequency check is vacuous")
            continue
        losses, expected, z = _loss_z(subset)
        good = z <= S3_OVERCONFIDENCE_Z
        ok &= good
        rows.append(f"{label}: {len(subset)}, lost in truth {losses} against {expected:.1f} quoted (z {z:+.1f})"
                    + ("" if good else "  ✗"))
    opt = next((r for r in reports if r["world"] == "optimal"), None)
    if opt is not None:
        st = _ordinary(opt["steps"])
        damage = sum(s["truth"] for s in st)
        limit = -S3_OPTIMAL_DAMAGE * opt["monthly_contribution"]
        good = damage >= limit
        ok &= good
        rows.append(f"no-edge world: {len(st)} steps, true total ${damage:,.0f} vs floor ${limit:,.0f}; "
                    f"promised ${sum(s['p50'] for s in st):,.0f}" + ("" if good else "  ✗"))
    return ok, rows


def s4(reports, stab):
    if not stab:
        return False, ["no stability report"]
    ok = bool(stab["byte_identical"]) and bool(stab["seed_invariant"])
    rows = [f"same inputs twice byte-identical: {stab['byte_identical']}; another simulation seed, same promises: "
            f"{stab['seed_invariant']}"]
    fs, fd = stab["flip_share"], stab["flip_dollar_share"]
    good = fs <= S4_MAX_FLIP_SHARE and fd <= S4_MAX_FLIP_DOLLARS
    ok &= good
    rows.append(f"one month dropped: {stab['flips']}/{stab['compared']} directions flipped ({fs:.3f}), "
                f"{fd:.3f} of the dollars" + ("" if good else "  ✗"))
    da = stab["drift_alarm_share"]
    good = da <= S4_MAX_DRIFT_ALARMS
    ok &= good
    rows.append(f"one clean month more: drift alarms on {da:.3f} of pairs" + ("" if good else "  ✗"))
    return ok, rows


def t1(reports, stab):
    rows, ok = [], True
    pooled_p, pooled_t = 0.0, 0.0
    for r in reports:
        st = _ordinary(r["steps"])
        p, t = sum(s["p50"] for s in st), sum(s["truth"] for s in st)
        if r["world"] in REALISED_WORLDS:
            pooled_p += p
            pooled_t += t
            ratio = t / p if p > 0 else None
            bad = p >= T1_MIN_PROMISED and not (T1_WORLD[0] <= ratio <= T1_WORLD[1])
            ok &= not bad
            rows.append(f"{r['world']}: steps true/promised {t:,.0f}/{p:,.0f}" + (f" = {ratio:.2f}" if ratio else "")
                        + ("  ✗" if bad else ""))
        if r["world"] == "drifting":
            good = t > 0
            ok &= good
            rows.append(f"drifting: steps' true total ${t:,.0f} (must be > 0)" + ("" if good else "  ✗"))
    ratio = pooled_t / pooled_p if pooled_p > 0 else 0.0
    good = T1_POOLED[0] <= ratio <= T1_POOLED[1]
    ok &= good
    rows.insert(0, f"price steps pooled true/promised {ratio:.3f} (target {T1_POOLED[0]}–{T1_POOLED[1]})" + ("" if good else "  ✗"))
    ra = [r["realloc"] for r in reports if r["realloc"] and r["realloc"]["truth"] is not None]
    if ra:
        misses = sum(not (x["p5"] <= x["truth"] <= x["p95"]) for x in ra)
        rp, rt = sum(x["p50"] for x in ra), sum(x["truth"] for x in ra)
        good = misses <= T1_BAND_MISSES and T1_POOLED[0] <= rt / rp <= T1_POOLED[1]
        ok &= good
        rows.append(f"reallocations: {len(ra) - misses}/{len(ra)} truths inside their band, pooled true/promised "
                    f"{rt / rp:.2f}" + ("" if good else "  ✗"))
    tr = [x for r in reports for x in r["trims"] if x["promised"] and x["truth"] is not None]
    if tr:
        tp, tt = sum(x["promised"] for x in tr), sum(x["truth"] for x in tr)
        good = T1_POOLED[0] <= tt / tp <= T1_POOLED[1]
        ok &= good
        rows.append(f"trims: {len(tr)}, pooled true/promised {tt / tp:.2f}" + ("" if good else "  ✗"))
    bl = [r["bleed"] for r in reports if r["bleed"]["promised"]]
    if bl:
        bp, bt = sum(x["promised"] for x in bl), sum(x["truth"] for x in bl)
        good = T1_POOLED[0] <= bt / bp <= T1_POOLED[1]
        ok &= good
        rows.append(f"negated terms: pooled true/promised {bt / bp:.2f}" + ("" if good else "  ✗"))
    return ok, rows


def t2(reports, stab):
    rows, ok = [], True
    for r in reports:
        if r["world"] in REALISED_WORLDS:
            st = _ordinary(r["steps"])
            full, half = sum(s["truth"] for s in st), sum(s["truth_half"] for s in st)
            good = half <= full + T2_HALF_TOLERANCE * abs(full)
            ok &= good
            rows.append(f"{r['world']}: steps at full size ${full:,.0f}, at half size ${half:,.0f}" + ("" if good else "  ✗"))
    for r in reports:
        inv = r["inventory"]
        # the question is "never bigger than the evidence pays for": the cost of
        # ordering ABOVE the optimum is judged; ordering below it is the timid
        # side (fractional Kelly), reported and allowed, as for price steps
        over = inv.get("over_excess")
        if inv["n"] >= T2_MIN_REORDERS and over is not None:
            good = over <= T2_INVENTORY_EXCESS
            ok &= good
            rows.append(f"{r['world']}: {inv['n']} orders — over-ordering costs {over:+.1%} of the true optimum's cost "
                        f"(under-ordering {inv.get('under_excess') or 0:+.1%}, total {inv['excess']:+.1%})"
                        + ("" if good else "  ✗"))
    return ok, rows


def t3(reports, stab):
    rows, ok = [], True
    for r in reports:
        ru = r["ruin"]
        if ru is None:
            continue
        n_paths = 4000
        tol = 2 * np.sqrt(max(ru["p_after"] * (1 - ru["p_after"]), 1e-9) / n_paths)
        good = ru["p_after"] <= max(ru["p_before"], T3_RUIN_WARNING) + tol
        ok &= good
        rows.append(f"{r['world']}: sweep at once moves P(ruin) {ru['p_before']:.3f} → {ru['p_after']:.3f} "
                    f"over {ru['n_moves']} cash moves ({ru.get('n_deferred', 0)} deferred by the engine)"
                    + ("" if good else "  ✗"))
    tails = [s for r in reports for s in _ordinary(r["steps"]) if s["risk_budget"]]
    if tails:
        breaches = sum(s["truth"] < -float(s["risk_budget"]) for s in tails)
        share = breaches / len(tails)
        good = stats.binom.sf(breaches - 1, len(tails), T3_TAIL_SHARE) >= S2_WORLD_ALPHA
        ok &= good
        rows.append(f"steps whose true loss exceeded their own risk budget: {share:.3f} of {len(tails)}"
                    + ("" if good else "  ✗"))
    return ok, rows


def g1(reports, stab):
    rows, ok = [], True
    inside, checks = 0, 0
    for r in reports:
        b = r.get("book")
        if not b or b.get("status") != "ok":
            return False, [f"{r['world']}: the engine publishes no book for the sweep  ✗"]
        if b.get("es5") is not None and b.get("risk_budget") is not None and b["es5"] < -float(b["risk_budget"]) - 1e-6:
            ok = False
            rows.append(f"{r['world']}: book ES5 ${b['es5']:,.0f} beyond its budget ${b['risk_budget']:,.0f}  ✗")
        if r["world"] == "drifting":
            continue
        for g in ("price_steps", "advertising"):
            band = (b.get("groups") or {}).get(g)
            t = (r.get("book_truth") or {}).get(g)
            if not band or t is None:
                continue
            checks += 1
            hit = band["p5"] <= t <= band["p95"]
            inside += hit
            rows.append(f"{r['world']} {g}: truth ${t:,.0f} in [{band['p5']:,.0f}, {band['p95']:,.0f}]"
                        + ("" if hit else "  (outside)"))
    need = min(G1_MIN_INSIDE, checks)
    good = inside >= need and checks > 0
    ok &= good
    rows.insert(0, f"book bands holding the truth: {inside}/{checks} (need {need})" + ("" if good else "  ✗"))
    return ok, rows


def g2(reports, stab):
    rows, ok = [], True
    dirty = next((r for r in reports if r["world"] == "dirty"), None)
    clean = next((r for r in reports if r["world"] == "clean"), None)
    if dirty:
        for cls, hit in dirty["dq"]["detected"].items():
            if hit is None:
                continue
            ok &= bool(hit)
            rows.append(f"dirty: {cls} {'flagged' if hit else 'NOT flagged  ✗'}")
        n = len(dirty["dq"]["no_cogs_steps"])
        ok &= n == 0
        rows.append(f"dirty: price steps on SKUs with no landed cost: {n}" + ("" if n == 0 else "  ✗"))
    if clean:
        good = clean["dq"]["status"] == "ok"
        ok &= good
        rows.append(f"clean: data quality {clean['dq']['status']}" + ("" if good else f" {clean['dq']['flags']}  ✗"))
    return ok, rows


def g3(reports, stab):
    rows, ok = [], True
    kinds = {}
    for r in reports:
        for k, v in r["record"].items():
            a = kinds.setdefault(k, {"n": 0, "promised": 0.0, "banked": 0.0, "truth": 0.0})
            a["n"] += v["n_measured"]
            a["promised"] += v["promised"]
            a["banked"] += v["banked"]
            a["truth"] += v["truth"]
    for k, a in sorted(kinds.items()):
        if a["n"] < G3_MIN_MEASURED or a["promised"] <= 0:
            rows.append(f"{k}: {a['n']} measured — too few to judge")
            continue
        ratio = a["banked"] / a["promised"]
        over = a["banked"] - a["truth"]
        good = G3_RATIO[0] <= ratio <= G3_RATIO[1] and over <= G3_OVERCLAIM * a["promised"]
        ok &= good
        rows.append(f"{k}: {a['n']} measured, banked/promised {ratio:.2f}, banked ${a['banked']:,.0f} vs truth "
                    f"${a['truth']:,.0f}" + ("" if good else "  ✗"))
    return ok, rows


CHECKS = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "T1": t1, "T2": t2, "T3": t3, "G1": g1, "G2": g2, "G3": g3}


def score(reports: list[dict], stability: dict | None) -> dict:
    results = []
    for cid, lens, name, problem in CRITERIA:
        try:
            passed, rows = CHECKS[cid](reports, stability)
        except Exception as exc:          # a criterion that cannot be computed fails, loudly
            passed, rows = False, [f"could not be computed: {type(exc).__name__}: {exc}"]
        results.append({"id": cid, "lens": lens, "name": name, "problem": problem, "pass": bool(passed),
                        "evidence": rows})
    return {"score": sum(r["pass"] for r in results), "of": len(results), "criteria": results}
