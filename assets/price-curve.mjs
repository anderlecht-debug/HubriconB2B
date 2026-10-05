// The Price Curve's arithmetic in the browser: the engine's per-SKU elasticity fit and its
// pricing rules, ported line for line so a reader can run the course on their own numbers
// with nothing uploaded. Pinned to the engine itself: scripts/learn/price_curve.py runs
// models/elasticity.py `_fit` and models/pricing_engine.py on golden cases and writes
// scripts/learn/price-curve.golden.json; scripts/learn/price-curve-tool.test.mjs holds this
// file to every one of them. Pure functions, no DOM.

export const MIN_PERIODS = 5;            // elasticity.MIN_PERIODS
export const MIN_PRICE_CV = 0.02;        // elasticity.MIN_PRICE_CV
export const STEP_CAP = 0.05;            // pricing_engine.STEP_CAP: the most one step moves
export const POLE_GUARD_SIGMAS = 2.0;    // pricing_engine.POLE_GUARD_SIGMAS
export const POLE_OPTIMUM_LOG_SD = 0.5;  // pricing_engine.POLE_OPTIMUM_LOG_SD
const MIN_LEVERAGE_SLACK = 1e-6;         // elasticity.MIN_LEVERAGE_SLACK
export const EDGES = [10, 50];           // Amazon's price-band edges: the fulfilment fee changes there

// Student's t, two-sided 95%, by degrees of freedom: scipy.stats.t.ppf(0.975, dof), to six places.
// Written by scripts/learn/price_curve.py beside the golden cases; the test checks they agree.
export const T975 = [null, 12.706205, 4.302653, 3.182446, 2.776445, 2.570582, 2.446912, 2.364624, 2.306004, 2.262157,
  2.228139, 2.200985, 2.178813, 2.160369, 2.144787, 2.13145, 2.119905, 2.109816, 2.100922, 2.093024,
  2.085963, 2.079614, 2.073873, 2.068658, 2.063899, 2.059539, 2.055529, 2.051831, 2.048407, 2.04523,
  2.042272, 2.039513, 2.036933, 2.034515, 2.032245, 2.030108, 2.028094, 2.026192, 2.024394, 2.022691,
  2.021075, 2.019541, 2.018082, 2.016692, 2.015368, 2.014103, 2.012896, 2.011741, 2.010635, 2.009575,
  2.008559, 2.007584, 2.006647, 2.005746, 2.004879, 2.004045, 2.003241, 2.002465, 2.001717, 2.000995,
  2.000298];
export const tCritical = (dof) => (dof >= 1 && dof < T975.length ? T975[dof] : null);

/**
 * models/elasticity.py `_fit`, without the sessions control: log(units a day) on log(price) by
 * least squares, HC3 standard error (classical where a period's leverage leaves no slack), the
 * Student-t interval. points: [{price, units, days?}]. A period with no price or no units is
 * not used. Returns a status before any number when the history cannot be read.
 */
export function fit(points) {
  const used = points.filter((p) => p && p.price > 0 && p.units > 0);
  const n = used.length;
  const base = { n, used };
  if (n < MIN_PERIODS) return { ...base, status: "insufficient_data" };
  const prices = used.map((p) => Number(p.price));
  const meanP = prices.reduce((a, b) => a + b, 0) / n;
  const cv = Math.sqrt(prices.reduce((a, p) => a + (p - meanP) ** 2, 0) / n) / meanP;
  if (cv < MIN_PRICE_CV) return { ...base, priceCv: cv, status: "insufficient_price_variation" };
  const x = prices.map(Math.log);
  const y = used.map((p) => Math.log(Number(p.units) / Math.max(1e-9, Number(p.days) || 1)));
  const xbar = x.reduce((a, b) => a + b, 0) / n, ybar = y.reduce((a, b) => a + b, 0) / n;
  const dx = x.map((v) => v - xbar), dy = y.map((v) => v - ybar);
  const sxx = dx.reduce((a, v) => a + v * v, 0);
  const sxy = dx.reduce((a, v, i) => a + v * dy[i], 0);
  const slope = sxy / sxx, intercept = ybar - slope * xbar;
  const resid = dy.map((v, i) => v - slope * dx[i]);
  const ssr = resid.reduce((a, v) => a + v * v, 0), sst = dy.reduce((a, v) => a + v * v, 0);
  const dof = n - 2;
  const lev = dx.map((v) => 1 / n + (v * v) / sxx);
  let se, estimator;
  if (Math.min(...lev.map((h) => 1 - h)) <= MIN_LEVERAGE_SLACK) {
    se = Math.sqrt(ssr / dof / sxx); estimator = "classical_hc3_degenerate";
  } else {
    se = Math.sqrt(dx.reduce((a, v, i) => a + (v * v * resid[i] ** 2) / (1 - lev[i]) ** 2, 0) / sxx ** 2); estimator = "HC3";
  }
  const t = tCritical(dof);
  return {
    ...base, status: "ok", priceCv: cv, elasticity: slope, intercept, stdErr: se, seEstimator: estimator,
    stdErrClassical: Math.sqrt(ssr / dof / sxx), dof, t, ci: [slope - t * se, slope + t * se],
    rSquared: sst > 0 ? 1 - ssr / sst : 0, residuals: resid,
  };
}

