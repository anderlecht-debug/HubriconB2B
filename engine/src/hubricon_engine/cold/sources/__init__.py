"""One module per data provider, all behind the same Protocol.

Business logic never calls a provider. It asks a `Source` for a
`ProspectSnapshot` and gets the same dataclass whichever provider answered,
which is what makes the paid providers a later purchase rather than a rewrite:

  harvest.HarvestSource   the free public-page crawl this repo already runs.
                          Marginal cost $0 — the pages were fetched anyway.
  (keepa)                 price, rank, offer-count and Buy Box *history*.
                          Fills Item fields the harvest leaves empty and turns
                          on the history detectors. Token-metered; the day it
                          exists it is a module here and nothing else changes.

Every source reports what a snapshot cost so the cost ledger can hold the batch
to COLD_DAILY_BUDGET_USD (COLD_ENGINE.md §2.5).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..snapshot import ProspectSnapshot


@runtime_checkable
class Source(Protocol):
    name: str

    def keys(self, limit: int) -> list[str]:
        """Prospect keys this source can snapshot right now, best first."""

    def snapshot(self, key: str) -> ProspectSnapshot | None:
        """One normalised snapshot, or None when the provider has nothing."""

    def estimated_cost_usd(self) -> float:
        """What one `snapshot` call is expected to cost, before it is made."""
