"""Morpho Blue GraphQL API (public, no key). Docs: https://docs.morpho.org/tools/offchain/api/"""

from src.data.cache import fetch_json

URL = "https://blue-api.morpho.org/graphql"

# Chains with listed Morpho markets, and their name in app.morpho.org URLs.
NETWORKS = {1: "ethereum", 42161: "arbitrum", 8453: "base", 999: "hyperevm"}

_MARKETS_BY_COLLATERAL = """
query($assets: [String!], $chains: [Int!]) {
  markets(first: 50, where: {collateralAssetAddress_in: $assets, chainId_in: $chains}) {
    items {
      marketId
      lltv
      collateralAsset { symbol address decimals price { usd } }
      loanAsset { symbol address decimals price { usd } }
      oracle { address type }
      state { collateralAssetsUsd borrowAssetsUsd supplyAssetsUsd }
    }
  }
}
"""


def markets_with_collateral(chain_id: int, asset_address: str) -> list[dict]:
    """Morpho markets that accept `asset_address` as collateral."""
    if chain_id not in NETWORKS:
        return []
    body = {"query": _MARKETS_BY_COLLATERAL,
            "variables": {"assets": [asset_address.lower()], "chains": [chain_id]}}
    return ((fetch_json(URL, body=body).get("data") or {}).get("markets") or {}).get("items") or []


def market_url(chain_id: int, market_id: str) -> str:
    return f"https://app.morpho.org/{NETWORKS.get(chain_id, chain_id)}/market/{market_id}"


_MARKET_FIELDS = """
  marketId
  lltv
  listed
  collateralAsset { symbol address decimals price { usd } }
  loanAsset { symbol address decimals price { usd } }
  oracle { address type }
  state { supplyAssetsUsd borrowAssetsUsd collateralAssetsUsd liquidityAssetsUsd
          utilization supplyApy }
"""


def market(chain_id: int, market_id: str) -> dict:
    """One Morpho market by its id."""
    q = f"query($id: String!, $chain: Int!) {{ marketById(marketId: $id, chainId: $chain) {{ {_MARKET_FIELDS} }} }}"
    return fetch_json(URL, body={"query": q, "variables": {"id": market_id, "chain": chain_id}}
                      )["data"]["marketById"]


def listed_markets(chain_id: int, first: int = 30) -> list[dict]:
    """Largest Morpho markets listed in the Morpho app, by supply.

    Unlisted markets include broken ones (billions supplied against a few
    dollars of collateral), so we only offer listed ones. Idle markets (no
    collateral asset, nothing can be borrowed) are skipped too.
    """
    q = f"""query($chains: [Int!], $first: Int) {{
      markets(first: $first, orderBy: SupplyAssetsUsd, orderDirection: Desc,
              where: {{chainId_in: $chains, listed: true}}) {{ items {{ {_MARKET_FIELDS} }} }} }}"""
    if chain_id not in NETWORKS:
        return []
    items = fetch_json(URL, body={"query": q, "variables": {"chains": [chain_id], "first": first}}
                       )["data"]["markets"]["items"]
    return [m for m in items if m.get("collateralAsset")]
