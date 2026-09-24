# Hubricon Engine — Mathematical Methods

Every model the engine runs, the derivation behind it, the assumption it rests
on, and — the section that matters most — what it cannot tell you.

Written for whoever maintains this engine next, and for anyone who has to defend
a number in it to a client, an accountant or an auditor. Nothing here is
marketing; the client-facing versions of these statements live in `index.html`
§05 and in `report/templates/report.html.j2`, and both are checked against this
file.

Scope: the pricing, elasticity, anomaly, inventory, cash and risk models. The
ingest layer, the Decision Ledger mechanics and the billing arithmetic are
documented in `OPERATIONS.md`.

---

## 1. True net margin

**What it computes.** Per SKU per period,

```
Net = Revenue − Σ|platform fees| − Units × c_landed − Ads × (Rev_SKU / Rev_total)
```

`c_landed` = unit cost + inbound freight + packaging + fulfilment + other, from
the client's own COGS sheet. Fee magnitudes are summed because fee columns arrive
with inconsistent signs across export versions.

**The fee split.** The same row also publishes `fee_split`:

```
f = (referral_fees + other_fees) / revenue         proportional to price
F = (fba_fulfillment_fees + storage_fees) / units  fixed per unit
```

with `basis: "itemized"` where the export separates them and
`"assumed_proportional"` where it reports one blended line. Pricing needs this
split (§3); putting the whole fee in `f` biases the price optimum downward, which
is the conservative direction, so that is the fallback.

`other_fees` stays in the proportional bucket. Its composition is unnamed in the
export, and the placement that biases `P*` down is the one to choose when you do
not know.

**Assumptions.**

- Ad spend is allocated to SKUs in proportion to revenue share within the period.
  This is an approximation and a material one: a campaign pushing one SKU has its
  cost spread across the catalog. The advertised-product report (SP-API) fixes it
  and is not yet ingested.
- A blank COGS column is `None`, never zero. A SKU with no cost sheet reports
  `cogs: null` and every downstream dollar figure that needs it is refused.

**What it cannot tell you.** Whether the ad spend allocated to a SKU actually
drove that SKU's sales. It is an accounting split, not an attribution.

### 1b. The fully loaded SKU, and which to cut

**What it computes** (`models/assortment.py`). Net margin is one period of one
measure. The loaded contribution per period is net margin (already net of fees, landed
cost and allocated ads) less the forward carry the fee lines do not yet show (the aged
surcharge and low-inventory fee the inventory-economics pass prices), less the returns
cost (returned units × the loss fraction of their disposition × landed cost), less an
operational cost per active SKU that is zero until a client states one, and says so.
Each SKU's mean is blended with the catalogue's by Bühlmann–Straub credibility
(`risk.buhlmann`), with the weight Z on the row; the interval is a normal on the pooled
within-SKU variance over n, and P(contribution < 0) comes from it. The twelve-month
value discounts the blended contribution by the catalogue's Kaplan–Meier survival
conditioned on the SKU's age, S(age + k)/S(age) — a SKU as old as the catalogue gets
no discount, because the curve has no information beyond the longest life it saw.

**What is flagged.** Cut: blended contribution below zero, Z ≥ 0.5, at least two
negative periods, P(< 0) ≥ 0.75 — four gates so one bad month never names a SKU.
Merge: a variant with under 5% of its family's revenue and a loaded contribution at
or below zero. The exit directive promises the avoided twelve-month loss and
supersedes the negative-margin instruction for its SKU; the Profit Record banks it
only as the periods without the SKU pass, and a SKU still selling ninety days on is
closed as never carried out.

**What it cannot tell you.** Where a cut SKU's buyers go (§3b's family
cross-elasticity is the only evidence); a SKU's worth to a rank or a bundle; the
operational cost, until stated.

---

## 2. Price elasticity

**What it computes.** Per item, log-log OLS over the periods on file:

```
ln Q_t = a + e·ln P_t  [+ g·ln Sessions_t]
```

so the price coefficient is the elasticity. Guardrails run before any fitting: at
least `MIN_PERIODS = 5` usable periods, and a price coefficient of variation of at
least `MIN_PRICE_CV = 2%`. Failing either returns a status, not a number.

The sessions control is dropped when `|corr(ln sessions, ln units)| > 0.98`,
because a traffic series that moves in lockstep with units absorbs the price
effect and returns a confidently wrong near-zero elasticity. The payload says when
it was dropped.

**The interval.** Student-t on the fit's own residual degrees of freedom, on HC3
heteroskedasticity-consistent standard errors:

```
e ± t_{0.975, n−k} · SE_HC3
V_HC3 = (X'X)^-1 X' diag(e_i^2 / (1 − h_i)^2) X (X'X)^-1
```

Two deliberate choices, both measured:

- **t, not 1.96.** At `MIN_PERIODS = 5` with an intercept and a price term the
  residual dof are 3 and the correct quantile is 3.182. The normal quantile would
  publish an interval 38% too narrow on exactly the thinnest SKUs.
- **HC3, not classical.** Log-demand residuals are not constant-variance across a
  SKU's price range. On 600 simulated fits with variance rising across the range,
  the empirical sd of the estimate is 0.500, the classical SE reports 0.456 and
  HC3 reports 0.548. HC3 is the noisier estimator at n = 8 and no claim is made
  that it is closer in absolute terms — the claim is that it misses on the
  conservative side. Where a period is fitted exactly and (1 − h_i) hits the
  floor, the classical covariance is returned and `se_estimator` says so.

Measured coverage of the published interval, 1,000 simulated SKUs per cell:
94.4%–96.6% at n = 5 and n = 12, homoskedastic and heteroskedastic. The same
critical value on the classical SE falls to 90.9% under heteroskedasticity.

**Shrinkage.** A per-SKU elasticity from five periods is noise, and `price_move`
feeds it into `e/(1+e)`, a function that does not know its input is noise.
Empirical Bayes:

```
tau^2   from DerSimonian–Laird across the level's pool
w_i     = tau^2 / (tau^2 + SE_i^2)
e_i*    = w_i·e_i + (1 − w_i)·mu        mu = precision-weighted pooled mean
SE_i*^2 = w_i·SE_i^2 + (1 − w_i)^2·Var(mu)
```

The weight is literally the ratio of between-SKU dispersion to within-SKU
sampling variance. The posterior SE carries both terms, so borrowing strength is
charged for. A SKU fitted exactly (SE = 0) is never shrunk. `details` carries
`epsilon_raw`, `epsilon_shrunk`, `shrinkage_weight`, `pooled_epsilon` and `tau2`;
the optimizer consumes the shrunk value and the report shows both.

Justification, measured: across 30 synthetic sellers of 20 SKUs each with
elasticities spread −2.6 to −1.4 and six noisy periods apiece, total squared error
of the shrunk estimates beats the raw per-SKU fits overall and on at least 20 of
the 30 sellers individually.

**The pool.** The catalog within a level (ASIN fits pool with ASIN fits, SKU with
SKU). No category taxonomy reaches the engine — no export carries one — so
`elasticity.run(groups=...)` takes a mapping if one ever does, and the payload
names the pool it used rather than implying a taxonomy.

**tau² = 0 is a real answer.** It says the spread of the fitted elasticities is no
wider than their own sampling noise explains, and in that case every SKU is
described better by the pooled estimate. It is visible in the payload (every
weight goes to zero) rather than silent.

### What the elasticity cannot tell you

**It is a correlation, and the price was not randomised.** The prices in the
regression were chosen by the seller, often in response to how demand was running —
and a price that moved *because* demand moved says less about demand than a price
that moved for no reason at all.
When demand is persistent and the seller reprices off last month's numbers,
`cov(ln P, shock) > 0` and the fitted curve reads demand as **less**
price-sensitive than it is.

Measured over 96 seeds × 60 SKUs per cell, nine periods, as the median
estimation error (fitted minus true):

| demand persistence rho | reaction strength phi | bias |
|---|---|---|
| 0.6 | 0.0 | +0.02 |
| 0.6 | 0.4 | **+0.51** |
| 0.0 | 0.6 | −0.16 |

**Corrected 2026-09-12.** This table previously reported a +0.15 "small-sample
attenuation baseline" at phi = 0 and described the endogeneity as the increment on
top — and warned that the two "must not be confused". There was only one thing.
The +0.15 was an artifact of eight seeds: twelve independent 8-seed blocks of that
cell run from −0.117 to +0.145 with a between-block sd of 0.079, and the pooled
figure over 96 seeds is **+0.022**. The test that pinned +0.15 passed 5 of those 12
blocks.

So the bias at phi = 0.4, rho = 0.6 is the whole **+0.51**, and essentially all of
it is endogeneity. The comfort that most of the error was just thin data was never
real, and the assumption is correspondingly more dangerous than the first write-up
said — as is its consequence, which was also understated (33% on the quoted
optimum, not 17%).

The sign at rho = 0 matters and is not a curiosity: with no persistence, reacting
to last month biases ε̂ the OTHER way (−0.16). A correction triggered on reaction
strength alone would therefore do harm on a non-persistent catalog, which is why
any such correction needs a persistence test too — and why the one designed on
2026-09-12 was not shipped (see below).

