import pytest

from src.risk import assumptions
from src.schemas import Node


def stats(p, sev, n=10):
    return {"annual_p": p, "severity": sev, "n_hacks": n, "rationale": "test"}


FAKE = {
    "hacks": {"_all": stats(0.05, 0.3), "Lending": stats(0.08, 0.2),
              "Derivatives": stats(0.06, 0.4),
              "Risk Curators": stats(0.02, None), "_oracle": stats(0.03, 0.15)},
    "cex": {"annual_p": 0.04, "severity": 0.1, "rationale": "test"},
    "depeg_usd": {"annual_p": 0.2, "severity": 0.05, "rationale": "test",
                  "per_mechanism": {"crypto-backed": {"annual_p": 0.4, "severity": 0.06,
                                                      "rationale": "test"}},
                  "symbols": {"USDE": {"mechanism": "crypto-backed", "coin_years": 5.0,
                                       "n_episodes": 0}}},
}


@pytest.fixture(autouse=True)
def fake_calibration(monkeypatch):
    monkeypatch.setattr(assumptions, "CAL", FAKE)


def p(node):
    return assumptions.params_for(node)[0]


def test_protocol_uses_its_category_rate():
    row = p(Node("protocol:aave", "protocol", "Aave", meta={"category": "Lending"}))
    assert (row["annual_p"], row["severity"]) == (0.08, 0.2)
    assert row["rationale"].startswith("DATA")


def test_category_without_stats_falls_back_to_all_defi():
    row = p(Node("issuer:x", "issuer", "x", meta={"category": "Basis Trading"}))
    assert row["annual_p"] == 0.05
    assert "all-DeFi rate" in row["rationale"]


def test_missing_severity_falls_back_to_all_defi():
    row = p(Node("vault:x", "vault", "Steakhouse"))
    assert (row["annual_p"], row["severity"]) == (0.02, 0.3)


def test_venues_assets_and_judgement_rows():
    assert p(Node("venue:binance", "venue", "Binance"))["annual_p"] == 0.04
    assert p(Node("venue:hl", "venue", "Hyperliquid", meta={"type": "perp exchange"}))["annual_p"] == 0.06
    usde = p(Node("asset:sUSDe", "asset", "sUSDe"))  # staked -> base coin USDe
    assert usde["incident"] == "depeg"
    assert abs(usde["annual_p"] - 0.2) < 1e-12  # (0 + 5 x 0.4) / (5 + 5)
    assert p(Node("asset:PYUSD", "asset", "PYUSD"))["annual_p"] == 0.2  # unknown coin: all stables
    assert p(Node("asset:wstETH", "asset", "wstETH"))["rationale"].startswith("JUDGEMENT")
    assert p(Node("chain:ethereum", "chain", "Ethereum"))["rationale"].startswith("JUDGEMENT")
    assert p(Node("oracle:x", "oracle", "Oracle"))["incident"] == "oracle_failure"


def test_without_calibration_file_rows_say_placeholder(monkeypatch):
    monkeypatch.setattr(assumptions, "CAL", None)
    assert p(Node("protocol:x", "protocol", "X"))["rationale"].startswith("PLACEHOLDER")
