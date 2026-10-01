"""Shared data contract. Everyone imports from here. Change it only after
telling the whole team (it breaks everybody's code if it moves silently)."""

from dataclasses import dataclass, field
from typing import Literal, Optional

NodeType = Literal[
    "position",   # the position we hold (e.g. a Pendle PT)
    "chain",      # settlement chain (Ethereum, Solana, ...)
    "protocol",   # a DeFi protocol (Pendle, Aave, ...)
    "asset",      # a token
    "issuer",     # entity behind a yield source / stablecoin
    "oracle",     # price feed
    "market",     # trading market / AMM pool
    "lending",    # lending market using the asset as collateral
    "venue",      # external venue (e.g. perp exchange)
]

PositionKind = Literal[
    "pendle_pt",      # holding a Pendle principal token
    "morpho_supply",  # lending the loan asset in one Morpho market
    "aave_supply",    # supplying an asset to an Aave pool
]

IncidentType = Literal[
    "hack",            # smart-contract exploit
    "oracle_failure",  # wrong / stale price
    "depeg",           # asset loses its peg
    "chain_halt",      # chain stops or is congested
    "liquidity_crunch" # market dries up
]


@dataclass
class Position:
    """What the user holds. Input of the whole pipeline."""
    chain_id: int                # EVM chain id, 1 = Ethereum
    market_address: str          # Pendle market / Morpho market id / Aave pool address
    size_usd: float              # notional of the pocket
    horizon_days: int = 30       # decision horizon: probabilities are over this window
    book_share: float = 0.10     # share of the whole book in this pocket (brief: 10 pockets of 10%)
    kind: PositionKind = "pendle_pt"
    asset_address: Optional[str] = None  # supplied asset, for "aave_supply"


@dataclass
class Node:
    id: str                      # unique, e.g. "oracle:chainlink-usde-usd"
    type: NodeType
    name: str
    chain: Optional[str] = None
    meta: dict = field(default_factory=dict)  # tvl, address, etc.


@dataclass
class Edge:
    """`source` DEPENDS ON `target`."""
    source: str                  # Node.id
    target: str                  # Node.id
    kind: str                    # free text: "priced_by", "issued_by", "collateral_in", ...
    exposure: float = 1.0        # 0..1 share of the source's value that relies on target
    evidence: Optional[str] = None  # URL or note proving this dependency exists


@dataclass
class DependencyGraph:
    position_id: str             # Node.id of the position
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def node(self, node_id: str) -> Node:
        return next(n for n in self.nodes if n.id == node_id)


@dataclass
class Scenario:
    """'Node X is hit by incident Y' and what it costs the position."""
    node_id: str
    incident: IncidentType
    probability: float           # over the decision horizon, 0..1
    loss_if_hit: float           # fraction of the position lost, 0..1
    rationale: str = ""          # where the numbers come from


@dataclass
class RiskResult:
    scenarios: list[Scenario]
    expected_loss: float         # fraction of the position
    worst_case_loss: float       # e.g. average loss in the worst 5% of runs
    breakeven_probability: Optional[float] = None


@dataclass
class Verdict:
    decision: Literal["STAY", "EXIT"]
    expected_loss: float
    exit_cost: float             # e.g. 0.11 for 11% slippage
    reason: str                  # one plain sentence a risk manager can read
    breakeven_probability: Optional[float] = None
