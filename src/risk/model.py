"""Scenarios -> propagation to the position -> Monte Carlo -> RiskResult."""

import networkx as nx
import numpy as np

from src.risk.assumptions import ASSUMPTIONS
from src.schemas import DependencyGraph, RiskResult, Scenario


def to_networkx(g: DependencyGraph) -> nx.DiGraph:
    G = nx.DiGraph()
    for n in g.nodes:
        G.add_node(n.id, type=n.type, name=n.name)
    for e in g.edges:
        G.add_edge(e.source, e.target, kind=e.kind, exposure=e.exposure)
    return G


def path_exposure(G: nx.DiGraph, source: str, target: str) -> float:
    """Share of `source` that depends on `target`.

    Each path contributes the product of its edge exposures. Paths are added
    up, because distinct paths usually carry distinct parts of the value (a
    vault lending to two markets backed by the same collateral), and the sum
    is capped at 1 for paths that overlap (everything settles on one chain).
    """
    if source == target:
        return 1.0
    total = 0.0
    for path in nx.all_simple_paths(G, source, target):
        e = 1.0
        for a, b in zip(path, path[1:]):
            e *= G.edges[a, b]["exposure"]
        total += e
    return min(1.0, total)


def horizon_probability(annual_p: float, horizon_days: int) -> float:
    """Constant-hazard conversion of a yearly probability to the horizon."""
    return 1 - (1 - annual_p) ** (horizon_days / 365)


def build_scenarios(g: DependencyGraph, horizon_days: int) -> list[Scenario]:
    G = to_networkx(g)
    out = []
    for n in g.nodes:
        if n.id == g.position_id:
            continue
        exp = path_exposure(G, g.position_id, n.id)
        if exp == 0:
            continue
        for a in ASSUMPTIONS.get(n.type, []):
            out.append(Scenario(
                node_id=n.id, incident=a["incident"],
                probability=horizon_probability(a["annual_p"], horizon_days),
                loss_if_hit=a["severity"] * exp,
                rationale=f"{a['rationale']} Exposure along graph = {exp:.2f}."))
    return out


def simulate(scenarios: list[Scenario], n_runs: int = 20_000, tail: float = 0.05,
             seed: int = 0) -> RiskResult:
    """Independent incidents. Losses compound: survived = prod(1 - loss_i)."""
    if not scenarios:
        return RiskResult([], 0.0, 0.0)
    rng = np.random.default_rng(seed)
    p = np.array([s.probability for s in scenarios])
    loss = np.array([s.loss_if_hit for s in scenarios])
    hits = rng.random((n_runs, len(scenarios))) < p
    run_loss = 1 - np.prod(np.where(hits, 1 - loss, 1.0), axis=1)
    k = max(1, int(n_runs * tail))
    worst = float(np.sort(run_loss)[-k:].mean())
    return RiskResult(scenarios=scenarios, expected_loss=float(run_loss.mean()),
                      worst_case_loss=worst)
