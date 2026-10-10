from src.risk.model import horizon_probability, path_exposure, simulate, to_networkx
from src.schemas import DependencyGraph, Edge, Node, Scenario


def test_horizon_probability_is_poisson():
    assert abs(horizon_probability(0.1, 365) - 0.0952) < 1e-3  # 1 - e^-0.1
    assert horizon_probability(0.1, 30) < 0.1
    assert 0 < horizon_probability(1.5, 365) < 1  # rate above 1/year stays a probability


def test_path_exposure_adds_paths_and_caps_at_one():
    g = DependencyGraph("p", [Node("p", "position", "P"), Node("a", "asset", "A"),
                              Node("o", "oracle", "O")],
                        [Edge("p", "a", "x", 0.5), Edge("a", "o", "x", 0.5), Edge("p", "o", "x", 0.4)])
    assert abs(path_exposure(to_networkx(g), "p", "o") - 0.65) < 1e-12  # 0.25 + 0.4
    g.edges.append(Edge("p", "o", "y", 0.9))
    g.edges = [e for e in g.edges if not (e.kind == "x" and e.target == "o" and e.source == "p")]
    assert path_exposure(to_networkx(g), "p", "o") == 1.0  # 0.25 + 0.9 capped


def test_monte_carlo_matches_single_scenario():
    r = simulate([Scenario("x", "hack", 0.2, 0.5)], n_runs=100_000)
    assert abs(r.expected_loss - 0.1) < 0.005
    assert r.worst_case_loss == 0.5
