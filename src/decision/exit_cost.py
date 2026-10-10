"""Exit cost of a Morpho position.

Withdrawing from a Morpho market or vault costs nothing (gas aside) while
there is idle liquidity (supply not borrowed). Above it, the rest is stuck
until borrowers repay: not a price loss, but the position cannot be exited,
which the returned note says.
"""

from src.schemas import DependencyGraph, Position


def exit_cost(pos: Position, graph: DependencyGraph) -> tuple[float, str]:
    # The vault's own liquidity (what it can pull back from its markets), else the market's.
    pool = next((n for n in graph.nodes if n.type == "vault"), None) or \
        next(n for n in graph.nodes if n.type == "lending")
    liquidity = pool.meta.get("liquidity_usd") or 0.0
    if liquidity >= pos.size_usd:
        return 0.0, f"Withdraw: {liquidity:,.0f} USD idle liquidity covers it"
    share = liquidity / pos.size_usd if pos.size_usd else 0.0
    return 0.0, (f"Only {share:.0%} withdrawable now ({liquidity:,.0f} USD idle liquidity); "
                 f"the rest is stuck until borrowers repay")