Both run the same way — toward zero, toward "raise the price, demand barely
cares" — which is the dangerous direction, because it is the direction that
argues for increases. A SKU whose true elasticity is −2.0 can read −1.6, and at
−1.6 the model puts the optimum **33% higher** than at −2.0 — the ratio is
[1.6/0.6]/[2.0/1.0] = 4/3 exactly, independent of cost and of the fee structure.
(This document said 17% until 2026-09-12. It was simply wrong, and the test that
was supposed to pin it asserted only `> 1.15`, so nothing caught it. The most
dangerous assumption is twice as dangerous as the first write-up said.)

~~**It is not corrected, and cannot be with the data on file.**~~ Correcting
simultaneity needs an instrument: something that moves price without moving
demand. Nothing in an Amazon or Shopify export is one. ~~What the engine does
instead:~~

**Corrected 2026-09-24: it is corrected, without an instrument, because the
thing the seller reacts to is in the export.** The bias comes from a price
set off *last* period's demand, and last period's demand is a column. A fit
that controls for it,

    ln q_t = a + ε ln p_t + b ln p_{t−1} + γ ln q_{t−1} + η_t,

has η_t independent of p_t — the price can only be correlated with the shock
through the two lags, which are now held fixed — so the coefficient on ln p_t
is ε (`elasticity._fit_controlled`, HC3 on n − 1 points and four
coefficients). The price is two coefficients on a short series: on twelve
monthly periods the controlled fit's standard error is roughly double the
static fit's, and on eight it is useless (3.3 against 0.7). So the catalogue
pays for the control once. The seller's habit is the seller's, not the
SKU's: the reaction strength φ is estimated across the whole catalogue
(`reaction_diagnostic`: the price the seller set next, demeaned within the
SKU, regressed on the residual of the static fit, HC3), and only when φ̂ is
positive and two standard errors from zero — a one-sided test, because the
within-SKU demeaning gives φ̂ a small mechanical negative bias and a seller
who *cuts* after a good month is not the case the engine is defending
against — is the difference between each SKU's static and controlled fit
taken, as a 20% trimmed mean over the catalogue with a bootstrap standard
error, and subtracted from every SKU's efficient static estimate, with that
error added to the SKU's own. Trimmed rather than the median because the
differences are right-skewed on a short series and the median under-read
the bias by up to 0.23 on the reactive catalogues it was tried on; trimmed
rather than the mean because a twelve-period controlled fit throws
outliers. Applied after shrinkage, since the pool mean carries the same
bias. A SKU's row shows `details.epsilon_uncorrected`,
`epsilon_controlled` and `endogeneity.{phi, t_phi, bias_hat, bias_se,
applied, reason}`; an experimental row (below) is never touched.

Measured (`tests/test_model_risk.py`, six seeds × 80 SKUs × 12 periods at
phi = 0.4, rho = 0.6): the static fit reads +0.52 to +0.65 too flat, the
controlled fit sits within ±0.1 of the truth, the corrected catalogue within
−0.09 to +0.19 (median +0.04); φ̂ reads 0.37–0.41 against 0.4. On six
non-reacting catalogues the correction never fires. On the model-risk
harness (MATH_SCORECARD.md, iteration 37) the reactive world's median error
went from +0.47 to +0.09 and the drifting world's from +0.55 to +0.29, and
in the horse race of `tests/test_horse_race.py` — whose sellers all react at
phi = 0.6 — realised profit rose for every rule that uses the fit. A
simulation-based variant, which needed the shock's persistence ρ, was built
first and dropped: ρ̂ read off the residuals of the very regression the
reaction biases came out at 0.19 against a true 0.6, and the correction it
produced was a fifth of the bias.

What it cannot do: a seller who reacts to something *other* than last
period's demand of the same SKU (a competitor's move, a stock position) is
not controlled for, and a reaction that changes over the window is averaged.
The randomised test (below) remains the only estimate that needs no model
of the seller. What the engine also does, unchanged:

1. The pole guard (§3) refuses a destination whenever the estimate cannot be
   separated from −1, and a bias toward zero pushes estimates into exactly that
   band — so the most-biased SKUs are disproportionately the ones the engine
   declines to price. Measured: on a reactive-pricing catalog the guarded group
   carries more estimation error than the group the engine is willing to quote.
2. The step is sized by a risk-averse objective, so an uncertain fit produces a
   small move a later export can correct.
3. ~~Every price step the engine issues is itself a price change made for a
   reason unrelated to demand, so the Ledger's own history is the instrument.~~

   **Corrected 2026-09-12.** This said the engine's own steps ARE that instrument and
   that it manufactures one each cycle. That is false twice over, and both
   reasons are now measured:

   (a) A step is a deterministic function of ε̂, its standard error, the fee
       structure and the trailing margin — every one of them a function of the
       same demand shocks that bias ε̂. A price change caused by an estimate
       caused by demand is not exogenous to demand. Selecting on the
       cap-bound stratum does not rescue it: the rail binds precisely when the
       fit says the optimum is far away, so selection INTO that stratum is on ε̂.
   (b) Even if it were exogenous, the estimator cannot see it. A step held for
       `price_tests.DEFAULT_TEST_DAYS` = 14 inside a calendar month of
       `sku_economics` blends to a monthly average price whose coefficient of
       variation is about 0.011 — under `MIN_PRICE_CV` = 0.02 — so the SKU comes
       back `insufficient_price_variation` and gets no number at all. Measured:
       eight months with three 14-day 5% steps gives price_cv 0.0112; the same
       steps held for a whole month each give 0.0244 and fit.

   What would make the claim true is a deliberately randomised component of the
   step whose draw is independent of the data, plus a price series fine enough
   to see it. ~~Neither exists today.~~

   **Corrected 2026-09-23: both now exist**, in `models/price_experiment.py`, and
   the bias is corrected for any SKU that has run the test. The design: five arms
   at −5%, −2.5%, 0, +2.5% and +5% of the current price — every one inside the
   standing cap — in six seven-day blocks. Two blocks are anchors at the ends,
   because a Thompson allocation alone can put every block on adjacent arms and
   hand the estimator a series under its own price-variation floor; the other
   four are allocated by Thompson sampling on the fitted posterior (uniform when
   there is no fit — the test is what creates the data), each arm floored at 10%.
   The block ORDER is a permutation drawn from a generator seeded by the client,
   the SKU and the start date and nothing else, so the arm a day gets is
   independent of that day's demand shock by construction. Seven-day blocks hold
   each weekday once. The series is the daily realised price and units from the
   settlement file (§4d, `models/daily.py`), read after a one-day washout at the
   start of each block because Transaction View rows post at shipment.

   The analysis regresses log units per counted day on the ASSIGNED log price
   (HC3, Student-t on the block dof), so slippage in the realised price cannot
   re-introduce endogeneity; the first stage and the Wald ratio are published
   beside it. Because HC3 treats blocks as independent and a persistent shock
   makes them not so, every distinct relabeling of the blocks is refitted and the
   standard error used is the larger of HC3 and the permutation sd, with the
   Fisher p-value for ε = 0 on the record. The result replaces the SKU's
   observational row in the fit and is NOT shrunk toward the catalogue pool —
   the pool mean is the observational one and carries the bias — while the
   observational estimate and the measured bias ε_obs − ε_exp ride in `details`
   with the sentence a seller reads.

   Measured on the reactive generator above (phi = 0.4, rho = 0.6, twelve seeds
   × 40 SKUs): the observational raw fit reads more than +0.3 too flat; the
   randomised test on the same SKUs lands within ±0.1 of the truth
   (`tests/test_price_experiment.py`). What the test cannot separate: Buy Box
   suppression at the high arm, which is part of the response the seller faces;
   and a SKU selling a unit a week has too few units per block for any six-block
   design, which the fit's own floor and interval report rather than hide.


**The season, divided out first (added 2026-09-24).** A catalogue with a
1.6× fourth quarter puts three consecutive high months into every SKU's
residual. Under exogenous prices that is variance, not bias — but it is a
lot of variance on twelve points, and it lands on whichever price noise
happened to fall in October. With a catalogue seasonal index on file (§5a;
twelve distinct calendar months, so one full season) the SKU fits run on
units divided by that month's *catalogue* index
(`seasonality.deseasonalise_economics`). The catalogue index and never the
SKU's own: with one season on file a SKU's own monthly ratio *is* its own
residual, and dividing by it would fit the noise away; the catalogue index
pools every SKU, so no single SKU's noise moves it. Measured on the harness
(`tests/test_model_risk.py`): the median standard error fell from 0.74 to
0.51 on the clean world with the median error unchanged inside noise, and
the family cross-price fit (§3b) went from a standard error of 0.89 — where
the "identified" families were the ones whose noise happened to be largest,
median error +1.0 — to 0.34 and a median error of −0.09. Without an index
nothing changes and every row says so (`details.seasonal_adjustment`).

**The other limits.** Constant elasticity is a local approximation; it is used
only inside a ±5% band around the observed price and extrapolation beyond the
observed price range is not attempted. Cross-price effects between the client's
own SKUs are modelled only inside a variant family (§3b) and used only where
identified. Competitor prices are not in the data at all.

