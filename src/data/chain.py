"""Direct on-chain reads through a public JSON-RPC node, plus source
verification from Sourcify. Used to inspect oracles."""

from src.data.cache import fetch_json

RPCS = {1: "https://ethereum-rpc.publicnode.com",
        42161: "https://arbitrum-one-rpc.publicnode.com",
        8453: "https://base-rpc.publicnode.com",
        56: "https://bsc-rpc.publicnode.com",
        999: "https://rpc.hyperliquid.xyz/evm",
        9745: "https://rpc.plasma.to"}
SOURCIFY = "https://sourcify.dev/server/v2/contract"

# 4-byte function selectors (keccak256 of the signature)
PRICE = "0xa035b1fe"  # price()  (Morpho oracle interface, scaled 1e36)

# EIP-1167 minimal proxy: <prefix><20-byte implementation><suffix>
_PROXY_PREFIX = "363d3d373d3d3d363d73"


def _rpc(chain_id: int, method: str, params: list):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = fetch_json(RPCS[chain_id], body=body, max_age_s=600)
    if "error" in resp:
        raise RuntimeError(resp["error"].get("message"))
    return resp["result"]


def _slim_batch(resp):
    """Bytecode is only checked for presence: keep its start, not 20 KB of it."""
    if isinstance(resp, list):
        for r in resp:
            if isinstance(r.get("result"), str) and len(r["result"]) > 2048:
                r["result"] = r["result"][:2048]
    return resp


def batch(chain_id: int, calls: list[tuple[str, list]]) -> list:
    """Several JSON-RPC calls in one request. Returns each call's result, or
    None where it failed (e.g. the contract has no such function)."""
    body = [{"jsonrpc": "2.0", "id": i, "method": m, "params": p}
            for i, (m, p) in enumerate(calls)]
    resp = fetch_json(RPCS[chain_id], body=body, max_age_s=600, transform=_slim_batch)
    by_id = {r.get("id"): r for r in resp} if isinstance(resp, list) else {}
    return [by_id.get(i, {}).get("result") for i in range(len(calls))]


def contract_info(chain_id: int, address: str) -> dict:
    """Sourcify: is the source code public, and the contract's name."""
    try:
        r = fetch_json(f"{SOURCIFY}/{chain_id}/{address}", {"fields": "compilation.name"},
                       max_age_s=24 * 3600)
    except Exception:
        return {"verified": False, "name": None}
    return {"verified": bool(r.get("match")),
            "name": (r.get("compilation") or {}).get("name")}


def eth_call(chain_id: int, to: str, data: str) -> str:
    return _rpc(chain_id, "eth_call", [{"to": to, "data": data}, "latest"])


def proxy_implementation(chain_id: int, address: str) -> str | None:
    """Implementation address if `address` is an EIP-1167 minimal proxy."""
    code = _rpc(chain_id, "eth_getCode", [address, "latest"])
    i = code.find(_PROXY_PREFIX)
    return "0x" + code[i + 20:i + 60] if i >= 0 else None


def is_verified(chain_id: int, address: str) -> bool:
    """True if the contract's source code is published on Sourcify."""
    try:
        r = fetch_json(f"{SOURCIFY}/{chain_id}/{address}", max_age_s=24 * 3600)
    except Exception:
        return False
    return bool(r.get("match"))


def morpho_oracle_price(chain_id: int, oracle: str, collateral_decimals: int,
                        loan_decimals: int) -> float:
    """Price of 1 collateral token in loan tokens, per the Morpho oracle."""
    raw = int(eth_call(chain_id, oracle, PRICE), 16)
    return raw / 10 ** (36 + loan_decimals - collateral_decimals)
