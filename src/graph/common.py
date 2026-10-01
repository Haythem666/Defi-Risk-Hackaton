"""Helpers shared by every graph builder: chain names, explorer links,
issuer discovery and oracle checks."""

from src.data import chain, defillama, ethena
from src.schemas import Edge, Node

# Chain id -> chain name as DeFiLlama spells it (used to match yield pools).
CHAINS = {1: "Ethereum", 42161: "Arbitrum", 8453: "Base", 56: "BSC",
          999: "Hyperliquid L1", 9745: "Plasma"}

EXPLORERS = {1: "https://etherscan.io/address/", 42161: "https://arbiscan.io/address/",
             8453: "https://basescan.org/address/", 56: "https://bscscan.com/address/",
             999: "https://hyperevmscan.io/address/", 9745: "https://plasmascan.to/address/"}

# Lending markets / collaterals smaller than this cannot move a position.
MIN_COLLATERAL_USD = 10_000

# Venues holding less than this share of an issuer's backing are left out.
MIN_VENUE_SHARE = 0.001


def chain_name(chain_id: int) -> str:
    return CHAINS.get(chain_id, f"chain-{chain_id}")


def explorer(chain_id: int, address: str) -> str:
    return EXPLORERS.get(chain_id, "") + address


def add_node(nodes: list[Node], node: Node) -> str:
    """Append `node` unless a node with the same id exists. Returns the id."""
    if all(n.id != node.id for n in nodes):
        nodes.append(node)
    return node.id


def add_chain(nodes: list[Node], cid: int) -> str:
    name = chain_name(cid)
    return add_node(nodes, Node(f"chain:{name.lower()}", "chain", name, name, {"chain_id": cid}))


def _risk_meta(slug: str) -> dict:
    """TVL, category, audits and past hacks from DeFiLlama, for the risk model."""
    info = defillama.protocol_info(slug)
    return {"tvl_usd": defillama.protocol_tvl(slug), "defillama": slug,
            "category": info.get("category"), "audits": info.get("audits"),
            "audit_links": info.get("audit_links"), "past_hacks": info.get("hacks") or []}


def add_protocol(nodes: list[Node], edges: list[Edge], cid: int, slug: str, name: str,
                 evidence: str) -> str:
    """Protocol node (TVL, audits, past hacks from DeFiLlama) deployed on the chain."""
    proto_id = f"protocol:{slug}"
    if all(n.id != proto_id for n in nodes):
        nodes.append(Node(proto_id, "protocol", name, chain_name(cid), _risk_meta(slug)))
        edges.append(Edge(proto_id, add_chain(nodes, cid), "deployed_on", 1.0, evidence))
    return proto_id


def add_issuer(nodes: list[Node], edges: list[Edge], cid: int, asset_id: str,
               symbols: list[str], token_address: str) -> str | None:
    """Issuer of a token: the DeFiLlama project that mints it from something else."""
    issuer = defillama.find_issuer(defillama.yield_pools(), chain_name(cid), symbols,
                                   token_address)
    if not issuer:
        return None
    slug = issuer["project"]
    issuer_id = f"issuer:{slug}"
    new = all(n.id != issuer_id for n in nodes)
    add_node(nodes, Node(issuer_id, "issuer", slug, chain_name(cid), _risk_meta(slug)))
    edges.append(Edge(asset_id, issuer_id, "issued_by", 1.0,
                      f"DeFiLlama pool issuing {issuer['symbol']}: "
                      f"{defillama.pool_url(issuer['pool'])}"))
    if new:
        add_issuer_venues(nodes, edges, cid, issuer_id, slug)
    return issuer_id


def add_issuer_venues(nodes: list[Node], edges: list[Edge], cid: int, issuer_id: str,
                      slug: str) -> None:
    """Off-chain venues an issuer depends on, where a public source lists them.

    Ethena: USDe backing is partly held as margin on exchanges to hedge
    (Binance, OKX, Bybit, ...). If a venue fails, that share of the backing is
    at risk. Exposure = the venue's share of total backing.
    """
    if not slug.startswith("ethena"):
        return
    try:
        venues = ethena.backing_by_venue()
    except Exception:
        return
    total = sum(venues.values()) or 1.0
    for venue, usd in sorted(venues.items(), key=lambda kv: -kv[1]):
        share = usd / total
        if venue == "Unallocated" or share < MIN_VENUE_SHARE:
            continue
        venue_id = add_node(nodes, Node(f"venue:{venue.lower()}", "venue", venue, None,
                                        {"backing_usd": usd, "share_of_backing": share}))
        edges.append(Edge(issuer_id, venue_id, "hedges_on", round(share, 3),
                          f"{share:.1%} of USDe backing on {venue}: {ethena.COLLATERAL} "
                          f"(dashboard {ethena.DASHBOARD})"))


def add_asset(nodes: list[Node], edges: list[Edge], cid: int, symbol: str, address: str,
              meta: dict | None = None) -> str:
    """Token node on its chain, with its issuer when one can be found."""
    asset_id = f"asset:{symbol}"
    if all(n.id != asset_id for n in nodes):
        nodes.append(Node(asset_id, "asset", symbol, chain_name(cid),
                          {"address": address, **(meta or {})}))
        edges.append(Edge(asset_id, add_chain(nodes, cid), "deployed_on", 1.0,
                          explorer(cid, address)))
        # Wrapped yield tokens are listed under their base name (wstETH -> stETH).
        # Only lowercase "w": WBTC/WETH are plain wrappers with no yield issuer.
        symbols = [symbol] + ([symbol[1:]] if symbol.startswith("w") and len(symbol) > 3 else [])
        add_issuer(nodes, edges, cid, asset_id, symbols, address)
    return asset_id


def add_oracle(nodes: list[Node], edges: list[Edge], cid: int, source_id: str,
               address: str, price_usd: float | None, market_price_usd: float | None,
               source: str, exposure: float = 1.0) -> str:
    """Oracle node (shared if several markets use it) + priced_by edge.

    Records the oracle's price, its gap to the market price, and whether
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
        nodes.append(Node(oracle_id, "oracle", f"Oracle {address[:10]}", chain_name(cid), {
            "address": address, "source": source, "price_usd": price_usd,
            "gap_to_market": gap, "proxy_of": impl, "source_verified": verified}))
    edges.append(Edge(source_id, oracle_id, "priced_by", round(exposure, 3),
                      explorer(cid, address)))
    return oracle_id


def morpho_oracle_usd(cid: int, market: dict) -> float | None:
    """USD price of a Morpho market's collateral according to its oracle."""
    oracle = (market.get("oracle") or {}).get("address")
    if not oracle or not market.get("collateralAsset"):
        return None
    try:
        loan = market["loanAsset"]
        price = chain.morpho_oracle_price(cid, oracle, market["collateralAsset"]["decimals"],
                                          loan["decimals"])
        return price * ((loan.get("price") or {}).get("usd") or 0) or None
    except Exception:
        return None
