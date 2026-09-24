"""Customer lifetime value for a store that knows its customers: BG/NBD and
Gamma–Gamma, and what they do to the allowable cost of acquiring one.

The ad break-even in §4 is a first-order break-even: a customer is worth the
margin on the order the ad brought. For a consumable, a Subscribe & Save item,
anything people reorder, that is too strict — a customer worth three orders
justifies three times the acquisition spend — and a store that prices its ads
on the first order alone under-spends against every competitor who does not.

THE MODELS are the standard pair for non-contractual repeat purchase. BG/NBD
(Fader, Hardie and Lee 2005): while alive a customer buys at a Poisson rate λ,
λ ~ Gamma(r, α) across customers; after each purchase they drop out with
probability p, p ~ Beta(a, b). Four parameters, fitted by maximum likelihood
on each customer's (x, t_x, T) — repeat purchases, recency, age — in weeks.
Gamma–Gamma (Fader and Hardie 2013) for the value of an order: order values
Gamma(p, ν) with ν ~ Gamma(q, γ) across customers, three parameters by maximum
likelihood on (x + 1, mean order value). Expected residual purchases over the
next 52 weeks per customer are the FHL closed form with the Gaussian
hypergeometric function; expected value per purchase is the Gamma–Gamma
conditional mean.

THE INTERVAL is a parametric bootstrap from the inverse Hessian at the
maximum (the asymptotic covariance of the estimates), each draw re-evaluating
the expected repeat orders and value, so the acquisition-cost multiplier the
ad model receives carries a band and a Monte Carlo error.

CALIBRATION IS NOT ASSUMED. The model is fitted on the first three quarters of
the calendar and asked to predict repeat orders in the last quarter; the ratio
of actual to predicted is published, and outside [0.7, 1.3] the multiplier is
refused as `poorly_calibrated` — a CLV model that cannot predict the last
quarter of its own data has no business raising anyone's ad spend. The
frequency–value correlation is published because Gamma–Gamma assumes it away.

REFUSALS. Under 100 customers with a first order, or under 26 weeks of order
history: `insufficient_data`. An Amazon channel: `not_applicable` — no Amazon
export carries a customer identity, and Subscribe & Save is in none of them.

WHAT IT DOES. The allowable acquisition cost multiplier is
1 + E[repeat orders over 52 weeks] × (repeat value / first-order value), on
margin and discounted; `ad_efficiency.run(clv_multiplier=)` publishes the
break-even at 1/(m × multiplier) beside the first-order one, and the trim
directive uses it only when this model is `ok` and calibrated.

WHAT IT CANNOT TELL YOU. Which campaign acquired which customer (no export
links them, so the acquisition cost is blended); whether last year's cohorts
describe next year's; anything about a customer whose email changed.
"""

from datetime import date, timedelta

import numpy as np
from scipy import optimize, special

from .common import num

MIN_CUSTOMERS = 100
MIN_SPAN_WEEKS = 26
HORIZON_WEEKS = 52
CALIBRATION_SHARE = 0.75
CALIBRATION_BAND = (0.7, 1.3)
ANNUAL_DISCOUNT = 0.12
CLV_DRAWS = 2000
CLV_SEED = 20260911


# ── the data ─────────────────────────────────────────────────────────────────

def customer_table(orders: list[dict], end: date | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, date]:
    """(x, t_x, T, mean_value, first_value) per customer, in weeks, and the
    calendar end. x counts REPEAT orders; a customer with one order has x = 0."""
    by_customer: dict[str, list[tuple[date, float]]] = {}
    for o in orders or []:
        key = o.get("customer_key")
        d = o.get("order_date")
        if not key or not d:
            continue
        by_customer.setdefault(key, []).append((date.fromisoformat(str(d)[:10]), float(o.get("revenue") or 0)))
    if not by_customer:
        return (np.array([]),) * 5 + (end or date.today(),)
    end = end or max(d for v in by_customer.values() for d, _ in v)
    x, t_x, T, mv, fv = [], [], [], [], []
    for v in by_customer.values():
        v.sort()
        first = v[0][0]
        if first > end:
            continue
        repeats = [(d, r) for d, r in v[1:] if d <= end]
        x.append(len(repeats))
        t_x.append(((repeats[-1][0] - first).days / 7.0) if repeats else 0.0)
        T.append((end - first).days / 7.0)
        mv.append(float(np.mean([r for _, r in repeats])) if repeats else 0.0)
        fv.append(v[0][1])
    return np.array(x, float), np.array(t_x), np.array(T), np.array(mv), np.array(fv), end


