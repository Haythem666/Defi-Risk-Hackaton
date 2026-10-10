"""Dependency graph of a Kamino position (Solana), from the Kamino API.

    position --deposited_in--> Earn vault --allocates_to (share)--> reserve
    reserve (a token's lending pool in a Kamino market)
        --secured_by (utilization x collateral share)--> each collateral of the market
    collateral --issued_by--> issuer (DeFiLlama) --> off-chain backing, when it applies
    collateral --also_collateral_in--> other lenders (contagion)

Like an Aave pool: borrowers of the reserve's token may post any collateral
reserve of the same market, so the lender's exposure to one collateral is
utilization x that collateral's share of the market's collateral. Kamino
oracles (Scope/Pyth) and the Solana programs' upgrade authorities are not
read: Solana is not reachable through the EVM RPC helpers.

The position address is either an Earn vault or a reserve (supplying to it).
"""

from src.data import kamino
from src.graph.collateral import _add_other_holders, add_contagion
from src.graph.common import (MIN_COLLATERAL_USD, add_asset, add_chain, add_node, add_protocol,
                              explorer)
from src.schemas import DependencyGraph, Edge, Node, Position

CID = kamino.CHAIN_ID
MIN_ALLOCATION_SHARE = 0.01
MAX_COLLATERALS = 8


def _f(x) -> float:
    return float(x or 0)


def build_kamino(pos: Position) -> DependencyGraph:
    nodes: list[Node] = []
    edges: list[Edge] = []
    index = kamino.reserve_index()
    v = kamino.vault(pos.market_address)
    if v is None and pos.market_address not in index:
        raise ValueError(f"{pos.market_address} is neither a Kamino Earn vault nor a Kamino reserve")
    chain_id = add_chain(nodes, CID)
    proto_id = add_protocol(nodes, edges, CID, "kamino-lend", "Kamino", "https://kamino.finance")

    if v is None:  # supplying to one reserve
        market, r = index[pos.market_address]
        pos_id = f"position:kamino-{pos.market_address[:10]}"
        nodes.append(Node(pos_id, "position", f"Supply {r['liquidityToken']} · Kamino {market['name']}",
                          "Solana", {"size_usd": pos.size_usd}))
        edges.append(Edge(pos_id, chain_id, "settles_on", 1.0, explorer(CID, pos.market_address)))
        tok = add_asset(nodes, edges, CID, r["liquidityToken"], r["liquidityTokenMint"])
        edges.append(Edge(pos_id, tok, "denominated_in", 1.0,
                          f"A claim on {r['liquidityToken']}: {kamino.market_url(market['lendingMarket'])}"))
        _add_reserve(nodes, edges, pos.market_address, market, r, index, pos_id, 1.0, "supplied_to", proto_id)
        add_contagion(nodes, edges)
        return DependencyGraph(position_id=pos_id, nodes=nodes, edges=edges)

    metrics = kamino.vault_metrics(v["address"])
    url = kamino.vault_url(v["address"])
    first = next(iter(v["allocations"]), None)
    symbol = index[first["reserve"]][1]["liquidityToken"] if first and first["reserve"] in index else "token"
    invested, available = _f(metrics.get("tokensInvestedUsd")), _f(metrics.get("tokensAvailableUsd"))
    pos_id = f"position:kamino-{v['address'][:10]}"
    nodes.append(Node(pos_id, "position", f"Deposit {symbol} · Kamino {v['name']}", "Solana",
                      {"size_usd": pos.size_usd, "net_apy": _f(metrics.get("apy"))}))
    edges.append(Edge(pos_id, chain_id, "settles_on", 1.0, explorer(CID, v["address"])))
    tok = add_asset(nodes, edges, CID, symbol, v["token_mint"])
    edges.append(Edge(pos_id, tok, "denominated_in", 1.0, f"Vault shares are a claim on {symbol}: {url}"))

    vault_id = f"vault:{v['address']}"
    total_ct = sum(a["ctokens"] for a in v["allocations"]) or 1
    # Withdrawable now: idle tokens + what each reserve could pay back (its unborrowed supply).
    liquidity = available + sum(
        min(invested * a["ctokens"] / total_ct,
            _f(index[a["reserve"]][1]["totalSupplyUsd"]) - _f(index[a["reserve"]][1]["totalBorrowUsd"]))
        for a in v["allocations"] if a["reserve"] in index)
    nodes.append(Node(vault_id, "vault", f"Kamino {v['name']}", "Solana", {
        "address": v["address"], "total_usd": invested + available, "liquidity_usd": liquidity,
        "fee": v["performance_fee"], "holders": metrics.get("numberOfHolders")}))
    edges.append(Edge(pos_id, vault_id, "deposited_in", 1.0, url))
    edges.append(Edge(vault_id, proto_id, "runs_on", 1.0, url))
    for role, kind, who in (("Vault admin", "owned_by", v["admin"]),
                            ("Allocation admin", "curated_by", v["allocation_admin"])):
        if who:
            admin = add_node(nodes, Node(f"admin:{who}", "admin", f"{role} {who[:4]}…{who[-4:]}", "Solana",
                                         {"address": who, "kind": "unknown (Solana account)"}))
            edges.append(Edge(vault_id, admin, kind, 1.0, f"{role} of the vault per Kamino API: {url}"))

    for a in v["allocations"]:
        share = a["ctokens"] / total_ct  # cToken units: close to the USD split (rates ~1-1.1)
        if share < MIN_ALLOCATION_SHARE or a["reserve"] not in index:
            continue
        market, r = index[a["reserve"]]
        _add_reserve(nodes, edges, a["reserve"], market, r, index, vault_id, share, "allocates_to", proto_id)
    add_contagion(nodes, edges)
    return DependencyGraph(position_id=pos_id, nodes=nodes, edges=edges)


