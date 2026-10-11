"""Part 5: the code, and the appendices."""

from kit import *  # noqa: F401,F403


def content():
    s = []
    s += part(5, "The project's code",
              "How the concepts of Parts 1 to 4 map onto files, functions and screens.")

    # ------------------------------------------------------------------ 27
    s += chapter(27, "The pipeline, file by file", new_page=False)
    s += diagram(TEXT_W, 150, {
        "pos": (0, 100, 82, 40, "Position\nwhat you hold", "position"),
        "data": (0, 20, 82, 50, "src/data/\nAPIs + RPC + cache", "plain"),
        "graph": (104, 100, 90, 40, "src/graph/\ndependency graph", "protocol"),
        "risk": (216, 100, 90, 40, "src/risk/\nscenarios + stress", "issuer"),
        "mc": (216, 20, 90, 50, "Monte Carlo\nexpected + worst 5%", "oracle"),
        "dec": (328, 100, 82, 40, "src/decision/\nverdict", "good"),
        "app": (430, 60, 52, 50, "app/\nStreamlit UI", "blue"),
    }, [("pos", "graph", ""), ("data", "graph", ""), ("graph", "risk", ""), ("risk", "mc", ""),
        ("mc", "dec", ""), ("risk", "dec", ""), ("dec", "app", "")],
        caption="The pipeline: a position goes in, a STAY / EXIT verdict with its reasons comes "
                "out.")
    s += section("The data contract: src/schemas.py")
    s += [P("Every module talks through a few shared objects. Think of them as the forms that "
            "pass from desk to desk:")]
    s += table([
        ["Object", "Fields (simplified)", "Concept"],
        ["`Position`", "chain_id, address, size_usd, horizon_days, book_share, kind",
         "What you hold. `kind`: pendle_pt, morpho_supply, aave_supply, morpho_vault, "
         "hyperliquid_vault, contract, kamino."],
        ["`Node`", "id, type, name, chain, meta", "One dependency. `type` is the box colour in "
                                                  "the app."],
        ["`Edge`", "source, target, kind, exposure, evidence",
         "\"source depends on target\". Every edge must carry evidence."],
        ["`DependencyGraph`", "position_id, nodes, edges", "The map of chapter 18."],
        ["`Scenario`", "node_id, incident, probability, loss_if_hit, rationale",
         "One line of the risk table (chapter 19)."],
        ["`RiskResult`", "scenarios, expected_loss, worst_case_loss", "Monte Carlo output."],
        ["`Verdict`", "decision, expected_loss, exit_cost, reason, breakeven_probability",
         "The answer (chapter 24)."],
    ], [0.18, 0.37, 0.45])
    s += section("Folder by folder")
    s += table([
        ["File", "What it does", "Chapters"],
        ["`src/data/cache.py`", "Every HTTP call goes through `fetch_json`, saved to "
                                "`data/cache/`; falls back to it if the API is down.", "4"],
        ["`src/data/chain.py`", "JSON-RPC reads (`eth_call`, `eth_getCode`…) and Sourcify "
                                "checks.", "4, 6"],
        ["`src/data/pendle.py`, `morpho.py`, `aave.py`, `kamino.py`, `hyperliquid.py`, "
         "`ethena.py`", "One fetcher per protocol API.", "13-17"],
        ["`src/data/defillama.py`, `coingecko.py`, `kyberswap.py`",
         "Protocols, yield pools, hacks; token websites; DEX quotes.", "10, 11"],
        ["`src/graph/build.py`", "Picks the builder for `Position.kind`.", "27"],
        ["`src/graph/pendle_pt.py`", "The five layers of a PT.", "15, 18"],
        ["`src/graph/lending.py`", "Morpho market, Aave pool, Morpho vault v1 and V2.", "13, 14"],
        ["`src/graph/kamino.py`", "Kamino Earn vaults and reserves (Solana).", "13, 14"],
        ["`src/graph/perp_vault.py`", "Hyperliquid vaults.", "17"],
        ["`src/graph/crawler.py`", "Any contract: standard questions, breadth-first, controllers.",
         "6, 7"],
        ["`src/graph/collateral.py`", "Behind each collateral: issuer, bridge, controllers, DEX "
                                      "exit, contagion, unwrapping.", "8, 9, 11, 22"],
        ["`src/graph/common.py`", "Chains, explorers, issuer discovery, oracle checks, off-chain "
                                  "backing.", "5, 10, 12"],
        ["`src/risk/calibration.py`", "Builds `data/calibration.json` from history.", "21"],
        ["`src/risk/assumptions.py`", "Rate and severity per node (DATA / JUDGEMENT).", "19, 21"],
        ["`src/risk/stress.py`", "Propagation, buffer, spiral, spectral radius.", "22"],
        ["`src/risk/model.py`", "Scenarios, Poisson, path exposure, Monte Carlo.", "20, 22"],
        ["`src/decision/exit_cost.py`", "Exit now (live quote) and late exit (with the crowd).",
         "23"],
        ["`src/decision/rule.py`", "STAY / EXIT, p*, late-exit adjustment.", "24"],
        ["`src/decision/snell.py`", "The exit trigger u*.", "25"],
        ["`src/decision/book.py`", "Whole book: evaluation per pocket, shared deps, book Monte "
                                   "Carlo.", "26"],
        ["`app/main.py`, `app/book_view.py`", "The Streamlit app: one pocket / whole book.",
         "28"],
    ], [0.33, 0.52, 0.15])
    s += section("One position, step by step in code")
    s += code("""
pos     = Position(1, "0x47ad…ef77e", 1_000_000, horizon_days=30, kind="pendle_pt")
graph   = build_graph(pos)                       # src/graph: nodes + edges with evidence
late    = late_exit(pos, graph)                  # cost of leaving with the crowd
scen    = with_late_exit(build_scenarios(graph, 30), late["cost"])
risk    = simulate(scen)                         # Monte Carlo: expected, worst 5%
cost, _ = exit_cost(pos, graph)                  # live Pendle quote
rule    = exit_rule(graph, cost)                 # u* (None for a PT)
forgone = position_yield(graph) * 30 / 365       # yield given up
verdict = decide(risk, cost, forgone, rule)      # STAY / EXIT + reason
""")
    s += [P("This is `book.evaluate()` in `src/decision/book.py`. The app's single-pocket view "
            "does the same, step by step, showing each intermediate result.")]

    # ------------------------------------------------------------------ 28
    s += chapter(28, "Running and reading the app")
    s += section("Commands")
    s += code("""
pip install -r requirements.txt          # install the libraries
streamlit run app/main.py                # the app, live data (cache as fallback)
DEFI_OFFLINE=1 streamlit run app/main.py # demo from data/cache only (no internet needed)
pytest                                   # tests (graph tests run offline)
python -m src.risk.calibration           # rebuild data/calibration.json
python -m src.trace morpho_vault 1 <vault> --api morpho  # API calls behind a graph
""")
    s += section("One pocket view, top to bottom")
    s += numbered([
        "**Sidebar**: choose the view (*One pocket* / *Whole book*), the pocket type, chain, "
        "market or vault, size, horizon and share of book.",
        "**1. Dependency graph**: coloured boxes (legend below it: colours are *types*, not risk "
        "levels), arrows labelled with edge kind and exposure. Expanders: *Edges and evidence* "
        "(every link and its proof), *API calls behind this graph* (what was asked, live or "
        "cache).",
        "**Red flags**: single-wallet owners, low-threshold multisigs, missing timelocks, "
        "unpublished code, bridged copies, reported-rate oracles, no DEX market…",
        "**Oracle checks**: on-chain price, gap to market, source verified, proxy.",
        "**2. Incident scenarios**: one row per node and incident, with probability, loss if hit, "
        "expected loss and the full rationale (DATA / JUDGEMENT).",
        "**Stress engine**: *What if?* (pick a dependency, how much it loses, and optionally "
        "its chance), then the table of every dependency hit at 5 / 20 / 50 / 100%, the spectral "
        "radius ρ and each collateral's spiral phase.",
        "**3. Decision**: verdict, expected loss, worst 5%, exit cost, p*, yield given up; *Leave "
        "now* vs *Leave late*; the *Exit trigger* panel (utilization, u*, haircut, hazard).",
    ])
    s += box("idea",
             "Read the app like an argument. **What do I depend on** (graph and evidence), **how "
             "likely is each failure and how bad for me** (scenarios and stress), **so what do I "
             "do** (decision). Each number has a rationale you can click into and challenge.")

    # ------------------------------------------------------------------ 29
    s += chapter(29, "Honest limits and where to go next")
    s += [P("A strong risk tool says what it does **not** know. From the code and CLAUDE.md:")]
    s += bullets([
        "**Coverage**: Kamino oracles and Solana program authorities are not read. Euler is not "
        "covered (no keyless API). Venue breakdown exists only for Ethena. Aave PT exposure is "
        "still crude (share of PT TVL).",
        "**JUDGEMENT anchors**: chain halts, Pendle pool crunches, lending cascades, the 30%/yr "
        "crisis PT yield, the freeze hazard (κ, γ) and the 50% crisis drop are expert estimates. "
        "They are labelled, but they move results.",
        "**Correlation**: within a pocket, incidents are independent draws. In the book, "
        "different nodes are independent. A market-wide crash hitting many nodes at once is not "
        "one event yet.",
        "**Late exit**: ignores liquidity providers pulling their liquidity from the Pendle pool "
        "in a crisis, which would make the crowded exit worse.",
        "**Constant-product fallback**: can be far from Pendle's real curve (chapter 11); live "
        "quotes are used whenever available.",
        "**Snapshots**: numbers in this course come from cached data in the repository. Live "
        "runs will differ.",
    ])
    s += box("idea",
             "You now have every concept the project uses: ledgers and contracts, tokens and "
             "bridges, AMMs, oracles, lending, vaults, Pendle, Ethena and perps; incidents, "
             "probabilities and calibration; propagation, buffers and spirals; exit costs, "
             "optimal stopping and portfolio correlation. The best next step is to open the app, "
             "pick a pocket, and explain every number on the screen out loud using this course.")

    # ------------------------------------------------------------------ appendices
    s += part("A", "Appendices", "Formula sheet, glossary, and answers to the *Check yourself* "
                                  "questions.")
    s += chapter("A", "Formula sheet", new_page=False)
    s += table([
        ["Quantity", "Formula", "Where"],
        ["Utilization", "borrowed ÷ supplied", "Ch. 13"],
        ["Implied APY of a PT", "(1 / p)<super>365/d</super> − 1", "Ch. 15"],
        ["AMM price impact (fallback)", "x ÷ (R + x), R = liquidity / 2", "Ch. 11"],
        ["Morpho liquidation bonus", "1 ÷ (0.3 × LLTV + 0.7) − 1, max 15%", "Ch. 13"],
        ["Horizon probability (Poisson)", "1 − e<super>−λ d / 365</super>", "Ch. 20"],
        ["Loss of a Monte Carlo run", "1 − ∏ (1 − loss<sub>i</sub>)", "Ch. 20"],
        ["Hack rate with shrinkage", "(n + 10 × 3 × rate<sub>all</sub>) ÷ (3 × (N + 10))",
         "Ch. 21"],
        ["Depeg rate blend", "(episodes + 5 × rate<sub>family</sub>) ÷ (coin-years + 5)", "Ch. 21"],
        ["Path exposure", "Σ over paths of ∏ edge exposures, capped at 1", "Ch. 22"],
        ["Lender shortfall", "0 if d ≤ 1 − LLTV, else 1 − (1 − d)(1 − i) ÷ LLTV", "Ch. 22"],
        ["Spiral loop gain", "g = impact of forced sales at −5% ÷ 5%", "Ch. 22"],
        ["Damped spiral total drop", "d ÷ (1 − g)", "Ch. 22"],
        ["Crisis PT floor (late exit)", "1 − 1.30<super>−days/365</super>", "Ch. 23"],
        ["Late-exit adjusted loss", "L + (1 − L) × late cost, if L ≥ late cost", "Ch. 23"],
        ["Yield given up", "APY × days ÷ 365", "Ch. 24"],
        ["Decision", "EXIT if expected loss > exit cost + yield given up, or u ≥ u*", "Ch. 24"],
        ["Breakeven probability", "p* = cost of leaving ÷ worst loss if hit", "Ch. 24"],
        ["Freeze hazard", "h(u) = κ ÷ (1 − u)<super>γ</super>, γ = 2, κ = 0.002", "Ch. 25"],
        ["Exit trigger", "u* = 1 − (κ (H − C) ÷ r)<super>1/γ</super>", "Ch. 25"],
    ], [0.3, 0.55, 0.15])

    s += chapter("B", "Glossary")
    s += glossary(GLOSSARY)

    s += chapter("C", "Answers to Check yourself")
    for ch, answers in ANSWERS:
        s += sub(f"Chapter {ch}")
        s += numbered(answers)
    return s