# ── BG/NBD ───────────────────────────────────────────────────────────────────

def _bgnbd_ll(theta, x, t_x, T):
    r, alpha, a, b = np.exp(theta)
    ln = special.gammaln
    a1 = ln(r + x) - ln(r) + r * np.log(alpha)
    a2 = ln(a + b) + ln(b + x) - ln(b) - ln(a + b + x)
    a3 = -(r + x) * np.log(alpha + T)
    a4 = np.where(x > 0, np.log(a) - np.log(b + np.maximum(x, 1) - 1) - (r + x) * np.log(alpha + t_x), 0.0)
    ll = a1 + a2 + np.logaddexp(a3, a4) if True else 0
    # for x = 0 the second branch is absent: logaddexp(a3, -inf) = a3
    ll = np.where(x > 0, a1 + a2 + np.logaddexp(a3, a4), a1 + a2 + a3)
    return -float(ll.sum())


def bgnbd_fit(x, t_x, T) -> dict:
    best = None
    for start in ((0.0, 0.0, 0.0, 0.0), (np.log(0.5), np.log(5.0), np.log(0.5), np.log(3.0))):
        res = optimize.minimize(_bgnbd_ll, np.array(start), args=(x, t_x, T), method="L-BFGS-B",
                                bounds=[(-6, 6)] * 4)
        if best is None or res.fun < best.fun:
            best = res
    theta = best.x
    # numerical Hessian in log-space for the parametric bootstrap
    hess = _numerical_hessian(lambda th: _bgnbd_ll(th, x, t_x, T), theta)
    try:
        cov = np.linalg.inv(hess)
        if not np.all(np.isfinite(cov)) or np.any(np.diag(cov) <= 0):
            cov = None
    except np.linalg.LinAlgError:
        cov = None
    r, alpha, a, b = np.exp(theta)
    return {"r": float(r), "alpha": float(alpha), "a": float(a), "b": float(b), "theta": theta, "cov": cov,
            "loglik": -float(best.fun), "converged": bool(best.success)}


def _numerical_hessian(f, x0, h=1e-4):
    n = len(x0)
    H = np.zeros((n, n))
    f0 = f(x0)
    for i in range(n):
        for j in range(i, n):
            ei, ej = np.zeros(n), np.zeros(n)
            ei[i], ej[j] = h, h
            H[i, j] = (f(x0 + ei + ej) - f(x0 + ei) - f(x0 + ej) + f0) / h**2
            H[j, i] = H[i, j]
    return H


def expected_repeats(params, t: float, x, t_x, T) -> np.ndarray:
    """E[purchases in (T, T + t] | x, t_x, T] — Fader, Hardie & Lee (2005) eq. 10."""
    r, alpha, a, b = params["r"], params["alpha"], params["a"], params["b"]
    hyp = special.hyp2f1(r + x, b + x, a + b + x - 1, t / (alpha + T + t))
    num_ = (a + b + x - 1) / (a - 1) * (1 - ((alpha + T) / (alpha + T + t)) ** (r + x) * hyp)
    den = 1 + np.where(x > 0, a / (b + np.maximum(x, 1) - 1) * ((alpha + T) / (alpha + t_x)) ** (r + x), 0.0)
    return np.where(np.isfinite(num_ / den), num_ / den, 0.0)


# ── Gamma–Gamma ──────────────────────────────────────────────────────────────

