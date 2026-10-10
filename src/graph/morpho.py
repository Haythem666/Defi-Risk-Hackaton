"""Dependency graph of a Morpho position, from the Morpho API only.

Two positions:
- lending in one Morpho market (build_morpho_supply),
- depositing in a Morpho vault, v1 or V2 (build_morpho_vault).

What each piece of the graph comes from:
    position --deposited_in--> vault            (the address you gave)
    vault --allocates_to (share)--> market      (vault allocation / V2 adapters)
    market --secured_by (utilization)--> collateral token
    market --priced_by--> oracle
    vault/market --runs_on--> Morpho  --deployed_on--> chain
    vault --owned_by / curated_by--> who controls it (addresses from the API)

Exposure on an edge = share of the source's value that relies on the target:
a vault with 30% of its money in a market has exposure 0.30 to it; a market
lending 90% of its supply has exposure 0.90 to its collateral (only what is
lent out is at risk if the collateral collapses).
"""

from src.data import morpho
from src.schemas import DependencyGraph, Edge, Node, Position

EXPLORERS = {1: "https://etherscan.io/address/", 42161: "https://arbiscan.io/address/",
             8453: "https://basescan.org/address/", 999: "https://hyperevmscan.io/address/"}
MIN_ALLOCATION_SHARE = 0.01  # vault allocations below 1% are left out of the graph
MAX_V2_NESTING = 2           # a V2 vault can hold other vaults: follow this many levels
# V2 settings that decide where deposits can go: with no timelock the curator
# can send money to a new market before depositors have time to withdraw.
V2_ROUTING = ("addAdapter", "increaseAbsoluteCap", "increaseRelativeCap")


class Graph:
    """Nodes and edges being built. Adding a node twice keeps the first one,
    so two markets sharing an oracle point to the same oracle node."""

    def __init__(self, chain_id: int):
        self.cid, self.chain = chain_id, morpho.CHAINS.get(chain_id, str(chain_id))
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []

    def node(self, id: str, type: str, name: str, **meta) -> str:
        self.nodes.setdefault(id, Node(id, type, name, self.chain, meta))
        return id

    def edge(self, source: str, target: str, kind: str, exposure: float, evidence: str):
        self.edges.append(Edge(source, target, kind, round(exposure, 3), evidence))

    def link(self, address: str) -> str:
        return EXPLORERS.get(self.cid, "") + address

    def chain_node(self) -> str:
        return self.node(f"chain:{self.chain.lower()}", "chain", self.chain, chain_id=self.cid)

    def morpho(self) -> str:
        """The Morpho protocol node, on its chain. Category "Lending" is what
        the risk model uses to pick Morpho's hack rate."""
        if "protocol:morpho" not in self.nodes:
            self.node("protocol:morpho", "protocol", "Morpho", category="Lending")
            self.edge("protocol:morpho", self.chain_node(), "deployed_on", 1.0,
                      "https://app.morpho.org")
        return "protocol:morpho"

    def token(self, t: dict) -> str:
        return self.node(f"asset:{t['symbol']}", "asset", t["symbol"], address=t["address"],
                         price_usd=(t.get("price") or {}).get("usd"))

    def done(self, position_id: str) -> DependencyGraph:
        return DependencyGraph(position_id, list(self.nodes.values()), self.edges)


def add_market(g: Graph, m: dict, parent: str, exposure: float, kind: str) -> None:
    """A Morpho market, its collateral and its oracle."""
    st, loan, coll = m["state"], m["loanAsset"], m["collateralAsset"]
    url = morpho.market_url(g.cid, m["marketId"])
    util = st["utilization"] or 0.0
    market_id = g.node(f"lending:{m['marketId'][:12]}", "lending",
                       f"Morpho {coll['symbol']}/{loan['symbol']}",
                       market_id=m["marketId"], lltv=int(m["lltv"]) / 1e18,
                       supply_usd=st["supplyAssetsUsd"], borrow_usd=st["borrowAssetsUsd"],
                       liquidity_usd=st["liquidityAssetsUsd"], utilization=util)
    g.edge(parent, market_id, kind, exposure, url)
    g.edge(market_id, g.morpho(), "runs_on", 1.0, url)
    g.edge(market_id, g.token(coll), "secured_by", util,
           f"Borrowers post {coll['symbol']}; {util:.0%} of supply is lent out: {url}")
    oracle = (m.get("oracle") or {}).get("address")
    if oracle:
        oracle_id = g.node(f"oracle:{oracle.lower()}", "oracle", f"Oracle {oracle[:10]}",
                           address=oracle, oracle_type=(m["oracle"] or {}).get("type"))
        g.edge(market_id, oracle_id, "priced_by", util, g.link(oracle))


def build_morpho_supply(pos: Position) -> DependencyGraph:
    """Lending the loan asset in one Morpho market."""
    g = Graph(pos.chain_id)
    m = morpho.market(pos.chain_id, pos.market_address)
    if m is None:
        raise ValueError(f"No Morpho market {pos.market_address} on {g.chain}")
    loan, coll = m["loanAsset"], m["collateralAsset"]
    url = morpho.market_url(pos.chain_id, m["marketId"])
    pos_id = g.node(f"position:lend-{m['marketId'][:12]}", "position",
                    f"Lend {loan['symbol']} · Morpho {coll['symbol']}/{loan['symbol']}",
                    size_usd=pos.size_usd)
    g.edge(pos_id, g.chain_node(), "settles_on", 1.0, url)
    g.edge(pos_id, g.token(loan), "denominated_in", 1.0, f"A claim on {loan['symbol']}: {url}")
    add_market(g, m, pos_id, 1.0, "supplied_to")
    return g.done(pos_id)


