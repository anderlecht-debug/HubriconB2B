# Hubricon Engine — Mathematical Scorecard

An adversarial self-assessment of the engine's mathematics, scored against named
artifacts. A score of 10 is only valid if the artifact that proves it is named; a
10 with no artifact named is a 6, and two dimensions below are scored lower than
they could be argued for, for exactly that reason.

Written for whoever reviews or maintains this engine. Derivations and limits live
in `MATH_METHODS.md`; this file is the audit trail of how the mathematics got
here and what it is and is not known to do.

Suite at time of writing (2026-09-25, iteration 39): **1,180 tests, all passing,
4½ minutes unthreaded** — the twenty-eight of `test_fleet` and `test_book` (the
network, iteration 39) added to the 1,152 left by the billing work of the same day.
Before that (2026-09-24, iteration 38): **1,129 tests, all passing,
4½ minutes unthreaded** (`OMP_NUM_THREADS=1`; threaded BLAS under pytest's single
process is slower, not faster) — the twelve of `test_bench_corrections` added to the
1,117 of the model-risk rounds; plus the Simons–Thorp–Griffin bench (`engine/bench/`,
iteration 38), three tests in about two minutes on twelve workers.
Before that: **1,116 tests, ~5 minutes**
— 1,106 after the interaction iteration (iterations 15–36 below) plus the ten of the
model-risk pass (iteration 37, `test_model_risk` and one in `test_ad_allocation`);
up from 979 before the interaction iteration, whose 115 new tests live in twenty files
(the extra minute of runtime since 2026-09-23 is the controlled fit and its bootstrap
running inside every elasticity call on a reacting catalogue): `test_ad_allocation`, `test_incrementality`,
`test_price_experiment`, `test_cross_price`, `test_markdown`, `test_replenishment`,
`test_cash_orders`, `test_seasonality`, `test_clv`, `test_assortment`,
`test_client_risk`, `test_ruin_cost`, `test_ad_drift`, `test_ad_form_selection`,
`test_obsolescence`, `test_drift`, `test_stress`, `test_data_quality`,
`test_headline_and_benchmark`, `test_daily`; the thinnest-input refusal test in
`test_degeneracy` now covers every model of the iteration. The suite's runtime grew
from ninety-five seconds to under four minutes, most of it the form ladder's refits
in the ad-curve tests and the markdown draws.

Before that iteration: 979 tests, ~95 seconds, up from 770 before the mathematics
work. The 193 of that work live in fifteen files:

```
test_pricing_derivation  21   test_degeneracy            25
test_pricing_pole_guard  17   test_dependence            20
test_elasticity_inference 13  test_anomaly_fdr           15
test_delta_propagation    9   test_calibration_math      15
test_robust_step         12   test_horse_race             6
test_mc                   7   test_endogeneity            7
test_replay              13   test_ad_curve_uncertainty   8
test_reproducibility      5
```

---

## Scores

| # | Dimension | Score | The artifact that proves it |
|---|---|---|---|
| 1 | Derivation correctness | **10** | `tests/test_pricing_derivation.py` — sympy solves dΠ/dP = 0 and checks the single root equals the published P*; a 200,001-point grid search confirms it at 4 elasticities × 4 fee structures; `test_closed_form_rop_matches_formula_and_tracks_mc`; `test_benjamini_hochberg_matches_the_textbook_step_up` worked by hand |
| 2 | Estimator validity | **10** | `tests/test_elasticity_inference.py` — t(3) = 3.182 not 1.96; HC3 matched against the textbook sandwich computed independently; HC3 vs classical against the empirical sd of 600 fits; shrinkage justified by a 30-seller squared-error race; `tests/test_endogeneity.py` documents the identification limit with a measured bias table; `tests/test_model_risk.py` removes the bias where the seller's reaction is measurable (iteration 37) |
| 3 | Uncertainty propagation | **10** | `tests/test_delta_propagation.py` — every uncertain input demonstrably widens the band; `tests/test_mc.py` checks the quantile standard error against 400 independent reruns and against the analytic normal formula; `tests/test_ad_curve_uncertainty.py` closed the last published number that had no interval |
| 4 | Calibration | **10** | `tests/test_calibration_math.py` — 1,000 synthetic SKUs, the whole pipeline, scored against realized deltas; elasticity interval coverage 94.4–96.6%; profit-delta band 91.6–94.0% at seven periods; an unconditional check that the coverage is not an artifact of selection; `engine/bench/` (iteration 38): the whole engine on six planted-truth catalogues per test, 10/10 on the three pre-registered tests, and on three validation seeds 8, 9 and 10 with every miss explained |
| 5 | Decision quality under uncertainty | **9** | `tests/test_horse_race.py` — five rules, 40 sellers × 25 SKUs, three regimes. **The robust policy does not beat the plug-in on raw realised profit.** It ties per directive, wins the tail in every regime, and wins on bankable dollars once the true elasticity drifts. Scored 9 because that is a split result and a simulation cannot settle it. Full table below. |
| 6 | Degeneracy coverage | **10** | `tests/test_degeneracy.py` — 25 tests, one per degenerate path, each with a named status; two NaN/inf sweeps over 144 and 12 parameter combinations |
| 7 | Multiple-testing discipline | **10** | `tests/test_anomaly_fdr.py` — 500 noise SKUs, 4,000 tests, 548 detector flags, 0 survivors; null p-values uniform for all four statistics; a planted step still clears the control |
| 8 | Dependence & tail modelling | **10** | `tests/test_dependence.py` — the generator's correlation and marginals verified; rho recovered at four known values; the simultaneous-stockout tail 10 → 15 at the 95th percentile; the cash trough deeper and its shortfall deeper still; MC errors on every published percentile |
| 9 | Reproducibility | **10** | `tests/test_reproducibility.py` — the whole cycle byte-identical on two runs; a caller's own generator cannot move a published promise; a re-measurement reproduces what it banked |
| 10 | Refusal discipline | **10** | `tests/test_degeneracy.py::test_the_thinnest_plausible_input_returns_statuses_not_numbers` — one SKU, five periods, one price change, no landed cost: every dollar figure absent, every absence named |

### Why dimension 5 is a 9 and stays a 9

The bar is two clauses: "robust objective beats plug-in optimum in out-of-sample
simulation" **and** "step size responds to SE". The second holds unconditionally
and is measured. The first is a split, and the split is worth setting out in full
because it is the most interesting result in this file.

**On raw realised profit** the robust step loses, in every regime, by 1–2%,
because it declines moves the plug-in takes. Per directive issued the two are a
dead heat: 131.4 against 132.0.

**On the tail** it wins, reproducibly, in every regime: the mean of the worst
decile of moves is 10–18% less bad and the dollars lost on losing moves 13–18%
lower.

**On bankable dollars — the metric the product is actually judged by** — the
picture changes with how non-stationary the world is. The Profit Record caps
upside at what was promised and does not cap downside, so a rule that takes
occasional large losses is punished twice. Scoring the same race that way, 40
sellers × 25 SKUs:

| regime | plug-in | certainty equivalent (shipped) | pure quantile | naive 3% |
|---|---|---|---|---|
| ε stationary | **56,395** | 54,569 | 52,259 | 41,172 |
| ε drifts 0.4 | 47,504 | 46,583 | **48,218** | 38,168 |
| ε drifts 0.8 | 25,021 | 26,278 | **36,522** | 30,952 |

So the robust step beats the plug-in on the product's own metric exactly when the
true elasticity moves — which is the case it exists for — and loses to it when
nothing moves. And the pure quantile objective wins that metric outright at
realistic drift, by 46% over the plug-in at drift 0.8, while putting 23% less raw
money in the seller's payout. Those two metrics point different ways, and the
engine resolves it in the seller's favour: the default maximises the payout
("more money landed in my payout this month" is the first clause of what they are
buying) and is conservative about what we bill against it.

The brief's standing rule says that if the simpler method wins, keep the simpler
method and say so. The simpler method did not win — it tied on raw money, lost the
tail in every regime, lost the banking metric once the world moves, and fails the
step-size clause outright. So the robust step ships.

**What would make this a 10:** a real client history through the replay harness
showing the robust policy's banked realisation ahead of a plug-in counterfactual
on that client's own exports. Every number above is a simulation, and a simulation
cannot settle a split result. That is item 5 on the list at the end of this file,
and it is the one item that can only be waited for.

---

## Iteration history

The audit trail. Each row is a red-team objection, what was done about it, and
what the score moved from and to.

### Iteration 0 — the nine defects (Layer 1)

Nine commits, `Math 1/9` through `Math 9/9`, each with its own tests. Before this
work the honest scores were: derivation 4 (P* wrong), estimator validity 3 (wrong
critical value, wrong standard errors, no shrinkage), uncertainty propagation 2
(a two-endpoint range called a 95% interval), calibration 0 (never measured),
decision quality 3 (a magic constant), degeneracy 6 (good statuses, no pole
guard), multiplicity 1 (none), dependence 2 (independence everywhere), reducibility
7 (seeded where it simulated), refusal 7 (strong except at the pole).

### Iteration 1 — Ledoit/Wolf: "your per-SKU estimate is noise; shrink it"

**Objection.** A per-SKU elasticity from five periods fed into ε/(1+ε) is the
Markowitz pathology. **Change.** Empirical-Bayes shrinkage toward the catalog
pool, weight τ²/(τ² + SE²), posterior SE carrying both the own and the borrowed
term. **Evidence.** 30 synthetic sellers, shrunk beats raw on total squared error
overall and on ≥20 of 30 individually; a SKU measured over 40 near-noiseless
periods keeps >95% of its own answer. **Score.** Estimator validity 3 → 8.

### Iteration 2 — Bertsimas/Ben-Tal: "you optimized the point estimate"

**Objection.** `P*` was computed at ε̂ and walked toward at a fixed 5%. **First
attempt.** Maximise the 25th percentile of the profit-delta distribution, as the
brief specifies. **It failed, and the failure is instructive.** Every quantile of
a positively scaled variable scales with it, so the objective is positively
homogeneous, its maximum against a box constraint is a corner, and the policy
collapsed to "the full cap, or nothing". Measured: on a SKU two percent above its
optimum, the whole curve of steps across a 28-fold range of standard error took
**two distinct values** and spent nine of ten cells refusing outright.

**Second attempt, shipped.** Add the term Almgren and Chriss add for the same
reason — a cost quadratic in the size of the move, here the variance the move
carries priced at the SKU's own risk budget. The objective becomes strictly
concave and the solution interior: s* = B·(gain per unit step)/(variance per unit
step). **Evidence.** The same sweep now returns 2.25%, 2.25%, 2.00%, 1.75%, 1.75%,
1.50%, 1.25%, 0.75%, 0%, 0% — monotone, seven distinct values, ending in a
refusal. Both failure and fix are pinned as tests
(`test_a_pure_quantile_objective_cannot_size_a_step`,
`test_the_certainty_equivalent_objective_does_size_one`). **Score.** Decision
quality 3 → 9.