GLOSSARY = sorted([
    ("ABI", "Application binary interface: the standard layout of a contract call and its answer "
            "(32-byte words in hex)."),
    ("Adapter", "In a Morpho Vault V2, a plug-in connecting the vault to a market, another vault "
                "or another protocol."),
    ("Address", "Public identifier of a wallet or contract (0x + 40 hex characters on EVM "
                "chains)."),
    ("Admin", "Address allowed to upgrade a contract or change its settings. Pink nodes in the "
              "app."),
    ("Aggregator (DEX)", "Service that searches many DEXes for the best price (KyberSwap)."),
    ("Aggregator (oracle)", "The Chainlink contract that stores price answers, behind a proxy."),
    ("AMM", "Automated market maker: a DEX that prices trades with a formula over a pool of "
            "tokens."),
    ("APY", "Annual percentage yield: yearly return including compounding. *Net APY* = after "
            "fees."),
    ("Audit", "Paid security review of a contract's code. Reduces but never removes risk."),
    ("Bad debt", "Loans whose collateral is worth less than the debt. Suppliers absorb the "
                 "difference."),
    ("Basis trade", "Holding an asset and shorting its future to earn the funding / price "
                    "difference without price exposure (Ethena)."),
    ("Block", "A batch of transactions added to the chain together."),
    ("Block explorer", "Website showing a chain's transactions and contracts (Etherscan, "
                       "Solscan…)."),
    ("Book", "All the pockets a fund manages together."),
    ("Breakeven probability (p*)", "Incident probability above which exiting is cheaper than "
                                   "staying."),
    ("Bridge", "System that moves tokens between chains (lock-and-mint or burn-and-mint)."),
    ("Burn", "Destroy tokens, reducing the supply."),
    ("Bytecode", "The machine code of a contract as stored on-chain."),
    ("CCIP", "Chainlink's Cross-Chain Interoperability Protocol, a bridge standard."),
    ("CEX", "Centralized exchange (Binance, OKX…): a company holding customers' funds."),
    ("Chain ID", "Number identifying an EVM chain (1 = Ethereum)."),
    ("Chain halt", "The chain stops producing blocks. Funds are frozen until it restarts."),
    ("Collateral", "Tokens a borrower locks as a guarantee for a loan."),
    ("Consensus", "The rules by which validators agree on the next block."),
    ("Constant product", "AMM rule x × y = k."),
    ("Contagion", "A failure spreading to others through shared exposures, e.g. lenders "
                  "dumping the same collateral."),
    ("Cooldown", "Waiting period before a token can be redeemed."),
    ("Curator", "Manager deciding where a vault's money goes."),
    ("DebtRank", "Method to spread losses through a network of exposures, round by round, "
                 "capped at 100%."),
    ("Decimals", "How many digits after the decimal point a token uses (USDC: 6, most: 18)."),
    ("DeFi", "Decentralized finance: financial services built as smart contracts."),
    ("DeFiLlama", "Public data site and API on protocols, TVL, yields, hacks and stablecoins."),
    ("Delta-neutral", "A position whose value does not move with the price of the asset."),
    ("Depeg", "A token trading clearly below its target (project: below 0.97 for 2+ days)."),
    ("DEX", "Decentralized exchange: a smart contract where tokens are traded from wallets."),
    ("DEX exit", "The project's node for whether liquidators can sell a collateral on DEXes."),
    ("EIP / ERC", "Ethereum improvement proposal / a standard interface (ERC-20, ERC-4626)."),
    ("EIP-1967", "Standard storage slots where a proxy keeps its implementation and admin."),
    ("EOA", "Externally owned account: a wallet controlled by one private key."),
    ("ERC-20", "The standard token interface."),
    ("ERC-4626", "The standard vault interface: deposit a token, get shares; `asset()` names the "
                 "token."),
    ("EVM", "Ethereum Virtual Machine: the computer running smart contracts on Ethereum and "
            "compatible chains."),
    ("Evidence", "URL or note proving a dependency edge exists. Required on every edge."),
    ("Exit cost", "What it costs to leave a position now (slippage + fees)."),
    ("Expected loss", "Probability-weighted average loss."),
    ("Expected shortfall", "Average of the worst outcomes (here the worst 5% of runs)."),
    ("Exposure", "Share of a node's value that relies on another node (edge weight, 0 to 1)."),
    ("Finality", "The point after which a block cannot be undone."),
    ("Fixed point", "State where another round of propagation changes nothing."),
    ("Flash loan", "A loan borrowed and repaid within one transaction, often used in oracle "
                   "manipulation."),
    ("Forgone yield", "Yield given up by leaving a position: APY × days ÷ 365."),
    ("Funding rate", "Periodic payment between longs and shorts that keeps a perp near the spot "
                     "price."),
    ("Gas", "Fee paid to validators to execute a transaction."),
    ("Guardian", "Role that can veto or pause changes in a vault."),
    ("Haircut (H)", "Loss if trapped through a crisis (stress engine, collateral −50%)."),
    ("Hash", "Digital fingerprint of data. Any change gives a different hash."),
    ("Hazard", "Expected number of events per year at a given state (freeze hazard h(u))."),
    ("Hex", "Base-16 notation (0-9, a-f), prefixed 0x."),
    ("HLP", "Hyperliquid's own market-making and liquidation vault."),
    ("Horizon", "The period the decision covers (30 days by default)."),
    ("Idle liquidity", "Supplied tokens not lent out: what can be withdrawn now."),
    ("Implementation", "The logic contract behind a proxy."),
    ("Implied APY", "Fixed yield locked in by buying a PT at its current price."),
    ("Interest rate model", "Formula setting borrow rates from utilization."),
    ("Issuer", "The entity or protocol that creates a token and manages its backing."),
    ("JSON-RPC", "Standard message format to ask a blockchain node questions."),
    ("JUDGEMENT", "Label for an expert estimate where no data exists."),
    ("Leverage", "Position size ÷ own money (margin)."),
    ("Limit order", "An order to buy or sell at a set price, filled by Pendle's router when it "
                    "is better."),
    ("Liquidation", "Forced closing of a loan whose collateral fell too far; the liquidator "
                    "repays and takes collateral plus a bonus."),
    ("Liquidation bonus", "Extra collateral a liquidator receives; its profit margin."),
    ("Liquidity", "How much can be traded or withdrawn without moving the price; value in a "
                  "pool."),
    ("Liquidity provider (LP)", "Someone depositing tokens into an AMM pool to earn fees."),
    ("LLTV", "Liquidation loan-to-value: the maximum loan ÷ collateral before liquidation "
             "(Morpho)."),
    ("Lock-up", "Period after deposit during which you cannot withdraw."),
    ("Long / short", "Gaining when the price rises / falls."),
    ("Looping", "Repeatedly borrowing against a token to buy more of it (leverage)."),
    ("LST", "Liquid staking token, e.g. stETH: a tradable claim on staked ETH."),
    ("LTV", "Loan-to-value: loan ÷ collateral value."),
    ("Margin", "Money deposited to back a leveraged position."),
    ("Market id", "Identifier of a Morpho market (loan token, collateral, oracle, LLTV)."),
    ("Maturity", "Date when a PT redeems 1:1 for its underlying."),
    ("Minimal proxy", "EIP-1167 clone: a cheap, non-upgradeable copy forwarding to another "
                      "contract."),
    ("Mint", "Create new tokens."),
    ("Monte Carlo", "Estimating outcomes by simulating many random scenarios."),
    ("Multisig (Safe)", "Contract wallet needing k of n signatures."),
    ("Node (blockchain)", "Computer keeping a full copy of the ledger and answering RPC calls."),
    ("Node (graph)", "One dependency in the project's graph."),
    ("Notional", "Full size of a derivatives position."),
    ("OFT", "LayerZero Omnichain Fungible Token: a token that moves itself across chains."),
    ("Off-chain backing", "Assets outside the blockchain (loans, bonds, bank deposits) behind "
                          "a token; where the visible graph stops."),
    ("Oracle", "Contract publishing prices on-chain for other contracts."),
    ("Overcollateralization", "Requiring collateral worth more than the loan."),
    ("Peg", "The fixed value a stablecoin targets (usually 1 USD)."),
    ("Perpetual future (perp)", "A futures contract with no expiry."),
    ("Pocket", "One slice of the book, one position (e.g. 10% of the fund)."),
    ("Poisson model", "Model of random events at a constant rate; gives 1 − e^(−rate × time)."),
    ("Pool", "Tokens deposited in a contract for trading (AMM) or lending (Aave)."),
    ("Price impact / slippage", "How much worse your average price is than the starting price, "
                                "due to your trade's size."),
    ("Private key", "Secret number that controls an address."),
    ("Proof of stake", "Consensus where validators lock money as a guarantee of honesty."),
    ("Protocol", "A DeFi service made of smart contracts."),
    ("Proxy", "Permanent contract address forwarding calls to a replaceable implementation."),
    ("PT", "Pendle principal token: redeems 1:1 for the underlying at maturity."),
    ("Quote", "The price an exchange would give for a trade now, without trading."),
    ("Reserve", "In Kamino or Aave, the lending pool of one token."),
    ("Router", "Contract that finds the best way to execute a trade (Pendle's router)."),
    ("RPC", "Remote procedure call: asking a node to run a function and return the answer."),
    ("RWA", "Real-world asset: token representing something off-chain."),
    ("Scenario", "Node X suffers incident Y with probability p and costs the position L."),
    ("Seed phrase", "12 or 24 words encoding a private key."),
    ("Selector", "First 4 bytes of the hash of a function's name, used to call it."),
    ("Severity", "Fraction of a node's value lost in an incident."),
    ("Shares", "Units representing your slice of a vault."),
    ("Shrinkage", "Pulling a small sample's estimate toward a broader average."),
    ("Signature", "Proof a transaction was approved by the private key's owner."),
    ("Smart contract", "Program on a blockchain that holds money and follows its code."),
    ("Snell envelope", "Optimal-stopping tool: the value of choosing the best time to stop."),
    ("Sourcify", "Service verifying that published source code matches on-chain bytecode."),
    ("Spectral radius (ρ)", "Largest eigenvalue size of the exposure matrix; ≥ 1 means a shock "
                            "can feed itself."),
    ("Spiral (liquidation)", "Liquidations push the price down, causing more liquidations."),
    ("Stablecoin", "Token designed to keep a fixed value (fiat-backed, crypto-backed, "
                   "algorithmic)."),
    ("Staking", "Locking tokens to help secure a chain, for rewards."),
    ("Stress test", "Hitting a node with a given loss and measuring the effect on the "
                    "position."),
    ("Supply queue", "Order in which a Morpho vault fills its markets with new deposits."),
    ("sUSDe", "Staked USDe: the yield-bearing version of Ethena's synthetic dollar."),
    ("SY", "Pendle standardized yield: wrapper around a yield-bearing token."),
    ("Timelock", "Mandatory delay between deciding and applying a change."),
    ("Token", "Unit of value managed by a smart contract."),
    ("Transaction", "Signed instruction that changes the ledger."),
    ("TVL", "Total value locked: USD value deposited in a protocol."),
    ("u* (exit trigger)", "Utilization above which a lender should leave before a freeze."),
    ("USDe", "Ethena's synthetic dollar backed by a delta-neutral position."),
    ("Utilization", "Borrowed ÷ supplied in a lending market."),
    ("Validator", "Computer that proposes and confirms blocks, with money at stake."),
    ("Vault", "Contract pooling deposits and allocating them according to a strategy."),
    ("Venue", "External trading place (an exchange) a protocol depends on."),
    ("Wrapped token", "Token representing another one 1:1 in a standard form (WETH, WBTC)."),
    ("YT", "Pendle yield token: receives the underlying's yield until maturity."),
], key=lambda t: t[0].lower())


