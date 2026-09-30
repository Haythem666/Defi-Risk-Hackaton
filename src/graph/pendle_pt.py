"""Build the dependency graph of a Pendle PT position from live data.

Layers (from the Belem brief):
  1. settlement chain
  2. underlying yield source + its issuer
  3. oracle pricing the asset (here: oracles of lending markets using the PT)
  4. PT market and its AMM curve
  5. lending markets holding the PT as collateral (Morpho, Aave)

Known gap: Euler v2 has no public API reachable without a key; not covered.
"""

from src.data import aave, chain, defillama, morpho, pendle
from src.schemas import DependencyGraph, Edge, Node, Position

CHAINS = {1: "Ethereum", 42161: "Arbitrum", 8453: "Base", 56: "BSC"}

# Lending markets holding less PT than this are too small to move its price.
MIN_COLLATERAL_USD = 10_000

EXPLORERS = {1: "https://etherscan.io/address/", 42161: "https://arbiscan.io/address/",
             8453: "https://basescan.org/address/", 56: "https://bscscan.com/address/"}


def _explorer(chain_id: int, address: str) -> str:
    return EXPLORERS.get(chain_id, "") + address


def _add_oracle(nodes: list[Node], edges: list[Edge], cid: int, chain_name: str,
                lend_id: str, address: str, price_usd: float | None,
                market_price_usd: float | None, source: str) -> None:
    """Oracle node (shared if several lending markets use it) + priced_by edge.

    Records the oracle's price, its gap to the PT market price, and whether
    its source code is public: an unverified or off-market feed is a risk flag.
    """
    oracle_id = f"oracle:{address.lower()}"
    if all(n.id != oracle_id for n in nodes):
        impl = None
        try:
            impl = chain.proxy_implementation(cid, address)
        except Exception:
            pass
        verified = chain.is_verified(cid, impl or address)
        gap = (price_usd / market_price_usd - 1) if price_usd and market_price_usd else None
        nodes.append(Node(oracle_id, "oracle", f"Oracle {address[:10]}", chain_name, {
            "address": address, "source": source, "price_usd": price_usd,
            "gap_to_market": gap, "proxy_of": impl, "source_verified": verified}))
    edges.append(Edge(lend_id, oracle_id, "priced_by", 1.0, _explorer(cid, address)))


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

    # Issuer: the DeFiLlama project that mints this token from something else.
    # Try the SY name (e.g. "wstETH") and the PT's base symbol (e.g. "stETH").
    base_symbol = pt_symbol.removeprefix("PT-").rsplit("-", 1)[0]
    issuer = defillama.find_issuer(defillama.yield_pools(), chain_name,
                                   [underlying_name, base_symbol], m["underlyingAsset"])
    if issuer:
        slug = issuer["project"]
        issuer_id = f"issuer:{slug}"
        nodes.append(Node(issuer_id, "issuer", slug, chain_name,
                          {"tvl_usd": defillama.protocol_tvl(slug), "defillama": slug}))
        edges.append(Edge(asset_id, issuer_id, "issued_by", 1.0,
                          f"DeFiLlama pool issuing {issuer['symbol']}: "
                          f"{defillama.pool_url(issuer['pool'])}"))

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
                          chain_name, {
                              "market_id": lm["marketId"], "lltv": int(lm["lltv"]) / 1e18,
                              "collateral_usd": coll_usd,
                              "borrow_usd": lm["state"]["borrowAssetsUsd"]}))
        share = min(1.0, coll_usd / pt_supply_usd) if pt_supply_usd else 0.0
        edges.append(Edge(pos_id, lend_id, "collateral_in", round(share, 3),
                          morpho.market_url(cid, lm["marketId"])))

        oracle = (lm.get("oracle") or {}).get("address")
        if oracle:
            price = None
            try:
                loan = lm["loanAsset"]
                price = chain.morpho_oracle_price(
                    cid, oracle, lm["collateralAsset"]["decimals"], loan["decimals"]
                ) * ((loan.get("price") or {}).get("usd") or 0) or None
            except Exception:
                pass
            _add_oracle(nodes, edges, cid, chain_name, lend_id, oracle, price,
                        pt_price_usd, "Morpho oracle price() read on-chain")

    for r in aave.reserves_for_asset(cid, m["pt"]):
        coll_usd = float(r["size"]["usd"] or 0)
        if coll_usd < MIN_COLLATERAL_USD:
            continue
        info = r["supplyInfo"]
        lend_id = f"lending:aave-{r['market_name']}"
        nodes.append(Node(lend_id, "lending", f"Aave {r['market_name']} ({pt_symbol})",
                          chain_name, {
                              "market_address": r["market_address"],
                              "liquidation_threshold": float(info["liquidationThreshold"]["value"]),
                              "max_ltv": float(info["maxLTV"]["value"]),
                              "can_be_collateral": info["canBeCollateral"],
                              "collateral_usd": coll_usd,
                              "frozen": r["isFrozen"], "paused": r["isPaused"]}))
        share = min(1.0, coll_usd / pt_supply_usd) if pt_supply_usd else 0.0
        edges.append(Edge(pos_id, lend_id, "collateral_in", round(share, 3),
                          f"Listed as a reserve in Aave API ({aave.URL}); pool "
                          f"{_explorer(cid, r['market_address'])}"))
        if r.get("usdOracleAddress"):
            _add_oracle(nodes, edges, cid, chain_name, lend_id, r["usdOracleAddress"],
                        float(r["usdExchangeRate"] or 0) or None, pt_price_usd,
                        "Aave API usdExchangeRate")

    return DependencyGraph(position_id=pos_id, nodes=nodes, edges=edges)