def build_morpho_vault(pos: Position) -> DependencyGraph:
    """Depositing in a Morpho vault. Asks the API for a v1 vault first, then a V2."""
    g = Graph(pos.chain_id)
    v1 = morpho.vault(pos.chain_id, pos.market_address)
    v = v1 or morpho.vault_v2(pos.chain_id, pos.market_address)
    if v is None:
        raise ValueError(f"No Morpho vault (v1 or V2) at {pos.market_address} on {g.chain}")
    asset = v["asset"]
    pos_id = g.node(f"position:vault-{v['address'][:10]}", "position",
                    f"Deposit {asset['symbol']} · {v['name']}", size_usd=pos.size_usd)
    g.edge(pos_id, g.chain_node(), "settles_on", 1.0, g.link(v["address"]))
    g.edge(pos_id, g.token(asset), "denominated_in", 1.0,
           f"Vault shares are a claim on {asset['symbol']}: {morpho.vault_url(g.cid, v['address'])}")
    if v1:
        add_vault_v1(g, v1, pos_id, 1.0, "deposited_in")
    else:
        add_vault_v2(g, v, pos_id, 1.0, "deposited_in")
    return g.done(pos_id)


def add_vault_v1(g: Graph, v: dict, parent: str, share: float, kind: str) -> str:
    """A v1 vault: its allocation lists how much sits in each market."""
    st, url = v["state"], morpho.vault_url(g.cid, v["address"])
    total = st["totalAssetsUsd"] or 0.0
    vault_id = g.node(f"vault:{v['address'].lower()}", "vault", v["name"], address=v["address"],
                      version=1, total_usd=total, liquidity_usd=(v.get("liquidity") or {}).get("usd"),
                      curators=[c["name"] for c in st.get("curators") or []],
                      timelock_days=(st.get("timelock") or 0) / 86400, fee=st.get("fee"),
                      warnings=[w["type"] for w in v.get("warnings") or []])
    g.edge(parent, vault_id, kind, share, url)
    g.edge(vault_id, g.morpho(), "runs_on", 1.0, url)
    for a in st["allocation"]:
        s = (a["supplyAssetsUsd"] or 0) / total if total else 0.0
        if s * share < MIN_ALLOCATION_SHARE:
            continue
        m = morpho.market(g.cid, a["market"]["marketId"])
        if m and m.get("collateralAsset"):  # else idle market: cash, nothing lent out
            add_market(g, m, vault_id, s, "allocates_to")
    return vault_id


def add_vault_v2(g: Graph, v: dict, parent: str, share: float, kind: str, depth: int = 0) -> str:
    """A V2 vault: money reaches markets through adapters. Each adapter says
    how many USD it holds; a MorphoMarketV1 adapter also lists its markets."""
    url = morpho.vault_url(g.cid, v["address"])
    total = v["totalAssetsUsd"] or 0.0
    locks = {morpho.V2_TIMELOCKS.get(t["selector"], t["selector"]): t["duration"] / 86400
             for t in v.get("timelocks") or []}
    flags = [f"{name}: no timelock, the curator can route deposits to a new market instantly"
             for name in V2_ROUTING if locks.get(name) == 0]
    vault_id = g.node(f"vault:{v['address'].lower()}", "vault", v["name"], address=v["address"],
                      version=2, total_usd=total, liquidity_usd=v.get("liquidityUsd"),
                      fee=v.get("performanceFee"), timelocks_days=locks,
                      timelock_days=max((locks.get(n) or 0) for n in V2_ROUTING),
                      warnings=[w["type"] for w in v.get("warnings") or []], flags=flags)
    g.edge(parent, vault_id, kind, share, url)
    g.edge(vault_id, g.morpho(), "runs_on", 1.0, url)

    for role, edge_kind in (("owner", "owned_by"), ("curator", "curated_by")):
        who = (v.get(role) or {}).get("address")
        if who:
            admin = g.node(f"admin:{who.lower()}", "admin", f"Controller {who[:6]}…{who[-4:]}",
                           address=who)
            g.edge(vault_id, admin, edge_kind, 1.0, f"{role} per Morpho API: {g.link(who)}")

    for ad in (v.get("adapters") or {}).get("items") or []:
        if ad["type"] == "MorphoMarketV1":  # direct lending in Morpho markets
            for p in (ad.get("positions") or {}).get("items") or []:
                s = (p["state"]["supplyAssetsUsd"] or 0) / total if total else 0.0
                if s * share < MIN_ALLOCATION_SHARE:
                    continue
                m = morpho.market(g.cid, p["market"]["marketId"])
                if m and m.get("collateralAsset"):
                    add_market(g, m, vault_id, s, "allocates_to")
            continue
        s = (ad.get("assetsUsd") or 0) / total if total else 0.0
        if s * share < MIN_ALLOCATION_SHARE:
            continue
        if ad["type"] == "MetaMorpho":  # money parked in a v1 vault
            inner = morpho.vault(g.cid, ad["metaMorpho"]["address"])
            if inner:
                add_vault_v1(g, inner, vault_id, s, "allocates_to")
        elif ad["type"] == "MorphoVaultV2" and depth < MAX_V2_NESTING:  # in another V2 vault
            inner = morpho.vault_v2(g.cid, ad["innerVault"]["address"])
            if inner:
                add_vault_v2(g, inner, vault_id, s, "allocates_to", depth + 1)
    return vault_id