def _add_reserve(nodes, edges, reserve: str, market: dict, r: dict, index: dict, parent: str,
                 share: float, kind: str, proto_id: str) -> None:
    """A reserve and the collaterals its borrowers may post (the market's
    collateral reserves), each weighted like an Aave pool."""
    murl = kamino.market_url(market["lendingMarket"])
    supply, borrow = _f(r["totalSupplyUsd"]), _f(r["totalBorrowUsd"])
    util = borrow / supply if supply else 0.0
    colls = [c for c in (row for m, row in index.values() if m["lendingMarket"] == market["lendingMarket"])
             if _f(c.get("maxLtv")) > 0 and c["reserve"] != reserve
             and _f(c["totalSupplyUsd"]) >= MIN_COLLATERAL_USD]
    colls.sort(key=lambda c: -_f(c["totalSupplyUsd"]))
    total = sum(_f(c["totalSupplyUsd"]) for c in colls) or 1.0
    lend_id = f"lending:kamino-{reserve[:10]}"
    nodes.append(Node(lend_id, "lending", f"Kamino {market['name']} {r['liquidityToken']} ({reserve[:4]})", "Solana", {
        "reserve": reserve, "market": market["lendingMarket"], "supply_usd": supply,
        "borrow_usd": borrow, "liquidity_usd": supply - borrow, "utilization": util,
        "pool_project": "kamino",
        "collateral_usd_by_asset": {f"asset:{c['liquidityToken']}": _f(c["totalSupplyUsd"]) for c in colls}}))
    edges.append(Edge(parent, lend_id, kind, round(share, 3),
                      f"Reserve {explorer(CID, reserve)} in {market['name']}: {murl}"))
    edges.append(Edge(lend_id, proto_id, "runs_on", 1.0, murl))
    for c in colls[:MAX_COLLATERALS]:
        cshare = _f(c["totalSupplyUsd"]) / total
        coll_id = add_asset(nodes, edges, CID, c["liquidityToken"], c["liquidityTokenMint"])
        edges.append(Edge(lend_id, coll_id, "secured_by", round(util * cshare, 3),
                          f"{c['liquidityToken']} is {cshare:.0%} of {market['name']}'s collateral "
                          f"(max LTV {_f(c['maxLtv']):.0%}); {util:.0%} of the reserve is lent out: {murl}"))
        coll = next(n for n in nodes if n.id == coll_id)
        if "posted_as_collateral" not in coll.meta:
            _add_other_holders(coll, CID, c["liquidityTokenMint"], {})