### Iteration 3 — DeMiguel/Garlappi/Uppal: "does it beat 1/N out of sample?"

**Objection.** Build the horse race or use the naive rule. **Change.** Built it:
five rules, 40 sellers × 25 SKUs, three regimes with reactive pricing and a
drifting true elasticity.

**First version was wrong and reported a win that did not reproduce.** It scored
the 5th-percentile seller out of twenty — essentially the worst seller — which
moved by hundreds of dollars between seeds. At 40 sellers × 30 SKUs it showed the
robust policy ahead in the tail; at 20 × 25 it showed the reverse. **Fix.** Score
per move over a thousand moves, where the statistics are stable to a couple of
percent, and print the per-seller figures without asserting them.

**The honest result.** Every rule using the elasticity fit beats a naive fixed 3%
step by >50% on total profit, so the fit earns its keep. The robust policy loses
1–2% of total profit to the plug-in in every regime and ties per move. It wins the
tail in every regime. The pure quantile objective earns 28% **more** per move and
loses 69% fewer dollars by declining 40% of the catalog — fewer and truer, at 23%
less money in the payout; available, not the default, because "more money landed
this month" is the first clause of what a seller is buying. **Score.** Decision
quality stays 9, and the reason it is not 10 is this iteration's finding.

### Iteration 4 — Imbens/Chernozhukov: "your ε is a correlation"

**Objection.** Price was chosen by the seller in response to demand; document the
bias direction and size. **Change.** Built the reactive-pricing simulation
properly: the demand shock is AR(1) and the seller reprices off **last** month's
demand, because nobody has next month's data. Endogeneity bites only when both
hold.

**Finding, as first reported and then corrected.** The original finding was a
median bias of +0.59 against a +0.15 no-reaction baseline, with the warning that
conflating attenuation with endogeneity "would have overstated the endogeneity
threefold". **Iteration 13 overturned that: there is no baseline.** Over 96 seeds
the φ = 0 cell is +0.022 and twelve independent 8-seed blocks of it span −0.117 to
+0.145. The whole +0.51 at φ = 0.4 is endogeneity. The careful separation was
itself the error, and it made the danger look smaller than it is. **Mitigations, measured rather than
asserted:** the pole guard disproportionately catches the worst-biased SKUs
(`test_the_pole_guard_catches_the_most_biased_skus`). **Not corrected**, and the
reason is stated: correcting it needs an instrument and no export is one.
**Score.** Estimator validity 8 → 10, because the identification limit is now
documented with numbers rather than absent.

### Iteration 5 — Harvey/López de Prado: "how many tests before that alert fired?"

**Objection.** Thousands of tests a sweep with per-series thresholds. **Change.**
A p-value per test against a simulated null, Benjamini–Hochberg across the sweep,
`flagged` gated on the q-value. **Two sub-problems had to be solved.** Three of
the four statistics have no closed form at n = 6–120, so each null is simulated
per series length — correct to cache by length because every statistic is
location- and scale-invariant under the Gaussian null. And a counted Monte Carlo
p-value floors at 1/(R+1) = 2.5e-4 while BH on a 3,000-test sweep needs 1.7e-5 at
the first rank, so without a tail extrapolation the procedure would reject nothing
ever; above the 99th percentile the p-value comes from an exponential fit to the
excesses, and `p_basis` says which.

**Finding.** On 500 pure-noise SKUs the detectors alone flag **548 of 4,000 tests**
and none survives. 391 of the 548 are the changepoint scan, whose BIC penalty of
2·log(n) = 4.6 at n = 10 sits near the **75th** percentile of its own null. The old
engine would have emitted roughly five hundred dollar-figured "findings" per sweep
on noise. **Score.** Multiplicity 1 → 10.

### Iteration 6 — Embrechts: "you simulated the SKUs independently, didn't you"

**Objection.** Yes. **Change.** One common factor, Gaussian copula, moment-matched
lognormal marginals, rho estimated from the cross-sectional mean of standardised
log-demand residuals and shrunk toward a conservative default. Applied to the
inventory panel, the cash cone and the monthly VaR.

**Finding.** The marginals are untouched (the expected number of stockouts is
unchanged at 6.0) and the tail is transformed: the 95th percentile of simultaneous
stockouts goes 10 → 15 and its expected shortfall 10.5 → 17.2. Independence
understated the tail by 63%. A second finding fell out: the truncated-normal rate
the three simulations used raises its own mean above the level it was calibrated
to and removes demand's skew, so the marginal is now lognormal. **Score.**
Dependence 2 → 10.

### Iteration 7 — Rockafellar/Uryasev: "a 5th percentile is not a risk measure"

**Objection.** Where is the shortfall. **Change.** Expected shortfall published
beside the percentile on the cash trough, the simultaneous-stockout count and the
monthly loss; the step-size constraint expressed as an ES rather than a
percentile, so it is coherent when the Desk aggregates.

**Finding, and an honest one.** On Amazon's fortnightly payout cycle the trough of
the 90-day horizon turns out to be **deterministic** — the day before the first
payout, when outflow has accrued and nothing has come in — so the percentile and
the tail mean coincide there and the correlation shows up later in the horizon
instead. That is a structural fact about the model, not a bug, and it has its own
test. On a daily payout cycle the trough is stochastic and the shortfall moves
further than the percentile does, which is the whole argument for publishing it.
**Score.** Dependence & tail 10 confirmed.

### Iteration 8 — Glasserman: "what is the standard error of your P5?"

**Objection.** 10,000 crude paths for a tail quantity is an estimate with its own
error. **Change.** `models/mc.py`: the asymptotic standard error of a sample
quantile with a Siddiqui density estimate, and expected shortfall with its own
error. Attached to every published percentile — the cash cone at the trough day,
the ruin probability, the stockout percentiles, VaR 95 and 99, every profit-delta
percentile.

**A bug found in the process.** The first bandwidth was a plain n^(−1/5), which at
the 5th percentile puts the window between the 0th and 22nd percentile and
measures the slope of the body rather than the tail — inflating the reported error
by 60%. The half-width is now capped at half the distance to the nearer end. The
test that caught it compares the reported error against the spread of 400
independent reruns, which is the only thing "standard error of the P5" can honestly
mean. **Score.** Uncertainty propagation 2 → 9.

### Iteration 9 — Derman/Cont: "which assumption, if wrong, costs the client most?"

**Objection.** Name it, and say whether the report says so. **Change.**
`MATH_METHODS.md` §10 ranks nine limits and names the most dangerous —
reactive-pricing bias, because its direction is the one that argues for raising
prices — then names the four mechanisms that stand between it and a client and the
data that retires it. The seller-facing version is a paragraph on the report
itself, and a test asserts both exist and agree, so the documentation cannot drift
away from the mathematics. **Score.** Estimator validity and refusal discipline
confirmed at 10.

### Iteration 10 — the replay harness, and two regressions it caught

**Objection, self-raised.** Every number above is a simulation. Is the promise
calibrated against a real outcome? **Change.** `replay.py` and
`hubricon replay <client>`: re-measure a client's whole directive history against
their own later exports and score the realisation ratio, the band coverage, and
whether every evidence blob can be rebuilt at all. Reports `pending` with too
little history rather than a ratio computed on nothing. Also checks for **drift**:
a banked measurement that no longer reproduces.

It caught two regressions immediately, both introduced by the Layer 1 fixes.

**Regression A.** `measure_price_step` banked "the least favourable reading of our
own fit" — the worse of the elasticity interval's two endpoints. Defensible while
that interval was ±1.96·classical SE. Once it became an HC3 Student-t interval on
a shrunk estimate, the upper end sits near −1, where the counterfactual claims the
seller would have sold almost as much at the old higher price. On 24 simulated
price cuts whose true elasticity was −2.4, **every one of which made money**, the
endpoint rule booked **eighteen as losses** and the realisation ratio came out at
−0.38. Taking an extreme of a wide interval is not conservatism; it is a wrong
answer. **Fix.** Integrate the posterior and bank its 25th percentile — the same
risk quantile the step was sized against.

**Regression B.** The model counterfactual anchors on the after-period's real units
and rolls them back with the promise's elasticity, which is reproducible and blind
to the case where the volume response did not happen. With a price cut and no
response at all it still said "you would have sold 12% less at the old price" and
booked a gain on a move that lost margin. **Fix.** Cap the claim at the per-period
change in the SKU's own profit. The raw before/after change is not a measurement —
it carries the season — but as a ceiling it can only reduce a claim.

**Evidence it now works.** As the volume response falls from 1.5× forecast to zero,
the realisation ratio falls 0.69 → 0.58 → −0.60 → −2.23, monotonically, and a cut
with no response is booked as the loss it was. **Score.** Calibration 9 → 10, and
this iteration is the reason dimension 4 is a 10 rather than an 8: without the
replay harness every calibration number in this file would be a claim about a
simulation rather than about the engine's own promises.

### Iteration 11 — the correlated draws did not fit in memory

**Objection, self-raised against iteration 6.** The common-factor generator
returned a `(n_skus, n_paths, days)` array. On a 400-SKU catalog over 10,000 paths
and 90 days that is **2.9 GB**, and the cash cone would have died on the first
real client large enough to need it. The per-SKU loop the old independent code used
had kept memory at the shape of one SKU's draw; vectorising across SKUs threw that
away.

**Change.** `dependence.rate_stream` and `multiplier_stream` yield one SKU's draw
at a time, holding the common factor and discarding each SKU's own shock after
use, in exactly the draw order the materialising form uses — so streaming and
materialising give bit-identical numbers and the tests can check one while the
engine uses the other. All three call sites stream.

**Evidence.** `test_streaming_and_materialising_give_identical_draws` pins the
equality; `test_a_large_catalog_cash_cone_does_not_materialise_the_panel` runs the
cone at a width where the panel would be 288 MB and asserts the peak allocation
stays under 25 one-SKU arrays. **Score.** Dependence & tail 10 confirmed — and a
reminder that a correct model that cannot run is not a correct model.

### Iteration 12 — the last published number with no interval

**Objection, self-raised against dimension 3.** Dimension 3 says *every* published
number carries an interval. The ad-efficiency break-even did not: `curve_fit`
returned a parameter covariance and the code discarded it, so a campaign trim —
a banked promise — was sized against a bare point estimate.

**Change.** Parameters drawn from the fit's asymptotic posterior with the fit's own
bounds enforced; marginal ROAS and break-even recomputed on each; P5/P50/P95 of
both published, plus P(the marginal dollar is already below break-even), which is
the number a trim decision actually rests on. The trim is sized off the cautious
end of the band, and no trim is drafted where the band reaches current spend.

**A refusal found in the process.** A campaign whose spend never moved: `curve_fit`
converges onto an arbitrary point of a flat likelihood ridge and returns a **zero**
covariance, which reads as perfect certainty — the worst possible failure mode for
a published interval. A spend-variation guard now runs before the fit, mirroring
the price-variation guard on elasticity. **Score.** Uncertainty propagation 9 → 10.

### Iteration 13 — five claims simulated and adversarially verified; the correction did not ship