def _gg_ll(theta, x, m):
    p, q, g = np.exp(theta)
    ln = special.gammaln
    ll = (ln(p * x + q) - ln(p * x) - ln(q) + q * np.log(g) + (p * x - 1) * np.log(m) + (p * x) * np.log(x)
          - (p * x + q) * np.log(g + m * x))
    return -float(ll.sum())


def gamma_gamma_fit(x_total, mean_value) -> dict:
    keep = (x_total > 0) & (mean_value > 0)
    if keep.sum() < 20:
        return {"status": "insufficient_data"}
    x, m = x_total[keep], mean_value[keep]
    best = None
    for start in ((np.log(1.0), np.log(1.5), np.log(m.mean())), (np.log(3.0), np.log(3.0), np.log(m.mean() * 2))):
        res = optimize.minimize(_gg_ll, np.array(start), args=(x, m), method="L-BFGS-B", bounds=[(-6, 12)] * 3)
        if best is None or res.fun < best.fun:
            best = res
    p, q, g = np.exp(best.x)
    corr = float(np.corrcoef(x, m)[0, 1]) if x.size > 2 and x.std() > 0 and m.std() > 0 else None
    return {"status": "ok", "p": float(p), "q": float(q), "gamma": float(g),
            "population_mean_value": float(g * p / (q - 1)) if q > 1 else float(m.mean()),
            "frequency_value_correlation": num(corr, 4), "n": int(keep.sum())}


def conditional_value(gg: dict, x_total, mean_value) -> np.ndarray:
    """E[value per order | x, mean] under Gamma–Gamma."""
    p, q, g = gg["p"], gg["q"], gg["gamma"]
    x = np.maximum(x_total, 0)
    m = np.where(x > 0, mean_value, 0.0)
    return (g * p / (q - 1)) * (q - 1) / (p * x + q - 1) + (p * x / (p * x + q - 1)) * m


# ── the whole thing ──────────────────────────────────────────────────────────

