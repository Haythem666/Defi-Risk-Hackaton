"""Exit cost of a position: live Pendle quote for PTs, pool liquidity for loans."""

from src.data import pendle
from src.decision.rule import amm_exit_cost
from src.schemas import DependencyGraph, Position


def pendle_exit_cost(pos: Position, graph: DependencyGraph) -> tuple[float, str]:
    """Return (cost as fraction of size, where the number comes from).

    Sells the PT into SY through Pendle's router quote (includes limit orders).
    Falls back to the constant-product approximation if the quote fails.
    """
    position = graph.node(graph.position_id)
    market = next(n for n in graph.nodes if n.type == "market")
    asset = next(n for n in graph.nodes if n.type == "asset")
    pt_price = (asset.meta.get("price_usd") or 1.0) * (1 - (position.meta.get("pt_discount") or 0.0))
    m = pendle.market(pos.chain_id, pos.market_address)
    decimals = pendle.assets(pos.chain_id).get(m["pt"], {}).get("decimals", 18)
    pt_amount = int(pos.size_usd / pt_price * 10 ** decimals)
    try:
        q = pendle.sell_quote(pos.chain_id, pos.market_address, m["pt"], m["sy"], pt_amount)
        cost = abs(q["priceImpact"]) + q["fee"]["usd"] / pos.size_usd
        return cost, "Pendle router quote (price impact + fee), live"
    except Exception:
        cost = amm_exit_cost(pos.size_usd, market.meta["liquidity_usd"],
                             market.meta.get("fee_rate") or 0.0)
        return cost, ("Constant-product approximation (Pendle router gave no quote, "
                      "usually because the size exceeds what the pool can absorb)")


def lending_exit_cost(pos: Position, graph: DependencyGraph) -> tuple[float, str]:
    """Withdrawing a loan costs nothing (gas aside) while the pool has idle
    liquidity. Above it, the rest is stuck until borrowers repay: not a
    price loss, but the position cannot be exited, which the source says."""
    pool = next(n for n in graph.nodes if n.type == "lending")
    liquidity = pool.meta.get("liquidity_usd") or 0.0
    if liquidity >= pos.size_usd:
        return 0.0, f"Withdraw from the pool: {liquidity:,.0f} USD idle liquidity covers it"
    share = liquidity / pos.size_usd if pos.size_usd else 0.0
    return 0.0, (f"Only {share:.0%} withdrawable now ({liquidity:,.0f} USD idle liquidity); "
                 f"the rest is stuck until borrowers repay")


def exit_cost(pos: Position, graph: DependencyGraph) -> tuple[float, str]:
    if pos.kind == "pendle_pt":
        return pendle_exit_cost(pos, graph)
    return lending_exit_cost(pos, graph)
