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
      supplyInfo { maxLTV { value } liquidationThreshold { value } canBeCollateral }
    }
  }
}
"""


def reserves_for_asset(chain_id: int, asset_address: str) -> list[dict]:
    """Aave v3 reserves (one per Aave market) listing `asset_address`."""
    data = fetch_json(URL, body={"query": _MARKETS, "variables": {"chains": [chain_id]}})
    asset = asset_address.lower()
    out = []
    for m in data["data"]["markets"]:
        for r in m["reserves"]:
            if r["underlyingToken"]["address"].lower() == asset:
                out.append({**r, "market_name": m["name"], "market_address": m["address"]})
    return out

