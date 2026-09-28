from src.risk.model import horizon_probability, path_exposure, simulate, to_networkx
from src.schemas import DependencyGraph, Edge, Node, Scenario


def test_horizon_probability():
    assert abs(horizon_probability(0.1, 365) - 0.1) < 1e-12
    assert horizon_probability(0.1, 30) < 0.1


def test_path_exposure_takes_most_exposed_path():
    g = DependencyGraph("p", [Node("p", "position", "P"), Node("a", "asset", "A"),
                              Node("o", "oracle", "O")],
                        [Edge("p", "a", "x", 0.5), Edge("a", "o", "x", 0.5), Edge("p", "o", "x", 0.4)])
    assert abs(path_exposure(to_networkx(g), "p", "o") - 0.4) < 1e-12


def test_monte_carlo_matches_single_scenario():
    r = simulate([Scenario("x", "hack", 0.2, 0.5)], n_runs=100_000)
    assert abs(r.expected_loss - 0.1) < 0.005
    assert r.worst_case_loss == 0.5
