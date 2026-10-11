"""Leaving late with the crowd, and the whole-book view on hand-made pockets."""

import pytest

from src.decision import book
from src.decision.exit_cost import lending_late_exit
from src.decision.rule import with_late_exit
from src.schemas import DependencyGraph, Edge, Node, Position, Scenario


def pocket(pid, chain_p=0.0, own_p=0.0, size=1e6):
    """A pocket on chain X (shared by every pocket) and its own protocol."""
    nodes = [Node(pid, "position", pid), Node("chain:x", "chain", "X"), Node(f"protocol:{pid}", "protocol", pid)]
    edges = [Edge(pid, "chain:x", "settles_on", 1.0, "t"), Edge(pid, f"protocol:{pid}", "runs_on", 1.0, "t")]
    scenarios = [Scenario("chain:x", "chain_halt", chain_p, 0.5), Scenario(f"protocol:{pid}", "hack", own_p, 0.5)]
    return {"graph": DependencyGraph(pid, nodes, edges), "scenarios": scenarios,
            "pos": Position(1, pid, size, kind="morpho_vault")}


def test_late_exit_is_added_only_to_hits_worth_unwinding():
    s = with_late_exit([Scenario("a", "hack", 0.1, 0.20), Scenario("b", "hack", 0.1, 0.01)], 0.05)
    assert s[0].loss_if_hit == pytest.approx(0.20 + 0.80 * 0.05)
    assert s[1].loss_if_hit == 0.01                      # smaller than unwinding: absorbed
    assert with_late_exit(s, 0.0) == s


def test_lending_late_exit_is_a_queue_not_a_price():
    g = DependencyGraph("P", [Node("P", "position", "P"),
                              Node("V", "vault", "V", meta={"liquidity_usd": 2e6, "total_usd": 20e6})], [])
    late = lending_late_exit(Position(1, "v", 4e6, kind="morpho_vault"), g)
    assert late["cost"] == 0.0
    assert late["withdrawable_now"] == pytest.approx(0.5)     # 2M idle for a 4M pocket
    assert late["withdrawable_in_run"] == pytest.approx(0.1)  # everyone runs: 2M / 20M


def test_shared_dependencies_and_book_stress():
    pockets = [pocket("A"), pocket("B"), pocket("C")]
    shared = book.shared_dependencies(pockets)
    assert [d["node_id"] for d in shared] == ["chain:x"] and shared[0]["pockets"] == [0, 1, 2]
    assert book.book_stress(pockets, "protocol:A", 1.0) == [1.0, 0.0, 0.0]


def test_a_shared_failure_is_drawn_once_for_every_pocket():
    pockets = [pocket(p, chain_p=0.04) for p in "ABCDE"]
    joint, alone = book.simulate_book(pockets), book.simulate_book(pockets, shared=False)
    assert joint["expected_usd"] == pytest.approx(alone["expected_usd"], rel=0.1)  # same average
    assert joint["worst_usd"] > 2 * alone["worst_usd"]  # but the tail: all five fail together
