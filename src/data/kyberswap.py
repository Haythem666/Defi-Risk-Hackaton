"""KyberSwap aggregator (public, no key): what selling a token returns over
every DEX of a chain at once. Used to check whether liquidators could sell a
lending market's collateral.
Docs: https://docs.kyberswap.com/kyberswap-solutions/kyberswap-aggregator/aggregator-api-specification/evm-swaps
"""

from src.data.cache import fetch_json

URL = "https://aggregator-api.kyberswap.com/{chain}/api/v1/routes"
CHAINS = {1: "ethereum", 42161: "arbitrum", 8453: "base", 56: "bsc"}


def _slim(raw: dict) -> dict:
    s = (raw.get("data") or {}).get("routeSummary") or {}
    return {"amountIn": s.get("amountIn"), "amountOut": s.get("amountOut"),
            "dexes": sorted({hop["exchange"] for path in s.get("route") or [] for hop in path})}


def sell_quote(chain_id: int, token_in: str, token_out: str, amount_raw: int) -> dict | None:
    """Best route to sell `amount_raw` (smallest units) of `token_in` for
    `token_out`: {"amountIn", "amountOut" (raw), "dexes"}. None if the chain
    is not covered."""
    if chain_id not in CHAINS:
        return None
    return fetch_json(URL.format(chain=CHAINS[chain_id]),
                      {"tokenIn": token_in, "tokenOut": token_out, "amountIn": str(amount_raw)},
                      max_age_s=600, transform=_slim)


def route_url(chain_id: int, token_in: str, token_out: str) -> str:
    return f"https://kyberswap.com/swap/{CHAINS.get(chain_id, chain_id)}/{token_in}-to-{token_out}"
