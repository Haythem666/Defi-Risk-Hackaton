"""Helpers shared by every graph builder: chain names, explorer links,
issuer discovery and oracle checks."""

import re

from src.data import chain, defillama, ethena
from src.schemas import Edge, Node

# Chain id -> chain name as DeFiLlama spells it (used to match yield pools).
CHAINS = {1: "Ethereum", 42161: "Arbitrum", 8453: "Base", 56: "BSC",
          999: "Hyperliquid L1", 9745: "Plasma", 101: "Solana"}  # 101: not EVM (Kamino)
EVM_CHAINS = [c for c in CHAINS if c != 101]

EXPLORERS = {1: "https://etherscan.io/address/", 42161: "https://arbiscan.io/address/",
             8453: "https://basescan.org/address/", 56: "https://bscscan.com/address/",
             999: "https://hyperevmscan.io/address/", 9745: "https://plasmascan.to/address/",
             101: "https://solscan.io/account/"}

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
        add_offchain_backing(nodes, edges, issuer_id, slug)
    return issuer_id


# DeFiLlama categories whose assets sit off-chain: a custodian, a fund, real-world
# loans or exchange accounts. The chain shows the token, not what backs it.
OFFCHAIN_CATEGORIES = {"RWA", "RWA Lending", "Basis Trading", "CeDeFi", "Off-Chain Credit"}


def add_offchain_backing(nodes: list[Node], edges: list[Edge], issuer_id: str, slug: str) -> None:
    """Where the graph stops: an issuer whose backing is held off-chain gets a
    box saying so. It carries no rate of its own (the issuer's does); it marks
    the dependency nobody can verify on-chain. Skipped when the off-chain
    venues are already listed (Ethena)."""
    issuer = next(n for n in nodes if n.id == issuer_id)
    category = issuer.meta.get("category")
    if category not in OFFCHAIN_CATEGORIES or any(
            e.source == issuer_id and e.kind == "hedges_on" for e in edges):
        return
    box_id = add_node(nodes, Node(f"venue:offchain-{slug}", "venue",
                                  f"Off-chain backing of {issuer.name}", None,
                                  {"role": "offchain_backing", "category": category,
                                   "flags": [f"{issuer.name} ({category}) holds its backing "
                                             f"off-chain: not verifiable on-chain"]}))
    edges.append(Edge(issuer_id, box_id, "backed_off_chain", 1.0,
                      f"DeFiLlama category '{category}' ({defillama.protocol_url(slug)}): the "
                      f"assets behind the token are held off-chain (custodian, fund, real-world "
                      f"loans or exchange accounts); the graph cannot follow them further"))


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
        try:
            _add_oracle_feeds(nodes, edges, cid, nodes[-1], address)
        except Exception:
            pass  # not a Morpho oracle, or the RPC is down: the oracle node stays
    edges.append(Edge(source_id, oracle_id, "priced_by", round(exposure, 3),
                      explorer(cid, address)))
    return oracle_id


# Morpho oracles (MorphoChainlinkOracleV2) build their price from up to four
# feeds and two ERC-4626 vaults, each readable on-chain.
ORACLE_PARTS = {"BASE_FEED_1": "0xf50a4718", "BASE_FEED_2": "0xdc53858c",
                "QUOTE_FEED_1": "0x56095e11", "QUOTE_FEED_2": "0xacfbd39e",
                "BASE_VAULT": "0xeaa2d7b4", "QUOTE_VAULT": "0x2e6f20a6"}
DESCRIPTION, OWNER = "0x7284e416", "0x8da5cb5b"
# Feed descriptions that mean "a rate reported by the issuer or computed",
# not a price observed on a market (Chainlink names them like this).
NOT_MARKET = re.compile(r"exchange rate|calculated|fundamental|\bnav\b|redemption|fixed",
                        re.IGNORECASE)


def _add_oracle_feeds(nodes: list[Node], edges: list[Edge], cid: int, oracle: Node,
                      address: str) -> None:
    """The feeds and vaults behind a Morpho oracle, who controls each feed,
    and a flag when the price is a reported rate rather than a market price:
    such a price does not fall when the token sells off on markets, so
    liquidations do not start and lenders are left holding the collateral."""
    from src.graph.crawler import _addr, _string, _words, control_flags, controller
    calls = [("eth_call", [{"to": address, "data": s}, "latest"]) for s in ORACLE_PARTS.values()]
    parts = {fn: _addr((_words(r) or [None])[0]) for fn, r in zip(ORACLE_PARTS, chain.batch(cid, calls))}
    parts = {fn: a for fn, a in parts.items() if a}
    if not parts:
        return
    feeds = [(fn, a) for fn, a in parts.items() if "FEED" in fn]
    calls = [("eth_call", [{"to": a, "data": s}, "latest"]) for _, a in feeds for s in (DESCRIPTION, OWNER)]
    res = chain.batch(cid, calls)
    flags = oracle.meta.setdefault("flags", [])
    oracle.meta["feeds"] = {}
    for i, (fn, a) in enumerate(feeds):
        desc, owner = _string(res[2 * i]), _addr((_words(res[2 * i + 1]) or [None])[0])
        oracle.meta["feeds"][fn] = {"address": a, "description": desc, "owner": owner}
        feed_id = add_node(nodes, Node(f"oracle:{a}", "oracle", f"Feed {desc or a[:10]}", chain_name(cid),
                                       {"address": a, "description": desc, "part_of": oracle.id}))
        edges.append(Edge(oracle.id, feed_id, "reads_from", 1.0,
                          f"{fn}() on {explorer(cid, address)} returns {a}"
                          + (f" ('{desc}')" if desc else "")))
        if desc and NOT_MARKET.search(desc):
            flags.append(f"price comes from '{desc}', a reported rate, not a market price: "
                         f"a sell-off on markets does not move it, so liquidations do not start")
        if owner:
            ctrl = controller(cid, owner)
            add_node(nodes, Node(f"admin:{owner}", "admin", ctrl["label"], chain_name(cid), ctrl))
            edges.append(Edge(feed_id, f"admin:{owner}", "owned_by", 1.0,
                              f"owner() of feed {explorer(cid, a)} is {owner} (read on-chain)"))
            flags += [f"feed {f}" for f in control_flags("owner", ctrl)]
    for fn in ("BASE_VAULT", "QUOTE_VAULT"):
        if fn in parts:
            oracle.meta["feeds"][fn] = {"address": parts[fn]}
            flags.append(f"{fn} {parts[fn][:10]}: the price includes that vault's own share "
                         f"price, which its contract reports")


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