---

## 3. The price optimum and how far to walk

**Derivation.** With Q(P) = Q0·(P/P0)^e and the fee split from §1,

```
Pi(P)   = Q0·(P/P0)^e · (P(1 − f) − c − F)
dPi/dP  = 0   =>   P* = [(c + F)/(1 − f)] · e/(1 + e)
```

Verified symbolically with sympy (`tests/test_pricing_derivation.py` solves
dPi/dP = 0 and checks the single root equals the formula) and numerically against
a 200,001-point grid search at four elasticities × four fee structures.

The fixed per-unit fee `F` therefore behaves exactly like extra unit cost, and the
proportional fee grosses the whole thing up. Collapsing the two into one rate
moves the optimum the wrong way: on a $20 SKU with a 15% referral fee and a $3.30
FBA fee, the blended treatment quotes an optimum more than 5% below the truth.

Valid only for elastic demand (e < −1). For −1 < e < 0 profit rises monotonically
with price in this model and there is no interior optimum.

### The pole at e = −1

`e/(1+e)` is 21 at e = −1.05 and 51 at e = −1.02 — two estimates three hundredths
apart. So a fit of −1.12 with a standard error of 0.18 names no price.

`near_unit_elastic` fires when the published interval straddles −1, or when
|1 + e| < `POLE_GUARD_SIGMAS` = 2 standard errors. Two sigma is deliberately the
same line the 95% interval draws, so the guard and the interval cannot disagree
about the same SKU. When it fires: no `destination`, status `near_unit_elastic`,
no dollar promise, and a plain sentence saying why.

**The direction survives the pole; the distance does not.** P* > P0 whenever
e/(1+e) > P0(1−f)/(c+F); that ratio exceeds 1 for any SKU with a positive
contribution margin, while e/(1+e) runs to infinity as e approaches −1 from below
and to 1 as e goes to minus infinity. Near the pole the inequality holds from
either side, so the move is up. The engine does **not** assert that, because the
same guard also fires on a clearly elastic estimate whose interval is merely wide
— forcing that SKU upward would assert the one thing the wide interval says is
unknown. Both directions are searched and the objective, which integrates the
whole posterior, decides.

### The risk budget is the client's

Every rule below that sizes a move against "15% of the SKU's trailing monthly net" —
the step, the reallocation of §4b, the markdown of §5b, and the downside guard that
routes a move to an explicit yes — reads that share off the client since 2026-09-23
(`clients.risk_budget_share`, bounded 0.05–0.30, `hubricon cash <client> --risk-share`),
with 0.15 as the default, and every payload says which it used. The same command sets
`--buffer`, the minimum cash the cone counts a path as ruined below (§6), in place of
zero. The default reproduces every number the engine produced before the columns
existed; a stated share moves them, and the client can see how far.

### The step size

The step is solved for, not capped. Over a grid of candidate prices at 0.25%
resolution inside the hard cap:

```
feasible:  ES5[dPi(s)] >= −B,    B = RISK_BUDGET_SHARE × trailing monthly net
chosen:    argmax  E[dPi(s)] − Var[dPi(s)] / 2B
rails:     |s| <= STEP_CAP = 5%,  and the walk stops at P*
refusal:   standing still scores exactly 0; a SKU that cannot beat it gets nothing
```

`ES5` is the expected shortfall — the mean of the worst twentieth — not the
percentile at its edge, so the constraint is coherent and behaves when the Desk
aggregates across SKUs.

**Why not a pure quantile objective.** Maximising the 25th percentile of the
profit delta is the obvious robust objective and it cannot size a step. For small
moves the delta is proportional to s, and every quantile of a positively scaled
variable scales with it: Q25[s·X] = s·Q25[X]. The objective is positively
homogeneous, its maximum against a box constraint is always a corner, and the
policy collapses to "the full cap, or nothing". Measured before the change: across
a sweep of elasticity, margin, demand noise and standard error, every
recommendation landed on a corner, and on one SKU the whole curve of steps across
a 28-fold range of standard error took two distinct values.

The variance term is the device Almgren and Chriss use for the same reason — a
cost quadratic in the size of the move — and it gives

```
s* = B · (expected gain per unit step) / (variance per unit step)
```

a rate set by the signal-to-uncertainty ratio. At the interior optimum the
variance penalty consumes exactly half the expected gain, whatever the SKU, which
is what makes one dimensionless constant enough. Doubling the standard error
shrinks the step: measured on one SKU across SE from 0.05 to 1.40, the step runs
2.25%, 2.25%, 2.00%, 1.75%, 1.75%, 1.50%, 1.25%, 0.75%, 0%, 0% — monotone, seven
distinct values, ending in a refusal.

The pure tail objectives remain selectable (`objective="quantile"` / `"cvar"`) and
the horse race in `tests/test_horse_race.py` prices them.

**What is deliberately not modelled.** Almgren–Chriss's convex cost is market
impact; the analogue here is Buy Box suppression, and nothing in the engine's data
prices the suppression hazard against step size — no competitor price series
reaches it. A quadratic hazard curve would make the policy prettier and would be
invented. Execution risk is carried by the two mechanisms that are real: the hard
cap (which is what `terms.html` §6 authorises), and Buy Box share watched while
the step is live with the step reversed if it drops.

### The published range

A parametric bootstrap over every uncertain input, seeded:

| input | distribution | source |
|---|---|---|
| elasticity | shrunk posterior, Student-t on the fit's dof | §2 |
| Q0 | lognormal, mean-preserving, sd = residual_sd_log × sqrt(2) | the fit's residual scale |
| f, F | normal at the dispersion of the SKU's own fee history | 2 or more periods of margin rows |
| c | fixed | landed cost is client-stated, not measured |

The **sqrt(2) on Q0** is load-bearing: the baseline period is one noisy demand
draw and the period the promise covers is another, so the uncertainty in the ratio
between them is twice the per-period variance. Without it the band is 41%
narrower than the thing it is a band for.

Published: `delta_p5`, `delta_p50`, `delta_p95`, `p_loss`, and the Monte Carlo
standard error of each percentile. The promise is the median; the plug-in value at
the point estimate is kept beside it. P5-to-P95 is a **90%** band and is named as
one everywhere it is printed.

Measured coverage against realized deltas on 1,000 simulated SKUs: 91.6%–94.0% at
seven periods across 5%–45% demand noise, and 96.0%–96.7% at five periods. So
calibrated at seven periods and **conservative at five** — at dof = 3, HC3 and a
t(3) draw compound, both deliberately on the safe side. Over-covering makes the
recommended step smaller than strictly necessary, which costs upside and cannot
cost a seller money, so it is reported rather than tuned.

Cost uncertainty is the gap: `cost_cv` exists and defaults to 0 because a COGS
sheet is a number the client states rather than a quantity the engine measures.
Where a client's sheet changes between cycles the dispersion is observable and the
parameter carries it.

### 3b. Cross-price effects inside a variant family

**What it computes.** A colour or size variant shares the family's demand. Where a
family exists — Amazon's `parent_asin` over child ASINs, or a Shopify product handle
over its variants — one own and one cross elasticity per family:

```
log q_it = α_i + ε_own·log p_it + ε_cross·log p̃_{−i,t} + e_it
```

with p̃ the revenue-weighted mean of the siblings' log prices (weights fixed over
the window). Child intercepts absorbed by a within transformation; OLS on the two
demeaned regressors; HC3; Student-t on N − n_children − 2. One cross term per family
because thirty-two observations cannot support a matrix of them. Families are shrunk
toward the catalogue's cross-elasticity by the empirical-Bayes rule of §2 once three
or more fit; the sign is the data's (substitutes positive). Refusals: fewer than two
children or five shared periods (`insufficient_data`), a sibling index that barely
moved (`insufficient_price_variation`), and no mapping at all (`no_variant_mapping`,
the whole model).

**Identified, or published and not used (added 2026-09-24).** At the price
variation a real catalogue shows — a 6% coefficient of variation over twelve
monthly periods — the family fit's standard error is of order one, and the
model-risk harness (MATH_SCORECARD.md, iteration 37) fitted cross-elasticities
of ±2 against planted truths under one. Fed into a step's sibling term, that
noise moved promises by more than the step itself. A family's cross term now
enters a step only when its shrunk estimate sits `MIN_CROSS_T` = 2 of its own
standard errors from zero; every fitted family is still published, with
`identified`, `t_cross` and its interval, and an unidentified one is kept out
of `by_sku` so no step carries it. The fit runs on units with the catalogue
seasonal index divided out (§2), which is what made identification real: on
the harness the standard error fell from 0.89 to 0.34, and the families that
passed the gate went from a median error of +1.0 — the gate had been
selecting the noisiest — to −0.09. A family planted at zero is "unidentified"
by construction, and that is the right answer: there is no effect to carry.

**What it does to a step.** Every candidate price in §3 is valued on own PLUS
sibling profit: sibling j's units move by (p_new/p_0)^(ε_cross·w_ij) − 1, w_ij being
this SKU's share of j's sibling index, ε_cross drawn from its own posterior on the
same common random numbers. The step is sized on the total. When the SKU alone
would have moved and the family together will not, no step is issued and the
finding is drafted as `cannibalisation_watch`, naming the sibling. A SKU with no
family, or in a family whose cross term is not identified, reproduces every
number it produced before the term existed.

