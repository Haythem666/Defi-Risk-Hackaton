"""On-chain crawler, on the cached snapshot in data/cache (no network needed)."""

import pytest

from src.graph import crawler
from src.graph.build import build_graph
from src.risk.model import build_scenarios
from src.schemas import Position

SUSDE = "0x9D39A5DE30e57443BfF2A8307A4256c8797A3497"
USDE = "0x4c9edd5852cd905f086c759e8383e09bff1e68b3"
STEAKHOUSE_USDC = "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("DEFI_OFFLINE", "1")


def _check(g):
    ids = {n.id for n in g.nodes}
    assert all(e.source in ids and e.target in ids for e in g.edges)
    assert all(e.evidence for e in g.edges), "every edge needs evidence"
    assert all(0 <= e.exposure <= 1 for e in g.edges)


def test_abi_decoding():
    word = "0" * 24 + USDE[2:]
    assert crawler._addr(word) == USDE
    assert crawler._addr("0" * 64) is None
    assert crawler._uint("0x" + f"{86400:064x}") == 86400
    usde = "0x" + f"{32:064x}" + f"{4:064x}" + b"USDe".hex().ljust(64, "0")
    assert crawler._string(usde) == "USDe"
    assert crawler._string("0x" + b"MKR".hex().ljust(64, "0")) == "MKR"  # old bytes32 tokens


def test_susde_found_from_the_contracts_alone():
    g = build_graph(Position(1, SUSDE, 1e6, kind="contract"))
    _check(g)
    susde = g.node(f"asset:{SUSDE.lower()}")
    assert any(e.source == susde.id and e.target == f"asset:{USDE}" and e.kind == "holds"
               for e in g.edges)
    assert any(e.kind == "minted_by" for e in g.edges)
    owner = next(e.target for e in g.edges if e.source == susde.id and e.kind == "owned_by")
    assert g.node(owner).meta["kind"] == "Timelock"
    assert susde.meta["cooldown_s"] > 0
    assert any("cooldown" in f for f in susde.meta["flags"])


def test_morpho_vault_markets_and_controllers_read_on_chain():
    g = build_graph(Position(1, STEAKHOUSE_USDC, 1e6, kind="contract"))
    _check(g)
    vault_id = f"vault:{STEAKHOUSE_USDC.lower()}"
    markets = [e for e in g.edges if e.source == vault_id and e.kind == "supplied_to"]
    assert len(markets) >= 3
    assert sum(e.exposure for e in markets) <= 1.0 + 1e-6
    for m in markets:
        assert any(e.source == m.target and e.kind == "secured_by" for e in g.edges)
    controllers = {e.kind: g.node(e.target).meta for e in g.edges if e.source == vault_id
                   and e.target.startswith("admin:")}
    assert controllers["owned_by"]["kind"] == "Safe"
    assert controllers["curated_by"]["threshold"] >= 2


def test_controllers_and_inner_feeds_add_no_double_counted_risk():
    g = build_graph(Position(1, STEAKHOUSE_USDC, 1e6, kind="contract"))
    scenario_nodes = {s.node_id for s in build_scenarios(g, 30)}
    assert not any(n.startswith("admin:") for n in scenario_nodes)
    inner = [n.id for n in g.nodes if n.meta.get("part_of")]
    assert inner and not scenario_nodes & set(inner)
    assert f"vault:{STEAKHOUSE_USDC.lower()}" in scenario_nodes