**Objection, self-raised.** Iteration 4 measured the endogeneity and named it the
most dangerous assumption. A design pass then proposed correcting it from data
already on disk: measure the seller's reaction strength φ, profile the demand
persistence ρ, quasi-difference, and subtract the implied bias — no experiment on
anyone's prices. Five claims were simulated, each then adversarially verified by a
second agent whose job was to overturn it.

**It was overturned, and four beliefs went with it.**

*The attenuation baseline does not exist* (see iteration 4 above). 96 seeds: +0.022.
The test that pinned +0.15 passed 5 of 12 seed blocks. The problem is bigger than
reported, not smaller.

*The correction is a tuned constant wearing an estimator's clothes.* Bias removal is
strongly monotone in the ρ fed to it — residual bias +0.421 / +0.194 / −0.099 at
ρ = 0.137 / 0.26 / 0.60 — and the profiled estimator recovers 0.26–0.48 against a
true 0.60. It works *because* of that error, which cancels the quasi-differenced
estimator's own incidental-parameter bias. Improving the ρ estimator (Prais–Winsten
with the Nickell fixed point, which lands in tolerance in 48/48 cells) *breaks* the
correction. A correction that degrades when you fix its inputs is not a correction.

*Its allocation rule is actively harmful, and the damage is invisible in the metric
it optimises.* The rule hands the largest correction to the SKUs that were never
repriced. On a mixed catalog (half φ = 0, half φ = 0.8) the catalog median bias goes
+0.431 → −0.011, which reads as a total success, while RMSE goes 0.758 → 2.252
(+197%) and the non-reacting SKUs go +0.028 → −2.363. **42% of SKUs made worse**,
with the induced error pointing at "cut the price" and landing on the thinnest data.

*"The correction makes the engine louder" validates nothing.* A placebo shift of the
same magnitude into cells with no bias to remove goes louder by +37.3pp — more than
the real correction's +21.7pp. Subtracting any positive number from ε̂ moves it off
the pole mechanically.

**And the one-sided bound failed too, 25 minutes after it shipped.** The asymptotic
inequality is exact (P = 1.000 in long panels, verified to three decimals against a
T = 1500 simulation). Per SKU, on the shrunk estimate the engine actually uses and
the SKUs it actually quotes: it holds 0.797 at (φ=0.4, ρ=0.6) and **0.373 at
(φ=0.4, ρ=0)** — inside the claim's own stated domain. A bound wrong for a quarter
to two-thirds of the SKUs it is printed on is not a bound. Withdrawn from the client
report and replaced with a catalogue-level statement that names its own limits.

**What survived.** The φ diagnostic: one pooled within-SKU regression of log price
on the lagged per-SKU demand *residual* recovers the reaction strength to 0.016
absolute at every T down to 7, on two independent implementations, with a 1–4%
false-positive rate. Two conditions are load-bearing and were undefined in the
proposal: the proxy must be the residual (demeaned log units attenuates φ sixfold
and pushes the false-positive rate to 12–22%) and the gate must be one-sided. It is
blind to a catalog with +0.8 and −0.8 SKUs in equal measure.

**Score.** Estimator validity stays 10 — the limit is now documented more accurately
than before, which is what the dimension measures — and calibration stays 10 because
the thing that failed was a proposal, not a shipped estimate. Iteration 14 is the
shipped consequence.

### Iteration 14 — the measurement was the bottleneck, not the estimator

**Finding.** Three things about what the estimator can SEE turned out to matter more
than anything about the estimator itself.

*A reverting price test is invisible, by identity.* Under the units-weighted monthly
average that ingest actually builds, a 14-day step that reverts gives a monthly price
whose coefficient of variation is 0.011 against `MIN_PRICE_CV` = 0.02 — so the SKU
returns `insufficient_price_variation` and carries no elasticity at all. An
**adopted** step, which is what the engine's walk makes, gives 0.024 and fits. The
withdrawal in iteration 13's commit was therefore too broad and is corrected here:
price *tests* are invisible, directive *steps* are not.

*Unequal period lengths biased the slope catastrophically, and this one is FIXED.*
`elasticity._fit` passed `units_sold` through unnormalised — `period_start` and
`period_end` were read only to sort. For a step held one whole a-day window against
a b-day baseline, ε̂ = ε + ln(a/b)/ln(1+s). At a 15-day step against a 16-day
baseline with s = 5% that is **−1.32**; at 14 against 16, **−2.74**. A calendar
fortnight inside a 31-day month forces 15/16. So the obvious improvement — ask for
fortnightly exports, which buys a 2.13× reduction in the standard error — was a trap
that would have shipped an elasticity biased by one to three whole units toward
price cuts. Units are now normalised to a daily rate, all-or-nothing across an
item's series (normalising some periods and not others is the very
price/length correlation the fix removes), with the bias it avoids pinned as the
closed form at three splits. On equal periods it moves nothing, which is exactly why
it would have been dropped as a nicety.

Fixing it exposed a latent bug in ten test fixtures that wrote `f"2026-{i:02d}-01"`
and therefore produced a thirteenth month past a year of history. Nothing had ever
read those dates before.

*The engine's step distribution is narrower than reported.* 71.8% of steps sit at
the rail over twelve seeds, not 57%.

**Score.** Estimator validity and calibration confirmed at 10 with the corrections
applied; the cadence work is on the list at the end of this file rather than done.

### Iteration 15 — the interactions between levers, part 1: money between campaigns

**Objection.** Each module optimises its own lever. Ad efficiency trims every
campaign toward its own break-even and never asks whether a dollar in campaign A
would earn more in campaign B — which it does whenever their marginal ROAS differ,
and it does so even in an account where no campaign is past break-even.

**Change.** `models/ad_allocation.py`: the same total, reallocated to equalise
marginal returns. Solved by an exact dynamic program on a spend grid rather than a
bisection on the multiplier, because the Hill form with h > 1 is S-shaped and a
Lagrangian bisection can skip the budget (`test_dp_is_exact_on_s_shaped_curves…`
demonstrates the gap). Solved on each campaign's posterior-mean curve, which is the
exact risk-neutral Bayes solution for a separable objective, and moved a fraction α
of the way by the same certainty-equivalent rule the price step uses, inside a risk
budget of 15% of the campaign set's monthly net. Interval from paired parameter
draws; per-campaign anchored measurement; one promise per campaign per run (trims
first, the reallocation over the rest). The covariance of every ad-curve fit now
rides on the row (`details.curve_cov`) so later modules redraw the same posterior.

**Two defects found on the way, fixed here.** `measurement.measure_spend_step`
filtered daily spend rows on a `date` key the rows never carry (`report_date`), so
every spend-step directive had returned "not yet" since the family shipped;
pinned by `test_spend_step_reads_report_date`. And `issue.issue_drafts` sorted
by expected dollars alone, so a directive with no dollar promise sorted last
forever; the drafting score now rides in evidence and breaks ties.

**Measured.** On a two-campaign account with identical true curves at $40 and $160
a day, the allocation moves toward equal spend inside the 30% move cap with
P(loss) under 20%; identical campaigns at equal spend refuse (`no_reallocation`);
a fit so noisy that under 50 of 400 draws land inside the bounds refuses
(`insufficient_draws`). `tests/test_ad_allocation.py`, 15 tests.

### Iteration 16 — part 2: what the attributed number is worth

**Objection.** Every ad number the engine publishes rests on the platform's own
attribution. Attribution overstates by the organic sales it claims and understates by
the halo it never sees, and the break-even inherits both errors with no sign of which
dominates.

**Change.** `models/incrementality.py`. An observational ratio of the two slopes on
first-differenced period totals, HC3 and a Student-t delta-method band, refused under
eight periods or flat spend, published as information. A randomised ON/OFF switchback
on one campaign, designed as a directive (`ad_switchback`, explicit, no dollars), run
by `hubricon adtest`, analysed from the daily settlement file with a block bootstrap
and a permutation test; only its ι moves the break-even, and the attributed break-even
stays on the row.

**Measured, and one claim withdrawn before it shipped.** The observational estimator
recovers ι = 0.4 within ±0.15 on fourteen clean periods and its 95% band covers the
truth on 80% of seeds; the switchback recovers it within ±0.1 over 24 seeds with a
permutation p under 0.05. The first draft stated that carryover biases ι toward 1. The
simulation showed the opposite for the real-effect mechanism (ι toward zero) and the
claimed direction only for attribution carryover; the payload now states both and
corrects neither. `tests/test_incrementality.py`, 10 tests.

### Iteration 17 — part 3: the instrument

**Objection.** The most dangerous assumption in this engine (the closing section
below) needed a price change made for a reason unrelated to demand, plus a price
series fine enough to see it. Iteration 13 measured that the engine's own steps were
neither. Nothing had been built since.

**Change.** `models/price_experiment.py`: five arms inside the standing cap, six
seven-day blocks, two anchors so the estimator's price-variation floor is always
cleared, the rest by Thompson sampling with a 10% floor, the order from a generator
seeded by identity and calendar only. Analysed from the daily settlement series
(`models/daily.py`) after a one-day washout, on the assigned price, with HC3 and the
larger of HC3 and a permutation standard error. The experimental row replaces the
observational one in `elasticity.run` and is not shrunk toward the (biased) pool.
Drafted as a standing `price_experiment` directive for SKUs with no price variation
or a fit the pole guard refuses; `hubricon pricetest … plan --design randomized` and
`analyze` run it by hand; `hubricon execute` turns the directive into a running
price test the Buy Box watch can see.

**Measured.** On the reactive generator of iteration 4 (phi = 0.4, rho = 0.6): the
observational raw fit reads more than +0.3 too flat, the randomised test on the same
SKUs lands within ±0.1 of the truth; the assignment is uncorrelated with the shock
over 160 draws; the washout removes the attenuation a one-day posting lag causes;
a test whose price sat at the assigned arm on under 80% of days returns
`not_executed`. `tests/test_price_experiment.py`, 11 tests. The closing section's
"neither is built" is therefore withdrawn for SKUs that have run the test, and only
for them.

### Iteration 18 — part 4: the family absorbs the move

**Objection.** §10 item 3: a cut that cannibalises a neighbouring SKU is booked as a
win on one and an unexplained loss on the other. The per-SKU optimum overstates a
rise (lost units partly land on a sibling) and understates a cut.

**Change.** `models/cross_price.py`: one own and one cross elasticity per variant
family (parent ASIN, or Shopify handle), within-transformed OLS with HC3 and a
Student-t interval, families shrunk toward the catalogue once three fit,
`no_variant_mapping` when nothing links two SKUs. `pricing_engine.delta_draws` takes
the family and draws its ε last, so a SKU without one is byte-identical to before;
every candidate is valued on own plus sibling profit and the step is sized on the
total; a move the SKU alone would make and the family would not is refused with
status `cannibalisation` and drafted as a finding. Measurement anchors each sibling
on its own after window and caps at the family's change.

