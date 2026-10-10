"""Generic on-chain crawler: finds what any contract depends on by asking the
contract itself, with no protocol-specific API.

Every token, vault or oracle is a smart contract, and its code stores the
addresses of the contracts it uses: an ERC-4626 vault's asset(), a Pendle
PT's SY(), a Morpho oracle's BASE_FEED_1(), a Morpho vault's MORPHO() and
supplyQueue. The crawler asks each contract these standard questions in one
batched RPC call, adds an edge for every answer, and repeats from the new
addresses (breadth-first, depth-limited).

It also reads who controls each contract (owner, curator, guardian, the
EIP-1967 upgrade admin), what kind of controller that is (one wallet, a Safe
multisig and its threshold, a timelock and its delay) and flags weak control.

Run: python -m src.graph.crawler <chain_id> <address>
"""

import sys
from collections import deque

from src.data import chain
from src.graph.common import add_chain, chain_name, explorer
from src.schemas import DependencyGraph, Edge, Node, Position

MAX_DEPTH = 4          # links are followed up to this many hops from the position
MAX_CONTRACTS = 40     # stop exploring after this many contracts
MIN_ALLOCATION_SHARE = 0.01  # vault allocations below this share are left out
# Plain base assets: their own risk is a depeg, not worth crawling into.
BASE_ASSETS = {"USDC", "USDT", "DAI", "USDS", "WETH", "WBTC", "CBBTC", "WSTETH", "STETH"}

# keccak256 selectors of the standard questions (no arguments)
SEL = {
    "asset": "0x38d52e0f", "UNDERLYING_ASSET_ADDRESS": "0xb16a19de", "yieldToken": "0x76d5de85",
    "SY": "0xafd27bf5", "readTokens": "0x2c8ce6bc", "minter": "0x07546172", "MORPHO": "0x3acb5624",
    "oracle": "0x7dc0d1d0", "aggregator": "0x245a7bfc", "token0": "0x0dfe1681", "token1": "0xd21220a7",
    "BASE_VAULT": "0xeaa2d7b4", "BASE_FEED_1": "0xf50a4718", "BASE_FEED_2": "0xdc53858c",
    "QUOTE_VAULT": "0x2e6f20a6", "QUOTE_FEED_1": "0x56095e11", "QUOTE_FEED_2": "0xacfbd39e",
    "owner": "0x8da5cb5b", "admin": "0xf851a440", "curator": "0xe66f53b7", "guardian": "0x452a9320",
    "timelock": "0xd33219b4", "cooldownDuration": "0x35269315", "totalAssets": "0x01e1d114",
    "supplyQueueLength": "0xa17b3130", "symbol": "0x95d89b41", "name": "0x06fdde03",
    "decimals": "0x313ce567", "description": "0x7284e416", "latestRoundData": "0xfeaf968c",
}
CONTROLLER_SEL = {"getThreshold": "0xe75235b8", "getOwners": "0xa0e67e2b",
                  "getMinDelay": "0xf27a0c92", "owner": "0x8da5cb5b"}
SUPPLY_QUEUE, ID_TO_PARAMS, MARKET, POSITION = "0xf7d18521", "0x2c3c9157", "0x5c60e39a", "0x93c52062"

# EIP-1967 storage slots of upgradeable proxies
IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"

# question -> (edge kind, exposure, what the answer means)
FEED = ("priced_by", 1.0, "Morpho oracle: the price is built from this feed")
LINKS = {
    "asset": ("holds", 1.0, "ERC-4626: deposits are held in this token"),
    "UNDERLYING_ASSET_ADDRESS": ("holds", 1.0, "Aave aToken: a claim on this token"),
    "yieldToken": ("holds", 1.0, "Pendle SY: wraps this yield-bearing token"),
    "SY": ("redeems_into", 1.0, "Pendle PT: redeems into this SY at maturity"),
    "minter": ("minted_by", 1.0, "only this contract can create new tokens"),
    "MORPHO": ("deposits_in", 1.0, "Morpho vault: lends through this Morpho contract"),
    "oracle": ("priced_by", 1.0, "reads its price from this oracle"),
    "aggregator": ("reads_from", 1.0, "Chainlink proxy: answers come from this aggregator"),
    "token0": ("holds", 0.5, "AMM pool: holds this token"),
    "token1": ("holds", 0.5, "AMM pool: holds this token"),
    "BASE_VAULT": FEED, "BASE_FEED_1": FEED, "BASE_FEED_2": FEED,
    "QUOTE_VAULT": FEED, "QUOTE_FEED_1": FEED, "QUOTE_FEED_2": FEED,
}
ROLES = {"owner": "owned_by", "admin": "administered_by", "curator": "curated_by",
         "guardian": "guarded_by"}


