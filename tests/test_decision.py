from src.decision.rule import amm_exit_cost, breakeven_probability, decide
from src.schemas import RiskResult, Scenario


def _risk(p, loss):
    s = Scenario("x", "hack", p, loss)
    return RiskResult([s], expected_loss=p * loss, worst_case_loss=loss)


def test_brief_reference_case():
    # Brief: exit costs 11%. If the pocket would lose 50% when hit, p* = 22%.
    assert abs(breakeven_probability(0.11, 0.50) - 0.22) < 1e-9
    assert decide(_risk(0.30, 0.50), 0.11).decision == "EXIT"   # 15% > 11%
    assert decide(_risk(0.10, 0.50), 0.11).decision == "STAY"   # 5% < 11%


def test_breakeven_edge_cases():
    assert breakeven_probability(0.11, 0.0) is None
    assert breakeven_probability(0.5, 0.1) == 1.0


def test_amm_exit_cost_grows_with_size():
    small = amm_exit_cost(10_000, 4_000_000)
    big = amm_exit_cost(1_000_000, 4_000_000)
    assert 0 < small < big < 1


def test_yield_given_up_counts_as_a_cost_of_leaving():
    risk = _risk(0.01, 0.20)                     # expected loss 0.2% over the horizon
    assert decide(risk, 0.0).decision == "EXIT"  # free exit, no yield: any risk says leave
    assert decide(risk, 0.0, forgone_yield=0.006).decision == "STAY"  # 7%/yr x 30 days = 0.6%


def test_crossed_exit_trigger_forces_exit():
    risk = _risk(0.001, 0.10)
    trigger = {"triggered": True, "utilization": 0.95, "u_star": 0.90, "haircut": 0.5}
    assert decide(risk, 0.0, 0.006, trigger).decision == "EXIT"
