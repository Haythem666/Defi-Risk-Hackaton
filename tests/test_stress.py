"""Stress engine on a hand-made graph: position -> vault -> market -> collateral."""

import pytest

from src.decision import snell
from src.risk import stress
from src.schemas import DependencyGraph, Edge, Node


def graph(impact=0.0, has_market=True, liquidated=None, bonus=0.05, util=0.91, lltv=0.86):
    nodes = [Node("P", "position", "P"), Node("V", "vault", "V", meta={"net_apy": 0.06}),
             Node("M", "lending", "M", meta={"lltv": lltv, "utilization": util,
                                             "liquidation_price_impact": impact,
                                             "liquidated_at_shock_usd": liquidated,
                                             "liquidation_bonus": bonus}),
             Node("C", "asset", "C"), Node("X", "chain", "Ethereum"),
             Node("E", "market", "DEX exit", meta={"has_market": has_market})]
    edges = [Edge("P", "V", "deposited_in", 1.0, "t"), Edge("V", "M", "allocates_to", 1.0, "t"),
             Edge("M", "C", "secured_by", util, "t"), Edge("M", "E", "liquidated_via", 0.0, "t"),
             Edge("P", "X", "settles_on", 1.0, "t"), Edge("V", "X", "deployed_on", 1.0, "t"),
             Edge("M", "X", "deployed_on", 1.0, "t"), Edge("C", "X", "deployed_on", 1.0, "t")]
    return DependencyGraph("P", nodes, edges)


def test_small_drops_stay_inside_the_borrowers_buffer():
    g = graph()
    assert stress.position_loss(g, "C", 0.10) == 0.0          # 10% < 1 - LLTV = 14%
    loss = stress.position_loss(g, "C", 0.50)                  # lender keeps collateral worth 0.5
    assert loss == pytest.approx(0.91 * (1 - 0.5 / 0.86))


def test_no_market_means_no_recovery_beyond_the_buffer():
    g = graph(has_market=False)
    assert stress.position_loss(g, "C", 0.20) == pytest.approx(0.91)


def test_shared_dependency_counts_once_and_losses_are_capped():
    g = graph()
    assert stress.position_loss(g, "X", 0.05) == pytest.approx(0.05)  # not 4 x 5%
    assert all(0 <= v <= 1 for v in stress.propagate(g, {"X": 1.0, "C": 1.0}).values())


def test_bigger_shocks_never_cost_less():
    g = graph(impact=0.03, liquidated=1e6)
    losses = [stress.position_loss(g, n, s) for n in ("C", "X") for s in stress.SEVERITIES]
    for n in range(2):
        row = losses[n * 4:(n + 1) * 4]
        assert row == sorted(row)


def test_spiral_phases():
    damped = stress.loop_gains(graph(impact=0.02, liquidated=1e6))["C"]
    assert damped["phase"] == "damped" and damped["gain"] == pytest.approx(0.4)
    hot = stress.loop_gains(graph(impact=0.08, liquidated=1e6, bonus=0.10))["C"]
    assert hot["phase"] == "supercritical" and stress.spectral(graph(impact=0.08, liquidated=1e6,
                                                                       bonus=0.10))["rho"] >= 1
    assert stress.loop_gains(graph(impact=0.30, liquidated=1e6))["C"]["phase"] == "stalled"


def test_exit_threshold_matches_the_closed_form():
    g = graph(has_market=False)
    rule = snell.exit_rule(g, exit_cost=0.0)
    H, r = rule["haircut"], 0.06
    assert rule["u_star"] == pytest.approx(1 - (snell.KAPPA * H / r) ** (1 / snell.GAMMA))
    assert rule["triggered"] == (0.91 >= rule["u_star"])
