"""Exit cost of a position: live Pendle quote for PTs, pool liquidity for loans.

Two moments to leave:
- now, before any incident (exit_cost): today's quote for the pocket alone;
- late, once an incident has hit (late_exit): everyone heads for the same
  door. A PT is sold into the same pool as the PTs that lenders liquidate; a
  lender queues behind the other depositors for the same idle liquidity.
"""

from datetime import datetime, timezone

from src.data import pendle
from src.decision.rule import amm_exit_cost
from src.schemas import DependencyGraph, Position


# JUDGEMENT: in a crisis, the PT falls until buyers who hold it to maturity
# (it redeems 1:1 for the underlying) earn this yield; it cannot fall further
# while the underlying holds, whatever the crowd sells.
CRISIS_PT_YIELD = 0.30


def _pendle_sale(pos: Position, graph: DependencyGraph, usd: float) -> tuple[float, str]:
    """Cost of selling `usd` of PT into SY: Pendle's router quote (includes
    limit orders), else the constant-product approximation."""
    position = graph.node(graph.position_id)
    market = next(n for n in graph.nodes if n.type == "market")
    asset = next(n for n in graph.nodes if n.type == "asset")
    pt_price = (asset.meta.get("price_usd") or 1.0) * (1 - (position.meta.get("pt_discount") or 0.0))
    m = pendle.market(pos.chain_id, pos.market_address)
    decimals = pendle.assets(pos.chain_id).get(m["pt"], {}).get("decimals", 18)
    pt_amount = int(usd / pt_price * 10 ** decimals)
    try:
        q = pendle.sell_quote(pos.chain_id, pos.market_address, m["pt"], m["sy"], pt_amount)
        cost = abs(q["priceImpact"]) + q["fee"]["usd"] / usd
        return cost, "Pendle router quote (price impact + fee), live"
    except Exception:
        cost = amm_exit_cost(usd, market.meta["liquidity_usd"], market.meta.get("fee_rate") or 0.0)
        return cost, ("Constant-product approximation (Pendle router gave no quote, "
                      "usually because the size exceeds what the pool can absorb)")


def pendle_exit_cost(pos: Position, graph: DependencyGraph) -> tuple[float, str]:
    """Return (cost as fraction of size, where the number comes from): selling
    the pocket alone, today."""
    return _pendle_sale(pos, graph, pos.size_usd)


def _days_to_maturity(graph: DependencyGraph) -> float | None:
    expiry = graph.node(graph.position_id).meta.get("expiry")
    if not expiry:
        return None
    end = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    return max(0.0, (end - datetime.now(timezone.utc)).total_seconds() / 86400)


def pendle_late_exit(pos: Position, graph: DependencyGraph) -> dict:
    """Selling the PT after an incident, at the same time as the crowd: the PT
    that Morpho liquidates when its price drops 5% (marketCollateralAtRisk) hits
    the same Pendle pool. The pocket sells inside that batch and pays the
    batch's price impact, at most the discount at which holding to maturity
    pays CRISIS_PT_YIELD."""
    crowd = sum(n.meta.get("liquidated_at_-5pct_usd") or 0 for n in graph.nodes if n.type == "lending")
    batch, src = _pendle_sale(pos, graph, pos.size_usd + crowd) if crowd else pendle_exit_cost(pos, graph)
    days = _days_to_maturity(graph)
    floor = 1 - (1 + CRISIS_PT_YIELD) ** (-(days or 0) / 365) if days is not None else None
    cost = min(batch, floor) if floor is not None else batch
    why = (f"Sold with {crowd:,.0f} USD of PT that lenders liquidate at a 5% drop (Morpho "
           f"marketCollateralAtRisk): batch of {pos.size_usd + crowd:,.0f} USD costs {batch:.2%} ({src})"
           if crowd else f"No forced sellers measured on this PT: today's quote, {batch:.2%}")
    if floor is not None:
        why += (f"; capped at {floor:.2%}, the discount at which holding the PT {days:.0f} days to "
                f"maturity earns {CRISIS_PT_YIELD:.0%}/yr (JUDGEMENT): buyers step in there")
    return {"cost": cost, "crowd_usd": crowd, "source": why + "."}


