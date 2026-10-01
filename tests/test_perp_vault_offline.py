"""Hyperliquid vault graph, on the cached snapshot in data/cache."""

import pytest

from src.data import hyperliquid
from src.graph.build import build_graph
from src.schemas import Position


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("DEFI_OFFLINE", "1")


def test_hlp_depends_on_venue_bridge_and_oracle():
    g = build_graph(Position(999, hyperliquid.HLP, 1e6, kind="hyperliquid_vault"))
    ids = {n.id for n in g.nodes}
    assert {"venue:hyperliquid", "protocol:hyperliquid-bridge",
            "oracle:hyperliquid-validators", "chain:arbitrum"} <= ids
    assert all(e.evidence for e in g.edges)
    assert all(0 <= e.exposure <= 1 for e in g.edges)
    vault = next(n for n in g.nodes if n.type == "vault")
    assert vault.meta["lockup_days"] == hyperliquid.LOCKUP_DAYS_HLP
