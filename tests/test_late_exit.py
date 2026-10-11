"""Leaving late with the crowd."""

import pytest

from src.decision.exit_cost import lending_late_exit
from src.decision.rule import with_late_exit
from src.schemas import DependencyGraph, Node, Position, Scenario


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