**Measurement.** Each sibling is anchored on its own after window exactly as the
SKU is: what it would have sold at the SKU's old price, at its own realised
contribution, over the same draws. The observed-change cap becomes the FAMILY's
change, not the SKU's, so a cut that stole from Red is charged for Red.

**What it cannot tell you.** One cross term for the whole family averages Red
stealing from Blue with Red ignoring Green. Substitution from outside the family is
in no export. Both slopes carry the observational caveat of §2 until a randomised
test has run.

---

## 4. Ad response and break-even

**What it computes.** Per campaign, sales as a saturating function of spend — Hill
first, log fallback:

```
Sales(s) = a·s^h / (k^h + s^h)
break-even at dSales/ds = 1/m,    m = contribution margin before ads
```

so ads break even on profit, not on revenue. Bleed terms are search terms with
spend above $10 and zero attributed sales.

**The interval.** `curve_fit`'s parameter covariance is propagated: parameters are
drawn from the asymptotic normal posterior, draws outside the fit's own bounds
rejected so the boundary constraints carry through, and the marginal ROAS and
break-even recomputed on each. Published: P5/P50/P95 of both, the Monte Carlo
error of the median, and **P(the marginal dollar is already below break-even)** —
which is the number a trim decision actually rests on. The trim directive is sized
off the cautious (higher) end of the break-even band, and no trim is drafted when
the interval reaches current spend. Measured on a simulated campaign: the
break-even band is $88–$95 at low noise and $64–$98 at high noise.

**Which form, chosen out of sample (2026-09-23).** Hill was taken whenever `curve_fit`
converged, and §10 #9 said every interval was conditional on the form. The form is now
chosen the way the forecast ladder chooses a model: a rolling-origin backtest over the
campaign's points in date order, one-step error scaled by the training window's
constant-ROAS error, across a ladder of three forms — a straight line (sales
proportional to spend, no saturation), log, Hill. A curve wins only when its
per-origin improvement over the line exceeds one standard error of that improvement,
because a curve nests the line (Hill with a huge k, log with a tiny b) and can edge
it out by noise. When the line wins the campaign is `no_diminishing_returns`: the
marginal dollar returns what the average dollar returns, there is no break-even to
trim toward — unless the whole return interval sits under break-even, in which case
every dollar loses and the trim fires at zero — and the reallocation treats the
campaign as linear at its ROAS, so it still gives or takes budget. The selection, the
candidates' errors and the improvement over the line ride on the row. Fewer than two
backtest origins: Hill by default, and the row says so.

**Refusals.** Fewer than 5 points, or a spend coefficient of variation below 2%:
`curve_fit` converges on a flat-spend campaign onto an arbitrary point of a flat
likelihood ridge and returns a **zero** covariance that reads as perfect
certainty. The guard runs before the fit. A non-positive covariance diagonal is
separately reported as `basis: "unavailable"`.

**What it cannot tell you.** The intervals are conditional on the curve form being
right, which no amount of resampling tests. Attribution is the platform's own
(Amazon's 7-day attributed sales), so the response curve inherits whatever that
window mis-attributes. And spend was chosen by the seller or their tool, so the
same endogeneity caveat as §2 applies in principle — unquantified here, because
the engine has no simulation of how sellers set budgets.

### 4b. Reallocating the budget across campaigns

**What it computes.** The trim above moves each campaign toward its own break-even.
The money BETWEEN campaigns is a different quantity: at the same total spend B, the
allocation that equalises marginal returns,

```
maximise  Σ_i E[f_i(s_i)]    subject to    Σ_i s_i = B,   lo_i ≤ s_i ≤ hi_i
```

with f_i the fitted Hill or log curve of §4. The margin is common to every
campaign, so at a fixed budget it cancels: the allocation that maximises attributed
sales maximises attributed profit. The Lagrangian reading — a multiplier λ at which
every campaign's marginal ROAS is equal — is what the client is told, but it is not
the solver. Hill with h > 1 is S-shaped, so the first-order condition is necessary
and not sufficient and a bisection on λ can skip the budget. The problem is a
separable allocation on a spend grid and has an exact dynamic program,
V_k(b) = max_j f̄_k(j) + V_{k−1}(b − j); λ* is read off the solution as the
marginal value of budget, (V(B+δ) − V(B−δ)) / 2δ.

**Which curve.** The posterior-mean curve of each campaign, f̄_i(s) = E[f_i(s; θ)]
over draws of θ from the fit's own covariance — not the point estimate. The objective
is additively separable and expectation is linear, so max E[Σ f_i(s_i)] =
max Σ E[f_i(s_i)]: the posterior mean IS the risk-neutral Bayes solution, exactly,
and the optimizer never sees a single noisy parameter vector.

**How far to move.** s_rec = s_0 + α(s* − s_0), α chosen as the price step's size
is chosen (§3): maximise E[Δ] − Var[Δ]/(2·tol) over α subject to the 5% expected
shortfall of the 30-day gain staying inside tol = 15% of the campaign set's own
monthly net (attributed sales × margin − spend, floored at zero — the same
net-after-ads base as `trailing_monthly_net`). A campaign set earning no net gets no
tolerance and no move; the trims still fire. Two rails: no campaign past 1.5× the
spend it was ever observed at, and no campaign moved more than 30% of its current
spend in one cycle.

**The interval.** Draw d of every campaign paired with draw d of every other
(campaigns are fitted separately, so the draws are independent and there is no
cross-campaign covariance to draw). Published: the P5/P50/P95 of the 30-day profit
gain, P(loss), and the Monte Carlo error of each percentile. The free-budget optimum
(every campaign at marginal ROAS = 1/m) is solved beside it and published as
information, so the report can say whether the account as a whole is over- or
under-spent while the directive itself moves no total.

**Refusals.** Fewer than two campaigns with a usable covariance
(`insufficient_campaigns`); a campaign whose covariance the fit could not produce
is `held` and named; fewer than 50 joint draws inside the bounds
(`insufficient_draws`); a median 30-day gain under $50 or fewer than 60% of draws
gaining (`no_reallocation`). Campaigns a trim moves this cycle are held out, so no
campaign carries two promises in one run.

**Measurement.** Anchored per campaign, as the price step is anchored on its after
period: each campaign's counterfactual sales at its old spend are what it actually
sold at its new spend scaled by f(s_old)/f(s_new) on draws of the stored curve, so a
demand shock in the window cancels campaign by campaign. Banked at the 25th
percentile, capped at the observed change in the set's net and at the promise
prorated to the window; a plan less than half executed is stalled, not measured.

**What it cannot tell you.** Everything §4 cannot: the interval is conditional on
the curve form, attribution is the platform's 7-day window, and spend was chosen by
the seller.

### 4c. Incrementality and the organic halo

**What it computes.** The break-even in §4 is on the platform's ATTRIBUTED sales.
Some of those would have happened organically (attribution overstates, the break-even
is too generous); ad-driven sales also lift organic rank (attribution understates, the
break-even is too strict). The number that settles it is the incrementality ratio

```
ι = d(total sales)/d(spend)  ÷  d(attributed sales)/d(spend)
```

Two estimators, of different honesty.

*Observational.* Per export period, total sales across the catalog, attributed
sales and spend summed from the daily campaign file, all as daily rates; first
differences remove level and trend; the two slopes by OLS with HC3 standard errors;
ι their ratio with a delta-method interval on a Student-t critical value at the
residual degrees of freedom. Refused under eight periods or when spend's coefficient
of variation across periods is under 10%. Season and everything else that moves total
sales sits in the residual, so on monthly exports this refuses or publishes a wide
band more often than not — which is the truthful answer. It is published as
information and never moves the break-even.

*Switchback.* One campaign ON and OFF in fourteen randomised two-day blocks over four
weeks, the order from a generator seeded by client, campaign and start date and
nothing else. Daily total sales from the settlement file (Amazon: per SKU; Shopify:
per order) against daily attributed sales; ι = total lift ÷ attributed lift, a 90%
band by seeded block bootstrap, a permutation p-value on the block labels. Executed
only if OFF days actually stopped spending (`not_executed` otherwise). Randomisation
makes E[shock | ON] = E[shock | OFF]. An executed switchback's ι moves the break-even:
the marginal attributed dollar must then return 1/(m·ι), and the attributed break-even
stays on the row beside it.

**What it cannot tell you.** Carryover, in both directions at once. Real sales
arriving on OFF days from ON-day clicks shrink the total lift and pull ι toward zero;
attribution following the click into OFF days (the seven-day window) shrinks the
attributed lift and pushes ι up. Which wins depends on whether the window carries
further than the real effect, and nothing in the data says which. The first draft of
this section claimed one direction; the simulation showed each mechanism moving ι the
opposite way, so both are stated and neither is corrected. And no export links a
campaign to the SKUs it advertises, so the total is the account's total: diluted, not
biased.

### 4d. Lifetime value, for a store that knows its customers

**What it computes** (`models/clv.py`, Shopify only). The break-even in §4 is a
first-order break-even. For anything people reorder that is too strict: a customer
worth three orders justifies three times the acquisition spend. BG/NBD (Fader, Hardie
and Lee 2005) — a Poisson buying rate per customer, Gamma across customers, a dropout
coin after each purchase, Beta across customers — fitted by maximum likelihood on each
customer's repeat count, recency and age in weeks; Gamma–Gamma (Fader and Hardie 2013)
for the value of an order. Expected repeats over the next 52 weeks per customer by the
closed form; expected value per order by the conditional mean. The customer is a
SHA-256 of the lower-cased email salted with the client id (`customer_orders`), and the
email is never stored.

**The multiplier.** 1 + E[repeats over 52 weeks] × (repeat value ÷ first-order value),
discounted; `ad_efficiency` divides the break-even threshold by it, so the marginal
attributed dollar need only return 1/(m × multiplier), and the first-order break-even
stays on the row beside it. The interval is a parametric bootstrap from the inverse
Hessian at the maximum, with a Monte Carlo error.

**Calibration is not assumed.** Fitted on the first three quarters of the calendar and
asked to predict the last quarter's repeats; actual over predicted is published, and
outside [0.7, 1.3] the multiplier is `poorly_calibrated` and moves nothing. The
frequency–value correlation is published because Gamma–Gamma assumes it away.

**Payback and LTV:CAC.** The acquisition cost is blended — the channel's ad spend over
the customers whose first order fell in the month, the last three months — because no
export links a campaign to a customer, and the payload says so. Payback is the week in
which a NEW customer's cumulative expected margin (the first order's margin plus the
expected repeats by that week at the repeat order's margin, from the same closed form
at zero age) covers that cost; LTV:CAC is the 52-week figure over it; both carry a band
from the parametric bootstrap, and a payback a year does not reach is None, not
fifty-three. The trim directive carries them on a Shopify run.