# --- ABI decoding -----------------------------------------------------------

def _words(raw: str | None) -> list[str]:
    if not raw or raw == "0x":
        return []
    h = raw[2:]
    return [h[i:i + 64] for i in range(0, len(h) - 63, 64)]


def _addr(word: str | None) -> str | None:
    if not word or len(word) != 64 or word[:24] != "0" * 24 or int(word, 16) == 0:
        return None
    return "0x" + word[24:]


def _uint(raw: str | None) -> int | None:
    w = _words(raw)
    return int(w[0], 16) if len(w) == 1 else None


def _string(raw: str | None) -> str | None:
    """ABI string, or bytes32 for old tokens."""
    w = _words(raw)
    try:
        if len(w) >= 3:
            n = int(w[1], 16)
            text = bytes.fromhex("".join(w[2:]))[:n].decode()
        elif len(w) == 1:
            text = bytes.fromhex(w[0]).rstrip(b"\0").decode()
        else:
            return None
    except (ValueError, UnicodeDecodeError):
        return None
    return text if text.isprintable() and text else None


def _short(a: str) -> str:
    return f"{a[:6]}…{a[-4:]}"


# --- reading one contract ---------------------------------------------------

def _probe(cid: int, a: str) -> dict:
    """Ask a contract every standard question in one request."""
    calls = [("eth_getStorageAt", [a, IMPL_SLOT, "latest"]),
             ("eth_getStorageAt", [a, ADMIN_SLOT, "latest"])]
    calls += [("eth_call", [{"to": a, "data": s}, "latest"]) for s in SEL.values()]
    res = chain.batch(cid, calls)
    out = dict(zip(SEL, res[2:]))
    out["_impl"] = _addr((res[0] or "")[2:])
    out["_admin"] = _addr((res[1] or "")[2:])
    return out


def controller(cid: int, a: str, hops: int = 2) -> dict:
    """What kind of thing controls a contract: one wallet (EOA), a Safe
    multisig, a timelock, or a contract owned by one of those."""
    calls = [("eth_getCode", [a, "latest"])]
    calls += [("eth_call", [{"to": a, "data": s}, "latest"]) for s in CONTROLLER_SEL.values()]
    code, threshold, owners, delay, owner = chain.batch(cid, calls)
    c = {"address": a}
    if not code or code == "0x":
        return {**c, "kind": "EOA", "label": f"Wallet {_short(a)} (one private key)"}
    k, w = _uint(threshold), _words(owners)
    if k is not None and len(w) >= 2:
        n = int(w[1], 16)
        return {**c, "kind": "Safe", "threshold": k, "signers": n,
                "label": f"Safe {k}/{n} {_short(a)}"}
    d = _uint(delay)
    if d is not None:
        return {**c, "kind": "Timelock", "delay_s": d,
                "label": f"Timelock {d / 86400:.1f}d {_short(a)}"}
    o = _addr((_words(owner) or [None])[0])
    if o and hops > 0 and o != a:  # e.g. a ProxyAdmin: what matters is who owns it
        inner = controller(cid, o, hops - 1)
        return {**inner, "via": a, "label": f"{inner['label']} via {_short(a)}"}
    return {**c, "kind": "contract", "label": f"Contract {_short(a)}"}


def control_flags(role: str, ctrl: dict) -> list[str]:
    if ctrl["kind"] == "EOA":
        return [f"{role} is a single wallet: one stolen key controls it"]
    if ctrl["kind"] == "Safe" and ctrl["threshold"] <= 2:
        return [f"{role} is a {ctrl['threshold']}-of-{ctrl['signers']} multisig"]
    return []


def _vault_markets(cid: int, vault: str, morpho: str, n: int, total: int) -> list[dict]:
    """A Morpho vault's markets and the share of the vault in each, read
    from the vault's supplyQueue and Morpho's market and position storage."""
    ids = [(_words(r) or [None])[0] for r in chain.batch(cid, [
        ("eth_call", [{"to": vault, "data": SUPPLY_QUEUE + f"{i:064x}"}, "latest"]) for i in range(n)])]
    ids = [i for i in ids if i]
    calls = []
    for i in ids:
        for sel, arg in ((ID_TO_PARAMS, i), (MARKET, i), (POSITION, i + "0" * 24 + vault[2:])):
            calls.append(("eth_call", [{"to": morpho, "data": sel + arg}, "latest"]))
    res = chain.batch(cid, calls)
    out = []
    for j, i in enumerate(ids):
        params, market, position = (_words(r) for r in res[3 * j:3 * j + 3])
        if len(params) < 5 or len(market) < 4 or len(position) < 1:
            continue
        supply_assets, supply_shares, borrow_assets = (int(x, 16) for x in market[:3])
        assets = int(position[0], 16) * supply_assets // supply_shares if supply_shares else 0
        out.append({"id": "0x" + i, "loan": _addr(params[0]), "collateral": _addr(params[1]),
                     "oracle": _addr(params[2]), "lltv": int(params[4], 16) / 1e18,
                     "share": assets / total if total else 0.0,
                     "utilization": borrow_assets / supply_assets if supply_assets else 0.0})
    return out


