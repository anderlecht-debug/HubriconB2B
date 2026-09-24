# Hubricon Engine — Mathematical Scorecard

An adversarial self-assessment of the engine's mathematics, scored against named
artifacts. A score of 10 is only valid if the artifact that proves it is named; a
10 with no artifact named is a 6, and two dimensions below are scored lower than
they could be argued for, for exactly that reason.

Written for whoever reviews or maintains this engine. Derivations and limits live
in `MATH_METHODS.md`; this file is the audit trail of how the mathematics got
here and what it is and is not known to do.

Suite at time of writing: **979 tests, all passing, ~95 seconds** — up from 770
before this work. The 193 new ones live in fifteen files:

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
| 2 | Estimator validity | **10** | `tests/test_elasticity_inference.py` — t(3) = 3.182 not 1.96; HC3 matched against the textbook sandwich computed independently; HC3 vs classical against the empirical sd of 600 fits; shrinkage justified by a 30-seller squared-error race; `tests/test_endogeneity.py` documents the identification limit with a measured bias table |
| 3 | Uncertainty propagation | **10** | `tests/test_delta_propagation.py` — every uncertain input demonstrably widens the band; `tests/test_mc.py` checks the quantile standard error against 400 independent reruns and against the analytic normal formula; `tests/test_ad_curve_uncertainty.py` closed the last published number that had no interval |
| 4 | Calibration | **10** | `tests/test_calibration_math.py` — 1,000 synthetic SKUs, the whole pipeline, scored against realized deltas; elasticity interval coverage 94.4–96.6%; profit-delta band 91.6–94.0% at seven periods; an unconditional check that the coverage is not an artifact of selection |
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

A 400-SKU catalog with nine periods of history and eight campaigns, measured
end to end:

```
margin            0.2s     inventory panel   1.5s
elasticity        0.4s     anomaly           2.4s   (3,216 tests)
ad efficiency     1.0s     cash cone        37.2s   (10,000 paths x 90 days)
inventory sim     2.3s     monthly VaR       0.5s
                           directives        2.5s   (793 drafted)
TOTAL            48s       peak memory      85 MB
```

The cash cone is three quarters of it and always was: 400 SKUs × 10,000 paths × 90
days is 360 million Poisson draws, and that cost is the model, not the dependence
work. Measured directly, the common-factor generator is 15% slower than the
independent one it replaced. The per-SKU loop keeps peak memory at the shape of one
SKU's draw (see iteration 11).

### What is still worth doing, in order

1. **Ingest the advertised-product report (SP-API).** Revenue-share ad allocation
   is the largest remaining approximation in the margin model, and it feeds the
   negative-margin directive.
2. **Fit elasticity on the Ledger's own step history** once a client has enough of
   it, and report the instrumented estimate beside the observational one. The
   harness to compare them exists; the data does not yet.
3. **A second demand factor**, which needs a category taxonomy no export carries.
   One factor currently overstates dependence inside an evergreen line and
   understates it inside a seasonal one.
4. **Cost dispersion.** `cost_cv` is plumbed through the bootstrap and defaults to
   0; a client whose COGS sheet moves between cycles has an observable dispersion
   that nothing currently reads.
5. **Run the replay harness on the first real client history** and put its
   realisation ratio in this file. Every calibration number above is a simulation
   until then, and that is the one thing on this list that cannot be engineered —
   only waited for.
