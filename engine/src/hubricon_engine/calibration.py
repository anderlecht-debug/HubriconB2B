"""What consenting clients' real accounts say the cold engine's guesses should be.

The cold teardown prices a stranger's listing from published rate cards and
two estimates it cannot check from the outside: how many units a sales rank
sells (`harvest/amazon.py`'s fitted curve, "comfortably wrong by a factor of
two either way") and how many orders a Shopify review stands for
(`HARVEST_SHOPIFY_ORDERS_PER_REVIEW`, a guess of 50 the whole $500k–$40M band
rides on). A client's own exports are the only ground truth those estimates
will ever get, and every client makes the next teardown sharper — which is
the one part of this loop that compounds on its own.

Two rules, because terms.html §10 says we never use one client's data to
advise another:

  1. Nothing is read from a client who has not granted the separate
     `calibration` consent, asked for on the same page as the testimonial.
     The consent kind exists for this alone.
  2. What is written is an aggregate — a slope, a rate, a ratio — with the
     number of clients and observations behind it on the row, and the
     teardown that uses it says so in its assumptions. Below the floor
     (`MIN_CLIENTS` accounts, `MIN_OBS` observations) the row records
     `insufficient` and a null, and the published card stands.

The cache is process-wide and loaded once (`load(db)`); readers call `get()`
and fall back to their published default when nothing is loaded, so the cold
engine works unchanged on a database that has never been calibrated.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from . import onboarding

MIN_CLIENTS = 2
MIN_OBS = 30
MIN_OBS_RATE = 30        # referral-rate rows: one client is enough, the card is published anyway
MIN_OBS_CLAIMS = 10

_CACHE: dict[str, dict] | None = None


def reset() -> None:
    global _CACHE
    _CACHE = None


def load(db) -> dict[str, dict]:
    """Read the table once. A database without it is a database without
    calibration, not an error."""
    global _CACHE
    try:
        rows = db.table("calibration").select("*").execute().data or []
    except Exception:
        rows = []
    _CACHE = {r["key"]: r for r in rows if r.get("value") is not None}
    return _CACHE


def get(key: str, default=None):
    if not _CACHE:
        return default
    row = _CACHE.get(key)
    return float(row["value"]) if row and row.get("value") is not None else default


def describe(key: str) -> str | None:
    """'calibrated on 3 client accounts (412 observations)' — or None when the
    published figure is in use."""
    if not _CACHE or key not in _CACHE:
        return None
    r = _CACHE[key]
    return (f"calibrated on {r.get('n_clients', 0)} client account"
            f"{'' if r.get('n_clients') == 1 else 's'} ({r.get('n_obs', 0)} observations)")


def curve(category: str | None) -> tuple[float, float] | None:
    """A fitted (a, b) for log10(units) = a - b·log10(rank), or None."""
    cat = (category or "").strip().lower()
    a, b = get(f"amazon.bsr_curve.{cat}.a"), get(f"amazon.bsr_curve.{cat}.b")
    return (a, b) if a is not None and b is not None else None


# -- the arithmetic ------------------------------------------------------------------

def fit_loglog(pairs: list[tuple[float, float]]) -> tuple[float, float, int] | None:
    """Least squares on log10(y) = a - b·log10(x). Returns (a, b, n)."""
    pts = [(math.log10(x), math.log10(y)) for x, y in pairs if x and y and x > 0 and y > 0]
    n = len(pts)
    if n < 2:
        return None
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    if sxx == 0:
        return None
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    slope = sxy / sxx
    a = my - slope * mx
    return round(a, 4), round(-slope, 4), n


def _row(key: str, value, n_clients: int, n_obs: int, method: str, note: str | None = None,
         low=None, high=None, floor_clients: int = MIN_CLIENTS, floor_obs: int = MIN_OBS) -> dict:
    enough = n_clients >= floor_clients and n_obs >= floor_obs and value is not None
    return {"key": key, "value": value if enough else None, "low": low if enough else None,
            "high": high if enough else None, "n_clients": n_clients, "n_obs": n_obs,
            "method": method if enough else "insufficient",
            "note": note if enough else f"needs {floor_clients} account(s) and {floor_obs} observations; "
                                        f"have {n_clients} and {n_obs}",
            "computed_at": datetime.now(timezone.utc).isoformat()}


def consented_clients(db, kind: str = "calibration", statuses: tuple[str, ...] | None = None) -> list[dict]:
    """Only clients who said yes to this specific use, and never internal ones.

    The one gate every consented aggregate reads through: `kind` names the
    use ('calibration' here; 'network' for fleet.py and `hubricon book`), and
    `statuses`, when given, keeps only clients whose status is in it."""
    granted = {k["client_id"] for k in db.table("consents").select("client_id").eq("kind", kind)
               .eq("granted", True).execute().data}
    if not granted:
        return []
    clients = db.table("clients").select("*").in_("id", sorted(granted)).execute().data
    return [c for c in clients if (statuses is None or c.get("status") in statuses)
            and not onboarding.is_internal(c.get("contact_email"), c.get("contact_name"))]


def _since(today: date, days: int = 365) -> str:
    return (today - timedelta(days=days)).isoformat()


def compute(db, today: date | None = None, log=print) -> list[dict]:
    """Every calibration row this database supports right now, written and
    returned. Safe to run on an empty database: it writes `insufficient`."""
    today = today or date.today()
    clients = consented_clients(db)
    rows: list[dict] = []
    amazon = [c for c in clients if (c.get("platform") or "amazon") in ("amazon", "both")]
    shopify = [c for c in clients if (c.get("platform") or "amazon") in ("shopify", "both")]

    # 1. Shopify: real orders per published review, by store.
    ratios, n_products = [], 0
    for c in shopify:
        domain = (c.get("shopify_domain") or "").strip().lower()
        if not domain:
            continue
        sellers = (db.table("harvest_sellers").select("seller_id")
                   .or_(f"website.ilike.%{domain}%,seller_id.ilike.%{domain}%").limit(3).execute().data)
        reviews = 0
        for s in sellers:
            prods = db.table("harvest_products").select("reviews").eq("seller_id", s["seller_id"]).execute().data
            reviews += sum(int(p.get("reviews") or 0) for p in prods)
            n_products += sum(1 for p in prods if p.get("reviews"))
        econ = (db.table("sku_economics").select("units_sold").eq("client_id", c["id"])
                .eq("channel", "shopify").gte("period_start", _since(today)).execute().data)
        units = sum(int(e.get("units_sold") or 0) for e in econ)
        if reviews and units:
            ratios.append(units / reviews)
    value = round(sum(ratios) / len(ratios), 2) if ratios else None
    rows.append(_row("shopify.orders_per_review", value, len(ratios), n_products,
                     "twelve months of real units divided by the store's published lifetime reviews "
                     "(a lower bound on the lifetime ratio)",
                     low=round(min(ratios), 2) if ratios else None,
                     high=round(max(ratios), 2) if ratios else None))

    # 2. Amazon: sales rank against real monthly units, one curve per category.
    pairs_by_cat: dict[str, list[tuple[float, float]]] = {}
    clients_by_cat: dict[str, set] = {}
    for c in amazon:
        traffic = (db.table("asin_traffic").select("child_asin, units_ordered, period_start, period_end")
                   .eq("client_id", c["id"]).gte("period_start", _since(today)).execute().data)
        asins = sorted({t["child_asin"] for t in traffic if t.get("child_asin")})
        if not asins:
            continue
        cats = {p["asin"]: (p.get("category") or "").strip().lower() for p in
                db.table("harvest_products").select("asin, category").in_("asin", asins).execute().data}
        obs = db.table("harvest_product_observations").select("asin, bsr, seen_on") \
            .in_("asin", asins).execute().data
        by_asin: dict[str, list[dict]] = {}
        for o in obs:
            if o.get("bsr"):
                by_asin.setdefault(o["asin"], []).append(o)
        for t in traffic:
            cat = cats.get(t.get("child_asin"))
            if not cat or not t.get("units_ordered"):
                continue
            start, end = str(t["period_start"])[:10], str(t["period_end"])[:10]
            days = max(1, (date.fromisoformat(end) - date.fromisoformat(start)).days + 1)
            monthly = float(t["units_ordered"]) * 30.0 / days
            inside = [o for o in by_asin.get(t["child_asin"], []) if start <= str(o["seen_on"])[:10] <= end]
            for o in inside:
                pairs_by_cat.setdefault(cat, []).append((float(o["bsr"]), monthly))
                clients_by_cat.setdefault(cat, set()).add(c["id"])
    for cat, pairs in sorted(pairs_by_cat.items()):
        fit = fit_loglog(pairs)
        n_c = len(clients_by_cat.get(cat, ()))
        if fit:
            a, b, n = fit
            rows.append(_row(f"amazon.bsr_curve.{cat}.a", a, n_c, n, "log-log least squares, rank vs real monthly units"))
            rows.append(_row(f"amazon.bsr_curve.{cat}.b", b, n_c, n, "log-log least squares, rank vs real monthly units"))

    # 3. Amazon: the referral rate actually charged, by category.
    fees_by_cat: dict[str, list[tuple[float, float]]] = {}
    clients_fee: dict[str, set] = {}
    for c in amazon:
        econ = (db.table("sku_economics").select("asin, sales, referral_fees").eq("client_id", c["id"])
                .gte("period_start", _since(today)).execute().data)
        asins = sorted({e["asin"] for e in econ if e.get("asin")})
        if not asins:
            continue
        cats = {p["asin"]: (p.get("category") or "").strip().lower() for p in
                db.table("harvest_products").select("asin, category").in_("asin", asins).execute().data}
        for e in econ:
            cat = cats.get(e.get("asin"))
            sales, fee = float(e.get("sales") or 0), abs(float(e.get("referral_fees") or 0))
            if cat and sales > 0 and fee > 0:
                fees_by_cat.setdefault(cat, []).append((sales, fee))
                clients_fee.setdefault(cat, set()).add(c["id"])
    for cat, pairs in sorted(fees_by_cat.items()):
        rate = round(sum(f for _, f in pairs) / sum(s for s, _ in pairs), 4)
        rows.append(_row(f"amazon.referral_rate.{cat}", rate, len(clients_fee[cat]), len(pairs),
                         "referral fees charged divided by sales, twelve months",
                         floor_clients=1, floor_obs=MIN_OBS_RATE))

    # 4. Amazon: how often a filed claim is paid, by claim type.
    outcomes: dict[str, list[int]] = {}
    clients_claim: dict[str, set] = {}
    for c in amazon:
        claims = (db.table("recovery_claims").select("claim_type, status").eq("client_id", c["id"])
                  .in_("status", ["paid", "denied"]).execute().data)
        for k in claims:
            outcomes.setdefault(k["claim_type"], []).append(1 if k["status"] == "paid" else 0)
            clients_claim.setdefault(k["claim_type"], set()).add(c["id"])
    for kind, xs in sorted(outcomes.items()):
        rows.append(_row(f"amazon.reimb_p_approve.{kind}", round(sum(xs) / len(xs), 4),
                         len(clients_claim[kind]), len(xs), "paid over paid plus denied, claims we filed",
                         floor_clients=1, floor_obs=MIN_OBS_CLAIMS))

    if rows:
        db.table("calibration").upsert(rows, on_conflict="key").execute()
    for r in rows:
        log(f"  {r['key']:<44} {('%.4g' % r['value']) if r['value'] is not None else '—':>10}  "
            f"{r['method']} · {r['n_clients']} client(s), {r['n_obs']} obs")
    if not clients:
        log("  no client has granted calibration consent yet; every row is 'insufficient' by design")
    reset()
    return rows
