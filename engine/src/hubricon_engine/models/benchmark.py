"""Where a client sits against the book: percentiles, with the book's consent.

The longer a client stays, the more of their own history the engine holds;
what it cannot make from one account is a comparison. This module places a
client's headline ratios among the other consenting clients' — the same
consent the cold-engine calibration reads, and nothing else, because terms
§10 says one client's data never advises another. What comes out is a
percentile and a band, never another client's number.

THE RATIOS, each from a client's latest succeeded run:
    tacos              allocated ad spend over revenue, latest period
    net_margin_pct     blended net margin, latest period
    stockout_share     share of SKUs at or over the 25% stockout alert
    fee_bleed_share    inventory fee bleed per month over monthly revenue
    realisation_ratio  measured over promised, from the replay scorecard

THE PLACEMENT. The client's percentile among the book's values, with a band
from resampling the book (a book of twelve is not a population), and the
book's median beside it. Below MIN_CLIENTS consenting accounts the whole
module refuses (`insufficient_clients`) and says how many short: a
percentile among four is a coin flip with a decimal point.

WHAT IT CANNOT TELL YOU. Whether the book resembles the client (no category,
no size band is on the row); anything about a client who did not consent.
"""

from datetime import date

import numpy as np

from .common import num

MIN_CLIENTS = 10
BOOK_BOOTSTRAP = 2000
BOOK_SEED = 20260911
RATIOS = ("tacos", "net_margin_pct", "stockout_share", "fee_bleed_share", "realisation_ratio")
HIGHER_IS_BETTER = {"tacos": False, "net_margin_pct": True, "stockout_share": False,
                    "fee_bleed_share": False, "realisation_ratio": True}


def ratios_for(margins: list[dict], inventory_rows: list[dict], inv_econ: dict | None,
               directives: list[dict]) -> dict:
    """A client's own five numbers from its own results."""
    out = {}
    if margins:
        latest = max(str(m["period_start"]) for m in margins)
        rows = [m for m in margins if str(m["period_start"]) == latest]
        rev = sum(float(m.get("revenue") or 0) for m in rows)
        if rev > 0:
            out["tacos"] = sum(float(m.get("ad_spend_allocated") or 0) for m in rows) / rev
            out["net_margin_pct"] = sum(float(m.get("net_margin") or 0) for m in rows) / rev
            bleed = float((((inv_econ or {}).get("summary") or {}).get("bleed") or {}).get("total_month") or 0)
            from .common import period_days
            days = period_days(latest, str(rows[0].get("period_end") or latest)) if rows[0].get("period_end") else 30
            out["fee_bleed_share"] = bleed / (rev * 30.0 / days) if rev > 0 else None
    if inventory_rows:
        out["stockout_share"] = sum(1 for r in inventory_rows if float(r.get("stockout_probability") or 0) >= 0.25) / len(inventory_rows)
    if directives:
        from ..replay import score
        card = score(directives)
        out["realisation_ratio"] = card.get("realisation_ratio")
    return {k: v for k, v in out.items() if v is not None}


def compare(book: dict[str, dict], client: dict) -> dict:
    """Percentiles of `client`'s ratios among `book` (client_id -> ratios)."""
    n = len(book)
    if n < MIN_CLIENTS:
        return {"status": "insufficient_clients", "n_clients": n, "needed": MIN_CLIENTS,
                "basis": f"{n} consenting client(s) on the book; {MIN_CLIENTS - n} more before a percentile means anything"}
    rng = np.random.default_rng(BOOK_SEED)
    out = {}
    for ratio in RATIOS:
        mine = client.get(ratio)
        others = np.array([v[ratio] for v in book.values() if v.get(ratio) is not None], dtype=float)
        if mine is None or others.size < MIN_CLIENTS:
            out[ratio] = {"status": "insufficient_data", "n": int(others.size)}
            continue
        pct = float(np.mean(others <= mine))
        idx = rng.integers(0, others.size, (BOOK_BOOTSTRAP, others.size))
        boots = (others[idx] <= mine).mean(axis=1)
        better = pct if HIGHER_IS_BETTER[ratio] else 1.0 - pct
        out[ratio] = {"status": "ok", "value": num(mine, 4), "percentile": num(pct, 4),
                      "percentile_p5": num(float(np.quantile(boots, 0.05)), 4),
                      "percentile_p95": num(float(np.quantile(boots, 0.95)), 4),
                      "book_median": num(float(np.median(others)), 4), "n": int(others.size),
                      "reading": ("better than" if better >= 0.5 else "worse than") + f" {max(better, 1 - better):.0%} of the book"}
    return {"status": "ok", "n_clients": n, "ratios": out, "seed": BOOK_SEED,
            "basis": (f"percentile among {n} consenting clients' latest runs, band by resampling the book "
                      f"({BOOK_BOOTSTRAP:,} draws); no other client's number leaves this module")}


def _latest_run_id(db, client_id: str) -> str | None:
    rows = (db.table("model_runs").select("id, started_at").eq("client_id", client_id)
            .eq("status", "succeeded").order("started_at", desc=True).limit(1).execute().data)
    return rows[0]["id"] if rows else None


def _client_ratios(db, client_id: str) -> dict:
    run_id = _latest_run_id(db, client_id)
    if not run_id:
        return {}
    margins = db.table("margin_results").select("*").eq("run_id", run_id).execute().data
    inventory = db.table("inventory_sim_results").select("*").eq("run_id", run_id).execute().data
    outputs = {r["model"]: r["payload"] for r in
               db.table("model_outputs").select("model, payload").eq("run_id", run_id).execute().data}
    directives = db.table("directives").select("*").eq("client_id", client_id).execute().data
    return ratios_for(margins, inventory, outputs.get("invecon"), directives)


def run(db, client_id: str, today: date | None = None) -> dict:
    from ..calibration import consented_clients

    consenting = [c for c in consented_clients(db) if c["id"] != client_id]
    book = {c["id"]: _client_ratios(db, c["id"]) for c in consenting}
    book = {k: v for k, v in book.items() if v}
    mine = _client_ratios(db, client_id)
    out = compare(book, mine)
    out["as_of"] = (today or date.today()).isoformat()
    out["client_ratios"] = {k: num(v, 4) for k, v in mine.items()}
    return out
