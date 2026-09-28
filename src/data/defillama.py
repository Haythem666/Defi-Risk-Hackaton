"""DeFiLlama API (public, no key). Docs: https://defillama.com/docs/api"""

from src.data.cache import fetch_json

BASE = "https://api.llama.fi"


def protocol_tvl(slug: str) -> float:
    """Current TVL in USD of a protocol, e.g. 'pendle', 'ethena-usde'."""
    return float(fetch_json(f"{BASE}/tvl/{slug}"))


def protocol_url(slug: str) -> str:
    return f"https://defillama.com/protocol/{slug}"
