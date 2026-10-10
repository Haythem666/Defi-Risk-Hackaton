"""CoinGecko API (public, no key, rate-limited): a token's website, used to
find who issues a token when DeFiLlama yield pools do not say.
Docs: https://docs.coingecko.com/v3.0.1/reference/introduction
"""

from src.data.cache import fetch_json

BASE = "https://api.coingecko.com/api/v3"
DAY = 24 * 3600


def _slim_search(raw: dict) -> list[dict]:
    return [{k: c.get(k) for k in ("id", "name", "symbol")} for c in raw.get("coins") or []]


def _slim_coin(raw: dict) -> dict:
    return {"id": raw.get("id"), "name": raw.get("name"), "symbol": raw.get("symbol"),
            "homepage": next((u for u in (raw.get("links") or {}).get("homepage") or [] if u), None),
            "platforms": raw.get("platforms") or {}, "categories": raw.get("categories") or []}


def find_coin(name: str, symbol: str) -> dict | None:
    """The coin with exactly this name and symbol (first search hit), with
    its website. None if there is no exact match."""
    hits = fetch_json(f"{BASE}/search", {"query": name}, max_age_s=DAY, transform=_slim_search)
    hit = next((c for c in hits if (c["name"] or "").lower() == name.lower()
                and (c["symbol"] or "").lower() == symbol.lower()), None)
    if not hit:
        return None
    return fetch_json(f"{BASE}/coins/{hit['id']}",
                      {"localization": "false", "tickers": "false", "market_data": "false",
                       "community_data": "false", "developer_data": "false"},
                      max_age_s=DAY, transform=_slim_coin)


def coin_url(coin_id: str) -> str:
    return f"https://www.coingecko.com/en/coins/{coin_id}"
