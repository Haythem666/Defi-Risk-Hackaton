"""Part 3: risk."""

import math

from kit import *  # noqa: F401,F403


def _poisson_plot():
    rates = [(0.059, "#2a5bd7", "hack, all DeFi (5.9%/yr)"), (0.245, "#c0392b", "USDe depeg (24.5%/yr)")]
    series = []
    for r, c, lab in rates:
        series.append(([(d, 100 * (1 - math.exp(-r * d / 365))) for d in range(0, 366, 5)], c, lab))
    return plot(TEXT_W, 170, series, (0, 365), (0, 23), "decision horizon (days)",
                "chance of at least one incident (%)", [0, 30, 90, 180, 365], [0, 5, 10, 15, 20],
                marks=[(30, 100 * (1 - math.exp(-0.245 * 30 / 365)), ""),
                       (30, 100 * (1 - math.exp(-0.059 * 30 / 365)), "")],
                caption="From an annual rate to the chance of an incident within the horizon "
                        "(Poisson model). Dots at 30 days: 2.0% for a USDe depeg, 0.5% for a hack.",
                yfmt=lambda v: f"{v:.0f}%")


def content():
    s = []
    s += part(3, "Risk: from a map to numbers",
              "What can go wrong, how often, how badly, and how a failure deep in the graph "
              "travels up to your position.")

    # ------------------------------------------------------------------ 19
    s += chapter(19, "Incidents: what can go wrong", new_page=False)
    s += [P("The project describes every risk as a **scenario**: *node X suffers incident Y, with "
            "probability p within the horizon, and the position loses L if it happens*. There are "
            "five kinds of incident:")]
    s += table([
        ["Incident", "Plain meaning", "Typical node"],
        ["**hack**", "Money stolen through a code bug, a manipulated price or a stolen key.",
         "Protocols, issuers, vaults, exchanges"],
        ["**oracle_failure**", "The price feed is wrong, stale or manipulated.", "Oracles"],
        ["**depeg**", "A token that should be worth 1 USD (or 1 ETH) trades clearly below.",
         "Stablecoins, staked tokens"],
        ["**chain_halt**", "The blockchain stops producing blocks.", "Chains"],
        ["**liquidity_crunch**", "Buyers vanish or withdrawals freeze: you cannot exit at a fair "
                                 "price.", "AMM pools, lending markets, DEX exits"],
    ], [0.2, 0.5, 0.3])
    s += section("Three numbers per scenario")
    s += bullets([
        "**Annual rate**: how many such incidents to expect per year on this node (e.g. 0.059 = "
        "about one every 17 years).",
        "**Severity**: the fraction of *that node's* value lost when it happens (e.g. 4.1% of a "
        "protocol's funds).",
        "**Loss if hit**: the fraction of *your position* lost. This is not the same as severity: "
        "it depends on how much of your value flows through that node (chapter 22).",
    ])
    s += box("code",
             "`params_for(node)` in `src/risk/assumptions.py` picks the incident, rate and "
             "severity for each node type. Every row carries a **rationale** that starts with "
             "**DATA** (computed from history) or **JUDGEMENT** (an expert estimate, labelled as "
             "such). Admin nodes and \"off-chain backing\" boxes get no incident of their own, so "
             "the same risk is not counted twice.")

    # ------------------------------------------------------------------ 20
    s += chapter(20, "A probability toolkit")
    s += section("From an annual rate to a probability over your horizon")
    s += [P("The decision is about a **horizon** (30 days by default). If incidents arrive at "
            "random at an average rate λ (lambda) per year, the chance of **at least one** within "
            "*d* days is given by the **Poisson model**:")]
    s += formula("P(at least one incident in d days) = 1 − e<super>−λ × d / 365</super>")
    s += [P("For small numbers, this is close to λ × d / 365. But it never exceeds 100%, even for "
            "rates above one per year (some algorithmic stablecoins depeg more than once a "
            "year).")]
    s += _poisson_plot()
    s += box("example",
             "All-DeFi hack rate λ = 0.059 per year, horizon 30 days: 1 − e<super>−0.059 × 30 / 365"
             "</super> = 1 − e<super>−0.00485</super> ≈ **0.48%**.")
    s += section("Expected value")
    s += [P("The **expected loss** of one scenario is probability × loss. A 2% chance of losing "
            "6.4% is an expected loss of 0.128%. It is not what will happen. Most of the time "
            "nothing happens, and occasionally you lose 6.4%. It is what you lose **on average** "
            "if you could repeat the situation many times. Decisions under uncertainty compare "
            "averages like this.")]
    s += section("Monte Carlo: rolling the dice 20,000 times")
    s += [P("With a dozen scenarios that can happen together, exact formulas get messy. **Monte "
            "Carlo simulation** replaces maths with repetition: simulate the next 30 days 20,000 "
            "times. In each run, every scenario happens or not according to its probability (like "
            "a weighted coin), and the run's loss is computed. Then look at the 20,000 "
            "results.")]
    s += [P("Losses **compound** rather than add: if one incident takes 10% and another 20%, you "
            "keep 0.9 × 0.8 = 72%, so you lost 28%, not 30%:")]
    s += formula("loss of a run = 1 − ∏ (1 − loss<sub>i</sub>)   over the incidents i that happened")
    s += bullets([
        "**Expected loss** = the average over all runs.",
        "**Worst-case loss (worst 5%)** = the average of the 5% worst runs. This tail measure, "
        "also called *expected shortfall*, answers \"when it goes badly, how badly?\"",
    ])
    s += box("code",
             "`simulate()` in `src/risk/model.py`: a 20,000 × (number of scenarios) table of random "
             "numbers, compared with the probabilities, gives which incidents hit in which run. "
             "`numpy` does it in one line. The random seed is fixed (`seed=0`), so the same input "
             "always gives the same output.")
    s += box("warn",
             "The single-pocket simulation assumes incidents are **independent**. In reality, a "
             "crisis often triggers several at once (a depeg, a liquidity crunch, an oracle "
             "lag). The whole-book view (chapter 26) partly fixes this by drawing a shared node's "
             "incident once for every pocket.")
    s += box("check",
             ["Compute the 30-day probability for a rate of 0.10 per year.",
              "Why do losses of 10% and 20% compound to 28%?",
              "What does \"worst 5%\" tell you that the expected loss does not?"])

    # ------------------------------------------------------------------ 21
    s += chapter(21, "Calibration: where the numbers come from")
    s += [P("A risk number is only useful if it is **defensible**. The project's rule: every "
            "number carries a rationale, and wherever history exists, numbers come from data. "
            "Running `python -m src.risk.calibration` rebuilds `data/calibration.json` from "
            "public DeFiLlama data.")]
    s += section("Hack rates per category")
    s += [P("**Method**: count hacks of at least 1M USD, over the last 3 years, on protocols that "
            "held at least 100M USD just before the hack (the size of protocols an institutional "
            "book uses). Divide by the number of such protocols times 3 years. **Severity** = "
            "the median of (amount stolen − funds returned) ÷ TVL before the hack.")]
    s += table([
        ["Category", "Hacks per protocol per year", "Median loss if hacked"],
        ["All DeFi (`_all`)", "5.9%", "4.1%"],
        ["Lending", "9.1%", "1.5%"],
        ["Dexs", "8.2%", "29%"],
        ["Bridge", "6.6%", "1.6%"],
        ["Onchain Capital Allocator", "5.6%", "4.1% (all-DeFi)"],
        ["Risk Curators (vaults)", "2.8%", "4.1% (all-DeFi)"],
        ["RWA", "2.4%", "4.1% (all-DeFi)"],
        ["Liquid Staking", "1.4%", "4.1% (all-DeFi)"],
        ["Oracle manipulation (`_oracle`)", "4.4%", "3.5%"],
        ["Large exchanges (`cex`)", "11.1%", "2.6%"],
    ], [0.4, 0.3, 0.3])
    s += section("Shrinkage: not trusting tiny samples")
    s += [P("A category with 6 protocols and 0 hacks would get a 0% rate, which is obviously too "
            "optimistic. A category with 2 hacks among 3 protocols would get an absurd 22%. The "
            "project **pulls each category toward the all-DeFi rate**, as if 10 extra protocols "
            "with the average rate had been observed:")]
    s += formula("rate = (hacks + 10 × 3 years × all-DeFi rate) ÷ (3 years × (protocols + 10))")
    s += [P("A big category keeps mostly its own rate. A small one leans on the average. When fewer "
            "than 3 losses were measured, the all-DeFi severity is used. This is a classic "
            "statistical technique (a *Bayesian prior*, here as \"pseudo-observations\").")]
    s += section("Depegs: blending a coin's own record with its family")
    s += [P("For a stablecoin, the project counts **depeg episodes** (below 0.97 for 2+ days) per "
            "**coin-year** since 2021, per family (fiat-backed, crypto-backed, algorithmic). A "
            "coin's own record is blended with its family's, as if it had 5 more years at the "
            "family rate:")]
    s += formula("rate = (own episodes + 5 × family rate) ÷ (own coin-years + 5)")
    s += box("example",
             "USDe: **0 episodes in 2.75 coin-years**. Family: crypto-backed, **38% per year**. "
             "Rate = (0 + 5 × 0.38) ÷ (2.75 + 5) = 1.90 ÷ 7.75 ≈ **24.5% per year**. Over 30 days: "
             "1 − e<super>−0.245 × 30/365</super> ≈ **2.0%**. Severity: the crypto-backed median "
             "drop, **6.4%**. That is exactly the top row of the PT-sUSDe scenario table. Note "
             "how a young coin with a clean record still leans heavily on its family.")
    s += section("JUDGEMENT rows")
    s += [P("Where no public dataset exists, the project uses labelled expert estimates:")]
    s += table([
        ["Node", "Incident", "Rate / yr", "Severity", "Reasoning"],
        ["Chain", "chain_halt", "1%", "2%", "Halts freeze but rarely destroy value."],
        ["Pendle pool (market)", "liquidity_crunch", "10%", "3%", "Exit pool thins, PT discount "
                                                                  "widens."],
        ["Lending market", "liquidity_crunch", "5%", "10%", "Liquidation cascade / bad debt."],
        ["DEX exit of a collateral", "liquidity_crunch", "10%", "10%",
         "DEX liquidity dries up, liquidators stop."],
        ["Contagion (other lender)", "liquidity_crunch", "5%", "10%",
         "Another lender's liquidations dump the same token."],
        ["Non-USD asset (LST)", "depeg", "3%", "5%", "stETH traded ~5% below ETH in June 2022."],
    ], [0.22, 0.17, 0.1, 0.1, 0.41])
    s += box("idea",
             "Honest labelling matters as much as the numbers. A risk manager can challenge a "
             "JUDGEMENT row and replace it. A DATA row can be traced to the events it counts.")
    s += box("check",
             ["Why would a 0% hack rate for a small category be misleading?",
              "A coin has 1 depeg in 1 coin-year, family rate 8.7%. What blended rate does the "
              "formula give?"])

    # ------------------------------------------------------------------ 22
    s += chapter(22, "From the graph to your loss: exposure and the stress engine")
    s += section("Exposure along the graph")
    s += [P("Each edge carries an **exposure** between 0 and 1: *what share of the source's value "
            "relies on the target*. Along a path, exposures **multiply**: if 100% of your money "
            "is in a vault, the vault puts 30% in market A, and market A has 90% utilization, "
            "your exposure to A's collateral is 1 × 0.3 × 0.9 = 27%. Over several paths, the "
            "simple version **adds** them and caps at 1.")]
    s += box("code", "`path_exposure()` in `src/risk/model.py` uses networkx's "
                     "`all_simple_paths` to list every path from the position to a node, "
                     "multiplies along each path, sums, and caps at 1. It is shown as \"linear "
                     "exposure along the graph\" in each scenario's rationale.")
    s += section("Why a smarter engine was needed")
    s += [P("Multiplying exposures is linear: a 5% hit and a 50% hit produce proportional losses. "
            "Real finance is not linear. A lender loses **nothing** from a small collateral drop "
            "(the LLTV buffer absorbs it) and **a lot** from a large one. Liquidations can "
            "**amplify** a drop. And the same dependency reached through two paths should not be "
            "counted twice. `src/risk/stress.py` handles all three.")]
    s += section("The propagation: dominoes, round after round")
    s += [P("Hit one node with a shock (say \"sUSDe loses 20%\"). In each round, every node "
            "recomputes its loss from the losses of what it depends on. Repeat until nothing "
            "changes. Losses can only grow and are capped at 100%, so the process always settles "
            "(mathematicians call the end point a **fixed point**). This is the **DebtRank** "
            "method from research on bank contagion (Battiston et al., 2012). The existence of "
            "the fixed point comes from Eisenberg and Noe (2001).")]
    s += section("Two kinds of edges")
    s += table([
        ["Edge type", "Examples", "How losses combine", "Why"],
        ["**Value edges**", "`allocates_to`, `secured_by`, `holds`, `hedges_on`, "
                            "`deposited_in`, `redeems_into`…",
         "**Add up** (capped at 100%)",
         "Each carries a different slice of the money. Losing 30% in market A and 30% in "
         "market B is 60%."],
        ["**Common edges**", "`settles_on`, `runs_on`, `priced_by`, `issued_by`…",
         "**Maximum**", "They are dependencies of the *whole* value. Ethereum failing through 5 "
                        "paths is still one failure."],
    ], [0.15, 0.3, 0.17, 0.38])
    s += section("Mechanism 1: the lender's buffer")
    s += [P("For an edge from a lending market to its collateral (`secured_by`), the market loses "
            "only if the collateral drop *d* exceeds the buffer 1 − LLTV. Beyond it, the lender "
            "recovers the collateral, worth (1 − *d*), sold at a price impact *i*, against a debt "
            "of LLTV:")]
    s += formula("shortfall = 0   if d ≤ 1 − LLTV,   else   1 − (1 − d)(1 − i) ÷ LLTV")
    s += [P("and the market's loss = utilization × shortfall (only the lent-out part is at "
            "risk).")]
    s += plot(TEXT_W, 170, [
        ([(d / 100, max(0, 1 - (1 - d / 100) * (1 - 0.05) / 0.8) if d / 100 > 0.2 else 0)
          for d in range(0, 101, 2)], "#2a5bd7", "LLTV 80%, DEX impact 5%"),
        ([(d / 100, max(0, min(1, 1 - (1 - d / 100) * 0 / 0.8)) if d / 100 > 0.2 else 0)
          for d in range(0, 101, 1)], "#c0392b", "LLTV 80%, no DEX market"),
    ], (0, 1), (0, 1.05), "collateral price drop d", "lender shortfall", [0, 0.2, 0.4, 0.6, 0.8, 1],
        [0, 0.25, 0.5, 0.75, 1], xfmt=lambda v: f"{v:.0%}", yfmt=lambda v: f"{v:.0%}",
        shade=(0, 0.2, "#e5f4ea"),
        caption="Nothing is lost inside the buffer (green). Beyond it, losses grow. With no DEX "
                "market (impact 100%), the lender cannot recover anything: a cliff.")
    s += box("example",
             ["LLTV 80%, drop 30%, impact 5%: 1 − 0.70 × 0.95 ÷ 0.80 = 1 − 0.831 = **16.9%** "
              "shortfall.",
              "LLTV 80%, drop 15%: inside the 20% buffer, so **0**.",
              "Huma market: LLTV 86%, PST drops 50%, no DEX market (*i* = 100%): 1 − 0.5 × 0 ÷ "
              "0.86 = **100%** shortfall. × utilization 90.6% = the vault loses **90.6%**. This is "
              "the \"haircut if trapped\" of chapter 25."])
    s += section("Mechanism 2: the liquidation spiral")
    s += [P("A price drop triggers liquidations. Liquidators sell the collateral, which pushes the "
            "price down further, which triggers more liquidations… The project measures one "
            "number per collateral, the **loop gain g**:")]
    s += formula("g = (price impact of the sales a 5% drop forces) ÷ 5%")
    s += diagram(TEXT_W, 110, {
        "drop": (20, 40, 110, 34, "Price drops", "bad"),
        "liq": (190, 72, 110, 30, "Loans liquidated", "lending"),
        "sell": (360, 40, 110, 34, "Liquidators sell on DEX", "market"),
        "imp": (190, 6, 110, 30, "Price impact", "plain"),
    }, [("drop", "liq", ""), ("liq", "sell", ""), ("sell", "imp", ""), ("imp", "drop", "")],
        caption="The spiral. Each turn multiplies the extra drop by g.")
    s += table([
        ["Phase", "Condition", "What happens", "Total drop from an initial drop d"],
        ["**Damped**", "g below 1", "Each round adds less; the spiral fades.",
         "d ÷ (1 − g)  (geometric series)"],
        ["**Supercritical**", "g ≥ 1", "The spiral feeds itself until forced sales run out.",
         "1 − (1 − d)(1 − impact)"],
        ["**Stalled**", "impact above the liquidation bonus, or no DEX",
         "Liquidators would lose money, so they stop. No spiral, but losses become bad debt.",
         "d (and the buffer mechanism takes over)"],
    ], [0.15, 0.2, 0.35, 0.3])
    s += box("example",
             "A 5% drop forces sales that move the price 2% more: g = 2% ÷ 5% = 0.4 (damped). "
             "Total drop = 5% ÷ (1 − 0.4) = **8.3%**. The 1 + 0.4 + 0.16 + … series adds up to "
             "1 / 0.6. If instead g = 1.2, each round is bigger than the last: supercritical.")
    s += section("The spectral radius ρ: one number for the whole system")
    s += [P("Put all edge exposures in a table (a **matrix** W, one row and one column per "
            "node), with each collateral's loop gain on the diagonal. Linear algebra gives this "
            "matrix a **spectral radius** ρ (rho): roughly, *by how much the system multiplies a "
            "shock each round* when the shock travels along its loops. ρ ≥ 1 means a shock can "
            "feed itself (supercritical). On these graphs the only loops are spirals, so ρ is the "
            "largest loop gain. Think of it as the **echo factor** of the system.")]
    s += box("real",
             ["PT-sUSDe: no measured spiral (the Pendle pool is the exit, not a DEX quote), ρ = "
              "0. The stress table shows: Ethereum, Pendle, sUSDe or Ethena hit by X% → position "
              "loses X%. Morpho market or its oracle hit at 100% → **99.2%**. Binance hit at 100% → "
              "**13.3%**.",
              "Huma: PST's spiral is **stalled**. A 5% drop would force 12.7M USD of sales, plus "
              "5% of the **183M USD** of PST held by other lenders, into DEXes that cannot absorb "
              "any of it, against a 4.4% bonus. So the risk shows up as bad debt, not as a "
              "spiral."])
    s += section("Contagion: other lenders holding the same collateral")
    s += [P("If another protocol also accepts PST as collateral and liquidates, it sells into the "
            "**same** DEX liquidity. The project adds those protocols as **contagion** nodes "
            "(`also_collateral_in` edges), with exposure = their forced sales if 5% of their "
            "holding is liquidated ÷ the token's DEX liquidity (1 if the token has no market).")]
    s += box("real",
             "PST in the Huma graph: contagion from Morpho (other markets, 0.91), Kamino on Solana "
             "(0.41), Fluid (0.37) and Jupiter Lend on Solana (0.10). Found from DeFiLlama, on "
             "Ethereum and on Solana where PST is bridged from.")
    s += box("check",
             ["Why do value edges add up but common edges take the maximum?",
              "Compute the shortfall for LLTV 90%, drop 25%, impact 10%.",
              "With g = 0.5, what does a 5% initial drop become?"])

    # ------------------------------------------------------------------ 23
    s += chapter(23, "Liquidity risk: can you get out, and at what price?")
    s += [P("Losing value is one risk. **Not being able to leave** is the other. They are linked: "
            "the moment you most want to leave is the moment everyone else does too.")]
    s += section("Leaving now: the exit cost")
    s += bullets([
        "**A PT**: sell it on Pendle. Cost = price impact + fee, from Pendle's **live router "
        "quote** for your exact size (0.045% for 1M USD of PT-sUSDe). If the router gives no "
        "quote (usually because the size is too large), the constant-product approximation is "
        "used.",
        "**A loan or vault**: withdrawing costs nothing (gas aside) **as long as there is idle "
        "liquidity**. Above it, the rest is stuck until borrowers repay.",
        "**A redeemable contract** (ERC-4626): redeem at the contract's own price, possibly after "
        "a cooldown.",
        "**Anything else**: no live quote, so the brief's reference cost of 11% is used.",
    ])
    s += section("Leaving late, with the crowd")
    s += [P("The decision is taken **now**, before any incident. Staying means that *if* an "
            "incident hits, you will leave **late**, at the same time as everyone else. The "
            "project models that crowded exit:")]
    s += bullets([
        "**PT**: you sell in the same batch as the PT that Morpho lenders liquidate after a 5% "
        "drop. But the price cannot fall forever. At some point, buyers who hold to maturity "
        "step in, because the PT still redeems 1:1. The project assumes they step in when "
        "holding to maturity earns **30% per year** (JUDGEMENT).",
        "**Loan or vault**: no price impact, but a **queue**. If every depositor runs, each gets "
        "at most idle liquidity ÷ total deposits.",
    ])
    s += box("example",
             "PT-sUSDe: crowd = 3.79M USD of liquidated PT + your 1M = a 4.79M USD batch. The "
             "approximation says **71.6%** impact. But with 46 days to maturity, the 30%/yr floor "
             "is 1 − 1.30<super>−46/365</super> = **3.25%**, so the late exit costs **3.25%**. "
             "Every incident costing more than 3.25% is increased by it: loss L becomes "
             "L + (1 − L) × 3.25%.")
    s += box("real",
             "Huma USDC Main: today **100%** of a 1M USD pocket can be withdrawn (3.59M USD idle). "
             "In a run where all 12.84M USD of deposits leave, each depositor gets **28%** out. "
             "The rest waits for borrowers to repay.")
    s += box("code",
             "`late_exit()` and `with_late_exit()` (`src/decision/exit_cost.py` and "
             "`src/decision/rule.py`). The app shows them side by side: *Leave now* vs *Leave "
             "late (after an incident, with the crowd)*.")
    s += box("check", ["Why can a PT's crisis price not fall below a certain level while its "
                       "underlying holds?",
                       "In a run, why do lenders not lose money to price impact, yet still "
                       "suffer?"])
    return s
