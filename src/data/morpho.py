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


def vault(chain_id: int, address: str) -> dict | None:
    """One Morpho vault (v1, "MetaMorpho"): curator, fee, timelock, liquidity
    and allocation. None if the address is not a v1 vault (e.g. a Vault V2)."""
    q = f"query($a: String!, $chain: Int!) {{ vaultByAddress(address: $a, chainId: $chain) {{ {_VAULT_FIELDS} }} }}"
    data = fetch_json(URL, body={"query": q, "variables": {"a": address, "chain": chain_id}})
    return (data.get("data") or {}).get("vaultByAddress")


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


# Vault V2: the curator plugs "adapters" (where money can go) and sets caps;
# each setting has its own timelock. Selectors of the ones that matter.
V2_TIMELOCKS = {
    "0x60d54d41": "addAdapter", "0x585cd34b": "removeAdapter",
    "0xf6f98fd5": "increaseAbsoluteCap", "0x2438525b": "increaseRelativeCap",
    "0xb192a84a": "setIsAllocator", "0x5b34b823": "setAdapterRegistry",
    "0x2cb19f98": "setReceiveSharesGate", "0xc21ad028": "setSendSharesGate",
    "0x04dbf0ce": "setReceiveAssetsGate", "0x871c979c": "setSendAssetsGate",
    "0x70897b23": "setPerformanceFee", "0xfe56e232": "setManagementFee",
    "0x6a5f1aa2": "setPerformanceFeeRecipient", "0x9faae464": "setManagementFeeRecipient",
    "0x47966291": "increaseTimelock", "0x5c1a1a4f": "decreaseTimelock",
    "0x3e9d2ac7": "setForceDeallocatePenalty", "0xb2e32848": "abdicate",
}

_VAULT_V2_FIELDS = """
  address name symbol listed totalAssetsUsd liquidityUsd netApy performanceFee managementFee
  asset { symbol address price { usd } }
  curator { address }
  owner { address }
  warnings { type level }
  timelocks { selector duration }
  adapters(first: 20) { items { address type assetsUsd
    ... on MorphoMarketV1Adapter {
      positions(first: 50) { items { market { marketId } state { supplyAssetsUsd } } } }
    ... on MetaMorphoAdapter { metaMorpho { address } }
    ... on MorphoVaultV2Adapter { innerVault { address } }
  } }
"""


def vault_v2(chain_id: int, address: str) -> dict | None:
    """One Morpho Vault V2: its adapters (Morpho markets, v1 vaults, other V2
    vaults) with the USD each holds, curator, owner and per-setting timelocks."""
    q = f"query($a: String!, $chain: Int!) {{ vaultV2ByAddress(address: $a, chainId: $chain) {{ {_VAULT_V2_FIELDS} }} }}"
    data = fetch_json(URL, body={"query": q, "variables": {"a": address, "chain": chain_id}})
    return (data.get("data") or {}).get("vaultV2ByAddress")


def listed_vaults_v2(chain_id: int, first: int = 30) -> list[dict]:
    """Largest Vault V2s listed in the Morpho app, by deposits."""
    if chain_id not in NETWORKS:
        return []
    q = """query($chains: [Int!], $first: Int) {
      vaultV2s(first: $first, orderBy: TotalAssetsUsd, orderDirection: Desc,
               where: {chainId_in: $chains, listed: true}) {
        items { address name asset { symbol } totalAssetsUsd } } }"""
    data = fetch_json(URL, body={"query": q, "variables": {"chains": [chain_id], "first": first}})
    return ((data.get("data") or {}).get("vaultV2s") or {}).get("items") or []


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
