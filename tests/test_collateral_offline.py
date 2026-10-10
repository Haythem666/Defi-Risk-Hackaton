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


BELEM_RWA_EURCV = "0xD6d4b804014EF27836dBe9f8f6Bf6c71251548Ec"   # lends EURCV against mGLOeuro
ROCKAWAYX_USDC_YIELD = "0xE0181090c22579B6A217f1522cbf8c9f1F0C1965"  # PT-reUSD, strUSD, siUSD...


def test_issuer_with_offchain_assets_gets_an_offchain_box(graph):
    box = _out(graph, "issuer:huma", "backed_off_chain")
    assert box and graph.node(box[0].target).meta["role"] == "offchain_backing"
    assert params_for(graph.node(box[0].target)) == []  # the issuer's rate covers it


def test_collateral_with_no_market_is_flagged_whatever_the_drop():
    g = build_graph(Position(1, BELEM_RWA_EURCV, 1e6, kind="morpho_vault"))
    exit_node = g.node("market:dex-exit-mGLOeuro")
    assert exit_node.meta["has_market"] is False
    assert any("no DEX market" in f for f in exit_node.meta["flags"])
    edge = next(e for e in g.edges if e.target == exit_node.id)
    assert edge.exposure == round(g.node(edge.source).meta["utilization"], 3)


def test_pt_and_vault_collateral_are_unwrapped():
    g = build_graph(Position(1, ROCKAWAYX_USDC_YIELD, 1e6, kind="morpho_vault"))
    assert _out(g, "asset:PT-reUSD-10DEC2026", "redeems_into")[0].target == "asset:reUSD"
    assert _out(g, "asset:siUSD", "holds")[0].target == "asset:iUSD"  # ERC-4626 asset()
    assert g.node("asset:PT-reUSD-10DEC2026").meta["wraps"] == "asset:reUSD"
    # a PT is quoted on its Pendle pool, not flagged as having no market
    pt_exit = g.node("market:dex-exit-PT-reUSD-10DEC2026")
    assert pt_exit.meta["has_market"] is True
