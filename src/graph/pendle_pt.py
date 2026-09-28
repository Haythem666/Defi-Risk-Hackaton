"""Build the dependency graph of a Pendle PT position from live data.

Layers (from the Belem brief):
  1. settlement chain
  2. underlying yield source + its issuer
  3. oracle pricing the asset (here: oracles of lending markets using the PT)
  4. PT market and its AMM curve
  5. lending markets holding the PT as collateral
"""

from src.data import defillama, morpho, pendle
from src.schemas import DependencyGraph, Edge, Node, Position

CHAINS = {1: "Ethereum", 42161: "Arbitrum", 8453: "Base", 56: "BSC"}

EXPLORERS = {1: "https://etherscan.io/address/", 42161: "https://arbiscan.io/address/",
             8453: "https://basescan.org/address/", 56: "https://bscscan.com/address/"}

# Pendle category -> DeFiLlama slug of the issuer behind the yield source.
# Extend when adding new underlyings. Each entry must be checkable on DeFiLlama.
ISSUERS = {
    "ethena": ("Ethena", "ethena-usde"),
}


def _explorer(chain_id: int, address: str) -> str:
    return EXPLORERS.get(chain_id, "") + address


def build_graph(pos: Position) -> DependencyGraph:
    cid = pos.chain_id
    chain_name = CHAINS.get(cid, f"chain-{cid}")
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
    nodes.append(Node(pos_id, "position", pt_symbol, chain_name, {
        "address": m["pt"], "expiry": m["expiry"], "size_usd": pos.size_usd,
        "pt_discount": live.get("ptDiscount"), "implied_apy": live.get("impliedApy")}))

    # Layer 1: chain
    chain_id = f"chain:{chain_name.lower()}"
    nodes.append(Node(chain_id, "chain", chain_name, chain_name, {"chain_id": cid}))
    edges.append(Edge(pos_id, chain_id, "settles_on", 1.0,
                      _explorer(cid, m["pt"])))

    # Pendle protocol (PT/SY contracts)
    proto_id = "protocol:pendle"
    nodes.append(Node(proto_id, "protocol", "Pendle", chain_name,
                      {"tvl_usd": defillama.protocol_tvl("pendle")}))
    edges.append(Edge(pos_id, proto_id, "contracts_of", 1.0,
                      f"PT and SY are Pendle contracts: {pendle_app}"))
    edges.append(Edge(proto_id, chain_id, "deployed_on", 1.0, _explorer(cid, m["sy"])))

    # Layer 2: underlying yield source + issuer
    asset_id = f"asset:{underlying_name}"
    nodes.append(Node(asset_id, "asset", underlying_name, chain_name,
                      {"address": m["underlyingAsset"], "price_usd": live.get("assetPriceUsd"),
                       "underlying_apy": live.get("underlyingApy")}))
    edges.append(Edge(pos_id, asset_id, "redeems_into", 1.0,
                      f"PT redeems 1:1 into the underlying at expiry ({m['expiry'][:10]}); "
                      f"SY wraps {_explorer(cid, m['underlyingAsset'])}"))
    edges.append(Edge(asset_id, chain_id, "deployed_on", 1.0,
                      _explorer(cid, m["underlyingAsset"])))

    for cat in m.get("categoryIds", []):
        if cat in ISSUERS:
            name, slug = ISSUERS[cat]
            issuer_id = f"issuer:{slug}"
            nodes.append(Node(issuer_id, "issuer", name, chain_name,
                              {"tvl_usd": defillama.protocol_tvl(slug), "defillama": slug}))
            edges.append(Edge(asset_id, issuer_id, "issued_by", 1.0,
                              f"Pendle category '{cat}'; {defillama.protocol_url(slug)}"))

    # Layer 4: PT market / AMM
    market_id = f"market:pendle-{m['name']}-{m['expiry'][:10]}"
    nodes.append(Node(market_id, "market", f"Pendle AMM {m['name']}", chain_name, {
        "address": m["address"], "liquidity_usd": live["liquidity"]["usd"],
        "tvl_usd": live.get("totalTvl", {}).get("usd"),
        "volume_24h_usd": live.get("tradingVolume", {}).get("usd"),
        "fee_rate": m.get("details", {}).get("feeRate")}))
    edges.append(Edge(pos_id, market_id, "exits_through", 1.0,
                      f"Only venue to sell the PT before expiry: {pendle_app}"))
    edges.append(Edge(market_id, proto_id, "runs_on", 1.0, pendle_app))

    # Layers 3 + 5: lending markets using the PT as collateral, and their oracles
    pt_supply_usd = live.get("totalTvl", {}).get("usd") or 0
    for lm in morpho.markets_with_collateral(cid, m["pt"]):
        coll_usd = lm["state"]["collateralAssetsUsd"] or 0
        lend_id = f"lending:morpho-{lm['marketId'][:10]}"
        nodes.append(Node(lend_id, "lending",
                          f"Morpho {lm['collateralAsset']['symbol']}/{lm['loanAsset']['symbol']}",
                          chain_name, {
                              "market_id": lm["marketId"], "lltv": int(lm["lltv"]) / 1e18,
                              "collateral_usd": coll_usd,
                              "borrow_usd": lm["state"]["borrowAssetsUsd"]}))
        # Liquidations there sell PT into our exit market. Exposure ~ share of
        # the PT market's TVL parked as collateral (crude, to refine in Phase 2).
        share = min(1.0, coll_usd / pt_supply_usd) if pt_supply_usd else 0.0
        edges.append(Edge(pos_id, lend_id, "collateral_in", round(share, 3),
                          morpho.market_url(cid, lm["marketId"])))

        oracle = lm.get("oracle") or {}
        if oracle.get("address"):
            oracle_id = f"oracle:{oracle['address'].lower()}"
            if all(n.id != oracle_id for n in nodes):
                nodes.append(Node(oracle_id, "oracle", f"Oracle {oracle['address'][:10]}",
                                  chain_name, {"address": oracle["address"],
                                               "type": oracle.get("type")}))
            edges.append(Edge(lend_id, oracle_id, "priced_by", 1.0,
                              _explorer(cid, oracle["address"])))

    return DependencyGraph(position_id=pos_id, nodes=nodes, edges=edges)
