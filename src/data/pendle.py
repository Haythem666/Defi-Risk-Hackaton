"""Pendle API (public, no key). Docs: https://api-v2.pendle.finance/core/docs"""

from src.data.cache import fetch_json

BASE = "https://api-v2.pendle.finance/core"


def _addr(pendle_id: str) -> str:
    """Pendle ids look like '1-0xabc...'; keep the address part."""
    return pendle_id.split("-", 1)[-1].lower()


def active_markets(chain_id: int = 1) -> list[dict]:
    return fetch_json(f"{BASE}/v1/{chain_id}/markets/active")["markets"]


def market(chain_id: int, address: str) -> dict:
    """Static info (pt/yt/sy/underlying, expiry, categories) from the active list."""
    address = address.lower()
    for m in active_markets(chain_id):
        if m["address"].lower() == address:
            return {**m, "pt": _addr(m["pt"]), "yt": _addr(m["yt"]),
                    "sy": _addr(m["sy"]), "underlyingAsset": _addr(m["underlyingAsset"])}
    raise ValueError(f"No active Pendle market {address} on chain {chain_id}")


def market_data(chain_id: int, address: str) -> dict:
    """Live numbers: liquidity, TVL, implied APY, PT discount, ..."""
    return fetch_json(f"{BASE}/v2/{chain_id}/markets/{address.lower()}/data")


def assets(chain_id: int = 1) -> dict[str, dict]:
    """All Pendle-known assets on a chain, keyed by lowercase address."""
    data = fetch_json(f"{BASE}/v3/{chain_id}/assets/all", max_age_s=24 * 3600)
    return {a["address"].lower(): a for a in data["assets"]}


def sell_quote(chain_id: int, market_address: str, token_in: str, token_out: str,
               amount_in_wei: int) -> dict:
    """Live quote from Pendle's router: price impact and fee of a swap."""
    return fetch_json(
        f"{BASE}/v2/sdk/{chain_id}/markets/{market_address.lower()}/swap",
        params={"receiver": "0x000000000000000000000000000000000000dEaD", "slippage": 0.01,
                "enableAggregator": "false", "tokenIn": token_in, "tokenOut": token_out,
                "amountIn": str(amount_in_wei)},
        max_age_s=600)["data"]
