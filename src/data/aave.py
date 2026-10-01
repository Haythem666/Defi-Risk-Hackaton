"""Aave v3 GraphQL API (public, no key). Docs: https://aave.com/docs/developers/aave-v3"""

from src.data.cache import fetch_json

URL = "https://api.v3.aave.com/graphql"

_MARKETS = """
query($chains: [ChainId!]!) {
  markets(request: {chainIds: $chains}) {
    name
    address
    reserves {
      underlyingToken { address symbol }
      size { usd }
      usdExchangeRate
      usdOracleAddress
      isFrozen
      isPaused
      supplyInfo { maxLTV { value } liquidationThreshold { value } canBeCollateral apy { value } }
      borrowInfo { total { usd } availableLiquidity { usd } utilizationRate { value } }
    }
  }
}
"""


def markets(chain_id: int) -> list[dict]:
    """All Aave v3 markets (pools) on a chain, with their reserves."""
    data = fetch_json(URL, body={"query": _MARKETS, "variables": {"chains": [chain_id]}})
    return data["data"]["markets"]


def market(chain_id: int, pool_address: str) -> dict:
    pool = pool_address.lower()
    return next(m for m in markets(chain_id) if m["address"].lower() == pool)


def reserves_for_asset(chain_id: int, asset_address: str) -> list[dict]:
    """Aave v3 reserves (one per Aave market) listing `asset_address`."""
    asset = asset_address.lower()
    out = []
    for m in markets(chain_id):
        for r in m["reserves"]:
            if r["underlyingToken"]["address"].lower() == asset:
                out.append({**r, "market_name": m["name"], "market_address": m["address"]})
    return out

