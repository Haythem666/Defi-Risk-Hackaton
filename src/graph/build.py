"""Entry point: build the dependency graph of any supported position."""

from src.graph.lending import build_aave_supply, build_morpho_supply
from src.graph.pendle_pt import build_graph as build_pendle_pt
from src.schemas import DependencyGraph, Position

BUILDERS = {
    "pendle_pt": build_pendle_pt,
    "morpho_supply": build_morpho_supply,
    "aave_supply": build_aave_supply,
}


def build_graph(pos: Position) -> DependencyGraph:
    return BUILDERS[pos.kind](pos)
