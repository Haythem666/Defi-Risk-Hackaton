"""Morpho Blue GraphQL API (public, no key). Docs: https://docs.morpho.org/tools/offchain/api/"""

from src.data.cache import fetch_json

URL = "https://blue-api.morpho.org/graphql"

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
    body = {"query": _MARKETS_BY_COLLATERAL,
            "variables": {"assets": [asset_address.lower()], "chains": [chain_id]}}
    return fetch_json(URL, body=body)["data"]["markets"]["items"]


def market_url(chain_id: int, market_id: str) -> str:
    network = {1: "ethereum", 8453: "base"}.get(chain_id, str(chain_id))
    return f"https://app.morpho.org/{network}/market/{market_id}"
