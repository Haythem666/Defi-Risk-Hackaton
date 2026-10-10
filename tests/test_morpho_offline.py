"""Morpho graphs, on the cached snapshot in data/cache (no network needed)."""

import pytest

from src.data import cache
from src.graph.build import build_graph
from src.schemas import Position

MORPHO_CBBTC_USDC = "0x64d65c9a2d91c36d56fbc42d69e979335320169b3df63bf92789e2c8883fcc64"
ROCKAWAYX_USDC_YIELD = "0xE0181090c22579B6A217f1522cbf8c9f1F0C1965"
BELEM_RWA_EURCV = "0xD6d4b804014EF27836dBe9f8f6Bf6c71251548Ec"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("DEFI_OFFLINE", "1")


def _check(g):
    ids = {n.id for n in g.nodes}
    assert all(e.source in ids and e.target in ids for e in g.edges)
    assert all(e.evidence for e in g.edges), "every edge needs evidence"
    assert all(0 <= e.exposure <= 1 for e in g.edges)


def test_market_depends_on_collateral_through_utilization():
    g = build_graph(Position(1, MORPHO_CBBTC_USDC, 1e6, kind="morpho_supply"))
    _check(g)
    secured = next(e for e in g.edges if e.kind == "secured_by")
    assert secured.target == "asset:cbBTC"
    assert secured.exposure == round(g.node(secured.source).meta["utilization"], 3)
    assert any(n.type == "oracle" for n in g.nodes)


@pytest.mark.parametrize("address", [BELEM_RWA_EURCV, ROCKAWAYX_USDC_YIELD])
def test_vault_spreads_exposure_over_its_markets(address):
    g = build_graph(Position(1, address, 1e6, kind="morpho_vault"))
    _check(g)
    vault = next(n for n in g.nodes if n.type == "vault")
    assert vault.meta["version"] == 2
    assert {e.kind for e in g.edges if e.source == vault.id} >= {"owned_by", "curated_by"}
    allocs = [e for e in g.edges if e.kind == "allocates_to"]
    assert len(allocs) >= 2
    assert sum(e.exposure for e in allocs) <= 1.0 + 0.0005 * len(allocs)


def test_only_the_morpho_api_is_called():
    cache.CALLS.clear()
    build_graph(Position(1, BELEM_RWA_EURCV, 1e6, kind="morpho_vault"))
    assert cache.CALLS and {c["api"] for c in cache.CALLS} == {"morpho"}
