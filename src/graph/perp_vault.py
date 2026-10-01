"""Dependency graph of a vault that deploys into an external perp venue:
a Hyperliquid vault (e.g. HLP, the exchange's market-making vault).

All of the vault's assets sit on the Hyperliquid exchange, so the venue
carries full exposure; the exchange settles on the Hyperliquid L1, prices
positions with its validator oracle, and holds deposited USDC through its
bridge on Arbitrum. The vault's largest perp positions are its market risk.
"""

from src.data import hyperliquid
from src.graph.common import add_chain, add_node, add_protocol
from src.schemas import DependencyGraph, Edge, Node, Position

HYPERLIQUID_CHAIN = 999  # Hyperliquid L1 (HyperCore + HyperEVM)
USDC_ARBITRUM = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
MAX_POSITIONS = 8


def build_hyperliquid_vault(pos: Position) -> DependencyGraph:
    addr = pos.market_address.lower()
    d = hyperliquid.vault_details(addr)
    value, notional = hyperliquid.vault_positions(addr)
    url = hyperliquid.vault_url(addr)
    is_hlp = addr == hyperliquid.HLP
    lockup = hyperliquid.LOCKUP_DAYS_HLP if is_hlp else hyperliquid.LOCKUP_DAYS_USER_VAULT

    nodes: list[Node] = []
    edges: list[Edge] = []
    pos_id = f"position:hl-vault-{addr[:10]}"
    nodes.append(Node(pos_id, "position", f"Deposit USDC · {d['name']}", "Hyperliquid L1",
                      {"size_usd": pos.size_usd, "apr": d.get("apr")}))

    vault_id = f"vault:{addr}"
    gross = sum(notional.values())
    nodes.append(Node(vault_id, "vault", d["name"], "Hyperliquid L1", {
        "address": addr, "leader": d.get("leader"), "account_value_usd": value,
        "gross_notional_usd": gross, "leverage": gross / value if value else None,
        "liquidity_usd": float(d.get("maxWithdrawable") or d.get("maxDistributable") or 0),
        "leader_commission": d.get("leaderCommission"), "lockup_days": lockup,
        "deposits_open": d.get("allowDeposits"), "closed": d.get("isClosed")}))
    edges.append(Edge(pos_id, vault_id, "deposited_in", 1.0, url))

    # The venue: every dollar of the vault is margin on the exchange.
    venue_id = add_node(nodes, Node("venue:hyperliquid", "venue", "Hyperliquid", "Hyperliquid L1",
                                    {"type": "perp exchange"}))
    edges.append(Edge(vault_id, venue_id, "trades_on", 1.0,
                      f"Vault account on Hyperliquid perps ({hyperliquid.URL} vaultDetails): {url}"))
    chain_id = add_chain(nodes, HYPERLIQUID_CHAIN)
    edges.append(Edge(venue_id, chain_id, "settles_on", 1.0, f"{hyperliquid.DOCS} (HyperCore)"))

    # Deposited USDC sits in the Hyperliquid bridge on Arbitrum.
    bridge_id = add_protocol(nodes, edges, 42161, "hyperliquid-bridge", "Hyperliquid Bridge",
                             "https://defillama.com/protocol/hyperliquid-bridge")
    edges.append(Edge(venue_id, bridge_id, "custodies_via", 1.0,
                      f"USDC deposits are held by the bridge on Arbitrum: {hyperliquid.DOCS}"))
    usdc_id = add_node(nodes, Node("asset:USDC", "asset", "USDC", "Arbitrum",
                                   {"address": USDC_ARBITRUM}))
    edges.append(Edge(pos_id, usdc_id, "denominated_in", 1.0, url))

    oracle_id = add_node(nodes, Node("oracle:hyperliquid-validators", "oracle",
                                     "Hyperliquid validator oracle", "Hyperliquid L1",
                                     {"source": "validators publish CEX-weighted spot prices",
                                      "source_verified": None}))
    edges.append(Edge(venue_id, oracle_id, "priced_by", 1.0, f"{hyperliquid.DOCS} (oracle)"))

    # Market risk: the largest perp positions, exposure = notional / account value.
    for coin, usd in sorted(notional.items(), key=lambda kv: -kv[1])[:MAX_POSITIONS]:
        market_id = add_node(nodes, Node(f"market:hl-{coin}-perp", "market", f"{coin}-PERP",
                                         "Hyperliquid L1", {"notional_usd": usd}))
        edges.append(Edge(vault_id, market_id, "holds_position_in",
                          round(min(1.0, usd / value), 3) if value else 0.0,
                          f"{usd:,.0f} USD {coin} position vs {value:,.0f} USD account value "
                          f"({hyperliquid.URL} clearinghouseState)"))
    return DependencyGraph(position_id=pos_id, nodes=nodes, edges=edges)
