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


def decide(risk: RiskResult, exit_cost: float) -> Verdict:
    worst_scenario = max(risk.scenarios, key=lambda s: s.loss_if_hit, default=None)
    p_star = breakeven_probability(exit_cost, worst_scenario.loss_if_hit) if worst_scenario else None
    if risk.expected_loss > exit_cost:
        decision = "EXIT"
        reason = (f"Expected loss {risk.expected_loss:.2%} is above the certain exit cost "
                  f"{exit_cost:.2%}: exiting is cheaper on average.")
    else:
        decision = "STAY"
        reason = (f"Expected loss {risk.expected_loss:.2%} is below the exit cost "
                  f"{exit_cost:.2%}: paying to exit would lose more than it saves on average.")
    return Verdict(decision, risk.expected_loss, exit_cost, reason, p_star)