# --- the crawl --------------------------------------------------------------

def _kind(p: dict) -> str:
    if p.get("supplyQueueLength"):
        return "vault"
    if p.get("BASE_FEED_1") or p.get("aggregator") or (
            p.get("latestRoundData") and not _string(p.get("symbol"))):
        return "oracle"
    if p.get("readTokens"):
        return "market"
    if _string(p.get("symbol")) and _uint(p.get("decimals")) is not None:
        return "asset"
    return "protocol"


def crawl(cid: int, root: str) -> tuple[dict, list, dict]:
    """Breadth-first walk from `root`. Returns (contracts, links, controllers):
    contracts[address] = what we read; links = (source, target, kind,
    exposure, evidence); controllers[address] = who/what controls."""
    root = root.lower()
    contracts: dict[str, dict] = {}
    links: list[tuple] = []
    controllers: dict[str, dict] = {}
    queue = deque([(root, 0)])
    seen = {root}

    def follow(src: str, dst: str | None, depth: int, kind: str, exposure: float, why: str):
        if not dst or dst == src:
            return
        links.append((src, dst, kind, exposure, why))
        if dst not in seen:
            seen.add(dst)
            queue.append((dst, depth + 1))

    while queue:
        a, depth = queue.popleft()
        p = _probe(cid, a)
        info = chain.contract_info(cid, p["_impl"] or a)
        c = {"address": a, "depth": depth, "kind": _kind(p), "verified": info["verified"],
             "contract_name": info["name"], "symbol": _string(p.get("symbol")),
             "name": _string(p.get("name")), "description": _string(p.get("description")),
             "implementation": p["_impl"], "flags": []}
        contracts[a] = c
        if not info["verified"]:
            c["flags"].append("source code not published (Sourcify)")
        cd = _uint(p.get("cooldownDuration"))
        if cd:
            c["cooldown_s"] = cd
            c["flags"].append(f"withdrawals wait {cd / 86400:.1f} days (cooldown)")
        c["redeemable"] = bool(_addr((_words(p.get("asset")) or [None])[0]))

        base = (c["symbol"] or "").upper() in BASE_ASSETS
        expand = depth < MAX_DEPTH and len(contracts) + len(queue) < MAX_CONTRACTS and not base
        c["base_asset"] = base
        if not expand:
            continue

        # Dependencies: every standard question that returns an address.
        for fn, (kind, exposure, why) in LINKS.items():
            if fn == "asset" and p.get("yieldToken"):  # Pendle SY: yieldToken() is the real holding
                continue
            dst = _addr((_words(p.get(fn)) or [None])[0])
            follow(a, dst, depth, kind, exposure,
                   f"{fn}() on {explorer(cid, a)} returns {dst} ({why})")
        tokens = _words(p.get("readTokens"))
        for label, w in zip(("SY", "PT"), tokens[:2]):
            follow(a, _addr(w), depth, "holds", 0.5,
                   f"readTokens() on {explorer(cid, a)}: the pool holds {label} {_addr(w)}")

        # Control: who can change this contract, and how safely.
        roles = {fn: _addr((_words(p.get(fn)) or [None])[0]) for fn in ROLES}
        t = _uint(p.get("timelock"))
        if t is not None and t >= 2 ** 64:  # an address, not a delay
            roles["timelock"], t = _addr(_words(p.get("timelock"))[0]), None
        if p["_impl"]:
            roles["upgrade admin"] = p["_admin"] or roles.get("owner")
            who = roles["upgrade admin"]
            c["flags"].append("upgradeable proxy: its code can be replaced"
                              + (f" by {_short(who)}" if who else ""))
        if t is not None and c["kind"] == "vault":
            c["timelock_s"] = t
            if t < 86400:
                c["flags"].append(f"timelock {t / 3600:.0f}h: changes apply before "
                                  f"depositors can react")
        c["controllers"] = {}
        for role, who in roles.items():
            if not who:
                continue
            if who not in controllers:
                controllers[who] = controller(cid, who)
            c["controllers"][role] = who
            c["flags"] += control_flags(role, controllers[who])

        # A Morpho vault: unroll its markets with the share of the vault in each.
        morpho = _addr((_words(p.get("MORPHO")) or [None])[0])
        n = _uint(p.get("supplyQueueLength"))
        if morpho and n:
            total = _uint(p.get("totalAssets")) or 0
            for m in _vault_markets(cid, a, morpho, min(n, 30), total):
                if not m["collateral"] or m["share"] < MIN_ALLOCATION_SHARE:
                    continue
                mid = f"morpho:{m['id']}"
                contracts[mid] = {"address": m["id"], "kind": "lending", "depth": depth + 1,
                                  "market": m, "flags": []}
                url = f"https://app.morpho.org/ethereum/market/{m['id']}" if cid == 1 else \
                    explorer(cid, morpho)
                links.append((a, mid, "supplied_to", m["share"],
                              f"supplyQueue of {explorer(cid, a)}: {m['share']:.0%} of the vault "
                              f"is lent in market {m['id'][:10]} (Morpho position read on-chain)"))
                links.append((mid, morpho, "runs_on", 1.0, url))
                util = min(1.0, m["utilization"])
                follow(mid, m["collateral"], depth + 1, "secured_by", util,
                       f"Market {m['id'][:10]} collateral; {util:.0%} of supply is lent out: {url}")
                follow(mid, m["oracle"], depth + 1, "priced_by", util,
                       f"Market {m['id'][:10]} oracle: {url}")
    return contracts, links, controllers