**Refusals.** Under 100 customers or 26 weeks (`insufficient_data`); Amazon
(`not_applicable` — no Amazon export carries a customer identity, and Subscribe & Save
is in none of them).

**What it cannot tell you.** Which campaign acquired which customer (the acquisition
cost is blended); whether last year's cohorts describe next year's; a customer whose
email changed.

---

## 5. Inventory

**Per SKU.** Lead-time demand:

```
L   ~ LogNormal(median = supplier lead time, sigma = 0.2)
r_i = mu_i·exp(sigma_i·Z_i − sigma_i^2/2),   sigma_i = sqrt(ln(1 + (sd/mu)^2))
D   ~ Poisson(r·L)
P(stockout) = P(D > fulfillable + inbound)
```

with a closed-form cross-check `ROP = mu_d mu_L + 1.645·sqrt(mu_L sd_d^2 + mu_d^2
sd_L^2)`.

The rate was a normal truncated at zero until 2026-09-11. Clipping a normal at
zero raises its mean above the one it was calibrated to and removes the skew
demand has, and it bit hardest on the thin volatile SKUs where the stockout
question is live. The lognormal is moment-matched and cannot go negative. The
−sigma²/2 is not decoration: without it the mean is inflated by 6% at a 35%
coefficient of variation.

**Across the catalog** (`inventory_sim.aggregate`). A per-SKU stockout probability
is a marginal statement and correlation cannot change it. "How many SKUs run out
in the same month" is a joint statement and independence answers it far too
comfortably. One common factor, Gaussian copula:

```
Z_i = rho·Z_common + sqrt(1 − rho^2)·eps_i
```

with rho estimated from the catalog's own history (§7). Published: the expected
number out of stock, its 95th percentile, the **expected shortfall of the count**,
P(at least 1) and P(at least 3) — each computed both with the measured correlation
and with independence, side by side, so the difference is visible. Measured on 24
SKUs at a pairwise correlation of 0.43: the mean is unchanged at 6.0, the 95th
percentile goes 10 to 15, the expected shortfall 10.5 to 17.2. Independence
understated the tail by 63%.

**Assumptions.** A missing supplier lead time is assumed at 45 days and flagged
`lead_time_assumed`. A single observed period has its rate sd assumed at 35% of
the mean and flagged `rate_std_assumed`. The lead-time sigma of 0.2 is an
assumption, not a measurement — no export carries realised lead times.

**What it cannot tell you.** The value of an avoided stockout. The counterfactual
— units you would have sold while out of stock — is unobservable, so the reorder
directive promises no dollars and the measurement pass proves the PO landed
instead.

### 5. Order sizing: the newsvendor, and obsolescence from the survival curve

The order-up-to level is the q*-quantile of demand over lead time plus the weekly
review period, q* = C_u / (C_u + C_o): C_u the lost contribution margin plus the
low-inventory fee, C_o the cycle's storage plus capital on the landed cost plus
obsolescence. (This section was absent from the document until 2026-09-23 although
the model had shipped; the sunk-cost rule for units already on hand is §5b.)

**Obsolescence** was a flat 2% of landed cost per cycle. It is now, per SKU, the
expected write-off on a unit ordered now: P(the SKU dies before this order sells
through) × (landed cost − liquidation recovery), with P read off the catalogue's
Kaplan–Meier survival curve (§8 of the risk pass) conditioned on the SKU's age,
1 − S(age + cycle)/S(age). A young SKU on a catalogue that dies young earns a lower
service level; a SKU as old as the catalogue carries no charge, because the curve has
no information beyond the longest life it saw. The charge's standard error gives a band
on q*, published beside it. Without a curve (under eight SKUs or six periods) the flat
rate stands and the row says so. The risk pass therefore runs before the order sizing.

### 5a. The seasonal term

**What it computes** (`models/seasonality.py`). Every simulation above drew a rate
that was flat over its horizon. The seasonal index is a multiplier per calendar
month, estimated hierarchically because the data is thin per SKU and wide across
SKUs: for each SKU and month, the ratio of that month's daily rate to the SKU's own
mean; the CATALOG index for a month is the mean of every SKU's ratio in it (forty
SKUs over one year give forty observations of December), shrunk toward 1 by the
empirical-Bayes rule of §2 against the sampling noise of each month's mean; each
SKU's own index is its ratios shrunk toward the catalog's. Every index carries a
standard error and a Student-t interval, and the basis says whether one season or
two were seen. Refused under twelve distinct calendar months (`insufficient_history`).

**How it is used.** The rate a lead-time window simulates on is the flat rate times
the mean index over that window's calendar days, and the index's own uncertainty is
added to the rate's dispersion in quadrature — sd² = sd_rate²·I² + rate²·se_I² — so a
reorder in a thin month widens rather than pretending the index is known. The cone
applies the index per calendar day; the peak-storage units are sold down at the
seasonal rate. The forecast ladder gains `seasonal_index_ses` — deseasonalise,
smooth, reseasonalise for the target month — scored by the same rolling-origin
backtest as every candidate and never chosen by assertion; it runs on a SKU with far
fewer than thirteen periods of its own because the index is the catalog's.

**What it cannot tell you.** A month never observed (index 1, no interval, listed);
a SKU whose season runs against the catalog's, from one season of evidence; holidays
that move between months.

### 5b. Excess stock: hold, liquidate, or mark it down

**Corrected 2026-09-23, twice.** The hold-or-liquidate rule in `inventory_econ`
valued hold as the discounted margin on the excess — price net of fees LESS landed
cost — against liquidation at 10% of price, gross. For units already on the shelf the
landed cost is sunk: it is the same cash gone whichever way the units leave. Charging
it on one side biased thin-margin SKUs toward liquidating stock that would have
netted several times more sold down; at $20 with $16 landed the old rule read $1 a
unit against $2 recovered, where the seller keeps $15.50 by selling. It also sold the
excess from month one, although excess is by definition the stock behind the target
cover. And `demand_over_cycle` still drew a normal clipped at zero — the generator
every other simulation retired on 2026-09-11 — while its docstring claimed the
lognormal. All three are fixed; the first is a change in numbers already issued.

**What it computes now** (`models/markdown.py`). The units on hand, valued three ways
as cash proceeds net of fees and carry, landed cost excluded, discounted monthly at
12%/yr with no separate capital charge (discounting is the time value; a capital
charge on sunk cost would count it twice):

- hold: the whole position first-in-first-out at p_0, storage and aged surcharge on
  whatever remains each month;
- liquidate: the excess at 10% of price now, the cover held;
- markdown at depth d: p_0(1 − d) for the listing until the position is back to
  the target cover, then p_0; demand r·(1 − d)^ε.

ε from its shrunk Student-t posterior, the rate lognormal from the SKU's own
dispersion, the fees from their history — common random numbers across every option.
Depths from 5% to 40%, floored where the markdown nets less per unit than
liquidation. The choice is the certainty equivalent of the gain versus hold inside the
same risk budget as the price step (15% of trailing monthly net), hold always a
candidate at zero. Published per option: P5/P50/P95 of the NPV and of the gain, P(loss),
the months to clear, the Monte Carlo error. A markdown deeper than the 5% standing cap
is the client's explicit decision. No elasticity: the corrected two-way decision
still runs, and says so.

