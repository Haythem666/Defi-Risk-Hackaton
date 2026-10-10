"""Entry point: build the dependency graph of a Morpho position."""

from src.graph.morpho import build_morpho_supply, build_morpho_vault
from src.schemas import DependencyGraph, Position

BUILDERS = {
    "morpho_supply": build_morpho_supply,  # lending in one Morpho market
    "morpho_vault": build_morpho_vault,    # depositing in a Morpho vault (v1 or V2)
}


def build_graph(pos: Position) -> DependencyGraph:
    if pos.kind not in BUILDERS:
        raise ValueError(f"This branch only covers Morpho: kind must be one of {list(BUILDERS)}")
    return BUILDERS[pos.kind](pos)
