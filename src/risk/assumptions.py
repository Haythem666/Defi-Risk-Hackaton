"""Incident rates and severities for each node of a dependency graph.

Data-driven where history exists (data/calibration.json, built by
`python -m src.risk.calibration` from DeFiLlama hacks, protocol TVL history
and stablecoin prices); expert judgement, labelled as such, where it does not.

annual_p: incidents per year on this node (a rate; converted to a probability
          over the horizon with a Poisson model in model.horizon_probability).
severity: fraction of the node's value lost when it happens.
"""

import json
from pathlib import Path

from src.schemas import Node

CALIBRATION = Path(__file__).resolve().parents[2] / "data" / "calibration.json"


# Stablecoins without "USD" in their symbol.
OTHER_USD_STABLES = {"DAI", "SDAI", "GHO", "FRAX", "BOLD", "LUSD", "CRVUSD"}

# A coin's own depeg history is blended with its family's (fiat-backed,
# crypto-backed, algorithmic) as if it had this many extra coin-years at the
# family rate: a young coin leans on its family, an old one on its own record.
PRIOR_COIN_YEARS = 5

JUDGEMENT = {
    "chain": {"incident": "chain_halt", "annual_p": 0.01, "severity": 0.02,
              "rationale": "JUDGEMENT: a halt freezes positions but rarely destroys value; "
                           "loss is the price move while stuck. No public dataset of halts."},
    "market": {"incident": "liquidity_crunch", "annual_p": 0.10, "severity": 0.03,
               "rationale": "JUDGEMENT: the exit pool thins out and the PT discount widens; "
                            "to calibrate on Pendle implied-rate history."},
    "lending": {"incident": "liquidity_crunch", "annual_p": 0.05, "severity": 0.10,
                "rationale": "JUDGEMENT: liquidation cascade / bad debt in this market; the "
                             "edge exposure already carries the measured liquidation pressure."},
    "asset_non_usd": {"incident": "depeg", "annual_p": 0.03, "severity": 0.05,
                      "rationale": "JUDGEMENT: liquid staking tokens vs their base asset; stETH "
                                   "traded about 5% below ETH in June 2022."},
}

# Used only if data/calibration.json has not been built yet.
FALLBACK = {
    "hack": {"incident": "hack", "annual_p": 0.02, "severity": 0.30,
             "rationale": "PLACEHOLDER: run python -m src.risk.calibration"},
    "oracle": {"incident": "oracle_failure", "annual_p": 0.03, "severity": 0.10,
               "rationale": "PLACEHOLDER: run python -m src.risk.calibration"},
    "venue": {"incident": "hack", "annual_p": 0.02, "severity": 0.50,
              "rationale": "PLACEHOLDER: run python -m src.risk.calibration"},
    "depeg": {"incident": "depeg", "annual_p": 0.05, "severity": 0.05,
              "rationale": "PLACEHOLDER: run python -m src.risk.calibration"},
}


def _load() -> dict | None:
    try:
        return json.loads(CALIBRATION.read_text())
    except (OSError, ValueError):
        return None


CAL = _load()


def _row(incident: str, stats: dict, prefix: str = "", fallback_severity: float | None = None) -> dict:
    return {"incident": incident, "annual_p": stats["annual_p"],
            "severity": stats.get("severity") or fallback_severity or 0.0,
            "rationale": f"DATA: {prefix}{stats['rationale']}"}


def _hack_row(category: str | None) -> dict:
    hacks = CAL["hacks"]
    stats = hacks.get(category) if category else None
    if stats:  # category rates are already pulled toward all-DeFi in calibration
        return _row("hack", stats, f"[{category}] ", hacks["_all"]["severity"])
    note = (f"[{category}: fewer than a handful of large protocols, all-DeFi rate] "
            if category else "[all DeFi] ")
    return _row("hack", hacks["_all"], note)


def is_usd_stable(symbol: str) -> bool:
    s = symbol.upper()
    return "USD" in s or s in OTHER_USD_STABLES


def _depeg_row(symbol: str) -> dict:
    """Depeg rate for a stablecoin: its own record blended with its family's.
    Staked/wrapped versions (sUSDe, sDAI) use the base coin (USDe, DAI)."""
    dep = CAL["depeg_usd"]
    coins = dep.get("symbols", {})
    s = symbol.upper()
    coin = coins.get(s) or (coins.get(s[1:]) if s[:1] in "SW" else None)
    family = dep.get("per_mechanism", {}).get((coin or {}).get("mechanism"))
    if not coin or not family:
        return _row("depeg", dep, "[all USD stablecoins] ")
    base = s if s in coins else s[1:]
    n, years = coin["n_episodes"], coin["coin_years"]
    rate = (n + PRIOR_COIN_YEARS * family["annual_p"]) / (years + PRIOR_COIN_YEARS)
    return {"incident": "depeg", "annual_p": rate, "severity": family["severity"],
            "rationale": (f"DATA: [{base}, {coin['mechanism']}] {n} depeg episodes of {base} in "
                          f"{years:.1f} coin-years, blended with its family "
                          f"({family['annual_p']:.0%}/y) as if {PRIOR_COIN_YEARS} more coin-years; "
                          f"family: {family['rationale']}")}


def params_for(node: Node) -> list[dict]:
    """Incident scenarios (annual probability, severity, rationale) for a node."""
    t, meta = node.type, node.meta
    if t == "admin":  # key theft / admin abuse is already in the hack rate of the contract it controls
        return []
    if meta.get("part_of"):  # e.g. the aggregator behind an oracle proxy: counted on the proxy
        return []
    if t in JUDGEMENT:
        return [JUDGEMENT[t]]
    if CAL is None:
        key = {"oracle": "oracle", "venue": "venue", "asset": "depeg"}.get(t, "hack")
        return [FALLBACK[key]]
    if t in ("protocol", "issuer"):
        return [_hack_row(meta.get("category"))]
    if t == "vault":
        return [_hack_row("Risk Curators")]
    if t == "oracle":
        return [_row("oracle_failure", CAL["hacks"]["_oracle"])]
    if t == "venue":
        if meta.get("type") == "perp exchange":  # on-chain venue: a DeFi derivatives protocol
            return [_hack_row("Derivatives")]
        return [_row("hack", CAL["cex"])]
    if t == "asset":
        if meta.get("wraps"):  # a wrapper's own risk is its code; the peg is the wrapped token's
            return [_hack_row(meta.get("category"))]
        if is_usd_stable(node.name):
            return [_depeg_row(node.name)]
        return [JUDGEMENT["asset_non_usd"]]
    return []
