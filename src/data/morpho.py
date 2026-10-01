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


_VAULT_FIELDS = """
  address
  name
  listed
  asset { symbol address price { usd } }
  liquidity { usd }
  warnings { type level }
  state { totalAssetsUsd netApy fee timelock guardian curators { name }
          allocation { supplyAssetsUsd market { marketId } } }
"""


def vault(chain_id: int, address: str) -> dict:
    """One Morpho vault: curator, fee, timelock, liquidity and allocation."""
    q = f"query($a: String!, $chain: Int!) {{ vaultByAddress(address: $a, chainId: $chain) {{ {_VAULT_FIELDS} }} }}"
    return fetch_json(URL, body={"query": q, "variables": {"a": address, "chain": chain_id}}
                      )["data"]["vaultByAddress"]


def listed_vaults(chain_id: int, first: int = 30) -> list[dict]:
    """Largest vaults listed in the Morpho app, by deposits."""
    if chain_id not in NETWORKS:
        return []
    q = """query($chains: [Int!], $first: Int) {
      vaults(first: $first, orderBy: TotalAssetsUsd, orderDirection: Desc,
             where: {chainId_in: $chains, listed: true}) {
        items { address name asset { symbol } state { totalAssetsUsd } } } }"""
    return fetch_json(URL, body={"query": q, "variables": {"chains": [chain_id], "first": first}}
                      )["data"]["vaults"]["items"]


def vault_url(chain_id: int, address: str) -> str:
    return f"https://app.morpho.org/{NETWORKS.get(chain_id, chain_id)}/vault/{address}"


def collateral_at_risk(chain_id: int, market_id: str, points: int = 20) -> list[tuple[float, float]]:
    """[(price ratio, USD of collateral liquidatable at that price), ...].
    A ratio of 0.95 means the collateral price falls 5% from now."""
    if chain_id not in NETWORKS:
        return []
    q = """query($id: String!, $chain: Int!, $n: Int) {
      marketCollateralAtRisk(uniqueKey: $id, chainId: $chain, numberOfPoints: $n) {
        collateralAtRisk { collateralPriceRatio collateralUsd } } }"""
    data = fetch_json(URL, body={"query": q, "variables": {"id": market_id, "chain": chain_id,
                                                           "n": points}})
    rows = (((data.get("data") or {}).get("marketCollateralAtRisk") or {})
            .get("collateralAtRisk") or [])
    return [(r["collateralPriceRatio"], r["collateralUsd"] or 0.0) for r in rows]


def liquidated_at(curve: list[tuple[float, float]], price_ratio: float) -> float:
    """USD liquidated if the collateral price falls to `price_ratio` (0..1)."""
    eligible = [usd for ratio, usd in curve if ratio >= price_ratio - 1e-9]
    return max(eligible, default=0.0)
