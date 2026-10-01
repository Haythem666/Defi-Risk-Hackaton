"""Build the dependency graph of a Pendle PT position from live data.

Layers (from the Belem brief):
  1. settlement chain
  2. underlying yield source + its issuer
  3. oracle pricing the asset (here: oracles of lending markets using the PT)
  4. PT market and its AMM curve
  5. lending markets holding the PT as collateral (Morpho, Aave)

Known gap: Euler v2 has no public API reachable without a key; not covered.
"""

from src.data import aave, morpho, pendle
from src.graph.common import (MIN_COLLATERAL_USD, add_chain, add_issuer, add_oracle,
                              add_protocol, chain_name, explorer, morpho_oracle_usd)
from src.schemas import DependencyGraph, Edge, Node, Position


def build_graph(pos: Position) -> DependencyGraph:
    cid = pos.chain_id
    cname = chain_name(cid)
    m = pendle.market(cid, pos.market_address)
    live = pendle.market_data(cid, pos.market_address)
    assets = pendle.assets(cid)
    pt_symbol = assets.get(m["pt"], {}).get("symbol", f"PT-{m['name']}")
    underlying_name = assets.get(m["sy"], {}).get("name", m["name"])
    pendle_app = f"https://app.pendle.finance/trade/markets/{m['address']}?chain=ethereum"

    nodes: list[Node] = []
    edges: list[Edge] = []

    # Position
    pos_id = f"position:{pt_symbol}"
    nodes.append(Node(pos_id, "position", pt_symbol, cname, {
        "address": m["pt"], "expiry": m["expiry"], "size_usd": pos.size_usd,
        "pt_discount": live.get("ptDiscount"), "implied_apy": live.get("impliedApy")}))

    # Layer 1: chain
    chain_id = add_chain(nodes, cid)
    edges.append(Edge(pos_id, chain_id, "settles_on", 1.0, explorer(cid, m["pt"])))

    # Pendle protocol (PT/SY contracts)
    proto_id = add_protocol(nodes, edges, cid, "pendle", "Pendle", explorer(cid, m["sy"]))
    edges.append(Edge(pos_id, proto_id, "contracts_of", 1.0,
                      f"PT and SY are Pendle contracts: {pendle_app}"))

    # Layer 2: underlying yield source + issuer
    asset_id = f"asset:{underlying_name}"
    nodes.append(Node(asset_id, "asset", underlying_name, cname,
                      {"address": m["underlyingAsset"], "price_usd": live.get("assetPriceUsd"),
                       "underlying_apy": live.get("underlyingApy")}))
    edges.append(Edge(pos_id, asset_id, "redeems_into", 1.0,
                      f"PT redeems 1:1 into the underlying at expiry ({m['expiry'][:10]}); "
                      f"SY wraps {explorer(cid, m['underlyingAsset'])}"))
    edges.append(Edge(asset_id, chain_id, "deployed_on", 1.0,
                      explorer(cid, m["underlyingAsset"])))
    # Try the SY name (e.g. "wstETH") and the PT's base symbol (e.g. "stETH").
    base_symbol = pt_symbol.removeprefix("PT-").rsplit("-", 1)[0]
    add_issuer(nodes, edges, cid, asset_id, [underlying_name, base_symbol], m["underlyingAsset"])

    # Layer 4: PT market / AMM
    market_id = f"market:pendle-{m['name']}-{m['expiry'][:10]}"
    nodes.append(Node(market_id, "market", f"Pendle AMM {m['name']}", cname, {
        "address": m["address"], "liquidity_usd": live["liquidity"]["usd"],
        "tvl_usd": live.get("totalTvl", {}).get("usd"),
        "volume_24h_usd": live.get("tradingVolume", {}).get("usd"),
        "fee_rate": m.get("details", {}).get("feeRate")}))
    edges.append(Edge(pos_id, market_id, "exits_through", 1.0,
                      f"Only venue to sell the PT before expiry: {pendle_app}"))
    edges.append(Edge(market_id, proto_id, "runs_on", 1.0, pendle_app))

    # Layers 3 + 5: lending markets using the PT as collateral, and their oracles.
    # Liquidations there sell PT into our exit market. Exposure ~ share of the
    # PT market's TVL parked as collateral (crude, to refine).
    pt_supply_usd = live.get("totalTvl", {}).get("usd") or 0
    pt_price_usd = (live.get("assetPriceUsd") or 1.0) * (1 - (live.get("ptDiscount") or 0.0))
    for lm in morpho.markets_with_collateral(cid, m["pt"]):
        coll_usd = lm["state"]["collateralAssetsUsd"] or 0
        if coll_usd < MIN_COLLATERAL_USD:
            continue
        lend_id = f"lending:morpho-{lm['marketId'][:10]}"
        nodes.append(Node(lend_id, "lending",
                          f"Morpho {lm['collateralAsset']['symbol']}/{lm['loanAsset']['symbol']}",
                          cname, {
                              "market_id": lm["marketId"], "lltv": int(lm["lltv"]) / 1e18,
                              "collateral_usd": coll_usd,
                              "borrow_usd": lm["state"]["borrowAssetsUsd"]}))
        share = min(1.0, coll_usd / pt_supply_usd) if pt_supply_usd else 0.0
        edges.append(Edge(pos_id, lend_id, "collateral_in", round(share, 3),
                          morpho.market_url(cid, lm["marketId"])))
        oracle = (lm.get("oracle") or {}).get("address")
        if oracle:
            add_oracle(nodes, edges, cid, lend_id, oracle, morpho_oracle_usd(cid, lm),
                       pt_price_usd, "Morpho oracle price() read on-chain")

    for r in aave.reserves_for_asset(cid, m["pt"]):
        coll_usd = float(r["size"]["usd"] or 0)
        if coll_usd < MIN_COLLATERAL_USD:
            continue
        info = r["supplyInfo"]
        lend_id = f"lending:aave-{r['market_name']}"
        nodes.append(Node(lend_id, "lending", f"Aave {r['market_name']} ({pt_symbol})", cname, {
            "market_address": r["market_address"],
            "liquidation_threshold": float(info["liquidationThreshold"]["value"]),
            "max_ltv": float(info["maxLTV"]["value"]),
            "can_be_collateral": info["canBeCollateral"],
            "collateral_usd": coll_usd,
            "frozen": r["isFrozen"], "paused": r["isPaused"]}))
        share = min(1.0, coll_usd / pt_supply_usd) if pt_supply_usd else 0.0
        edges.append(Edge(pos_id, lend_id, "collateral_in", round(share, 3),
                          f"Listed as a reserve in Aave API ({aave.URL}); pool "
                          f"{explorer(cid, r['market_address'])}"))
        if r.get("usdOracleAddress"):
            add_oracle(nodes, edges, cid, lend_id, r["usdOracleAddress"],
                       float(r["usdExchangeRate"] or 0) or None, pt_price_usd,
                       "Aave API usdExchangeRate")

    return DependencyGraph(position_id=pos_id, nodes=nodes, edges=edges)
