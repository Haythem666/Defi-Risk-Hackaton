"""Kamino API (Solana lending; public, no key). Docs: https://api.kamino.finance/documentation

Two kinds of Kamino positions:
- an Earn vault ("kvault"): a curator spreads deposits over lending reserves,
- a reserve: one token's lending pool inside a Kamino market; borrowers of
  that token post the market's other reserves as collateral.
"""

from src.data.cache import fetch_json

BASE = "https://api.kamino.finance"
CHAIN_ID = 101  # Solana, as this project numbers it (not an EVM chain id)


def _slim_vaults(raw: list) -> list[dict]:
    """Keep what the graph needs: the full list is several MB."""
    out = []
    for v in raw:
        st = v["state"]
        out.append({"address": v["address"], "name": st.get("name"),
                    "token_mint": st["tokenMint"], "decimals": st["tokenMintDecimals"],
                    "admin": st.get("vaultAdminAuthority"), "allocation_admin": st.get("allocationAdmin"),
                    "performance_fee": int(st.get("performanceFeeBps") or 0) / 1e4,
                    "management_fee": int(st.get("managementFeeBps") or 0) / 1e4,
                    "allocations": [{"reserve": a["reserve"], "ctokens": int(a["ctokenAllocation"])}
                                    for a in st["vaultAllocationStrategy"]
                                    if int(a["ctokenAllocation"] or 0) > 0]})
    return out


def vaults() -> list[dict]:
    return fetch_json(f"{BASE}/kvaults/vaults", transform=_slim_vaults)


def vault(address: str) -> dict | None:
    return next((v for v in vaults() if v["address"] == address), None)


def vault_metrics(address: str) -> dict:
    """AUM, tokens available to withdraw, APY, number of holders."""
    return fetch_json(f"{BASE}/kvaults/{address}/metrics")


def markets() -> list[dict]:
    """Every Kamino lending market: name and address."""
    return fetch_json(f"{BASE}/v2/kamino-market", max_age_s=24 * 3600)


def reserves(market: str) -> list[dict]:
    """The reserves of one market: token, supply, borrow (USD), max LTV.
    A reserve with max LTV > 0 can be posted as collateral."""
    return fetch_json(f"{BASE}/kamino-market/{market}/reserves/metrics")


def reserve_index() -> dict[str, tuple[dict, dict]]:
    """reserve address -> (its market, its metrics), over every market."""
    out = {}
    for m in markets():
        try:
            rows = reserves(m["lendingMarket"])
        except Exception:
            continue
        for r in rows:
            out[r["reserve"]] = (m, r)
    return out


def vault_url(address: str) -> str:
    return f"{BASE}/kvaults/vaults/{address}"


def market_url(market: str) -> str:
    return f"{BASE}/kamino-market/{market}/reserves/metrics"