def lending_exit_cost(pos: Position, graph: DependencyGraph) -> tuple[float, str]:
    """Withdrawing a loan costs nothing (gas aside) while the pool has idle
    liquidity. Above it, the rest is stuck until borrowers repay: not a
    price loss, but the position cannot be exited, which the source says."""
    pool = _pool(graph)
    liquidity = pool.meta.get("liquidity_usd") or 0.0
    lockup = pool.meta.get("lockup_days")
    wait = f"; {lockup}-day lock-up after deposit" if lockup else ""
    if liquidity >= pos.size_usd:
        return 0.0, f"Withdraw from the pool: {liquidity:,.0f} USD idle liquidity covers it{wait}"
    share = liquidity / pos.size_usd if pos.size_usd else 0.0
    return 0.0, (f"Only {share:.0%} withdrawable now ({liquidity:,.0f} USD idle liquidity); "
                 f"the rest is stuck until borrowers repay")


def _pool(graph: DependencyGraph):
    """A vault's own liquidity (what it can pull back from its markets), else the pool's."""
    return next((n for n in graph.nodes if n.type == "vault"), None) or \
        next(n for n in graph.nodes if n.type == "lending")


def lending_late_exit(pos: Position, graph: DependencyGraph) -> dict:
    """Withdrawing after an incident: the price does not move, the queue does.
    Idle liquidity is first come, first served; if every depositor heads for
    the door, each gets out at most idle liquidity / total deposits, and the
    rest waits for borrowers to repay, through the whole incident (the loss
    if hit already assumes the pocket sits through it)."""
    pool = _pool(graph)
    liquidity = pool.meta.get("liquidity_usd") or 0.0
    total = pool.meta.get("total_usd") or pool.meta.get("supply_usd") or 0.0
    now = min(1.0, liquidity / pos.size_usd) if pos.size_usd else 0.0
    run = min(1.0, liquidity / total) if total else now
    return {"cost": 0.0, "crowd_usd": total, "withdrawable_now": now, "withdrawable_in_run": run,
            "source": (f"No sale, a queue: today {now:.0%} of the pocket can be withdrawn "
                       f"({liquidity:,.0f} USD idle); if all {total:,.0f} USD of deposits run, "
                       f"each depositor gets {run:.0%} out and the rest is stuck until borrowers repay.")}


def late_exit(pos: Position, graph: DependencyGraph) -> dict | None:
    """Cost of leaving once an incident has hit (None: no model for this kind)."""
    if pos.kind == "pendle_pt":
        return pendle_late_exit(pos, graph)
    if pos.kind in ("morpho_supply", "aave_supply", "morpho_vault", "kamino"):
        return lending_late_exit(pos, graph)
    return None


def contract_exit_cost(pos: Position, graph: DependencyGraph) -> tuple[float, str]:
    """A contract found by the crawler: an ERC-4626 token can be redeemed at
    the contract's own price (no market sale), possibly after a cooldown.
    Anything else has no live quote yet, so the brief's reference is used."""
    held = next(e.target for e in graph.edges
                if e.source == graph.position_id and e.kind == "holds")
    root = graph.node(held).meta
    if root.get("redeemable"):
        cd = root.get("cooldown_s")
        wait = f" after a {cd / 86400:.1f}-day cooldown" if cd else ""
        return 0.0, (f"Redeem directly from the contract{wait}, no market sale (gas aside); "
                     f"a vault can only pay out its idle liquidity")
    return 0.11, "No live exit quote for this contract: the brief's reference exit cost (11%)"


def exit_cost(pos: Position, graph: DependencyGraph) -> tuple[float, str]:
    if pos.kind == "pendle_pt":
        return pendle_exit_cost(pos, graph)
    if pos.kind == "contract":
        return contract_exit_cost(pos, graph)
    return lending_exit_cost(pos, graph)