**Extrapolation.** The elasticity is a local fit used inside a ±5% band (§2); a 25%
markdown is outside it. The interval is the mechanism — uncertainty in ε scales with
|log(1 − d)|, so deep depths on thin fits publish wide bands and lose the race — and a
markdown price under 90% of the lowest price ever observed on the SKU is flagged in
words.

**The stretch.** The mirror case: stockout likely, replenishment on its way. Demand
over the lead time is Poisson at the base rate; at p_0(1 + d) it is the same draw
thinned by (1 + d)^ε (a binomial of the base draw, one uniform per draw so every
step sits on the same numbers), so the two are compared whether the stock binds or
not. The rise is chosen as every price step is — the certainty equivalent of the
window's profit, min(D, on hand) × contribution at each price, inside the risk budget —
and drafted as an ordinary price step, with the change in P(stockout) reported beside
it. The first draft targeted the smallest rise that brought P(stockout) under 25%; the
simulation refused it, because on an elastic SKU the rise that stops the stockout
throws away more sales than the higher price recovers, and a stockout target alone
recommends losing money. The avoided stockout's own value is not priced (§10 #5), so
the decision stands on the measurable gain; when no rise inside the cap beats standing
still the answer is `no_stretch_pays`.

**Measurement.** A markdown is measured BEFORE landed cost: the counterfactual of §9
with unit cost zero and the factual as revenue less fees, because the promise is a
difference in cash proceeds and selling more units at a lower price raises COGS in the
window, so the net-of-COGS reading would book a markdown that won as a loss. Plus the
storage and surcharge the cleared stock no longer bills, read off the next
inventory-economics pass and capped at the promised carry. A stretch is measured as a
price step, which under-credits it when the stock binds after the rise — the
counterfactual volume at the old price exceeds what the stock allowed — in the
direction that costs us credit, not the client.

**What it cannot tell you.** Whether the markdown price holds the Buy Box; whether
Amazon's excess estimate is right; the curve far from the observed range.

### 5c. The purchase order as the supplier writes it

**What it computes** (`models/replenishment.py`), on the same simulated cycle demand
the newsvendor sized the order on (its quantile ladder rides on the row, so nothing
is re-simulated):

- **MOQ and case pack.** q rises to the minimum and to whole cases; the forced units
  cost their own overage, C_o × (E[max(0, q − D)] − E[max(0, q* − D)]), published so
  the client sees what the supplier's minimum costs per cycle.
- **The price break.** Taken when the unit saving on the larger order exceeds the
  extra expected overage plus the capital on the larger wire, with P(net > 0) from the
  draws; both wires shown.
- **The joint order.** A can-order policy per supplier: when any SKU hits its reorder
  point, every sibling due within one review period joins the wire; the wire events
  saved over the horizon against independent ordering are counted.
- **Air against sea.** On common random numbers (one uniform per draw scales both lead
  times), the stockout units avoided — E[max(0, D_sea − position)] − E[max(0, D_air −
  position)] — at margin plus the low-inventory fee, less the freight premium on the
  order; air recommended when the median is positive and 60% of draws agree. Drafted
  as `expedite_air`, explicit, with no dollar promise: the avoided stockout is the
  counterfactual §10 #5 calls unobservable.

**Where the terms come from.** Optional columns on the client's cost sheet: supplier,
MOQ, case pack, the break quantity and its unit cost, the air freight per unit and lead
time; sea is the existing inbound freight and lead time. A blank column is priced as
absent (`no_supplier_terms`, `no_freight_options`), never guessed.

**What it cannot tell you.** Container capacity, supplier lead-time variance beyond
the assumed 20%, and whether the break is still on offer.

---

## 6. Cash horizon

90 simulated days. In: the platform disburses accumulated (revenue − fees − ads)
every `payout_cycle_days` — 14 on Amazon, 1 on Shopify Payments, taken from
`channels.py`. Out: fixed costs accrue daily at monthly/30; supplier POs leave as
lump-sum wires on the schedule the inventory model implies. Demand uses the §5
generator with the §7 common factor, so the cone and the stockout numbers can
never disagree about what demand is.

Published: `p_ruin` with its Monte Carlo standard error, the daily P5/P50/P95 cone,
the Monte Carlo error of each percentile **at the trough day** — where the cone is
read and the decision is made — and the trough's **expected shortfall** beside its
5th percentile.

**Why expected shortfall.** A percentile is a threshold, not a risk measure: it
says nothing about whether the 1% case is a little worse or catastrophically
worse, and it is not sub-additive, so percentiles of parts do not bound the
percentile of the whole (Artzner, Delbaen, Eber & Heath 1999; Rockafellar &
Uryasev 2000). The mean of the worst twentieth of troughs is the number a runway
decision needs.

Measured effect of correlation, daily payouts: trough P5 $69,081 correlated
against $71,034 independent; expected shortfall $68,261 against $70,619. The tail
mean moves further than the percentile, which is why it is published. The median
barely moves — correlation reshapes the tail, not the centre.

**A structural fact worth knowing.** On a fortnightly payout cycle the trough of
the horizon is the day before the first payout, when outflow has accrued and
nothing has come in — and that day's balance is **deterministic**, so the
percentile and the tail mean of the trough coincide there. The dependence model
shows up later in the horizon instead, where the 5th percentile falls and the
median does not. `tests/test_dependence.py` pins both behaviours.

**What it cannot tell you.** Cash on hand and monthly fixed costs are
client-stated, not modelled. Fixed costs accrue daily; real due dates are lumpier.
"Ruin" means a simulated balance crossing zero — a bridge-capital line, never a
bankruptcy prophecy.

### 6b. Inventory under a cash budget

**What it computes** (`models/cash_orders.py`). The cone and the order-sizing model
did not talk to each other: the newsvendor recommended, the cone warned. With a
budget K the problem is

```
maximise  Σ_i E[profit_i(Q_i)]    subject to    Σ_i c_i·Q_i ≤ K
```

whose Lagrangian gives, per SKU, the critical fractile with the cash a unit ties up
priced at the shadow price λ:

```
F_i(Q_i) = (C_u,i − λ·c_i) / (C_u,i + C_o,i)
```

Q_i(λ) is read off the demand ladder the newsvendor stored (§5), the total wire is
non-increasing in λ, and a bisection meets the budget exactly. The order this induces
is by C_u,i / c_i — contribution at risk per inventory dollar, the GMROI ranking
derived rather than asserted. λ = 0 reproduces the unconstrained newsvendor.

**The budget** comes off the cone already computed, not a re-run: the first cycle's
wires plus the 5th-percentile trough's overdraft, with the expected-shortfall variant
beside it. The wires precede the trough — that is the approximation, and it is on the
payload.

**Published.** λ, the funded order per SKU with its service level and residual
stockout probability, the deferred dollars and the bridge capital that would fund the
whole set. The directive `budget_order_set` replaces the individual reorders for the
SKUs it covers, is explicit, and promises nothing: the avoided stockout is §10 #5.
`no_cash_inputs` and `fully_funded` leave the reorders as they were.

### 6c. The ruin cost of a decision

**What it computes.** Sequence-of-returns risk is the order outcomes arrive in: a wire
that is fine on average can cross the buffer early, before the good months land. The
cone already holds the answer in its paths. A wire of W on day d lowers every path by W
from d on, so a path is ruined afterwards when its minimum before d is under the floor,
or its minimum from d on is under floor + W. `cashflow.ruin_ladder` keeps, per day,
P(pre-minimum under the floor) and the quantiles of the post-minimum among the paths
still above it; `cashflow.ruin_delta` reads P(ruin | W on day d) off that for any W, with
a Monte Carlo error, no second simulation. An inflow is a negative W.

**Where it lands.** Every directive that moves cash carries `evidence.ruin_delta` —
the reorder wire, the cash-constrained order set, the air-freight premium, the
liquidation inflow — and one that pushes the ninety-day ruin probability past the 5%
line where it sat under it is routed to an explicit yes with the two probabilities in
the reason. Without a cone nothing is attached and nothing is invented.

**Measured.** On a simulated account the ladder's P(ruin | $2,000 on day 20) matches a
second simulation with the wire added within its Monte Carlo error; a zero wire leaves
it unchanged; a wire past every path's minimum makes it one.

### 6d. What would break you

**What it computes** (`models/stress.py`). Platform and concentration risk are the
questions the cone does not ask. Each is a change to one component of the cone's
arithmetic, and the cone keeps its components during a run, so every scenario is the
same paths recomputed with no new draws: the platform fee up 3 points of revenue; the
largest SKU by revenue earning nothing for thirty days; every click 30% dearer; the
largest SKUs' inbound thirty days late, each earning nothing from the day its cover
runs out; every payout held thirty days. Each reports p(ruin) with its Monte Carlo
error, the trough's 5th percentile and expected shortfall, and the ninety-day net
change against the base, ranked by the change in p(ruin). The base scenario must
reproduce the published cone exactly, and the payload says whether it did.

**What it cannot tell you.** How likely any scenario is — these are stresses, not
forecasts — and any second-order response.

---

## 7. Demand dependence

```
r_i = mu_i·exp(sigma_i·(rho·Z_common + sqrt(1−rho^2)·Z_i) − sigma_i^2/2)
corr(ln r_i, ln r_j) = rho^2
```