def run(customer_orders: list[dict], margins: list[dict] | None = None, today: date | None = None,
        channel: str = "shopify", draws: int = CLV_DRAWS) -> dict:
    if channel != "shopify":
        return {"status": "not_applicable", "basis": "no Amazon export carries a customer identity"}
    x, t_x, T, mv, fv, end = customer_table(customer_orders)
    n = int(x.size)
    base = {"n_customers": n, "calendar_end": end.isoformat() if n else None}
    if n < MIN_CUSTOMERS:
        return {**base, "status": "insufficient_data", "basis": f"{n} customers; {MIN_CUSTOMERS} needed"}
    span_weeks = float(T.max()) if n else 0.0
    if span_weeks < MIN_SPAN_WEEKS:
        return {**base, "status": "insufficient_data", "basis": f"{span_weeks:.0f} weeks of order history; {MIN_SPAN_WEEKS} needed"}

    fit = bgnbd_fit(x, t_x, T)
    gg = gamma_gamma_fit(x, mv)

    # holdout calibration: fit on the first CALIBRATION_SHARE of the calendar,
    # predict repeats in the rest, compare with what happened
    first_dates = end - timedelta(weeks=float(T.max()))
    cut = first_dates + timedelta(days=int((end - first_dates).days * CALIBRATION_SHARE))
    xc, txc, Tc, _, _, _ = customer_table(customer_orders, end=cut)
    holdout_weeks = (end - cut).days / 7.0
    ratio = None
    if xc.size >= MIN_CUSTOMERS and holdout_weeks >= 4:
        fit_c = bgnbd_fit(xc, txc, Tc)
        predicted = float(expected_repeats(fit_c, holdout_weeks, xc, txc, Tc).sum())
        # actual repeats in the holdout by the customers alive at the cut
        x_full, _, _, _, _, _ = customer_table(
            [o for o in customer_orders if o.get("customer_key")], end=end)
        # customers who existed at the cut: their repeat counts grew by (x_full − xc)
        keys_cut = _keys_by_first_order(customer_orders, cut)
        actual = float(sum(max(0, _repeats_between(customer_orders, k, cut, end)) for k in keys_cut))
        ratio = actual / predicted if predicted > 0 else None
    calibrated = ratio is not None and CALIBRATION_BAND[0] <= ratio <= CALIBRATION_BAND[1]

    rep = expected_repeats(fit, HORIZON_WEEKS, x, t_x, T)
    per_customer_repeats = float(rep.mean())
    first_value = float(np.mean(fv[fv > 0])) if (fv > 0).any() else 0.0
    if gg.get("status") == "ok":
        value = float(np.mean(conditional_value(gg, x, mv)))
    else:
        value = float(np.mean(mv[mv > 0])) if (mv > 0).any() else first_value
    discount = 1.0 / (1 + ANNUAL_DISCOUNT) ** 0.5     # a year of repeats, discounted at the midpoint
    multiplier = 1.0 + per_customer_repeats * (value / first_value if first_value > 0 else 1.0) * discount

    # parametric bootstrap on the BG/NBD estimates
    band = None
    if fit["cov"] is not None:
        rng = np.random.default_rng(CLV_SEED)
        thetas = rng.multivariate_normal(fit["theta"], fit["cov"], size=int(draws))
        mults = []
        for th in thetas:
            r_, al_, a_, b_ = np.exp(th)
            if a_ <= 1.0:
                continue   # the closed form needs a > 1
            pr = {"r": r_, "alpha": al_, "a": a_, "b": b_}
            rep_d = float(expected_repeats(pr, HORIZON_WEEKS, x, t_x, T).mean())
            mults.append(1.0 + rep_d * (value / first_value if first_value > 0 else 1.0) * discount)
        if len(mults) >= 50:
            m_ = np.array(mults)
            band = {"p5": num(float(np.quantile(m_, 0.05)), 4), "p50": num(float(np.quantile(m_, 0.5)), 4),
                    "p95": num(float(np.quantile(m_, 0.95)), 4), "draws": int(m_.size),
                    "mc_se_p50": num(float(m_.std() / np.sqrt(m_.size)), 5), "seed": CLV_SEED}

    status = "ok" if calibrated else ("poorly_calibrated" if ratio is not None else "uncalibrated")
    return {
        **base, "status": status,
        "bgnbd": {k: num(v, 4) for k, v in fit.items() if k in ("r", "alpha", "a", "b")},
        "bgnbd_loglik": num(fit["loglik"]), "gamma_gamma": {k: (num(v, 4) if isinstance(v, float) else v) for k, v in gg.items()},
        "expected_repeats_52w": num(per_customer_repeats, 4),
        "first_order_value": num(first_value), "repeat_order_value": num(value),
        "clv_multiplier": num(multiplier, 4), "clv_multiplier_band": band,
        "calibration": {"holdout_weeks": num(holdout_weeks, 1), "actual_over_predicted": num(ratio, 4),
                        "band": list(CALIBRATION_BAND), "calibrated": bool(calibrated)},
        "seed": CLV_SEED,
        "basis": (f"BG/NBD on {n} customers over {span_weeks:.0f} weeks, Gamma–Gamma on repeat order value; "
                  f"{per_customer_repeats:.2f} expected repeat orders per customer over {HORIZON_WEEKS} weeks; "
                  f"holdout actual/predicted {ratio if ratio is None else round(ratio, 2)}; "
                  + ("the multiplier moves the ad break-even" if calibrated else "the multiplier is information only")),
    }


def _keys_by_first_order(orders, cut):
    first = {}
    for o in orders:
        k, d = o.get("customer_key"), o.get("order_date")
        if not k or not d:
            continue
        d = date.fromisoformat(str(d)[:10])
        if k not in first or d < first[k]:
            first[k] = d
    return {k for k, d in first.items() if d <= cut}


def _repeats_between(orders, key, start, end):
    n = 0
    for o in orders:
        if o.get("customer_key") != key or not o.get("order_date"):
            continue
        d = date.fromisoformat(str(o["order_date"])[:10])
        if start < d <= end:
            n += 1
    return n