# --- crawl -> DependencyGraph -----------------------------------------------

def _label(c: dict) -> str:
    if c["kind"] == "asset":
        return c["symbol"]
    if c["kind"] == "vault":
        return c["name"] or c["contract_name"] or _short(c["address"])
    if c["kind"] == "oracle":
        return f"Oracle {c['description'] or c['contract_name'] or ''} {_short(c['address'])}".replace("  ", " ")
    return f"{c['contract_name'] or 'Contract'} {_short(c['address'])}"


def build_contract(pos: Position) -> DependencyGraph:
    cid, cname = pos.chain_id, chain_name(pos.chain_id)
    contracts, links, controllers = crawl(cid, pos.market_address)
    ids = {a: f"{c['kind']}:{a}" for a, c in contracts.items()}

    nodes: list[Node] = []
    edges: list[Edge] = []
    for a, c in contracts.items():
        meta = {k: v for k, v in c.items() if k not in ("kind", "market")}
        if c["kind"] == "lending":
            m = c["market"]
            sym = lambda x: (contracts.get(x) or {}).get("symbol") or _short(x)  # noqa: E731
            name = f"Morpho {sym(m['collateral'])}/{sym(m['loan'])}"
            meta.update(lltv=m["lltv"], utilization=m["utilization"], market_id=m["id"])
        else:
            name = _label(c)
        nodes.append(Node(ids[a], c["kind"], name, cname, meta))
    for a, ctrl in controllers.items():
        nodes.append(Node(f"admin:{a}", "admin", ctrl["label"], cname, dict(ctrl)))

    root = contracts[pos.market_address.lower()]
    pos_id = f"position:{root['address']}"
    nodes.append(Node(pos_id, "position", f"Hold {_label(root)}", cname,
                      {"size_usd": pos.size_usd}))
    edges.append(Edge(pos_id, add_chain(nodes, cid), "settles_on", 1.0, explorer(cid, root["address"])))
    edges.append(Edge(pos_id, ids[root["address"]], "holds", 1.0, explorer(cid, root["address"])))

    for src, dst, kind, exposure, why in links:
        edges.append(Edge(ids[src], ids[dst], kind, round(exposure, 3), why))
    for a, c in contracts.items():
        for role, who in (c.get("controllers") or {}).items():
            edges.append(Edge(ids[a], f"admin:{who}", ROLES.get(role, f"{role}_is"), 1.0,
                              f"{role} of {explorer(cid, a)} is {who} (read on-chain)"))

    # Risk bookkeeping for the model (see risk/assumptions.py):
    by_id = {n.id: n for n in nodes}
    for e in edges:
        src, dst = by_id[e.source], by_id[e.target]
        # a token that wraps another: its own risk is its code, the peg is the wrapped token's
        if src.type == "asset" and e.kind in ("holds", "redeems_into") and dst.type == "asset":
            src.meta["wraps"] = dst.id
        # the aggregator behind an oracle proxy is the same price feed: count it once
        if src.type == "oracle" and dst.type == "oracle":
            dst.meta.setdefault("part_of", src.id)
    return DependencyGraph(position_id=pos_id, nodes=nodes, edges=edges)


if __name__ == "__main__":
    g = build_contract(Position(int(sys.argv[1]), sys.argv[2], 1e6, kind="contract"))
    names = {n.id: n.name for n in g.nodes}
    for e in g.edges:
        print(f"{names[e.source]:<40} --{e.kind} {e.exposure:.0%}--> {names[e.target]}")
    print("\nRed flags:")
    for n in g.nodes:
        for f in n.meta.get("flags") or []:
            print(f"  {n.name}: {f}")
