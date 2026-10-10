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


def _protocol_meta(raw: dict) -> dict:
    """Drop the TVL history, keep what describes the protocol's risk."""
    keep = ("name", "category", "audits", "audit_links", "parentProtocol", "hacks", "chains")
    return {k: raw.get(k) for k in keep}


def protocol_info(slug: str) -> dict:
    """Category, audit count and past hacks of a protocol."""
    try:
        return fetch_json(f"{BASE}/protocol/{slug}", max_age_s=24 * 3600,
                          transform=_protocol_meta)
    except Exception:
        return {}


def protocol_url(slug: str) -> str:
    return f"https://defillama.com/protocol/{slug}"


def pool_url(pool_id: str) -> str:
    return f"https://defillama.com/yields/pool/{pool_id}"


def _big_pools(raw: dict) -> list[dict]:
    """Pools with at least 1M USD of TVL, only the fields we use."""
    keep = ("pool", "chain", "project", "symbol", "tvlUsd", "underlyingTokens")
    return [{k: p.get(k) for k in keep} for p in raw["data"] if (p["tvlUsd"] or 0) >= 1e6]


def yield_pools() -> list[dict]:
    """DeFiLlama yield pools with at least 1M USD TVL (slimmed for the cache)."""
    return fetch_json(YIELDS, max_age_s=24 * 3600, transform=_big_pools)


def _slim_protocols(raw: list) -> list[dict]:
    keep = ("slug", "name", "url", "category", "tvl")
    return [{k: p.get(k) for k in keep} for p in raw if p.get("url")]


def protocols() -> list[dict]:
    """Every DeFiLlama protocol: slug, name, website, category, TVL."""
    return fetch_json(f"{BASE}/protocols", max_age_s=24 * 3600, transform=_slim_protocols)


def site(url: str) -> str:
    """Registrable domain of a URL: https://app.huma.finance/x -> huma.finance."""
    host = url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].lower()
    return ".".join(host.split(".")[-2:])


# Shared hosting: a website there says nothing about who runs the project.
SHARED_SITES = {"github.com", "github.io", "gitbook.io", "medium.com", "x.com", "twitter.com",
                "linktr.ee", "notion.site", "t.me", "discord.gg", "vercel.app", "netlify.app",
                "google.com", "substack.com", "mirror.xyz"}


def protocol_by_site(url: str) -> dict | None:
    """The largest DeFiLlama protocol whose website is on the same domain."""
    if site(url) in SHARED_SITES:
        return None
    same = [p for p in protocols() if site(p["url"]) == site(url)]
    return max(same, key=lambda p: p["tvl"] or 0, default=None)


def token_pools(pools: list[dict], chain: str, address: str) -> list[dict]:
    """Yield pools on `chain` that hold `address` (EVM addresses compared
    lowercase, others such as Solana mints as they are)."""
    a = address.lower() if address.startswith("0x") else address
    return [p for p in pools if p["chain"] == chain and a in
            [(u.lower() if u.startswith("0x") else u) for u in p.get("underlyingTokens") or []]]


def find_issuer(pools: list[dict], chain: str, symbols: list[str],
                token_address: str) -> dict | None:
    """Protocol that issues a yield-bearing token.

    For each candidate symbol, look at the largest pool holding that token on
    `chain`. It is the issuer only if it *produces* the token from something
    else (its underlying is not the token itself: Ethena turns USDe into
    sUSDe, Lido turns ETH into stETH) and is not a lender or DEX. Requiring
    the largest pool rules out small projects that merely wrap the token:
    for USDC or WBTC the largest pool is a lender, so no issuer is claimed.
    """
    token = token_address.lower()
    for symbol in symbols:
        same = [p for p in pools
                if p["chain"] == chain and (p["symbol"] or "").upper() == symbol.upper()]
        if not same:
            continue
        top = max(same, key=lambda p: p["tvlUsd"] or 0)
        underlying = [u.lower() for u in (top.get("underlyingTokens") or [])]
        if not top["project"].startswith(NOT_ISSUERS) and token not in underlying:
            return top
    return None