**Estimating rho.** From the cross-sectional mean of standardised log-demand
residuals rather than from N² pairs: for standardised residuals
`Var_t(mean_i x_it) = (1 + (N−1)·rho_bar)/N`, which inverts to a stable estimator
of the average pairwise correlation. Recovery tested at rho_bar = 0.0, 0.15, 0.4
and 0.7.

**Shrinkage.** rho_bar is shrunk toward `DEFAULT_PAIRWISE_CORR = 0.25` with weight
`T/(T+4)`. A four-period panel cannot measure a correlation, and the cost of
underestimating it falls entirely on the client, so the default is a meaningfully
positive number rather than zero. Retail panels commonly sit between 0.2 and 0.5
pairwise; 0.25 is the middle of that. The payload names the basis, the raw
estimate, the weight and the number of shared periods.

**What it cannot tell you.** One factor is one factor. A catalog with two
genuinely distinct demand regimes — a seasonal line and an evergreen line — is
described by a single average correlation, which overstates the dependence within
the evergreen group and understates it within the seasonal one. A second factor
would need a category taxonomy the engine does not have.

---

## 8. Change detection, and the multiplicity behind it

Four detectors, each a pure function over one series: `robust_z` (is the latest
point an outlier), `cusum` (did the level shift, and when), `changepoint` (a single
mean shift by likelihood-ratio scan), and `weekly_decompose + spikes` (for daily
spend, with a leave-one-out remainder so a median does not absorb the point it is
judging). Each returns `insufficient_data` rather than raising.

**The multiplicity.** A threshold on one series is a statement about one series.
This module runs four detectors over every SKU's four fee lines, every ASIN's three
traffic metrics, every campaign's daily spend and every settlement bucket —
thousands of tests a sweep. Measured on a panel of 500 pure-noise SKUs:

```
4,000 tests · the detectors alone flag 548 · 0 survive the control
```

391 of the 548 come from the changepoint scan, whose BIC penalty of 2·log(n) is
4.6 at n = 10 while the simulated null's 95th percentile of the same statistic is
8.33 — so the penalty sits near the 75th percentile and the detector fires on a
quarter of all noise series. 150 noise ASINs: 900 tests, 117 detector flags, 0
survivors.

**The procedure.** Every test carries a p-value against a simulated null
(`models/null_calibration.py`), Benjamini–Hochberg runs across the whole sweep's
test family, and `flagged` means the detector crossed its threshold **and** the
q-value cleared `FDR_Q = 0.05`. A demoted row loses its direction, delta and dollar
figure and its basis says so in words. `detector_flagged` keeps the detector's own
verdict on the record, and every row carries `p_value`, `q_value`, `n_tests` and
the effective threshold.

**Why simulated nulls.** Three of the four statistics have no closed form at n = 6
to 120 — a CUSUM path maximum, a likelihood-ratio scan maximised over split
points, a maximum of robust z scores. Every statistic is invariant to the series'
location and scale under an i.i.d. Gaussian null, which is what makes caching the
null by series length correct rather than merely convenient. Uniformity of the
resulting p-values is tested for all four.

**The tail extrapolation.** A counted Monte Carlo p-value cannot go below
1/(R+1) = 2.5e-4, and BH on a 3,000-test sweep needs 1.7e-5 at the first rank — so
without a tail the strongest finding on a large catalog could never clear the first
threshold and the procedure would reject nothing, ever. Above the 99th percentile
of the null the p-value is extrapolated from an exponential fit to the excesses
(peaks-over-threshold with the shape held at zero, the conservative choice for a
tail we have no reason to believe is heavier). `p_basis` says which of the two
produced each number.

### Ad cost drift, and the regime break

Since 2026-09-23 the campaign scan also covers the cost of a click (spend ÷ clicks)
and what a click brings back (sales ÷ clicks), day by day, through the same CUSUM and
changepoint detectors and the same false-discovery control. Spend can sit still while
the auction moves under it; these two series are where non-stationarity in the ad
account shows first. A shift is valued at the campaign's own clicks over thirty days
and drafted as `cpc_drift` or `conversion_drift`, worth no dollars in itself.

A flagged shift is also a REGIME BREAK for §4: a response curve fitted across it is two
curves averaged. `ad_efficiency.run(breaks=)` drops the points before the break and
refits on the new regime; with fewer than five points since, the campaign is
`regime_break` — no break-even, no trim, held out of the reallocation — until enough
days have run. The anomaly scan therefore runs before the ad fit.

### 8b. Garbage in: does the data agree with itself

Before any model (`models/data_quality.py`): per period, pairs of exports that
measure the same thing two ways — SKU Economics sales against the settlement file's
orders and against the Business Report, units sold against inventory-ledger
shipments, daily campaign spend against search-term spend — with the relative gap
flagged above 5%; per report, the calendar months missing inside its own span and the
days since its latest period, stale past 45. Nothing is corrected: the flags ride on
the payloads that read a flagged source, the health score's signal sub-score subtracts
for disagreement and gaps as it does for an unforecastable catalogue, and the memo
names the largest disagreement so the client can fix the upload. A missing month is
reported as missing, never as zero. It cannot say which of two disagreeing exports is
right.

### What the change detection cannot tell you

- **The null assumes independent Gaussian noise with no trend and no
  seasonality.** A fee series with a slow drift, or a traffic series with a
  seasonal shape the weekly decomposition did not remove, produces p-values that
  are too small: the detector is reacting to real structure that is not the step
  change it was looking for. The daily spend path removes a weekday pattern; the
  monthly paths remove nothing.
- **BH controls the FDR under independence and positive regression dependence.**
  Two detectors on the same series are strongly positively dependent, which is the
  benign case. An adversarial dependence structure would need Benjamini–Yekutieli
  and a log(m) penalty. This is a choice, not an oversight.
- **The spikes null is calibrated on i.i.d. normal points**, not on the
  leave-one-out remainder of a weekly decomposition, whose neighbouring values are
  correlated through overlapping windows. The remainder's MAD/sd is about 1.0
  against i.i.d. noise (validated in simulation), which is why the approximation
  is acceptable, but it is an approximation.
- **A detected shift is not a cause.** "Fees rose in May" is a measurement;
  "because the listing was re-measured" is a hypothesis the directive states as
  one.

---

## 9. Measurement, and what gets banked

The measurement pass values a directive against the client's own later exports.
For a price step:

```
factual        = revenue − fees − COGS in the measured window (observed)
counterfactual = q_after·(P0/P1)^e · (P0(1−f) − c − F)
```

Anchoring on the **after** period's own units is the point: whatever demand shock,
season or competitor hit that period hit both arms identically, so it cancels.
Rolling forward from a stale baseline would credit us with the weather.

**What gets banked is a quantile, not an endpoint.** The rule used to be "the least
favourable reading of our own fit" — the worse of the elasticity interval's two
endpoints. Defensible while that interval was a narrow ±1.96·classical SE; it
stopped being defensible the moment the interval became an HC3 Student-t interval
on a shrunk estimate. The replay harness measured it: on 24 simulated price cuts
whose true elasticity was −2.4, **every one of which made money**, the endpoint
rule booked eighteen as losses, because the upper end of a wide interval sits near
−1 where the counterfactual claims the seller would have sold almost as much at
the old higher price. Taking an extreme of a wide interval is not conservatism, it
is a wrong answer. The posterior is now integrated and the banked figure is its
`MEASURE_QUANTILE` = 25th percentile — the same risk quantile the step was sized
against.

**And capped at what actually happened.** The model counterfactual is reproducible
and blind to the case where the volume response simply did not occur; with a price
cut and no response it still said "you would have sold 12% less at the old price".
The claim is now capped at the per-period change in the SKU's own profit. The raw
before/after change is **not** a measurement — it carries the season and the
weather, which is why it is not what gets banked — but as a ceiling it can only
ever reduce a claim. After the cap, as the volume response falls from 1.5× forecast
to zero, the realisation ratio falls 0.69, 0.58, −0.60, −2.23, monotonically, and
a cut with no response is booked as the loss it was.

**Corrected 2026-09-24: the ceiling was booking the weather.** Written as it
was, the cap *replaced* a positive reading with the observed change whenever
the reading exceeded it — including when the observed change was negative.
The model-risk harness (MATH_SCORECARD.md, iteration 37) put a catalogue
with a 20% month-to-month demand sd through it: a step whose anchored
counterfactual read +$350, and whose true effect was +$350, was banked at
−$293 because the SKU's August shock reverted in September. Over three
worlds the Record's realisation ratio read −0.4 to −1.1 against a true 0.4
to 0.7 — a correct engine reported as losing money, and `replay.score`
would have called it OVER-PROMISING. The rationale two paragraphs up says
the raw change is not a measurement; a number that is not a measurement
cannot be banked as a loss. Two changes:

