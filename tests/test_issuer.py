from src.data.defillama import find_issuer

SUSDE = "0x9d39a5de30e57443bff2a8307a4256c8797a3497"
USDE = "0x4c9edd5852cd905f086c759e8383e09bff1e68b3"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"


def pool(project, symbol, tvl, underlying, chain="Ethereum"):
    return {"pool": project, "chain": chain, "project": project, "symbol": symbol,
            "tvlUsd": tvl, "underlyingTokens": underlying}


def test_issuer_is_the_largest_pool_minting_the_token():
    pools = [pool("ethena-usde", "SUSDE", 1.2e9, [USDE]),   # mints sUSDe from USDe
             pool("aave-v3", "SUSDE", 1.6e8, [SUSDE]),      # lends sUSDe
             pool("other", "SUSDE", 5e9, [USDE], chain="Base")]
    assert find_issuer(pools, "Ethereum", ["sUSDe"], SUSDE)["project"] == "ethena-usde"


def test_no_issuer_when_a_lender_is_the_largest_holder():
    # USDC: the largest pool lends USDC, a small project wraps it -> no issuer
    pools = [pool("maple", "USDC", 2.8e9, [USDC]),
             pool("midas-rwa", "USDC", 3e7, ["0xabc"])]
    assert find_issuer(pools, "Ethereum", ["USDC"], USDC) is None


def test_excluded_projects_and_symbol_fallback():
    pools = [pool("pendle-v2", "SUSDE", 3e9, ["0xabc"]),
             pool("ethena-usde", "USDE2", 1e9, [USDE])]
    assert find_issuer(pools, "Ethereum", ["sUSDe"], SUSDE) is None
    assert find_issuer(pools, "Ethereum", ["sUSDe", "USDe2"], SUSDE)["project"] == "ethena-usde"
