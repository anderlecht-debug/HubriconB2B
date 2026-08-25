"""Shared helpers for the model modules."""

import math
from datetime import date


def num(value, digits: int = 2) -> float | None:
    """JSON-safe number: NaN/inf become None, everything else is rounded."""
    if value is None:
        return None
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        return None
    return round(v, digits)


def period_days(start: str, end: str) -> int:
    return max(1, (date.fromisoformat(end) - date.fromisoformat(start)).days + 1)


def latest_snapshot(inventory_rows: list[dict]) -> dict[str, dict]:
    """inventory_levels rows -> {sku: row} for the most recent snapshot_date."""
    if not inventory_rows:
        return {}
    newest = max(r["snapshot_date"] for r in inventory_rows)
    return {r["sku"]: r for r in inventory_rows if r["snapshot_date"] == newest}


def sku_asin_bridge(econ_rows: list[dict], cogs_rows: list[dict]) -> dict[str, str]:
    """sku -> asin, preferring SKU Economics over the client's COGS sheet."""
    bridge: dict[str, str] = {}
    for row in cogs_rows:
        if row.get("asin"):
            bridge[row["sku"]] = row["asin"]
    for row in econ_rows:
        if row.get("asin"):
            bridge[row["sku"]] = row["asin"]
    return bridge
