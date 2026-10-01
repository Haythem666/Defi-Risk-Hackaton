"""Lending graphs, on the cached snapshot in data/cache (no network needed)."""

import pytest

from src.graph.build import build_graph
from src.schemas import Position

MORPHO_CBBTC_USDC = "0x64d65c9a2d91c36d56fbc42d69e979335320169b3df63bf92789e2c8883fcc64"
AAVE_CORE = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("DEFI_OFFLINE", "1")


def _check(g):
    ids = {n.id for n in g.nodes}
    assert all(e.source in ids and e.target in ids for e in g.edges)
    assert all(e.evidence for e in g.edges), "every edge needs evidence"
    assert all(0 <= e.exposure <= 1 for e in g.edges)


def test_morpho_supply_depends_on_collateral_through_utilization():
    g = build_graph(Position(1, MORPHO_CBBTC_USDC, 1e6, kind="morpho_supply"))
    _check(g)
    secured = next(e for e in g.edges if e.kind == "secured_by")
    assert secured.target == "asset:cbBTC"
    assert secured.exposure == round(g.node(secured.source).meta["utilization"], 3)
    assert any(n.type == "oracle" for n in g.nodes)


def test_aave_supply_lists_pool_collaterals():
    g = build_graph(Position(1, AAVE_CORE, 1e6, kind="aave_supply", asset_address=USDC))
    _check(g)
    collaterals = [e for e in g.edges if e.kind == "secured_by"]
    assert len(collaterals) >= 3
    # no claimed issuer for plain USDC / WBTC (largest holders are lenders)
    issuers = {e.source for e in g.edges if e.kind == "issued_by"}
    assert "asset:USDC" not in issuers and "asset:WBTC" not in issuers
