"""Kamino (Solana) graphs, on the cached snapshot in data/cache."""

import pytest

from src.graph.build import build_graph
from src.schemas import Position

RWA_USDC_VAULT = "DWSXb18xZApz29vnQpgR2m6MynCT7PznaXt7Ut7M7KaP"  # RockawayX RWA USDC (Belem)
HUMA_PST_RESERVE = "DzgYbR8HFQKf8YLCJ6M3E6ricB1xWAiNGZ2TB7X2KDHz"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("DEFI_OFFLINE", "1")


def test_kamino_vault_reaches_reserves_collaterals_and_issuers():
    g = build_graph(Position(101, RWA_USDC_VAULT, 1e6, kind="kamino"))
    ids = {n.id for n in g.nodes}
    assert all(e.source in ids and e.target in ids and e.evidence for e in g.edges)
    allocs = [e for e in g.edges if e.kind == "allocates_to"]
    assert len(allocs) >= 3 and sum(e.exposure for e in allocs) <= 1.0 + 0.0005 * len(allocs)
    secured = {e.target for e in g.edges if e.kind == "secured_by"}
    assert {"asset:PST", "asset:ONyc"} <= secured
    assert any(e.source == "asset:ONyc" and e.kind == "issued_by" for e in g.edges)
    assert any(e.kind == "backed_off_chain" for e in g.edges)
    assert g.node(f"vault:{RWA_USDC_VAULT}").meta["liquidity_usd"] > 0


def test_kamino_reserve_position():
    g = build_graph(Position(101, HUMA_PST_RESERVE, 1e6, kind="kamino"))
    assert g.node(g.position_id).name.startswith("Supply PST")
