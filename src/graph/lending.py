"""Dependency graphs of lending positions: supplying an asset to a Morpho
market or an Aave pool.

A lender loses money when borrowers default: their collateral collapses (hack,
depeg, wrong oracle price) faster than liquidations can cover the debt. Only
the borrowed part of the pool is at risk, so the lender's exposure to the
collateral side is the pool's utilization (borrowed / supplied). The other
risk is getting stuck: a lender can only withdraw the pool's idle liquidity.
"""

from src.data import aave, morpho
from src.graph.common import (MIN_COLLATERAL_USD, add_asset, add_chain, add_oracle,
                              add_protocol, chain_name, explorer, morpho_oracle_usd)
from src.schemas import DependencyGraph, Edge, Node, Position

# Aave pools accept dozens of collaterals; keep the largest ones in the graph.
MAX_AAVE_COLLATERALS = 8


def _add_morpho_market(nodes: list[Node], edges: list[Edge], cid: int, m: dict,
                       parent_id: str, exposure: float, kind: str) -> str:
    """A Morpho market a position (or vault) lends into: the market node,
    its collateral (exposure = utilization) and its oracle."""
    st, loan, coll = m["state"], m["loanAsset"], m["collateralAsset"]
    url = morpho.market_url(cid, m["marketId"])
    util = st["utilization"] or 0.0
    proto_id = add_protocol(nodes, edges, cid, "morpho-blue", "Morpho", url)

    lend_id = f"lending:morpho-{m['marketId'][:10]}"
    nodes.append(Node(lend_id, "lending", f"Morpho {coll['symbol']}/{loan['symbol']}",
                      chain_name(cid), {
        "market_id": m["marketId"], "lltv": int(m["lltv"]) / 1e18, "listed": m.get("listed"),
        "supply_usd": st["supplyAssetsUsd"], "borrow_usd": st["borrowAssetsUsd"],
        "collateral_usd": st["collateralAssetsUsd"], "liquidity_usd": st["liquidityAssetsUsd"],
        "utilization": util}))
    edges.append(Edge(parent_id, lend_id, kind, round(exposure, 3), url))
    edges.append(Edge(lend_id, proto_id, "runs_on", 1.0, url))

    coll_id = add_asset(nodes, edges, cid, coll["symbol"], coll["address"],
                        {"price_usd": (coll.get("price") or {}).get("usd")})
    edges.append(Edge(lend_id, coll_id, "secured_by", round(util, 3),
                      f"Borrowers post {coll['symbol']}; {util:.0%} of supply is lent out: {url}"))
    oracle = (m.get("oracle") or {}).get("address")
    if oracle:
        add_oracle(nodes, edges, cid, lend_id, oracle, morpho_oracle_usd(cid, m),
                   (coll.get("price") or {}).get("usd"), "Morpho oracle price() read on-chain",
                   exposure=util)
    return lend_id


def build_morpho_supply(pos: Position) -> DependencyGraph:
    cid, cname = pos.chain_id, chain_name(pos.chain_id)
    m = morpho.market(cid, pos.market_address)
    st, loan, coll = m["state"], m["loanAsset"], m["collateralAsset"]
    url = morpho.market_url(cid, m["marketId"])

    nodes: list[Node] = []
    edges: list[Edge] = []
    pos_id = f"position:lend-{loan['symbol']}-morpho-{m['marketId'][:10]}"
    nodes.append(Node(pos_id, "position", f"Lend {loan['symbol']} · Morpho {coll['symbol']}/{loan['symbol']}",
                      cname, {"size_usd": pos.size_usd, "supply_apy": st.get("supplyApy"),
                              "utilization": st["utilization"] or 0.0}))

    edges.append(Edge(pos_id, add_chain(nodes, cid), "settles_on", 1.0, url))
    proto_id = add_protocol(nodes, edges, cid, "morpho-blue", "Morpho", url)
    edges.append(Edge(pos_id, proto_id, "contracts_of", 1.0, url))
    loan_id = add_asset(nodes, edges, cid, loan["symbol"], loan["address"],
                        {"price_usd": (loan.get("price") or {}).get("usd")})
    edges.append(Edge(pos_id, loan_id, "denominated_in", 1.0,
                      f"The position is a claim on {loan['symbol']}: {url}"))
    _add_morpho_market(nodes, edges, cid, m, pos_id, 1.0, "supplied_to")
    return DependencyGraph(position_id=pos_id, nodes=nodes, edges=edges)


# Vault allocations below this share of the vault are left out of the graph.
MIN_ALLOCATION_SHARE = 0.01