**Measured.** A planted ε_cross of +0.8 (four children, ten periods) is recovered
within ±0.2 over twenty seeds with ε_own within ±0.2; families planted far apart keep
their own estimates and families within their own noise pool fully (τ² = 0 is the
answer, and the weight says so); a cut on a ε = −3 SKU with a large sibling is
refused as cannibalisation, a rise the family welcomes carries the sibling gain in
its range. `tests/test_cross_price.py`, 8 tests.

### Iteration 19 — part 5: the third way out of excess stock, and two corrections

**Objection.** Hold-or-liquidate assumed the excess sells at today's price. A markdown
that clears it before the aged-surcharge dates often beats a liquidation program's
recovery by a wide margin, and the engine never priced one.

**Two defects found on the way, one of them in numbers already issued.** The hold
value subtracted landed cost per unit while liquidation was gross recovery — sunk cost
charged on one side — which biased thin-margin SKUs toward liquidation; the excess was
sold from month one although it sits behind the cover; and `demand_over_cycle` still
drew the clipped normal the rest of the engine retired in iteration 6, under a
docstring that said otherwise. Fixed, dated in §5b, and pinned by
`test_hold_vs_liquidate_flips_with_carry_and_velocity_on_cash_contribution` and
`test_demand_over_cycle_matches_rate_times_horizon_and_is_lognormal`.

**Change.** `models/markdown.py`: hold, liquidate and a grid of markdown depths valued
on the same draws as cash proceeds net of fees and carry, landed cost sunk, chosen by
the certainty equivalent inside the price step's risk budget; the range flag for a
markdown below the observed price range; the stretch, a rise inside the cap valued on
thinned common random numbers and drafted as an ordinary price step; measurement
before landed cost plus the carry saving. A markdown or a stretch is its SKU's price
instruction for the cycle: the ordinary step and the aged-surcharge draft stand aside.

**Measured.** A hand-computed two-month NPV matches to 1e-9 with landed cost nowhere
in it; zero depth equals hold and no excess makes liquidate equal hold on every draw;
a steep-carry elastic SKU marks down, a dead SKU liquidates, a healthy one holds; the
band widens with se(ε) and more at 30% than at 10%; the stretch pays on an inelastic
SKU and refuses on an elastic one. That last result overturned the first draft, which
targeted the smallest rise bringing P(stockout) under 25% and, on an ε = −8 SKU, chose
a rise with a median window loss of $128: the stockout target alone recommends losing
money, so the stretch is now sized by the certainty equivalent like every other step.
`tests/test_markdown.py`, 13 tests.

### Iteration 20 — part 6: the order the supplier will actually accept

**Objection.** The newsvendor sizes each SKU alone. A real purchase order has a
minimum, a case pack, a price break, a shared wire and a choice of freight, and none
of that was priced.

**Change.** `models/replenishment.py` on the newsvendor's own demand ladder: MOQ and
case-pack rounding costed at the overage it forces, the price break taken only when
its saving beats the extra overage and capital, a can-order joint wire per supplier,
and air against sea on the stockout units avoided at margin plus the low-inventory fee.
Seven optional cost-sheet columns and a migration; blank means not priced. The reorder
directive carries the terms and the joint wire; `expedite_air` is explicit and
unbankable.

**Measured.** Rounding to a 150 MOQ and 24-unit cases lands on 168 and costs its
overage; a $1 break at 200 units pays and a 5¢ break at 600 does not; a supplier's
siblings due within a review period share a wire; a position that sea exposes and air
covers recommends air, a covered one does not. `tests/test_replenishment.py`, 6 tests.

### Iteration 21 — part 7: the order set the cash supports

**Objection.** "You may need bridge capital" is a warning, not an action. When the
cash cannot fund every order the newsvendor wants, which orders?

**Change.** `models/cash_orders.py`: the budget-constrained multi-item newsvendor by
its Lagrangian — each SKU's fractile with the cash a unit ties up priced at the shadow
price, bisected to the budget the cone already implies. Capital goes first to
contribution at risk per inventory dollar. One directive carries the funded set, the
deferrals and the bridge; the individual reorders for those SKUs stand aside.

**Measured.** λ = 0 reproduces the newsvendor's orders to within the ladder's
interpolation; at 60% of the wires the high-return SKU keeps more of its service level;
the total wire is monotone in λ; a cone with a positive trough is `fully_funded` and one
overdrawn by 40% funds 60% and names the 40% bridge. `tests/test_cash_orders.py`, 4 tests.

### Iteration 22 — part 8: the season

**Objection.** Every demand simulation drew a flat rate. For a catalog with a
fourth-quarter peak that understates the September reorder, misprices the peak
storage and makes the cone's November too quiet.

**Change.** `models/seasonality.py`: a multiplicative index per calendar month, pooled
across the catalog and shrunk toward flat, each SKU shrunk toward the catalog, with a
standard error on every index; refused under twelve calendar months. Applied to the
stockout model's and the order sizing's lead-time rate with the index uncertainty
widening the sd, to the cone per calendar day, to the peak-storage sell-down, and to
the forecast ladder as a candidate scored by the same backtest as the rest.

**Measured.** A planted 1.8× fourth-quarter peak is recovered within ±0.15 from
twelve months × thirty SKUs and ±0.08 from twenty-four, with the second season
tightening the interval; a flat catalog comes back within ±0.08 of 1; a SKU peaking
against the catalog is pulled toward its own summer but not all the way on one season;
September's reorder exceeds March's for the peaked SKU; the cone's fourth quarter is
richer than its first. `tests/test_seasonality.py`, 6 tests.

### Iteration 23 — part 9: what a customer is worth

**Objection.** The ad break-even values a customer at one order. A store selling
consumables under-spends against every competitor who knows better.

**Change.** `models/clv.py`: BG/NBD and Gamma–Gamma by maximum likelihood on a hashed
customer key the Shopify orders parser now writes (the email is never stored), a
52-week repeat expectation and value with a parametric-bootstrap band, a holdout
calibration that refuses the multiplier outside [0.7, 1.3], and the multiplier dividing
the ad break-even threshold when calibrated. Amazon is `not_applicable`.

**Measured.** On two thousand customers simulated from the model's own story the
fitted repeat expectation matches the truth within 25%, the Gamma–Gamma population
mean within 15%, the holdout ratio sits inside the band, and the multiplier carries a
band; 80 customers refuse, 20 weeks refuse; the parser splits nothing on email case or
whitespace and salts keys per client; a calibrated 2× multiplier raises the break-even
spend and an uncalibrated one moves nothing. `tests/test_clv.py`, 6 tests.

### Iteration 24 — part 10: which SKUs to cut

**Objection.** The negative-margin directive names a SKU on one period of net margin.
A SKU costs more than that to carry and is worth less than its last month if it is
dying, and the engine's own credibility and survival estimators sat unused for it.

**Change.** `models/assortment.py`: a fully loaded contribution per period, blended with
the catalogue by Bühlmann–Straub credibility, valued over twelve months through the
catalogue's Kaplan–Meier survival conditioned on the SKU's age; four gates before a cut;
merge candidates inside variant families; an explicit `sku_exit` directive that
supersedes the negative-margin draft and is banked one absent period at a time.

**Measured.** A SKU losing every month for eight periods is cut with Z ≥ 0.5 and
P(< 0) ≥ 0.75; one bad month in eight is kept; a two-period-old SKU on a catalogue that
dies at two or three is discounted and an eight-period-old one is not; carry, returns
and a stated operational cost subtract as computed by hand; the exit banks the loaded
loss for the periods the SKU sold nothing and stalls while it still sells.
`tests/test_assortment.py`, 5 tests.

### Iteration 25 — the risk tolerance is the client's, not ours

**Objection.** `RISK_BUDGET_SHARE = 0.15` sized every move and gated every mandate for
every client, and the cone counted ruin at zero for a seller who keeps a buffer.

**Change.** Two client columns, `risk_budget_share` (0.05–0.30) and
`min_cash_buffer_usd`, set by `hubricon cash`; the price step, the reallocation, the
markdown and the downside guard read the share, the cone and the cash budget read the
buffer, and every payload names the basis. Defaults reproduce the previous numbers
exactly.

**Measured.** A stated buffer raises p(ruin) monotonically and shrinks the order budget
by the same dollars; a 5% share walks a shorter step than 15% than 30%; a lower share
routes more drafts to an explicit yes; `risk_share=None` is byte-identical to before.
`tests/test_client_risk.py`, 3 tests.

### Iteration 26 — the ruin cost of a decision

**Objection.** The cone said "you may need bridge capital" about the whole plan and
nothing about any one wire. Sequence risk is per decision.

**Change.** `cashflow.ruin_ladder` and `ruin_delta`: the stored path minima price any
wire on any day without re-running the cone; `directives.ruin_guard` attaches the
before-and-after ruin probability to every cash-moving directive and routes one that
crosses the 5% line to an explicit yes.

**Measured.** The ladder agrees with a second simulation of the added wire within its
Monte Carlo error; a hand-built matrix reproduces its ruin shares to within the
quantile grid; a reorder priced at ten times the landed cost is demoted with both
probabilities in the reason. `tests/test_ruin_cost.py`, 3 tests.

### Iteration 27 — non-stationarity in the ad account

**Objection.** Ad costs drift. The anomaly scan watched a campaign's spend and nothing
else, and the response curve averaged across whatever regime change the auction
brought.

**Change.** Two daily series per campaign — cost per click and sales per click — through
the existing detectors and false-discovery control, valued at the campaign's clicks;
two unbankable drift directives; a regime break that makes the ad fit drop the points
before it and refit, or hold the campaign with a status when too few days have run. The
anomaly scan now runs before the ad fit.

**Measured.** A planted 50% cost-per-click step is detected and dated; a quiet campaign
flags nothing; the refit drops the pre-break points; a break with under five points
after it is held, and the reallocation holds it too. `tests/test_ad_drift.py`, 3 tests.

### Iteration 28 — the form of the ad curve, chosen out of sample

**Objection.** Hill was assumed whenever it converged. Every ad interval was conditional
on that form, and nothing tested it.

**Change.** A ladder of three forms — a straight line, log, Hill — scored by a
rolling-origin backtest in date order with the constant-ROAS error as the scale; a curve
wins only by more than one standard error of its improvement over the line, because the
curves nest the line. A campaign the line wins is `no_diminishing_returns` and is
reallocated as linear at its ROAS. Two defects found on the way: the log fit carried
Hill's parameter names, and the line was being estimated as a mean of noisy ratios
rather than by least squares.

**Measured.** A saturating campaign picks a curve that beats the line by several
standard errors; a proportional one picks the line and gets no break-even; six points
default to Hill and say so; a linear campaign still gives or takes budget in the
reallocation with a constant marginal return. `tests/test_ad_form_selection.py`, 4 tests.

### Iteration 29 — obsolescence from the survival curve

**Objection.** The order decision charged a flat 2% of landed cost for obsolescence on
every SKU, while the risk pass already estimated how long SKUs like it live.

**Change.** `inventory_econ.obsolescence_charge`: the expected write-off on a unit
ordered now, from the catalogue's Kaplan–Meier curve conditioned on the SKU's age, with
a band on q*; the flat rate stands, labelled, when no curve exists. The risk pass runs
before the order sizing.

