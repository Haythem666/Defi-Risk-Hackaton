"""Base incident rates and severities per node type.

PHASE 0 PLACEHOLDERS. Every number here must be replaced by a calibrated one
(DeFiLlama hacks database, past depegs, oracle incidents) before the demo.

annual_p: probability the incident happens to this node over one year.
severity: fraction of the node's value lost when it happens.
"""

ASSUMPTIONS: dict[str, list[dict]] = {
    "chain": [
        {"incident": "chain_halt", "annual_p": 0.01, "severity": 0.02,
         "rationale": "PLACEHOLDER: major L1 halts are rare; loss is mostly temporary mark-to-market."},
    ],
    "protocol": [
        {"incident": "hack", "annual_p": 0.02, "severity": 0.50,
         "rationale": "PLACEHOLDER: order of magnitude of yearly exploit rate for audited blue-chip DeFi."},
    ],
    "asset": [
        {"incident": "depeg", "annual_p": 0.05, "severity": 0.15,
         "rationale": "PLACEHOLDER: the asset loses value vs its reference (USD for stablecoins, ETH for LSTs)."},
    ],
    "issuer": [
        {"incident": "hack", "annual_p": 0.02, "severity": 0.60,
         "rationale": "PLACEHOLDER: issuer insolvency / custody failure."},
    ],
    "market": [
        {"incident": "liquidity_crunch", "annual_p": 0.10, "severity": 0.03,
         "rationale": "PLACEHOLDER: pool liquidity drops, PT discount widens before expiry."},
    ],
    "lending": [
        {"incident": "liquidity_crunch", "annual_p": 0.05, "severity": 0.10,
         "rationale": "PLACEHOLDER: liquidation cascade dumps PT into the AMM."},
    ],
    "vault": [
        {"incident": "hack", "annual_p": 0.01, "severity": 0.20,
         "rationale": "PLACEHOLDER: curator allocates to a bad market or vault contract exploit."},
    ],
    "venue": [
        {"incident": "hack", "annual_p": 0.02, "severity": 1.0,
         "rationale": "PLACEHOLDER: exchange insolvency or freeze (FTX 2022); assets held there are lost."},
    ],
    "oracle": [
        {"incident": "oracle_failure", "annual_p": 0.03, "severity": 0.10,
         "rationale": "PLACEHOLDER: stale / wrong price triggers bad liquidations."},
    ],
}
