"""Hyperliquid info API (public, no key): vaults trading on the Hyperliquid
perp exchange. Docs: https://hyperliquid.gitbook.io/hyperliquid-docs"""

from collections import defaultdict

from src.data.cache import fetch_json

URL = "https://api.hyperliquid.xyz/info"
DOCS = "https://hyperliquid.gitbook.io/hyperliquid-docs"
HLP = "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"  # Hyperliquidity Provider vault

# Withdrawal lock-up after a deposit (Hyperliquid docs, vaults section).
LOCKUP_DAYS_HLP = 4
LOCKUP_DAYS_USER_VAULT = 1


def _info(body: dict):
    return fetch_json(URL, body=body, max_age_s=600)


def vault_details(address: str) -> dict:
    return _info({"type": "vaultDetails", "vaultAddress": address.lower()})


def vault_positions(address: str) -> tuple[float, dict[str, float]]:
    """(account value USD, {coin: absolute position notional USD}).

    A parent vault like HLP trades through child vaults: their positions
    and account values are added up."""
    details = vault_details(address)
    rel = details.get("relationship") or {}
    accounts = (rel.get("data") or {}).get("childAddresses") if rel.get("type") == "parent" else None
    accounts = accounts or [address.lower()]
    value, notional = 0.0, defaultdict(float)
    for acct in accounts:
        state = _info({"type": "clearinghouseState", "user": acct})
        value += float(state["marginSummary"]["accountValue"])
        for p in state["assetPositions"]:
            notional[p["position"]["coin"]] += abs(float(p["position"]["positionValue"]))
    return value, dict(notional)


def vault_url(address: str) -> str:
    return f"https://app.hyperliquid.xyz/vaults/{address}"