def build_morpho_vault(pos: Position) -> DependencyGraph:
    """Deposit in a Morpho vault: a curator spreads deposits over markets.
    Exposure to each market = its share of the vault's assets."""
    cid, cname = pos.chain_id, chain_name(pos.chain_id)
    v = morpho.vault(cid, pos.market_address)
    st, asset = v["state"], v["asset"]
    url = morpho.vault_url(cid, v["address"])
    total = st["totalAssetsUsd"] or 0.0
    curators = [c["name"] for c in (st.get("curators") or [])]

    nodes: list[Node] = []
    edges: list[Edge] = []
    pos_id = f"position:vault-{v['address'][:10]}"
    nodes.append(Node(pos_id, "position", f"Deposit {asset['symbol']} · {v['name']}", cname,
                      {"size_usd": pos.size_usd, "net_apy": st.get("netApy")}))
    edges.append(Edge(pos_id, add_chain(nodes, cid), "settles_on", 1.0, explorer(cid, v["address"])))
    proto_id = add_protocol(nodes, edges, cid, "morpho-blue", "Morpho", url)
    asset_id = add_asset(nodes, edges, cid, asset["symbol"], asset["address"],
                         {"price_usd": (asset.get("price") or {}).get("usd")})
    edges.append(Edge(pos_id, asset_id, "denominated_in", 1.0,
                      f"Vault shares are a claim on {asset['symbol']}: {url}"))

    vault_id = f"vault:{v['address'].lower()}"
    nodes.append(Node(vault_id, "vault", v["name"], cname, {
        "address": v["address"], "curators": curators, "fee": st.get("fee"),
        "timelock_days": (st.get("timelock") or 0) / 86400, "guardian": st.get("guardian"),
        "total_usd": total, "liquidity_usd": (v.get("liquidity") or {}).get("usd"),
        "warnings": [w["type"] for w in (v.get("warnings") or [])]}))
    edges.append(Edge(pos_id, vault_id, "deposited_in", 1.0, url))
    edges.append(Edge(vault_id, proto_id, "runs_on", 1.0, url))

    for a in st["allocation"]:
        share = (a["supplyAssetsUsd"] or 0) / total if total else 0.0
        if share < MIN_ALLOCATION_SHARE:
            continue
        m = morpho.market(cid, a["market"]["marketId"])
        if not m.get("collateralAsset"):
            continue  # idle market: cash waiting in the vault, nothing lent out
        _add_morpho_market(nodes, edges, cid, m, vault_id, share, "allocates_to")
    return DependencyGraph(position_id=pos_id, nodes=nodes, edges=edges)


def build_aave_supply(pos: Position) -> DependencyGraph:
    cid, cname = pos.chain_id, chain_name(pos.chain_id)
    mk = aave.market(cid, pos.market_address)
    asset = (pos.asset_address or "").lower()
    res = next(r for r in mk["reserves"] if r["underlyingToken"]["address"].lower() == asset)
    tok, borrow = res["underlyingToken"], res["borrowInfo"] or {}
    util = float((borrow.get("utilizationRate") or {}).get("value") or 0)
    pool_link = f"Aave API ({aave.URL}), pool {explorer(cid, mk['address'])}"

    nodes: list[Node] = []
    edges: list[Edge] = []
    pos_id = f"position:supply-{tok['symbol']}-{mk['name']}"
    nodes.append(Node(pos_id, "position", f"Supply {tok['symbol']} · Aave {mk['name']}", cname, {
        "size_usd": pos.size_usd, "utilization": util,
        "supply_apy": float((res["supplyInfo"].get("apy") or {}).get("value") or 0)}))

    edges.append(Edge(pos_id, add_chain(nodes, cid), "settles_on", 1.0,
                      explorer(cid, mk["address"])))
    proto_id = add_protocol(nodes, edges, cid, "aave-v3", "Aave v3", explorer(cid, mk["address"]))
    edges.append(Edge(pos_id, proto_id, "contracts_of", 1.0, pool_link))

    asset_id = add_asset(nodes, edges, cid, tok["symbol"], tok["address"],
                         {"price_usd": float(res["usdExchangeRate"] or 0) or None})
    edges.append(Edge(pos_id, asset_id, "denominated_in", 1.0,
                      f"aToken is a claim on {tok['symbol']}: {pool_link}"))

    lend_id = f"lending:aave-{mk['name']}-{tok['symbol']}"
    nodes.append(Node(lend_id, "lending", f"Aave {mk['name']} {tok['symbol']} reserve", cname, {
        "market_address": mk["address"], "supply_usd": float(res["size"]["usd"] or 0),
        "borrow_usd": float((borrow.get("total") or {}).get("usd") or 0),
        "liquidity_usd": float((borrow.get("availableLiquidity") or {}).get("usd") or 0),
        "utilization": util, "frozen": res["isFrozen"], "paused": res["isPaused"]}))
    edges.append(Edge(pos_id, lend_id, "supplied_to", 1.0, pool_link))
    edges.append(Edge(lend_id, proto_id, "runs_on", 1.0, pool_link))

    # Aave pools share collateral: any collateral-enabled reserve backs the
    # borrows. Exposure to each one ~ utilization x its share of collateral
    # (crude: ignores e-mode groups and which assets borrowers actually post).
    colls = [r for r in mk["reserves"]
             if r["supplyInfo"]["canBeCollateral"]
             and r["underlyingToken"]["address"].lower() != asset
             and float(r["size"]["usd"] or 0) >= MIN_COLLATERAL_USD]
    total = sum(float(r["size"]["usd"]) for r in colls) or 1.0
    colls.sort(key=lambda r: float(r["size"]["usd"]), reverse=True)
    nodes[-1].meta["collaterals_total"] = len(colls)
    for r in colls[:MAX_AAVE_COLLATERALS]:
        share = float(r["size"]["usd"]) / total
        ct = r["underlyingToken"]
        coll_id = add_asset(nodes, edges, cid, ct["symbol"], ct["address"],
                            {"price_usd": float(r["usdExchangeRate"] or 0) or None})
        edges.append(Edge(lend_id, coll_id, "secured_by", round(util * share, 3),
                          f"{ct['symbol']} is {share:.0%} of the pool's collateral: {pool_link}"))
        if r.get("usdOracleAddress"):
            add_oracle(nodes, edges, cid, lend_id, r["usdOracleAddress"],
                       float(r["usdExchangeRate"] or 0) or None, None,
                       f"Aave oracle for {ct['symbol']}", exposure=util * share)

    return DependencyGraph(position_id=pos_id, nodes=nodes, edges=edges)
