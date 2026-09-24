"""The engine, run on a world exactly as `hubricon run` runs it: the same
models in the same order with the same arguments, then `draft_directives`.
Nothing here decides anything; it only calls the engine."""
import numpy as np

from hubricon_engine import directives
from hubricon_engine.models import (ad_allocation, ad_efficiency, anomaly, assortment, cash_orders, cashflow,
                                    cross_price, data_quality, elasticity, forecast, incrementality, inventory_econ,
                                    inventory_sim, margin, markdown, replenishment, risk, seasonality, stress)

from .worlds import CLIENT, TODAY


def run_engine(data: dict, seed: int = 42, sims: int = 8000, paths: int = 4000) -> dict:
    r = np.random.default_rng(seed)
    out = {}
    out["dq"] = data_quality.run(data, TODAY)
    out["margins"] = margin.run(data)
    avg_m = margin.average_margin(out["margins"])
    out["sea"] = seasonality.indices(data)
    out["fc"] = forecast.run(data, seasonal=out["sea"])
    overrides = {f["item_id"]: forecast.rate_moments(f) for f in out["fc"] if f["status"] == "ok" and f["level"] == "sku"}
    out["inv"] = inventory_sim.run(data, r, sims, rate_overrides=overrides, seasonal=out["sea"], today=TODAY)
    out["el"] = elasticity.run(data, experiments=None, seasonal=out["sea"])
    out["cross"] = cross_price.run(data, out["el"], seasonal=out["sea"])
    out["anom"] = anomaly.run(data)
    out["incr"] = incrementality.run(data, [])
    out["breaks"] = ad_efficiency.regime_breaks(out["anom"])
    out["ads"] = ad_efficiency.run(data, avg_margin=avg_m, breaks=out["breaks"])
    out["alloc"] = ad_allocation.run(out["ads"], avg_m, exclude=set(directives.trim_candidates(out["ads"], avg_m)))
    out["risk"] = risk.run(data, out["margins"], out["fc"], out["inv"], out["ads"], r, 4000)
    out["ie"] = inventory_econ.run(data, out["inv"], out["margins"], out["fc"], r, sims, TODAY,
                                   seasonal=out["sea"], risk_out=out["risk"])
    out["md"] = markdown.run(data, out["ie"], out["el"], out["margins"], out["inv"], TODAY, "amazon", draws=2000)
    out["rep"] = replenishment.run(out["ie"], data, r, TODAY)
    out["asrt"] = assortment.run(out["margins"], out["ie"], data, out["risk"], out["cross"], TODAY)
    out["client"] = client = sized_client(out, paths)
    cash = cashflow.run(client, out["inv"], out["margins"], np.random.default_rng(seed + 1), n_paths=paths,
                        seasonal=out["sea"], today=TODAY, keep_paths=True)
    out["cash_paths"] = cash.pop("_paths")
    out["cash"] = cash
    out["stress"] = stress.run(out["cash_paths"], cash)
    out["co"] = cash_orders.run(out["ie"], cash, TODAY)
    book = {}
    out["drafts"] = directives.draft_directives(
        out["inv"], out["ads"], out["el"], out["margins"], search_terms=data["ppc_search_terms"],
        brand_terms=["acme"], recovery=None, inv_econ=out["ie"], anomaly_rows=out["anom"], channel="amazon",
        ad_allocation=out["alloc"], incrementality=out["incr"], client_id=CLIENT["id"], cross_price=out["cross"],
        markdown=out["md"], replenishment=out["rep"], cash_orders=out["co"], assortment=out["asrt"], cash=cash,
        **_book_kwarg(book))
    out["book"] = book or None
    out["avg_margin"] = avg_m
    return out


CASH_CUSHION = 1.20


def sized_client(out: dict, paths: int) -> dict:
    """A client whose cash covers the plan's own trough with a 20% cushion.

    The cone's trough falls before the first payout, where every flow is a
    known wire, fee or budget, so a fixed cash figure would make ruin either
    certain or impossible depending on the world's scale. Sizing the cash to
    the plan's own trough leaves the sweep's extra cash moves able to matter,
    which is what the survival criterion tests."""
    probe = cashflow.run({**CLIENT, "cash_on_hand": 0.0}, out["inv"], out["margins"], np.random.default_rng(0),
                         n_paths=500, seasonal=out["sea"], today=TODAY, keep_paths=True)
    pp = probe.pop("_paths")
    base = cashflow.cash_from_components(pp, pp["sales_net"], pp["ad_daily_total"], pp["outflow"], pp["payout_days"], 0)
    depth = max(0.0, -float(base.min()))
    return {**CLIENT, "cash_on_hand": float(round(CASH_CUSHION * depth, -4) or CLIENT["cash_on_hand"])}


def _book_kwarg(book: dict) -> dict:
    """The engine's own book for the sweep, when its drafting call publishes one."""
    import inspect
    return {"book_out": book} if "book_out" in inspect.signature(directives.draft_directives).parameters else {}


def pricing_sweep(data: dict) -> list[dict]:
    """Only the models a price step reads, for the stability checks."""
    margins = margin.run(data)
    sea = seasonality.indices(data)
    el = elasticity.run(data, experiments=None, seasonal=sea)
    cross = cross_price.run(data, el, seasonal=sea)
    return directives.draft_directives([], [], el, margins, cross_price=cross)
