"""Morpho GraphQL API (public, no key). Docs: https://docs.morpho.org/tools/offchain/api/

Every function sends ONE GraphQL query: a text that lists exactly the fields
we want back. The API answers with those fields, as JSON. All calls go
through cache.fetch_json (saved in data/cache/, logged).
"""

from src.data.cache import fetch_json

URL = "https://blue-api.morpho.org/graphql"

# Chains where Morpho runs, and their name in app.morpho.org URLs.
NETWORKS = {1: "ethereum", 42161: "arbitrum", 8453: "base", 999: "hyperevm"}
CHAINS = {1: "Ethereum", 42161: "Arbitrum", 8453: "Base", 999: "HyperEVM"}


def _ask(query: str, variables: dict, field: str):
    """Send a query, return data[field] (None if the API found nothing)."""
    data = fetch_json(URL, body={"query": query, "variables": variables})
    return (data.get("data") or {}).get(field)


# --- One lending market --------------------------------------------------------

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


def market(chain_id: int, market_id: str) -> dict | None:
    """One Morpho market: what is lent, against which collateral, priced by
    which oracle, and how much of it is borrowed (utilization)."""
    q = f"query($id: String!, $chain: Int!) {{ marketById(marketId: $id, chainId: $chain) {{ {_MARKET_FIELDS} }} }}"
    return _ask(q, {"id": market_id, "chain": chain_id}, "marketById")


def listed_markets(chain_id: int, first: int = 30) -> list[dict]:
    """Largest markets shown in the Morpho app (for the app's menu)."""
    q = f"""query($chains: [Int!], $first: Int) {{
      markets(first: $first, orderBy: SupplyAssetsUsd, orderDirection: Desc,
              where: {{chainId_in: $chains, listed: true}}) {{ items {{ {_MARKET_FIELDS} }} }} }}"""
    items = (_ask(q, {"chains": [chain_id], "first": first}, "markets") or {}).get("items") or []
    return [m for m in items if m.get("collateralAsset")]  # skip idle markets (nothing to borrow)


def market_url(chain_id: int, market_id: str) -> str:
    return f"https://app.morpho.org/{NETWORKS.get(chain_id, chain_id)}/market/{market_id}"


# --- Vaults v1 ("MetaMorpho") ------------------------------------------------

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
    """A v1 vault: curator, fee, timelock, liquidity and how much it has in
    each market (allocation). None if the address is not a v1 vault."""
    q = f"query($a: String!, $chain: Int!) {{ vaultByAddress(address: $a, chainId: $chain) {{ {_VAULT_FIELDS} }} }}"
    return _ask(q, {"a": address, "chain": chain_id}, "vaultByAddress")


def listed_vaults(chain_id: int, first: int = 30) -> list[dict]:
    q = """query($chains: [Int!], $first: Int) {
      vaults(first: $first, orderBy: TotalAssetsUsd, orderDirection: Desc,
             where: {chainId_in: $chains, listed: true}) {
        items { address name asset { symbol } state { totalAssetsUsd } } } }"""
    return (_ask(q, {"chains": [chain_id], "first": first}, "vaults") or {}).get("items") or []


# --- Vaults V2 ---------------------------------------------------------------

# A V2 vault reaches markets through "adapters", and each of the curator's
# powers has its own timelock, identified by a function selector.
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
    """A V2 vault: its adapters (Morpho markets, v1 vaults, other V2 vaults)
    with the USD each holds, curator, owner and per-setting timelocks."""
    q = f"query($a: String!, $chain: Int!) {{ vaultV2ByAddress(address: $a, chainId: $chain) {{ {_VAULT_V2_FIELDS} }} }}"
    return _ask(q, {"a": address, "chain": chain_id}, "vaultV2ByAddress")


def listed_vaults_v2(chain_id: int, first: int = 30) -> list[dict]:
    q = """query($chains: [Int!], $first: Int) {
      vaultV2s(first: $first, orderBy: TotalAssetsUsd, orderDirection: Desc,
               where: {chainId_in: $chains, listed: true}) {
        items { address name asset { symbol } totalAssetsUsd } } }"""
    return (_ask(q, {"chains": [chain_id], "first": first}, "vaultV2s") or {}).get("items") or []


def vault_url(chain_id: int, address: str) -> str:
    return f"https://app.morpho.org/{NETWORKS.get(chain_id, chain_id)}/vault/{address}"