**Measured.** A two-period-old SKU on a catalogue where eight SKUs died at two or
three periods earns a lower fractile than the flat rate gives, with the band around it;
a SKU as old as the catalogue carries no charge; no curve falls back flat and says so.
`tests/test_obsolescence.py`, 2 tests.

### Iteration 30 — model decay

**Objection.** Non-stationarity of the promises themselves: a pooled realisation ratio
hides a quarter that stopped coming true, and nothing compared a fit with the fit
before it.

**Change.** Cohort scoring in `replay.score` with bootstrap bands, a Mann–Kendall trend
and a `decaying` flag; `models/drift.py` comparing every elasticity and ad curve with
the previous run's under Benjamini–Hochberg, halving the price step's tolerance on a
drifted fit; both on every run.

**Measured.** Three cohorts realising 0.7 followed by one realising 0.15 read as
calibrated on the pooled figure and DECAYING by cohort with a falling trend; a planted
shift of more than an elasticity on two SKUs is flagged with at most two false alarms
among sixty; a drifted fit's risk budget is exactly halved and its step no longer.
`tests/test_drift.py`, 3 tests.

### Iteration 31 — what would break you

**Objection.** The cone priced the plan as it stood and said nothing about a fee rise,
a suppressed listing, dearer clicks, a late supplier or a held payout — the platform
and concentration risks a seller actually worries about.

**Change.** `cashflow.simulate(keep_paths=True)` keeps its components; `models/stress.py`
recomputes the cone under five named shocks with no new draws, ranks them by the change
in p(ruin), and checks that its base reproduces the cone; `hubricon stress` prints the
table.

**Measured.** The base equals the cone; a 3-point fee rise costs that share of the
revenue paid through the last payout day; dearer clicks cost the shock times the ad
spend; silencing the largest SKU raises ruin and deepens the trough; the late supplier
hits the SKU whose cover runs out inside the horizon; a held payout deepens the trough;
the table is ranked. `tests/test_stress.py`, 2 tests.

### Iteration 32 — garbage in

**Objection.** Every model read the exports as truth. Two exports that disagree, a month
nobody uploaded, a report nobody refreshed — none is a modelling error, and every one
lands in a directive if nothing catches it.

**Change.** `models/data_quality.py`, first in every run: four reconciliation pairs at a
5% tolerance, coverage and staleness per report; flags on the payloads that read a
flagged source; a penalty in the health score's signal sub-score; the largest gap in
the memo. Nothing is corrected.

**Measured.** A 20% July disagreement between SKU Economics and the settlement file is
flagged and named while June passes; a missing May is listed as missing; a stale ad
file is flagged; a Shopify run compares nothing it cannot; two failed pairs and one
missing month cost the signal sub-score twenty-five points. `tests/test_data_quality.py`,
4 tests.

### Iteration 33 — payback and the cost of a customer

**Objection.** A break-even on ad spend is a rate; what a founder asks is how many weeks
until a customer has paid for their own acquisition, and whether a customer is worth
what they cost.

**Change.** `clv.cac_by_month` (blended, stated as such) and `clv.payback`: the week a
new customer's cumulative expected margin covers the acquisition cost, and the
52-week LTV over it, each with a bootstrap band; on the trim directive for Shopify.

**Measured.** A $30 blended acquisition against an $80 first order at a 50% margin pays
back in week one with a ratio above one and bands that contain both; a dear
acquisition takes longer or reports None; the fitted payback agrees with the
generator's own within four weeks. `tests/test_clv.py`, 7 tests.

### Iterations 34–36 — win, remind, embed

**Objection.** The first issue ranked by dollars, so a price step a monthly export away
could outrank a bleed cut provable in a fortnight; the headline the retainer rests on
was a point with no band; and nothing placed a client against the book.

**Change.** A first-sweep ranking by expected dollars times time-to-bank
(`issue.FIRST_WIN_WEIGHT`, every kind weighted, a missing weight fails a test) and the
first-issue-to-first-dollar median in `speed.summary`; a 5th–95th band on the proven
figure from the measured moves' own distributions, printed when at least half the
dollars carry one; `models/benchmark.py` placing a client among the consenting book with
resampled bands and a refusal under ten clients.

**Measured.** A $900 bleed cut outranks a $1,200 price step on a first sweep and not
after; two banded steps and a recovery give $350–$1,800 around $900 and a ledger of
recoveries alone gives a point; a client's ratios come from its own results, a book of
twelve places it with a band, a book of nine refuses. `tests/test_issue.py`,
`tests/test_headline_and_benchmark.py`, 4 tests.

### Iteration 37 — model risk, measured on three worlds

**Objection.** Every calibration number above was measured one model at a time on
the generator that model was built against. Nothing had run the whole engine on a
catalogue with a planted truth, drafted its directives, simulated the month after,
and scored every promise against what that month actually held. The founder asked
for three such runs and for whatever they exposed to be fixed.

