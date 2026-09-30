"""DeFiLlama API (public, no key). Docs: https://defillama.com/docs/api"""

from src.data.cache import fetch_json

BASE = "https://api.llama.fi"
YIELDS = "https://yields.llama.fi/pools"

# Projects that hold or trade a token without issuing it.
NOT_ISSUERS = ("pendle", "aave", "morpho", "euler", "spark", "fluid", "compound",
               "uniswap", "curve", "balancer", "convex", "yearn", "beefy")


def protocol_tvl(slug: str) -> float:
    """Current TVL in USD of a protocol, e.g. 'pendle', 'ethena-usde'."""
    return float(fetch_json(f"{BASE}/tvl/{slug}"))


def protocol_url(slug: str) -> str:
    return f"https://defillama.com/protocol/{slug}"


def pool_url(pool_id: str) -> str:
    return f"https://defillama.com/yields/pool/{pool_id}"


def _issuer_pools(raw: dict) -> list[dict]:
    """Keep only pools that could be an issuer, and only the fields we use."""
    keep = ("pool", "chain", "project", "symbol", "tvlUsd", "underlyingTokens")
    return [{k: p.get(k) for k in keep} for p in raw["data"]
            if not p["project"].startswith(NOT_ISSUERS)]


def yield_pools() -> list[dict]:
    """DeFiLlama yield pools that could issue a token (slimmed for the cache)."""
    return fetch_json(YIELDS, max_age_s=24 * 3600, transform=_issuer_pools)


def find_issuer(pools: list[dict], chain: str, symbols: list[str],
                token_address: str) -> dict | None:
    """Protocol that issues a yield-bearing token.

    Among pools on `chain` whose symbol is one of `symbols`, the issuer is
    the one that *produces* the token from something else: its underlying is
    not the token itself (Ethena turns USDe into sUSDe, Lido turns ETH into
    stETH). Lending markets and DEXs just hold the token, so they are skipped.
    The largest such pool by TVL wins.
    """
    wanted = {s.upper() for s in symbols}
    token = token_address.lower()
    candidates = [
        p for p in pools
        if p["chain"] == chain and (p["symbol"] or "").upper() in wanted
        and not p["project"].startswith(NOT_ISSUERS)
        and token not in [u.lower() for u in (p.get("underlyingTokens") or [])]
    ]
    return max(candidates, key=lambda p: p["tvlUsd"] or 0, default=None)