/** pricing_engine.near_unit_elastic for a fitted row: too close to −1 to name a destination. */
export function nearUnitElastic(eps, se, ci) {
  if (ci && ci[0] != null && ci[1] != null) {
    const [lo, hi] = [Math.min(...ci), Math.max(...ci)];
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return true;
    if (lo <= -1 && -1 <= hi) return true;
  }
  if (se != null && se > 0) {
    if (!Number.isFinite(se)) return true;
    if (Math.abs(1 + eps) < POLE_GUARD_SIGMAS * se) return true;
    return eps < -1 ? se / Math.abs(eps * (1 + eps)) > POLE_OPTIMUM_LOG_SD : false;
  }
  return true;
}

/** pricing_engine.optimal_price: P* = [(c + F) / (1 − f)] · ε/(1 + ε), or null where none exists. */
export function bestPrice(eps, unitCost, feeRate, fixedFee = 0) {
  if (eps >= -1 || !(feeRate >= 0 && feeRate < 1)) return null;
  const cost = unitCost + fixedFee;
  if (cost <= 0) return null;
  return (cost / (1 - feeRate)) * (eps / (1 + eps));
}

/** pricing_engine.profit and profit_delta: a period's profit at price p, and its change from p0. */
export const profit = (eps, p0, q0, unitCost, feeRate, p, fixedFee = 0) => q0 * (p / p0) ** eps * (p * (1 - feeRate) - unitCost - fixedFee);
export const profitDelta = (eps, p0, q0, unitCost, feeRate, p, fixedFee = 0) =>
  profit(eps, p0, q0, unitCost, feeRate, p, fixedFee) - profit(eps, p0, q0, unitCost, feeRate, p0, fixedFee);

/** The course's rule: toward the best price; up where there is none to walk to (inelastic, or near −1). */
export function direction(eps, p0, best, guard) {
  if (best != null) return best > p0 ? "up" : best < p0 ? "down" : "hold";
  return eps >= -1 || guard ? "up" : "hold";
}

/** One step toward the best price, never more than STEP_CAP, to the cent. */
export function stepPrice(p0, best, way) {
  // To the cent on the exact stored value, as Python's round() does: $52.815 is stored just under it.
  const cents = (v) => Number(v.toFixed(2));
  if (way === "up") return cents(p0 * (1 + Math.min(STEP_CAP, best != null ? best / p0 - 1 : STEP_CAP)));
  if (way === "down") return cents(p0 * (1 - Math.min(STEP_CAP, 1 - best / p0)));
  return cents(p0);
}

/** Does a move between two prices cross $10 or $50, where Amazon's fulfilment fee changes? */
export function crossesEdge(a, b) {
  const lo = Math.min(a, b), hi = Math.max(a, b);
  return (lo < EDGES[0] && EDGES[0] <= hi) || (lo <= EDGES[1] && EDGES[1] < hi);
}

/** Break-even: how far units can fall (negative) or must rise (positive) at price p for profit to stand still. */
export function breakEven(p0, p, unitCost, feeRate, fixedFee = 0) {
  const m0 = p0 * (1 - feeRate) - unitCost - fixedFee, m = p * (1 - feeRate) - unitCost - fixedFee;
  return m > 0 ? m0 / m - 1 : null;
}

/**
 * Everything the course reads off one SKU: the fit, the guard, the best price, the next step and
 * what it is worth, the break-even on a raise and on a discount. econ: {price, units (a month),
 * cost, referral, fixed, discount}.
 */
export function read(points, econ) {
  const f = fit(points);
  if (f.status !== "ok") return { fit: f };
  const guard = nearUnitElastic(f.elasticity, f.stdErr, f.ci);
  const { price: p0, units: q0, cost, referral, fixed = 0, discount = 0.2 } = econ;
  const ready = p0 > 0 && q0 > 0 && cost >= 0 && referral >= 0 && referral < 1;
  if (!ready) return { fit: f, guard };
  const best = guard ? null : bestPrice(f.elasticity, cost, referral, fixed);
  const way = direction(f.elasticity, p0, best, guard);
  const next = stepPrice(p0, best, way);
  const pd = p0 * (1 - discount);
  return {
    fit: f, guard, best, way, next,
    margin: p0 * (1 - referral) - cost - fixed,
    profitNow: profit(f.elasticity, p0, q0, cost, referral, p0, fixed),
    nextDelta: profitDelta(f.elasticity, p0, q0, cost, referral, next, fixed),
    bestDelta: best != null ? profitDelta(f.elasticity, p0, q0, cost, referral, best, fixed) : null,
    raise: { breakEven: breakEven(p0, p0 * 1.05, cost, referral, fixed), implied: 1.05 ** f.elasticity - 1,
      delta: profitDelta(f.elasticity, p0, q0, cost, referral, p0 * 1.05, fixed) },
    discount: { rate: discount, price: pd, needed: breakEven(p0, pd, cost, referral, fixed), implied: (1 - discount) ** f.elasticity - 1,
      delta: profitDelta(f.elasticity, p0, q0, cost, referral, pd, fixed) },
    edge: crossesEdge(p0, best ?? next),
  };
}