1. *The no-response case is caught where it can be seen: in the batch.* One
   month of one SKU cannot distinguish "the volume did not respond" from "a
   bad month" — at a 20% sd a 5% step's expected 12% volume move is inside
   the noise — but two dozen steps can. Before any step is measured, the
   realised volume change of every price step and markdown in the batch is
   regressed through the origin on the change its own fit predicted,
   `r_i = κ·ε̂_i·ln(p1/p0) + noise`, weighted by each SKU's residual sd
   (`measurement.volume_realisation`). Every counterfactual then runs on
   ε̂_i·κ with κ drawn from its estimate and its residual-based standard
   error — and only when κ sits `REALISATION_T` = 2 of those errors from 1.
   A cut that produced no response anywhere gives κ = 0 and the reading
   itself becomes the margin given away — the loss it was; a catalogue
   whose volume moved as the fits said gives κ = 1 ± 0.2, within noise of
   1, and every reading stands on its own fit. Applied unconditionally, the
   pooled ±0.2 folded into every draw on top of the SKU's own posterior
   halved what a correct engine banked on the harness, which is why the
   gate. Under `MIN_STEPS_FOR_REALISATION` = 6 steps κ is not estimated.
2. *The ceiling allows the SKU its own noise, and never manufactures a
   loss.* A positive reading is capped at the observed rise plus
   `OBSERVED_CAP_NOISE_Z` = 1 month-to-month standard deviation of the
   SKU's own profit (√2 × the fit's residual sd × the window's profit), and
   held at zero when the profit fell by more than that — a Buy Box loss
   still stops a claim. A negative reading, the model's own, stands.
   Setting the constant to 0 restores the strict ceiling with a zero floor.

The four-world ladder above still runs 1.5×, 1.0×, 0.5×, 0 in that order and
still ends below zero (`tests/test_replay.py`); on the harness the
realisation ratio moved from −0.7/−0.4/−1.1 to the figures in iteration 37.

**A row's fee split, rebuilt when the totals are missing (2026-09-24).** The
counterfactual charges the proportional fee at the old price and the fixed
fee per unit, read from the margin row's `fee_split`. A row that carried the
split's *rate* and *per-unit fee* without its dollar totals was read as
fee-free, and the counterfactual at the old price charged no referral fee at
all — a four-figure loss on every step. `measurement._split_fees` now rebuilds
the totals from the row's own revenue and units, capped at the fees the row
actually paid.

Three further gates, all pre-existing: execution (a step not actually made in the
account is `stalled`, not measured), materiality (under $25 the directive closes
rather than banking noise), and the promise cap (never bank more than was
promised).

**Therefore a correct engine books LESS than it promised.** Between the 25th
percentile and the actual-profit cap, a forecast that is exactly right realises
around 0.6 of its promise on a noise-free after period, and less under
month-to-month noise (iteration 37 gives the figure on a 20% sd). `replay.py`
states the target band as 0.30–1.30 rather than 1.00, and labels anything
below it OVER-PROMISING.

---

### 9b. Model decay: the promises by cohort, and the parameters run to run

A model tuned last quarter quietly decays, and two things say so. The promises: the
replay harness pooled every measured directive into one realisation ratio until
2026-09-23, and a ratio calibrated on last year's directives would still read fine
while this quarter's failed. `replay.score` now also scores by 90-day cohort of the
measurement date — ratio and band coverage per cohort, a seeded bootstrap band on each
ratio, a Mann–Kendall trend across cohorts with at least four scored — and flags
`decaying` when the latest cohort sits below the floor the pooled figure clears. The
parameters: `models/drift.py` compares every elasticity and every ad curve's marginal
return with the previous run's on the same item, z = (θ_new − θ_old) / √(se_new² +
se_old²), Benjamini–Hochberg across the sweep so four hundred SKUs do not produce
twenty drifted fits by chance each fortnight; a drifted fit carries `details.drift`
and the price step halves its risk tolerance for the cycle. The two fits share most
of their data, so z overstates their independence — the conservative direction for a
flag that only shortens a step; stated, not corrected.

### 9c. The first thirty days, the headline's band, and the book

**The first sweep** (`issue.FIRST_WIN_WEIGHT`). Before anything has been measured, a
client has seen nothing come true, and the thirty days where churn is highest are the
days one measured dollar buys months of patience. The first issue therefore ranks
drafts by expected dollars times how soon the kind can bank — measured from a
fortnight of daily spend 1.0, from the next monthly export 0.5, on Amazon's clock 0.4,
per absent month 0.3, never 0 — and later sweeps rank by dollars as before. Every kind
the engine drafts has a weight, and a kind without one fails a test. `speed.summary`
reports the median days from the first issue to the first banked dollar, which is the
number this ranking exists to shorten.

**The headline's band** (`value.compute`). The proven figure was a point. A measured
price step, markdown or reallocation carries the distribution it was banked from, so
the headline now carries the sum of those 5th and 95th percentiles with every other
dollar at its point, and the record line and the memo print the range when at least
half the proven dollars have one. The basis says what share did.

**The book** (`models/benchmark.py`). A client's TACoS, net margin, stockout share, fee
bleed share and realisation ratio as percentiles among the other consenting clients'
latest runs — the calibration consent of terms §10, and nothing else — each with a band
from resampling the book and the book's median beside it. Under ten consenting clients
the whole comparison refuses and says how many short, because a percentile among four
is a coin flip with a decimal point. No other client's number leaves the module.

## 10. What this engine cannot tell you — the short list

If you read one section, read this one.

1. **Whether a price change caused what followed — until a randomised test has
   run on the SKU.** The elasticity is fitted from prices the seller chose, in
   response to demand. The bias is measured (§2), it runs toward "raise the
   price", and on an observational fit it ~~is not corrected~~ is corrected
   (since 2026-09-24) only for the one mechanism the export can see: a seller
   who reprices off last period's demand of the same SKU. That correction is
   a model of the seller, applied once per catalogue when the seller's
   reaction is measurable, and a seller who reacts to something else is not
   corrected. The engine's own steps are NOT an instrument for it — see §2,
   corrected 2026-09-12 — because the step is chosen by the fit and because a
   fortnight-long step is invisible to a monthly estimator. Since 2026-09-23
   the randomised six-block test (`models/price_experiment.py`) IS one, for
   the SKUs that have run it; every other SKU's fit carries whatever bias the
   correction did not reach, and the report says which is which.
2. **A price optimum, for most SKUs, on a first upload.** With seven periods and
   20% demand noise, the elasticity cannot be separated from −1 for roughly five
   SKUs in six, and the engine declines to name a destination for them. It still
   gives a direction and a step. See the closing section of `MATH_SCORECARD.md`
   for the table of how much data it takes.
3. **Cross-price effects outside a variant family.** Inside one — a parent ASIN or
   a product handle — the family's cross-elasticity is estimated (§3b) and every
   step is valued on the family; a cut the family absorbs is refused and named.
   Between families, and against competitors, a cut that cannibalises is still
   booked as a win on one listing and an unexplained loss on another.
4. **Competitor behaviour.** No competitor price, assortment or stock signal
   reaches the engine. The Buy Box share series is the only shadow of it.
5. **The value of an avoided stockout.** Unobservable counterfactual; no dollars
   are promised for a reorder.
6. **Whether allocated ad spend drove the SKU it was allocated to.**
   Revenue-share allocation is accounting, not attribution.
7. **Why a detected shift happened.** Detection is a measurement; causes are
   hypotheses, stated as hypotheses.
8. **Anything about a seller's cash that they did not state.** Cash on hand and
   fixed costs are inputs, not findings.
9. **Whether the curve forms are right.** Constant-elasticity demand, Hill ad
   response, lognormal demand rates, one demand factor, a multiplicative seasonal
   index by calendar month. Every interval in this engine is conditional on its
   form, and no resampling tests a form.

### The single most dangerous assumption

Of those, the one that costs a client the most if wrong is **#1**, and not because
the bias is large — it is about 0.4 of an elasticity. It is because the bias has a
direction, and that direction is the one that argues for raising prices. An engine
that systematically nudges a seller's prices up, on evidence that systematically
understates how much volume they will lose, would take months of exports to catch
and would look like ordinary seasonality while it happened.

Four things stand between that and a client: the pole guard refuses the
worst-biased SKUs a destination; the step is small when the fit is uncertain; Buy
Box share is watched while every step is live and the step is reversed if it
drops; and the Profit Record books the 25th percentile of the measured outcome,
capped at what the SKU's profit actually did, so a move that did not work cannot
be banked as one that did.

**The data that would retire it**, and what stands in the way. A price change made
for a reason unrelated to demand is the only instrument this problem admits, and
the engine does not currently make one: its steps are chosen by the fit, and a
fortnight-long step blends away below the estimator's own price-variation floor.
Two things would have to change — a deliberately randomised component of the step
whose draw is independent of the data, and a price series fine enough to see a
14-day move. Both are cheap; as of 2026-09-23 both are built (§2, corrected); and
the claim that the engine already compounded its own identification through its
ordinary steps was wrong and has been withdrawn from this document, from
MATH_SCORECARD.md and from the client report. The correction is per SKU and only
after a test has run: nothing here retires the bias on a fit that has not.

There is a second route that needs no experiment on anyone's prices, because the
seller's own repricing habit is itself measurable from their export: if the
strength with which they react to last month's demand can be estimated, the bias
it induces becomes a nuisance parameter to subtract rather than an assumption to
disclose. Whether that works is under measurement, not yet claimed.