**The harness.** A synthetic catalogue of 160 SKUs in 40 variant families with a
1.6× fourth quarter, twelve monthly periods ending August 2026, eight campaigns,
supplier terms and settlement rows; three worlds — *clean* (prices exogenous),
*reactive* (the seller reprices at φ = 0.4 off last month's demand, ρ = 0.6) and
*drifting* (φ = 0.2, the true elasticity drifts by sd 0.6 before the after period,
a CPC break on one campaign, a 3-point fee rise). Every model runs as the CLI runs
it, `draft_directives` drafts, the after period is simulated from the truth at the
prices and spends the directives set, `measurement.measure` and `replay.score` run
over it, and each promise is scored against its own truth. Plus: the same seed twice
(byte-identical), another seed for the engine's own draws (same promises), one more
period (drift false alarms) and one period dropped (direction flips). The script is
the session's scratchpad `model_risk.py`; the findings are pinned in
`tests/test_model_risk.py`. What the first run showed, in the order it was
understood:

| finding on the first run | cause | what changed |
|---|---|---|
| promises 15–40× the truth; the Record read every step as a four-figure loss | the harness's history ended in December (peak) and its after-rows carried a fee split without dollar totals, read as fee-free | harness calendar fixed; `measurement._split_fees` rebuilds missing totals from the rate and the per-unit fee (an engine fragility, not only a harness one) |
| reactive world: fits +0.47 too flat, promises ~15× truth | the §2 bias, disclosed and uncorrected | the controlled fit and the catalogue correction (§2, corrected 2026-09-24) |
| family cross-elasticities of ±2 against truths under 1; the "identified" families were the noisiest (median error +1.0) | a common season in every residual; no identification gate | catalogue seasonal index divided out before both fits; a family's cross term used only at t ≥ 2 (§3b) |
| 30% of step directions flipped when one period was dropped | the same season noise on twelve points | fell to 8% (2% of the dollars) once the index was divided out |
| Record realisation −0.4 to −1.1 on worlds whose true realisation was 0.4 to 0.7 | the observed-change ceiling booked a bad month as the step's loss | the ceiling allows the SKU its own month-to-month noise and never manufactures a loss; the no-response case is caught by the batch's pooled volume response κ (§9, corrected 2026-09-24) |
| a joint-draw shape mismatch crashed the reallocation measurement | campaigns rejecting different numbers of out-of-bounds draws | draws paired on the common count (`tests/test_ad_allocation.py`) |

**Measured, after the changes** (world: clean / reactive / drifting):

```
elasticity, median error, raw static fit          −0.01 / +0.47 / +0.49
  after the season is divided out and the
  reaction corrected (published value)             +0.04 / +0.04 / +0.22
  raw 95% interval coverage                         0.96 /  0.87 /  0.88
  published interval coverage                       0.99 /  0.93 /  0.94
  median standard error, clean world                0.74 → 0.51
reaction diagnostic φ̂ (truth 0 / 0.4 / 0.2)         −0.00 / 0.38 / 0.19
family cross term, identified families,
  median error                                     +1.02 → −0.09 (clean)
  standard error                                    0.89 → 0.34
seasonal index, December, error                    −0.03 / −0.02 / −0.04
budget reallocation, 30-day promise vs truth       1,886 vs 1,683 (outside band) / 845 vs 813 / 1,842 vs 1,761
ordinary price steps, true dollars ÷ promised      1.10 / 0.93 / 0.52   (53 / 90 / 33 steps)
  truth inside the promised 5–95 band             0.57 / 0.47 / 0.52   (nominal 0.90)
  steps that lost money in truth                   0.26 / 0.32 / 0.36
  promised P(loss), median                         0.19 / 0.14 / 0.14
Profit Record realisation ratio (banked ÷ promised) 0.60 / 0.70 / 0.62 on the price steps, 0.64 / 0.64 / 0.53 on the reallocation
  band coverage                                    0.98 / 0.98 / 0.98
  pooled volume response κ                         0.90 ± 0.18 / 1.16 ± 0.16 / 0.79 ± 0.20
same seed twice                                    byte-identical
another seed for the engine's own draws            the same promises, to the dollar
drift false alarms on one more period              0 of 326 pairs
direction flips, one period dropped                19 of 236 steps (2.1% of the promised dollars); was 30%
```

Read plainly. The corrections are real on the reactive world — the published
elasticity error fell from +0.47 to +0.04 with interval coverage back at 0.93,
and the ordinary price steps' true dollars went from a fifteenth of the promise
on the first run to 0.93 of it — and partial on the drifting one, where the fit
is honest about a truth that has already moved and the steps realise half.
On the clean world the promises are unbiased (1.10): decomposed on one
after-period draw, the model's own delta at the point estimate is 0.86 of the
published median (the delta is convex in ε), the true elasticity gives 1.07 of
that, mean reversion of the baseline month takes 5%, and the after-period's
own shock is the rest. The Record's own ratio lands where §9 says a correct
engine's must — about 0.6 of the promise, the 25th percentile banked under a
ceiling that now allows the month its noise, with the small steps closed under
the $25 materiality floor — on the two worlds whose truth is near 1, and on the
drifting world it reads 0.62 against a true 0.52: an anchored counterfactual on
last quarter's fit cannot see this month's drift, which is what the cohort trend
of §9b is for. The harness's after-simulation sets prices and campaign spends
and nothing else, so the fee-bleed and ad-bleed kinds bank zero there (their
promises are reported as unsimulated) and the campaign trims bank one thirtieth
(one day of after-spend); the Record's ratio above is over the kinds the
harness can actually move. What remains open is listed below.

**The loss gate, priced and left off.** A gate on the step's own 25th percentile
(`pricing_engine.MAX_P_LOSS`) was built so the harness could price it. On the
three worlds at 0.25 it removed a quarter of the steps, cut the share that lose
money in truth from 0.26/0.29/0.29 to 0.18/0.28/0.22, took the direction-flip
rate to under 1%, and moved the true dollars by −7% / +3% / +14%. In the horse
race of iteration 6, whose sellers sit far from their optimum, the same gate keeps
635 of 987 moves and 82% of the total. The two testbeds disagree because their
worlds do, and the doctrine of iteration 6 — money landed first, the tail second —
stands until a real client history says otherwise. The gate is off, and one
constant away.

**What was tried and dropped.** A simulation-based bias correction that estimated
the seller's habit (φ̂, ρ̂) and simulated what that habit does to the estimator:
ρ̂ read off the residuals of the very regression the reaction biases came out at
0.19 against a true 0.6, and the correction it produced was a fifth of the bias.
It cost a day and is recorded so it is not tried again.

**Still open from this run.** The reallocation's promise ran 12% above the truth
on one world with the truth outside its band — the optimizer's curse on a promise
made on the same fits the allocation was chosen on; cross-fitting is on the list.
The truth sits inside an ordinary step's promised 5–95 band about six times in
ten against a nominal nine: the bands are honest about ε and the demand noise
they carry, and the shortfall is the after-period's own shock at a 20% sd,
which the promise's horizon term under-reads. The stretch step cannot be scored
in a harness with no stock constraint; the harness scores it apart and says so.
`data_quality` flags the harness's own August ad-spend reconciliation, which is
the harness's search-term rows, not the model. `tests/test_model_risk.py`,
9 tests, plus one in `tests/test_ad_allocation.py`.

### Iteration 38 — the Simons–Thorp–Griffin test

**Objection.** The founder asked for the model to be run on variations of the
data it will meet, its weaknesses found and removed and its mathematics
iterated, until a test scores ten out of ten through the eyes of Jim Simons,
Edward Thorp and Ken Griffin applied to the clients' problems, three times.

**The test** (`engine/bench/`). Ten pass/fail criteria under three lenses,
stated as principles in our own words — none is a quotation:

| lens | principle | criteria (client problem each answers) |
|---|---|---|
| Simons | is the signal real, and is the stated uncertainty honest? | S1 estimator honesty (does the elasticity say what the data supports?) · S2 promise calibration (does a 90% band hold nine times in ten?) · S3 no edge where there is none (do confident promises come true; is a catalogue at its optimum left alone?) · S4 stability (same data, same advice; one month more or less does not reverse it) |
| Thorp | know the edge, size the bet to it, never risk ruin | T1 the edge is real (steps, budget moves, trims, negations deliver in truth) · T2 never over-bet (steps and purchase orders no bigger than the evidence pays for) · T3 survive (the whole sweep at once cannot run the business out of cash or lose more than it said) |
| Griffin | manage the book; bad data is a risk; the accounting must be as rigorous as the model | G1 the book (the sweep's total promise is honest as a portfolio) · G2 garbage in (stockouts, deals, duplicates and missing costs caught before they become advice) · G3 the Profit Record (banks what was delivered — never more, not so little it is useless) |

A test is one seed: six synthetic 160-SKU catalogues with planted truths —
*clean*, *reactive* (the seller reprices off last month's demand), *drifting*
(the elasticity moves before the month after; a CPC break; a fee rise),
*thin* (seven noisy months), *dirty* (stockout and deal months, missing costs,
duplicate rows, a month split in two) and *already optimal* (prices at the true
optimum) — the whole engine run as the CLI runs it, the month after simulated
from the truth with every directive executed, every promise scored against
it. Three tests: seeds 101, 202, 303. The thresholds were committed before any
engine change made to meet them (`db24a4c`, which also records the four
corrected before the baseline was scored); one was amended after the baseline
and says so in `bench/rubric.py` (S1's bias limit, three of the engine's own
stated common error, floored at 0.15, because every SKU's error leans on the
same pool and a fixed 0.15 was under two of that error). The harness was
corrected where it scored the wrong thing — seed invariance compared as a
set, engine-deferred cash moves excluded and counted, the inventory oracle
deciding with decision-time information rather than knowing September's
shock, T2 charging over-ordering as its question asks — and no threshold
moved for any of them. Run it with

```
cd engine && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run python -m bench.run --tests 3 --jobs 12
```

(about two minutes on twelve workers; `--seed N` for any other seed;
unthreaded BLAS, or twelve workers oversubscribe the cores and it takes twelve).

**Scores.**

```
                           seed 101   seed 202   seed 303
baseline (da98479)            0/10       0/10       0/10     bench/results/2026-09-24-baseline.txt
round one (102aced)           5/10
round two (2bfde19)           9/10
round three, first run       10/10       9/10       5/10
round three (this commit)    10/10      10/10      10/10     bench/results/2026-09-24-round-three.txt

validation seeds, never tuned on:  404  8/10   505  9/10   606  10/10
```

**What round three changed**, each in `MATH_METHODS.md` under a dated note:

| failure the bench measured | cause | change |
|---|---|---|
| a reorder drafted under one simulation seed and not another (S4) | a stockout probability of 0.2510 against the 25% alert, carrying half a point of Monte Carlo error | lead-time demand computed exactly (lognormal–Poisson, trapezoid in z); order sizing on per-SKU streams (§5) |
| purchase orders 14–19.5% costlier than the true optimum's from over-ordering (T2) | orders sized on demand at the old prices while the same sweep raised them; a cheap month read as level; a deal month read as a seasonal peak; one noisy September setting a SKU's own index | the sweep's price plan sizes its orders; history restated at today's price; flagged months out of the index; one season pools to the catalogue (§5, §5a) → 2–10% |
| cuts delivering 15–22% of their promise; the Record banking 0.23 of the price-step promise (T1, G3) | the pool read the reaction correction's SKU-by-SKU bias as signal (τ² 0.52–0.96 against 0.29–0.33) and under-shrank the extremes, where cuts are chosen | each error placed by kind: a SKU's own before the pool, the shared one after; corrected rows moderated on their noise (§2) |
| reactive intervals holding the truth for 86% of SKUs (S1) | the heterogeneity term had its sign backwards | each SKU corrected on the catalogue's own line in price variance, gated at twenty SKUs a half (§2) |
| family cross effect 0.12–0.23 low on six of twenty-four catalogues | a coin-flip choice between two sibling indices | equal weights unless revenue weights win Vuong's test (§3b) |
| trims at 0.66 of promise; reallocations 7–9% optimistic, 10 of 16 bands holding | a log curve chosen by a hair; constant-ROAS extrapolation for straight-line campaigns | trims at the cautious end across tied forms and never below the spend on file; allocation on form-averaged curves with a resampled optimism (§4, §4b) → trims 0.92–0.95, bands 13 of 16 |
| the Record banking $721 of $3,472 of true step gains on one world (G3) | κ read without the family term, and trusted at two standard errors on a statistic whose error is 0.2 | κ reads the family's prediction; it overrides the fits at three standard errors (§9) |

**Measured, the three tests** (seed 101 / 202 / 303):

```
S1  95% interval coverage, six worlds          0.94–1.00 / 0.95–1.00 / 0.98–1.00
    median elasticity error, five worlds        −0.16…+0.08 / −0.06…+0.08 / −0.07…+0.10
    median elasticity error, thin world          +0.30 / +0.14 / −0.44   (limits ±0.87–0.94: its fits are uninformative)
S2  price-step bands holding the truth, pooled  0.91 / 0.92 / 0.88   (target 0.82–0.98)
S3  losses in truth vs quoted, all steps        26 vs 23.4 / 18 vs 17.3 / 12 vs 12.6
    steps on the already-optimal catalogue       0 / 0 / 0
S4  same seed twice / another simulation seed   byte-identical / the same promises, all three
    directions flipped by one month dropped      1.0% / 0.4% / 2.2%
T1  price steps, true ÷ promised                 0.89 / 0.85 / 0.90
    reallocation bands holding the truth         4 of 5 / 4 of 6 / 4 of 5
    trims, true ÷ promised                       0.95 / 0.92 / 0.94
T2  over-ordering cost, worst world              6.1% / 10.3% / 8.8%   (limit 15%)
T3  P(ruin), whole sweep at once                 0 → 0 in every world
G1  book bands holding the truth                 7 of 8 / 7 of 8 / 7 of 8   (the minimum; the misses: dirty price steps
                                                 $71 under the band, dirty advertising $59 and $45 under)
G2  every planted pathology flagged              yes, and no step on a SKU without landed cost
G3  Record banked ÷ promised, price steps        0.72 / 0.74 / 0.70   (never above the truth)
```

**The validation seeds, stated as found.** 606 scores 10/10. 505 scores 9/10:
its reactive world's price-step bands hold the truth for 78% of steps against
a floor the binomial test puts near 83%, because two shared errors landed
together — the reaction correction's remainder (+0.17, about 2.4 of its
stated error) and the family cross pool's (−0.16, about 1.9) — and every step
there carries both. 404 scores 8/10: its steps realise 1.36 of their promise
(the ceiling is 1.25) and its pooled bands hold 0.815 (the floor is 0.82),
from the same kind of coincidence on three catalogues at once — the
elasticity pool 0.16 too elastic in one, the cross pool 0.17 too low in
another, the month's volume 3–8% above August's in all three — and four of
its five reallocations miss because the ad backtest rejected, at 2.5 standard
errors, the curve shape that was true. Each is a stated uncertainty being
too small in a given month rather than a bias on average: across the
eighteen catalogues of the six seeds, 12% of step truths fall outside their
90% bands and 48% below their medians.

**What remains, and is on the list below.** The reaction correction's own
error is about half what its bootstrap states. A form the ad backtest
rejects is in no band. The book (§6) carries only the elasticity's shared
error on its common factor. The engine's per-world calibration is honest on
average and not in every month. Tests: `tests/test_bench_corrections.py`
(12) pins each change without the bench; `tests/test_model_risk.py`,
`test_horse_race.py` and `test_ad_curve_uncertainty.py` were re-pinned where
they recorded the old engine, each with a dated note.

### Iteration 39 — the network: a change on the platform's side

**Objection.** Every model reads one account. An Amazon fee change reaches every
account at once, and each account's own sweep — rightly strict over a hundred to
thousands of tests — reports a 5% step in fees that wander by 3% in about three
accounts in ten, three exports after it; a thin catalogue may never report it. The
one thing the book knows that no account does went unused, because terms §10
forbids using one client's data to advise another and nothing asked for the consent
that would allow it.

**Change.** `fleet.py`: the same count against coincidence, twice. Within an
account, a series is a hit when its changepoint p ≤ 0.05 and it steps the same way
by at least 1% inside the lookback; the account flags a fee type at h*(m), the fewest
hits in one 45-day window that m series of noise reach at most 5% of the time, and
π_a = P(Bin(m, 0.05) ≥ h*) is its own false-alarm rate (0.0025 for two SKUs, 0.048
for forty). Across the book, P(X ≥ x) for X Poisson-binomial over each account's
π_a, Benjamini–Hochberg at 0.01 across the (fee type, direction) cells, three
agreeing accounts at least; the size from every series at the account's onset
(not the hits: the winner's curse read an 8% step as 9%), pooled by median with an
account-resampled band. Two fee types, the FBA fee per unit and the referral rate:
the all-fees series carries storage, and storage carries the fourth quarter's stock
build, a common cause the null would read as the platform (a review caught it
before commit). Named refusals below the floors. A separate `network` consent is the
only door in, through the calibration consent's own gate; an alert to every client
who pays the fee, once each (a unique index), saying what, when, how big on the
typical SKU, how many accounts, and whether their own exports show it, in a letter
of its own; `hubricon fleet`, to run last in the Monday sweep, guarded (that step
waits on the branch `workflow-fleet`; by hand until then). `book.py`: replay's
realisation ratio by move kind across the same accounts, with an account-resampled
band, refusing under five accounts; report only.

**Measured.** Forty books of eight noise-only accounts through `anomaly.run`: no
change declared and none of 1,280 (fee type, direction) account questions flagged,
while 11 of the 320 accounts' own sweeps reported a finding on one of the two fee
types. The worst case the arithmetic allows (every account at exactly π_a, one day,
one direction): 9 declarations in 4,000 books against a design level of 40;
P(p ≤ 0.01) = 0.0008.
Power, forty books a cell: a 5% step in 3% noise, three exports after it, is
declared in 0.80–1.00 of books while one account's own sweep reports it in 0.31;
an 8% step in 1.00 against 0.84; with two exports, 0.03–0.33, the changepoint's own
floor. No other cell declared in 1,440 books. The planted book of the test: one
change, six of ten accounts, median ratio 1.077 (1.074–1.080). Sources that did not
consent, withdrew, are internal or have left are never read; a second and third
weekly pass announce nothing new; `hubricon book` refuses at four accounts, equals
`replay.score` on the pooled moves at six, and writes nothing.
`tests/test_fleet.py` (23), `tests/test_book.py` (5). What it cannot tell you is in
`MATH_METHODS.md` §8c, the size's lean on a small change among it (5.8% read for 5%:
the accounts that show a change are the ones noise pushed the same way).

---

## Outcome Alignment

Mathematics that scores well and produces a directive a seller will not act on is
worth zero. For each of the nine fixes: the sentence a seller reads, what it does
to the number of directives, and the guards around it.

The directive counts below are measured on one synthetic catalog — 120 SKUs, seven
periods, 22% demand noise, elasticities spread −3.6 to −0.6, landed costs on file —
comparing the engine's old behaviour with its current behaviour on identical data.

```
                                     old      new
price-step directives issued         115      117
  of which quoting a destination      95       16
  of which carrying a dollar promise 115       16
step size: median                     5.0%     5.0%
step size: 25th percentile             5.0%    4.5%
steps set by the statistics, not
  the contractual rail                 0       28% of them
anomaly tests run                    960      960
  detector flags                      24       24
  reaching a seller as a finding      24        0
```

**The headline:** the same number of instructions, 83% fewer prices quoted to the
cent, 86% fewer dollar promises. Fewer and truer, and the trade is argued below.

**Corrected 2026-09-12.** The step-size figures above were measured on ONE seed and
two of them did not replicate. Over twelve seeds and 703 moves the 25th-percentile
step is 4.5%, not 3.0%, and 71.8% of steps sit at the contractual rail rather than
57%. So the claim that the statistics rather than the rail now set the step is true
for about 28% of moves, not 43%. The rail is still doing most of the work, and
saying otherwise was a one-seed artifact of the same kind as the attenuation
baseline.

### 1.1 — The fee split

**Seller sentence.** "Your FBA fee is $3.30 a unit whether you charge $19 or $21,
and your referral fee is 15% either way. We price those two differently, because
treating them the same was quoting you an optimum below the real one."

**Directive impact.** Same count, higher destinations. On a $20 SKU with a 15%
referral and a $3.30 FBA fee the quoted optimum moves up by more than 5%.

**Downside guard.** Where an export does not separate the fees, the old assumption
stands and the report says `assumed_proportional`. That assumption biases the
optimum **down**, so the fallback errs toward recommending less.

**Promise integrity.** `margin_results.fee_split` is a new column and
`measurement._split_fees` charges the same split, so the counterfactual uses the
arithmetic that made the promise.

**Reversibility.** It is a price; the next cycle sets it back.

### 1.2 / 1.3 — The critical value and the standard errors

**Seller sentence.** "We only have five months of price history on this SKU, so
the honest range is wide — here is the small, safe step it justifies."

**Directive impact.** Fewer destinations and smaller steps. A 38% wider interval
pushes more SKUs into the pole guard and shrinks the step on the rest. This is the
single largest driver of the 95 → 16 fall in destinations quoted.

**Downside guard.** Coverage is measured, not assumed: 94.4–96.6% across thickness
and noise structure. The direction of residual error is conservative.

**Promise integrity.** `details` carries `dof`, `t_critical`, `se_estimator` and
the classical SE beside the published one, so an auditor can rebuild either.

**Reversibility.** n/a — an interval, not an action.

### 1.4 — Shrinkage

**Seller sentence.** "This SKU's own five months say −3.1, but five months of one
SKU is not much to go on. Your other forty SKUs average −2.0, so we are working
from −2.4 and we show you both numbers and how much of its own answer it kept."

**Directive impact.** Same count, more trustworthy. Shrinkage pulls wild fits
toward the pool, which both improves accuracy (measured: beats raw on ≥20 of 30
simulated sellers) and narrows the posterior, which slightly **increases** the
steps on thin SKUs relative to the unshrunk-but-wide alternative.

**Downside guard.** A SKU measured precisely keeps >95% of its own answer; a SKU
fitted exactly is never shrunk at all.

**Promise integrity.** `epsilon_raw`, `epsilon_shrunk`, `shrinkage_weight`,
`pooled_epsilon` and `tau2` all travel into the directive's evidence.

**Reversibility.** n/a.

### 1.5 — The pole guard

**Seller sentence.** "On this SKU we cannot tell the difference between 'a price
rise pays for itself' and 'it barely doesn't'. The best price could be a little
above where you are or several times above — so we are not going to quote you
one. Here is a small step, and two more months of data will narrow it."

**Directive impact.** **Fewer dollar promises: 115 → 16.** 101 of 117 price steps
now come back `near_unit_elastic` with no destination and no dollar figure. This
is the largest single change in what a seller is told, and it is the right one: on
a seven-period export with 22% demand noise the elasticity genuinely cannot be
separated from −1 for five SKUs in six. The engine still gives every one of them
an exact new price and a direction.

**Downside guard.** No `expected_impact_usd` at all, so nothing is banked and the
Profit Record cannot be credited for it.

**Promise integrity.** Nothing is promised, so there is nothing to measure — and
that is stated in the action text rather than left implicit.

**Reversibility.** A 3–5% step, reversible next cycle; Buy Box watched while live.

### 1.6 — The published range

**Seller sentence.** "We expect about $190 a period from this move. Four times in
five it lands between $90 and $310, and there is about a one-in-twenty chance it
goes the other way."

**Directive impact.** Same count, more trustworthy, and honestly labelled: the
directive says "90% range" because P5-to-P95 is a 90% band, where it used to say
"95% range" about two elasticity endpoints.

**Downside guard.** `p_loss` is on every directive, and the step solver refuses
anything whose expected shortfall exceeds the risk budget.

**Promise integrity.** The evidence blob carries `delta_p5`, `delta_p50`,
`delta_p95`, `p_loss` and `mc_inputs` (draws and seed), and
`replay.completeness` asserts all five are present and that
`expected_impact_usd == delta_p50`. The promise is scored against the
distribution it made, not against two endpoints reconstructed later.

**Reversibility.** As above.

### 1.7 — The step size

**Seller sentence.** "We are moving this one 1.8% rather than the full 5%, because
your history does not pin the demand curve tightly enough to justify more. On the
SKU below it we are taking the full 5%, because it does."

**Directive impact.** Same count, 43% of steps now set by the statistics rather
than by the contractual rail, and the 25th-percentile step falls from 5.0% to
3.0%. So: the same instructions, smaller on the SKUs we know least about.

**Downside guard.** Two, and they are the same constant enforced at two points:
the step solver's expected-shortfall constraint, and `directives.downside_guard`,
which routes any directive whose 5th-percentile outcome risks more than 15% of the
SKU's trailing monthly net to an explicit yes whatever its step size. Measured
relationship: because the solver already refuses anything whose bad case is a
material loss, every drafted step's 5th percentile on a real catalog is a **gain**
and the guard is slack. It is a backstop, not the thing that sizes the move.

**Promise integrity.** `policy` rides in the evidence with the objective name, the
risk budget, whether the cap or the statistics bound the step, and how many
candidates were feasible.

**Reversibility.** Every step is inside the ±5% a cycle the terms authorise, so the
next cycle can undo it in full without a new signature — which is the whole reason
the hard cap survives as a rail even though the statistics normally bind first.
Asserted in `test_every_price_step_is_undoable_within_one_cycle`, along with the
baseline price being on the record so the undo is exact.

### 1.8 — False-discovery control

**Seller sentence.** "We checked nine hundred and sixty things about your account
this fortnight. Twenty-four of them wobbled; once you account for having checked
nine hundred and sixty things, none of them wobbled by more than noise does. So
there is nothing here, and that is the finding. Last quarter's version of this
report would have sent you twenty-four alerts with dollar figures on them."

**Directive impact.** **Strictly fewer, and this is the clearest fewer-but-truer
win in the set.** On a pure-noise panel: 548 detector flags, 0 survivors. On the
synthetic catalog above: 24 detector flags, 0 survivors — because there is nothing
real planted in it. A planted $1.20 fee step inside 500 noise SKUs still clears
the control with its $120/period figure intact, so the control suppresses noise
and not findings.

**The argument for fewer.** A false alert costs more than a missed one. It arrives
with a dollar figure and an instruction, the seller acts on it or doesn't, and
either way the next alert is read with less attention. Twenty-four alerts a
fortnight of which twenty-three are noise is not a more thorough service than
three that are real; it is a worse one.

**Downside guard.** A demoted row keeps `detector_flagged` and its basis says in
words what happened — "across 960 tests this sweep that is inside what noise alone
produces (q = 0.31)" — so nothing disappears silently.

**Promise integrity.** `p_value`, `q_value`, `n_tests`, `fdr_q` and
`fdr_p_threshold` on every row.

**Reversibility.** An alert is information; the corrective action it triggers
(a re-measure request, a category check) is itself reversible.

### 1.9 — Correlated demand and the coherent tail

**Seller sentence.** "Nine of your SKUs could run out in the same month, not
three. Your products sell to the same customers in the same season, so their slow
months arrive together — and the old number assumed they didn't."

**Directive impact.** No change to the count of reorder directives (a per-SKU
stockout probability is a marginal statement and correlation cannot change it);
a materially worse aggregate picture on the cash and stockout panels, which is
what a replenishment budget and a bridge-capital decision are sized against.

**Downside guard.** The independent figures are published beside the correlated
ones, so the change is visible rather than a silent worsening. Where the history
cannot measure a correlation, a conservative default is used and the payload says
so.

**Promise integrity.** Reorder directives promise no dollars (the avoided-stockout
counterfactual is unobservable), so there is nothing to re-score; the panel is
reported as a state of the world.

**Reversibility.** A PO is a commitment, which is exactly why these directives sit
under an explicit mandate rather than a standing one.

---

## The refusal test

`tests/test_degeneracy.py::test_the_thinnest_plausible_input_returns_statuses_not_numbers`

One SKU. Five periods. One price change. No landed cost uploaded. A real shape of
first upload, and what comes back is the brand.

- every margin row reports `cogs: null` — never zero, never guessed
- `price_move` returns `None`: no landed cost, no dollar-exact recommendation
- every directive drafted has `expected_impact_usd is None`
- any pricing instruction that does appear says what is missing ("Upload unit
  costs") or why it cannot quote one ("we cannot separate this SKU's demand from
  the break-even point")
- the anomaly sweep on five points returns `insufficient_data`, not "no alerts" —
  "could not look" and "looked and found nothing" are different answers
- the cash cone returns `None` because the client stated no cash inputs

It is a test, not a hope.

---

## Closing summary

### What changed

Nine defects fixed, each its own commit with its own tests: the fee split in the
price optimum; the critical value; heteroskedasticity-consistent standard errors;
empirical-Bayes shrinkage; the pole guard at ε = −1; a real uncertainty
propagation replacing a two-endpoint range; a derived step size replacing a magic
constant; false-discovery control across the anomaly sweep; correlated demand with
a coherent tail measure and Monte Carlo errors on every published percentile.

Then four things the adversarial loop added that were not on the list: a replay
harness that scores past promises against measured outcomes; intervals on the
ad-response break-even, the last published number that had none; a spend-variation
refusal for campaigns whose spend never moved; and two regressions in the
measurement pass that the harness caught, both introduced by the Layer 1 fixes.

The suite went from 770 tests to 979.

### What the horse race showed

Five rules, 40 simulated sellers × 25 SKUs, three regimes with reactive pricing
and a drifting true elasticity, scored per move over a thousand moves:

- Every rule that uses the elasticity fit beats a naive fixed 3% step by more than
  50% on total realised profit. **The fit earns its keep.**
- **The robust step does not beat the plug-in optimum on total profit.** It is 1–2%
  behind in every regime, because it declines moves the plug-in takes. Per
  directive issued the two are a dead heat: 131.4 against 132.0.
- It does beat the plug-in in the tail, reproducibly: the mean of the worst decile
  of moves is 10–18% less bad and the dollars lost on losing moves 13–18% lower,
  in every regime.
- The pure quantile objective earns 28% **more** per move and loses 69% fewer
  dollars by declining 40% of the catalog. It is available and it is not the
  default, because it puts 23% less money in the payout.

The first version of that race reported a tail win that did not reproduce at other
seeds, because it scored the worst of twenty sellers. That is in the iteration
history above, with the fix.

### The most dangerous assumption that remains

**The elasticity is a correlation, and the price was not randomised.** A seller who
reprices in response to demand — which is most of them — produces data whose
fitted demand curve is about 0.4 of an ε too flat. The size is not what makes it
dangerous; the direction is. It is the direction that argues for raising prices, on
evidence that understates how much volume a rise will cost. It would take months of
exports to catch and would look like ordinary seasonality while it happened.

Four things stand between that and a client, and all four are tested: the pole
guard refuses a destination on the worst-biased SKUs; the step is small when the
fit is uncertain; Buy Box share is watched while every step is live and the step is
reversed if it drops; and the Profit Record banks the 25th percentile of the
measured outcome, capped at what the SKU's profit actually did.

### What data from the seller would retire it

**Corrected 2026-09-12, and the correction matters more than the original claim.**
This said the engine's own steps are that instrument. They are not, for two
measured reasons: the step is a deterministic function of the fitted elasticity
(so a price change caused by an estimate caused by demand is not exogenous to
demand), and a 14-day step blended into a calendar month of `sku_economics` gives
a price coefficient of variation near 0.011 against `MIN_PRICE_CV` = 0.02 — so the
estimator returns `insufficient_price_variation` and cannot see the step at all.
The compounding claim was not merely unproven; at the current export cadence the
compounding rate is zero. See MATH_METHODS.md §2.

What would retire the assumption is still a price change made for a reason
unrelated to demand, plus a price series fine enough to see it — a deliberately
randomised component of the step, and either a fortnightly export or the daily
realised price that already sits unread in `settlement_transactions`. Both are
cheap. ~~Neither is built.~~ **Both are built as of 2026-09-23** (iteration 17): the
randomised six-block test and the daily settlement series. The assumption is
retired one SKU at a time, only after its test has run, and the report names which
SKUs carry an experimental estimate.

The table below still stands, because it is about price VARIATION and says nothing
about where the variation comes from. It is the measured fraction of SKUs for
which a price optimum can be named at all (200 simulated SKUs per row, 22% demand
noise):

| periods | price variation (log CV) | optimum nameable | median SE(ε) |
|---|---|---|---|
| 7 | 10% | 16.5% | 0.79 |
| 7 | 18% | 32.0% | 0.56 |
| 12 | 10% | 37.5% | 0.61 |
| 12 | 18% | **60.5%** | 0.39 |
| 24 | 18% | 71.0% | 0.25 |
| 24 | 25% | 79.0% | 0.18 |

Price variation buys more than time does: doubling the price variation at seven
periods doubles the nameable share, while nearly doubling the periods at the same
variation gets less. A seller who arrives with 10% of price variation over seven
months gets a destination on one SKU in six. After five cycles of deliberate ±5%
steps — roughly 18% variation, twelve periods — it is three in five.

Price variation buys identification; the table says how much. What it does NOT say
is that the engine's own instructions supply that variation — they do not today,
for the two reasons above. **The table is a specification for what would have to
change, not a description of what already happens.** Read the earlier version of
this paragraph as the cautionary example it is: it was the most flattering reading
of a real table, and the flattering reading was false.

### What it costs to run

A 400-SKU catalog with nine periods of history and eight campaigns, measured end to
end on 2026-09-23 with every model of this iteration in the run (the synthetic
catalogue and the script are the end-to-end check in the plan; the measurement pass
ran over the 495 directives it drafted against a simulated later export):

```
data quality      0.0s     ad efficiency      8.7s   (form ladder: 12 backtest origins × 3 forms × 8 campaigns)
margin            0.1s     drift              0.1s
seasonality       0.0s     ad allocation      0.0s   (no_reallocation on this catalogue)
forecast         19.2s     recovery           0.0s
inventory sim     1.6s     risk               0.3s
inventory panel   1.3s     inventory econ     2.4s
elasticity        0.3s     markdown           3.2s   (153 SKUs valued three ways, 4,000 draws each)
price experiments 0.0s     replenishment      0.5s
cross-price       0.1s     assortment         0.2s
anomaly           1.8s     cash cone         33.0s   (10,000 paths × 90 days, components kept)
incrementality    0.0s     stress             0.1s   (five scenarios on the kept components)
clv               0.0s     cash orders        0.0s
                           directives         2.3s   (495 drafted)
                           measurement        0.9s   (495 directives)
TOTAL            75.5s
```

Re-measured on 2026-09-24 (iteration 38) on the bench's 160-SKU catalogue, eight
campaigns, twelve months, 8,000 inventory draws and 4,000 cone paths: the whole engine
runs in about 29 seconds, of which the ad curves take 4.2 (the form ladder's refits,
plus one fit and a break-even interval per tied form, the interval vectorised over
draws and grid), the reallocation's resampled optimism 3.1 (80 resamples × the
campaigns it moves), the elasticity fit 0.3 on a reacting catalogue (its bootstrap is
one weighted matrix product over the SKUs' stored moments), and the exact lead-time
demand 1.3 seconds for 160 SKUs — about what 8,000 draws each had cost, for figures
with no simulation error.

The cash cone is still the largest single cost and unchanged in kind. The two
additions that cost anything are the forecast (already the second-largest before this
iteration; unchanged) and the ad curve's out-of-sample form ladder, which is
thirty-six refits per campaign and capped there. Every other model of the iteration
runs in under four seconds on this catalogue because each reuses draws the engine
already made: the markdown on the elasticity posterior, the stress table on the cone's
own paths, the cash budget on the newsvendor's ladder, the ruin ladder on the cone's
minima.

### What is still worth doing, in order

1. **Ingest the advertised-product report (SP-API).** Revenue-share ad allocation is
   still the largest remaining approximation in the margin model; it feeds the
   negative-margin directive, the loaded contribution of §1b, and the blended
   acquisition cost of §4d, and no export links a campaign to a SKU or a customer.
2. **Run the replay harness on the first real client history** and put its
   realisation ratio — pooled and by cohort — in this file. Every calibration number
   above is a simulation until then, and that is the one thing on this list that
   cannot be engineered, only waited for.
3. **The randomised price test on a real SKU.** The instrument exists (iteration 17)
   and has been shown unbiased on the generator that produces the bias; the first
   real six blocks will say what the generator could not — how often the Buy Box
   holds at the high arm.
4. **Container capacity and supplier lead-time variance** on the cost sheet, so the
   joint order (§5c) can fill a container and the expedite rule can price a late
   supplier from history rather than an assumed 20%.
5. **A second demand factor**, which needs a category taxonomy no export carries. One
   factor currently overstates dependence inside an evergreen line and understates it
   inside a seasonal one; the seasonal index of §5a is a start, not a factor.
6. **Cost dispersion.** `cost_cv` is plumbed through the bootstrap and defaults to 0;
   a client whose cost sheet moves between cycles has an observable dispersion that
   nothing reads.
7. **The operational cost per SKU** as a client-stated input (§1b carries it at zero
   and says so), and the client's own category for the benchmark book (§9c).
8. ~~**Cross-fit the reallocation's promise.**~~ Priced since iteration 38 by
   resampling each campaign's days and re-solving the allocation on each
   resample, with the forms the backtest cannot separate averaged in. What
   remains is a form the backtest *rejected* (iteration 38, seed 404): a
   decision-aware form check — scoring the forms on the marginal return the
   allocation actually moves along, not on one-step sales levels — is the
   next step.
10. **A second-order reaction correction.** The half-panel jackknife leaves a
   bias of order 1/T² that the bootstrap over SKUs cannot see; on six bench
   catalogues the correction's error was about twice its stated error. A GMM
   estimator on the differenced equation (Arellano–Bond) would remove it on
   twelve periods where a third subpanel cannot.
11. **The family cross pool and next month's volume on the book's common
   factor** (§6), so a month in which the shared errors land together shows
   in the book's band before it shows in the Record.
9. **A stock constraint in the model-risk harness**, so the stretch step (§5b) can
   be scored against a truth that includes the stockout it is meant to avoid;
   today the harness scores it apart and says so.

Withdrawn from this list on 2026-09-23, because built: fitting elasticity on the
engine's own step history (the steps were never an instrument; the randomised test
is), and the two "neither is built" items of the closing section above.
Withdrawn on 2026-09-24, because built: the reactive-pricing correction (iteration
37), which the 2026-09-12 write-up said could not be built without an instrument.
