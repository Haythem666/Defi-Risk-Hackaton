"""Runs on the cached snapshot in data/cache (no network needed)."""

import os

import pytest

from src.graph.pendle_pt import build_graph
from src.schemas import Position

PT_SUSDE_NOV26 = "0x47ad2cd1dd15739a7a035b9d3b7828d916fef77e"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("DEFI_OFFLINE", "1")


def test_pt_susde_has_all_five_layers():
    g = build_graph(Position(1, PT_SUSDE_NOV26, 1_000_000))
    types = {n.type for n in g.nodes}
    assert {"chain", "asset", "issuer", "oracle", "market", "lending"} <= types
    assert all(e.evidence for e in g.edges), "every edge needs evidence"
    ids = {n.id for n in g.nodes}
    assert all(e.source in ids and e.target in ids for e in g.edges)
