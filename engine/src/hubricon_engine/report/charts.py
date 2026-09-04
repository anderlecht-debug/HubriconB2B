"""Brand-styled matplotlib charts, returned as base64 PNGs for inlining."""

import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

NAVY = "#0A1130"
NAVY_DEEP = "#050A1F"
AMBER = "#FFC000"
INK = "#F4F6FC"
INK_60 = "#9AA1B5"
RULE = "#2A3252"
RED = "#E0604F"
GREEN = "#5FBF8F"

plt.rcParams.update(
    {
        "figure.facecolor": NAVY_DEEP,
        "axes.facecolor": NAVY,
        "axes.edgecolor": RULE,
        "axes.labelcolor": INK_60,
        "text.color": INK,
        "xtick.color": INK_60,
        "ytick.color": INK_60,
        "grid.color": RULE,
        "font.family": "monospace",
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.4,
    }
)


def _to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight", facecolor=NAVY_DEEP)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def stockout_bars(rows: list[dict]) -> str | None:
    rows = sorted((r for r in rows if r["stockout_probability"] is not None),
                  key=lambda r: r["stockout_probability"], reverse=True)[:12]
    if not rows:
        return None
    skus = [r["sku"] for r in rows][::-1]
    probs = [float(r["stockout_probability"]) for r in rows][::-1]
    fig, ax = plt.subplots(figsize=(7.6, 0.42 * len(rows) + 1.2))
    colors = [RED if p >= 0.25 else AMBER for p in probs]
    ax.barh(skus, probs, color=colors)
    ax.axvline(0.25, color=RED, linestyle="--", linewidth=1, alpha=0.7)
    ax.set_xlim(0, 1)
    ax.set_xlabel("P(stockout before replenishment)")
    ax.set_title("Stockout risk at current inventory position", color=INK, loc="left")
    return _to_b64(fig)


def elasticity_scatter(results: list[dict], max_panels: int = 4) -> str | None:
    ok = [r for r in results if r["status"] == "ok" and r.get("details", {}).get("points")][:max_panels]
    if not ok:
        return None
    fig, axes = plt.subplots(1, len(ok), figsize=(3.9 * len(ok), 3.4), squeeze=False)
    for ax, r in zip(axes[0], ok):
        pts = r["details"]["points"]
        price = np.array([p["price"] for p in pts], dtype=float)
        units = np.array([p["units"] for p in pts], dtype=float)
        ax.scatter(price, units, color=AMBER, zorder=3)
        e = float(r["elasticity"])
        grid = np.linspace(price.min(), price.max(), 60)
        scale = np.exp(np.mean(np.log(units)) - e * np.mean(np.log(price)))
        ax.plot(grid, scale * grid**e, color=INK, linewidth=1.2, alpha=0.8)
        ax.set_title(f"{r['item_id']}  ε = {e:.2f}", color=INK, fontsize=9, loc="left")
        ax.set_xlabel("avg price ($)")
        ax.set_ylabel("units / period")
    fig.suptitle("Price vs demand — fitted elasticity", color=INK, x=0.01, ha="left")
    fig.tight_layout()
    return _to_b64(fig)


def ad_curves(results: list[dict], max_panels: int = 4) -> str | None:
    ok = [r for r in results if r["status"] == "ok"][:max_panels]
    if not ok:
        return None
    fig, axes = plt.subplots(1, len(ok), figsize=(3.9 * len(ok), 3.4), squeeze=False)
    for ax, r in zip(axes[0], ok):
        p = r["curve_params"]
        top = max(float(r["current_spend"] or 1), float(r["breakeven_spend"] or 1)) * 1.6
        s = np.linspace(0.01, top, 120)
        if r["curve_model"] == "hill":
            y = p["a"] * s ** p["h"] / (p["k"] ** p["h"] + s ** p["h"])
        else:
            y = p["a"] * np.log1p(p["k"] * s) if "k" in p else p["a"] * np.log1p(s)
        ax.plot(s, y, color=INK, linewidth=1.3)
        if r["current_spend"]:
            ax.axvline(float(r["current_spend"]), color=AMBER, linestyle="-", linewidth=1.2, label="current")
        if r["breakeven_spend"]:
            ax.axvline(float(r["breakeven_spend"]), color=RED, linestyle="--", linewidth=1.2, label="break-even")
        name = r["campaign_name"][:24]
        ax.set_title(name, color=INK, fontsize=9, loc="left")
        ax.set_xlabel("spend ($)")
        ax.set_ylabel("attributed sales ($)")
        ax.legend(fontsize=7, facecolor=NAVY, labelcolor=INK_60, edgecolor=RULE)
    fig.suptitle("Ad spend saturation — marginal-return curves", color=INK, x=0.01, ha="left")
    fig.tight_layout()
    return _to_b64(fig)


def margin_bars(rows: list[dict], fee_label: str = "Amazon fees") -> str | None:
    """Latest-period margin decomposition, top SKUs by revenue. `fee_label`
    names the platform's fee stack (channels.fee_label)."""
    if not rows:
        return None
    latest_start = max(r["period_start"] for r in rows)
    latest = sorted(
        (r for r in rows if r["period_start"] == latest_start and (r["revenue"] or 0) > 0),
        key=lambda r: r["revenue"], reverse=True,
    )[:8]
    if not latest:
        return None
    skus = [r["sku"] for r in latest][::-1]
    fees = np.array([float(r["amazon_fees"] or 0) for r in latest])[::-1]
    cogs = np.array([float(r["cogs"] or 0) for r in latest])[::-1]
    ads = np.array([float(r["ad_spend_allocated"] or 0) for r in latest])[::-1]
    net = np.array([float(r["net_margin"] or 0) for r in latest])[::-1]
    fig, ax = plt.subplots(figsize=(7.6, 0.5 * len(latest) + 1.4))
    left = np.zeros(len(latest))
    for values, color, label in ((fees, RULE, fee_label), (cogs, INK_60, "COGS"),
                                 (ads, AMBER, "Ads"), (net, GREEN, "Net margin")):
        ax.barh(skus, values, left=left, color=color, label=label)
        left = left + np.clip(values, 0, None)
    ax.set_xlabel(f"latest period ({latest_start}) — $ per SKU")
    ax.set_title("Where each revenue dollar goes", color=INK, loc="left")
    ax.legend(fontsize=7, facecolor=NAVY, labelcolor=INK_60, edgecolor=RULE, ncols=4)
    return _to_b64(fig)
