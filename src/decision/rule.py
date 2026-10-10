"""Exit cost and the STAY / EXIT decision."""

from typing import Optional

from src.schemas import RiskResult, Verdict


def amm_exit_cost(size_usd: float, liquidity_usd: float, fee_rate: float = 0.0) -> float:
    """Slippage to sell `size_usd` into a pool with `liquidity_usd`.

    Constant-product approximation (reserve on each side = liquidity / 2):
    price impact = x / (R + x). Pendle's real curve is a logit curve that is
    flatter near the current rate; replace with the real curve in Phase 2.
    """
    if liquidity_usd <= 0:
        return 1.0
    reserve = liquidity_usd / 2
    return min(1.0, size_usd / (reserve + size_usd) + fee_rate)


def breakeven_probability(exit_cost: float, loss_if_hit: float) -> Optional[float]:
    """p* such that p* x loss_if_hit = exit_cost. Above p*, exiting is cheaper."""
    if loss_if_hit <= 0:
        return None
    return min(1.0, exit_cost / loss_if_hit)


def decide(risk: RiskResult, exit_cost: float, forgone_yield: float = 0.0,
           exit_trigger: Optional[dict] = None) -> Verdict:
    """EXIT if the expected loss over the horizon is more than what leaving
    costs: the exit cost (slippage) plus the yield given up by holding cash
    instead over the same horizon. Also EXIT when the lending position has
    crossed its freeze trigger (decision/snell.py), whatever the average says."""
    cost = exit_cost + forgone_yield
    worst_scenario = max(risk.scenarios, key=lambda s: s.loss_if_hit, default=None)
    p_star = breakeven_probability(cost, worst_scenario.loss_if_hit) if worst_scenario else None
    cost_txt = (f"the cost of leaving {cost:.2%} (exit cost {exit_cost:.2%} + yield given up "
                f"{forgone_yield:.2%})" if forgone_yield else f"the certain exit cost {exit_cost:.2%}")
    if exit_trigger and exit_trigger.get("triggered"):
        decision = "EXIT"
        reason = (f"Utilization {exit_trigger['utilization']:.1%} is above the exit trigger "
                  f"{exit_trigger['u_star']:.1%}: withdrawals risk freezing with a "
                  f"{exit_trigger['haircut']:.1%} haircut if trapped. (Expected loss "
                  f"{risk.expected_loss:.2%} vs {cost_txt}.)")
    elif risk.expected_loss > cost:
        decision = "EXIT"
        reason = (f"Expected loss {risk.expected_loss:.2%} is above {cost_txt}: "
                  f"exiting is cheaper on average.")
    else:
        decision = "STAY"
        reason = (f"Expected loss {risk.expected_loss:.2%} is below {cost_txt}: "
                  f"staying pays more than it risks on average.")
    return Verdict(decision, risk.expected_loss, cost, reason, p_star)
