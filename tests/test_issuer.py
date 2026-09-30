from src.data.defillama import find_issuer

SUSDE = "0x9d39a5de30e57443bff2a8307a4256c8797a3497"
USDE = "0x4c9edd5852cd905f086c759e8383e09bff1e68b3"

POOLS = [
    # Ethena mints sUSDe from USDe -> issuer
    {"pool": "a", "chain": "Ethereum", "project": "ethena-usde", "symbol": "SUSDE",
     "tvlUsd": 1e9, "underlyingTokens": [USDE]},
    # Aave just lends sUSDe (underlying is sUSDe itself) -> not issuer
    {"pool": "b", "chain": "Ethereum", "project": "aave-v3", "symbol": "SUSDE",
     "tvlUsd": 2e9, "underlyingTokens": [SUSDE]},
    # Pendle is excluded by name even if underlying differs
    {"pool": "c", "chain": "Ethereum", "project": "pendle-v2", "symbol": "SUSDE",
     "tvlUsd": 3e9, "underlyingTokens": ["0xabc"]},
    # Other chain
    {"pool": "d", "chain": "Base", "project": "other", "symbol": "SUSDE",
     "tvlUsd": 4e9, "underlyingTokens": [USDE]},
]


def test_issuer_is_the_minter_not_the_lender():
    assert find_issuer(POOLS, "Ethereum", ["sUSDe"], SUSDE)["project"] == "ethena-usde"


def test_symbol_fallback_and_no_match():
    assert find_issuer(POOLS, "Ethereum", ["wstETH", "sUSDe"], SUSDE)["project"] == "ethena-usde"
    assert find_issuer(POOLS, "Ethereum", ["XYZ"], SUSDE) is None
