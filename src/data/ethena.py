"""Ethena transparency API (public, no key): where USDe's backing sits.
Dashboard: https://app.ethena.fi/dashboards/transparency"""

from collections import defaultdict

from src.data.cache import fetch_json

COLLATERAL = "https://ethena.fi/api/positions/current/collateral"
DASHBOARD = "https://app.ethena.fi/dashboards/transparency"


def backing_by_venue() -> dict[str, float]:
    """USD of USDe backing per venue (Binance, OKX, ..., 'Unallocated')."""
    rows = fetch_json(COLLATERAL)["collateral"]
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        out[r["exchange"]] += r["usdAmount"] or 0.0
    return dict(out)
