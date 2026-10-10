"""What a market's collateral depends on, on the cached snapshot in data/cache."""

import pytest

from src.data import defillama
from src.graph.build import build_graph
from src.graph.collateral import _base58
from src.risk.assumptions import params_for
from src.schemas import Position

HUMA_USDC = "0x8aC91877b93330f52b2979a31a4879506021475c"  # Vault V2 lending USDC against PST


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("DEFI_OFFLINE", "1")


@pytest.fixture
def graph():
    return build_graph(Position(1, HUMA_USDC, 1e6, kind="morpho_vault"))


def _out(g, node_id, kind):
    return [e for e in g.edges if e.source == node_id and e.kind == kind]


def test_collateral_issuer_bridge_and_controller(graph):
    g = graph
    assert all(e.evidence for e in g.edges), "every edge needs evidence"
    assert [e.target for e in _out(g, "asset:PST", "issued_by")] == ["issuer:huma"]
    assert "coingecko" in _out(g, "asset:PST", "issued_by")[0].evidence.lower()
    assert [e.target for e in _out(g, "asset:PST", "bridged_by")] == ["protocol:ccip"]
    assert [e.target for e in _out(g, "asset:PST", "backed_on")] == ["chain:solana"]
    assert _out(g, "asset:PST", "controlled_by")
    pst = g.node("asset:PST")
    assert pst.meta["remote_tokens"]["Solana"] == "59obFNBzyTBGowrkif5uK7ojS58vsuWz3ZCvg6tfZAGw"
    assert any(r["chain"] == "Solana" for r in pst.meta["posted_as_collateral"])


def test_oracle_feed_is_a_reported_rate(graph):
    oracle = next(n for n in graph.nodes if n.type == "oracle" and not n.meta.get("part_of"))
    feeds = _out(graph, oracle.id, "reads_from")
    assert feeds and all(graph.node(e.target).meta["part_of"] == oracle.id for e in feeds)
    assert any("reported rate" in f for f in oracle.meta["flags"])
    assert all(params_for(graph.node(e.target)) == [] for e in feeds)  # counted once, on the oracle


def test_liquidation_exit_measured_against_the_bonus(graph):
    edge = next(e for e in graph.edges if e.kind == "liquidated_via")
    market = graph.node(edge.source)
    assert 0 < edge.exposure <= round(market.meta["utilization"], 3)
    assert "KyberSwap" in edge.evidence
    exit_node = graph.node(edge.target)
    assert params_for(exit_node)[0]["rationale"].startswith("JUDGEMENT")


def test_website_match_ignores_shared_hosting():
    assert defillama.site("https://app.huma.finance/pools") == "huma.finance"
    assert defillama.protocol_by_site("https://github.com/someone/token") is None


def test_base58_of_a_solana_mint():
    raw = bytes.fromhex("3db012feaceb9de59e2cc3fbbb7a23b6f2ae778ae9a4fbc63f44e38f01f7e9e0")
    assert _base58(raw) == "59obFNBzyTBGowrkif5uK7ojS58vsuWz3ZCvg6tfZAGw"