ANSWERS = [
    (1, ["Because money already is a ledger entry. A blockchain is a way to keep that ledger "
         "without trusting a single keeper.",
         "Spending the same digital money twice. The bank keeps the single official ledger and "
         "refuses the second payment."]),
    (2, ["Block 99's fingerprint changes, so the fingerprint stored in block 100 no longer "
         "matches, nor anything after it. The network rejects the edited version.",
         "So that cheating costs the validator money (its stake can be slashed).",
         "Contracts and balances are untouched. You only lose from prices moving while you "
         "cannot act."]),
    (3, ["The key is the secret that signs. The address is the public identifier derived from "
         "it.",
         "An attacker must steal 4 keys instead of 1, and no single person can act alone."]),
    (4, ["It only reads data, and reading is free. It never sends transactions.",
         "Empty code (\"0x\"): the address is a plain wallet, not a contract."]),
    (5, ["Ethereum is an L1 with its own validators. Arbitrum is an L2 that runs on top and "
         "posts its activity to Ethereum.",
         "Solana is not an EVM chain: different programs, RPC methods and address format."]),
    (6, ["That the published source compiles to the on-chain code. Not that the code is safe or "
         "honest.",
         "Each answer that is an address becomes an edge, then the crawler asks the new address "
         "the same questions (up to 4 hops, 40 contracts)."]),
    (7, ["To fix bugs or add features. Whoever holds the admin role can change the rules, "
         "including in their own favour.",
         "Time to see a change coming and withdraw before it applies."]),
    (8, ["1 USDC is stored as 1,000,000 units.",
         "Its backing is volatile crypto or hedges rather than cash. The data shows 38% vs 8.7% "
         "depeg episodes per coin-year.",
         "It can prove the token supply, transfers and who can mint. It cannot prove the "
         "off-chain assets exist."]),
    (9, ["Locked in the bridge contract on the home chain.",
         "An attacker can mint unbacked copies and sell them or post them as collateral. The "
         "copy's value collapses and lenders accepting it face bad debt."]),
    (10, ["The USD value deposited in a protocol's contracts.",
          "So that a small project that merely wraps a token is not mistaken for its issuer."]),
    (11, ["Each unit sold adds to one reserve and the constant product leaves less of the other "
          "per unit.",
          "1,200 ETH in the pool, so 2,000,000,000 / 1,200 = 1,666,667 USDC remain. You receive "
          "333,333 USDC (1,667 per ETH): 16.7% impact."]),
    (12, ["A contract only sees its own chain; it cannot fetch web data.",
          "The rate does not fall when the market price falls, so liquidations never start and "
          "lenders hold under-collateralized loans."]),
    (13, ["10% (the buffer is 1 − LLTV).",
          "When the price impact of selling the collateral exceeds the liquidation bonus, or no "
          "DEX trades it: they would lose money.",
          "48 / 50 = 96%. Only 2M can be withdrawn now."]),
    (14, ["Which markets get the money, how much (caps), and in what order.",
          "Depositors can withdraw before money is sent to a risky new market."]),
    (15, ["One unit of the underlying (here sUSDe) per PT.",
          "(1 / 0.98)<super>365/182</super> − 1 ≈ 4.1% per year.",
          "Liquidators sell the PT into the same Pendle pool, which worsens the price you can "
          "exit at."]),
    (16, ["The gain on one side offsets the loss on the other, so the total stays near the "
          "starting dollar value.",
          "Part of Ethena's hedges sit on Binance. A Binance failure breaks part of USDe's "
          "backing, which hits sUSDe, which is what the PT redeems into."]),
    (17, ["Margin is the money deposited. Notional is the full position size.",
          "Any three of: the Hyperliquid exchange, its L1 chain, its validator oracle, the bridge "
          "on Arbitrum holding USDC, the leader's positions."]),
    (20, ["1 − e<super>−0.1 × 30/365</super> ≈ 0.82%.",
          "You keep 0.9 × 0.8 = 72% of the value, so the loss is 28%.",
          "How bad the bad outcomes are: the size of the tail, not just the average."]),
    (21, ["Few protocols over a short window: having seen no hack does not mean the risk is zero.",
          "(1 + 5 × 0.087) ÷ (1 + 5) = 1.435 ÷ 6 ≈ 23.9% per year."]),
    (22, ["Value edges carry different slices of money, which add up. Common edges are the same "
          "single failure seen through several paths.",
          "The buffer is 10% and the drop is 25%: 1 − 0.75 × 0.90 ÷ 0.90 = 25% shortfall.",
          "5% ÷ (1 − 0.5) = 10%."]),
    (23, ["Because it still redeems 1:1 at maturity: below a certain price, buyers lock in a "
          "high yield and step in.",
          "There is no sale, so no price impact, but only a fraction can be withdrawn and the rest "
          "stays trapped through the incident."]),
    (24, ["8% × 45 ÷ 365 ≈ 0.99%.",
          "2% ÷ 40% = 5%.",
          "Because a lending position crossed its exit trigger u*: freeze risk overrides the "
          "average."]),
    (25, ["Being trapped costs more, so the yield covers the freeze risk only while the hazard "
          "is lower, that is, at lower utilization.",
          "1 − √(0.002 × 0.2 ÷ 0.05) = 1 − √0.008 ≈ 91.1%.",
          "u* = 100%: being trapped costs no more than leaving, so leaving early is never "
          "worth it."]),
    (26, ["Shared draws do not change each pocket's own probabilities (so the average barely "
          "moves), but they put losses in the same runs, which fattens the tail.",
          "A bridged collateral token (PST on Ethereum and Solana), a stablecoin (USDC), an "
          "issuer or its off-chain backing, an exchange, or the same multisig signers."]),
]
