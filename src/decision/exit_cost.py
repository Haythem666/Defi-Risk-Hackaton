"""Exit cost of a Pendle PT position from a live router quote."""

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
    pt_amount = int(pos.size_usd / pt_price * 1e18)
    m = pendle.market(pos.chain_id, pos.market_address)
    try:
        q = pendle.sell_quote(pos.chain_id, pos.market_address, m["pt"], m["sy"], pt_amount)
        cost = abs(q["priceImpact"]) + q["fee"]["usd"] / pos.size_usd
        return cost, "Pendle router quote (price impact + fee), live"
    except Exception:
        cost = amm_exit_cost(pos.size_usd, market.meta["liquidity_usd"],
                             market.meta.get("fee_rate") or 0.0)
        return cost, "Constant-product approximation (Pendle quote unavailable)"
