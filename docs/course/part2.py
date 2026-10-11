"""Part 2: DeFi building blocks."""

from kit import *  # noqa: F401,F403


def _amm_curve():
    pts = [(x, 2_000_000 * 1000 / x / 1e6) for x in range(500, 2001, 25)]
    return plot(TEXT_W, 175, [(pts, "#2a5bd7", "pool reserves: ETH × USDC = constant")],
                (500, 2000), (0.9, 4.1), "ETH in the pool", "USDC in the pool (millions)",
                [500, 1000, 1500, 2000], [1, 2, 3, 4],
                marks=[(1000, 2.0, "start: 1,000 ETH / 2.0M USDC (price 2,000)", 6, 6, "start"),
                       (1100, 1.818, "after selling 100 ETH: 1,100 ETH / 1.818M USDC", -4, -16, "start")],
                caption="Constant product: every trade moves the pool along this curve. The bigger "
                        "the sale relative to the pool, the worse the average price.",
                yfmt=lambda v: f"{v:.0f}M")


def content():
    s = []
    s += part(2, "DeFi building blocks",
              "Exchanges, oracles, lending markets, vaults, Pendle, Ethena and perpetual futures: "
              "the pieces a DeFi position is made of, and how they depend on each other.")

    # ------------------------------------------------------------------ 10
    s += chapter(10, "DeFi, protocols and DeFiLlama", new_page=False)
    s += [P("**DeFi** (decentralized finance) is the set of financial services built as smart "
            "contracts: exchanging, lending, borrowing, earning yield, trading with leverage. "
            "Anyone with a wallet can use them, at any hour, with no account opening. A "
            "**protocol** is one such service, usually a family of contracts with a name and a "
            "team: Pendle, Morpho, Aave, Kamino, Ethena, Hyperliquid…")]
    s += section("TVL: the size of a protocol")
    s += [P("**TVL** (total value locked) is the total value of the tokens deposited in a "
            "protocol's contracts, in USD. It is the standard measure of size. Pendle held about "
            "1.2 billion USD in the project's cached data, Ethena's USDe about 4.8 billion.")]
    s += section("DeFiLlama: the project's encyclopedia")
    s += [P("**DeFiLlama** is a free public website and API that tracks thousands of protocols. "
            "The project uses four of its datasets:")]
    s += table([
        ["Dataset", "What it contains", "Used for"],
        ["Protocols", "Name, **category** (Lending, Dexs, RWA, Basis Trading…), TVL, audits, "
                      "past hacks.", "Protocol and issuer nodes. The category picks the hack "
                                     "rate (chapter 20)."],
        ["Yield pools", "Every pool that pays a yield: chain, token symbol, TVL, underlying "
                        "tokens.", "**Issuer discovery**: who mints a token."],
        ["Hacks", "Date, amount, technique of every recorded exploit.",
         "Calibrating hack probabilities and severities."],
        ["Stablecoins", "Daily prices and circulating supply of every stablecoin.",
         "Calibrating depeg probabilities."],
    ], [0.17, 0.43, 0.4])
    s += box("code",
             "**How the project finds an issuer automatically** (`defillama.find_issuer`): look at "
             "the *largest* yield pool of the token on that chain. If that pool **produces** the "
             "token from something else (Ethena turns USDe into sUSDe, Lido turns ETH into stETH) "
             "and is not a lender or exchange, it is the issuer. For USDC the largest pool is a "
             "lender, so no issuer is claimed rather than a wrong one. If that fails, the token's "
             "website on **CoinGecko** is matched to a DeFiLlama protocol with the same website "
             "(this is how PST is linked to Huma).")
    s += box("check", ["What does TVL measure?",
                       "Why does the project require the *largest* pool before calling a protocol "
                       "the issuer?"])

    # ------------------------------------------------------------------ 11
    s += chapter(11, "Exchanges and AMMs: where tokens are traded")
    s += section("Centralized vs decentralized exchanges")
    s += bullets([
        "A **CEX** (centralized exchange) such as Binance, OKX or Bybit is a company. You send it "
        "your tokens, it keeps them (it has **custody**) and matches buyers and sellers in its own "
        "database. Fast and deep, but you trust the company. If it is hacked or fails (FTX in "
        "2022), customers can lose their funds.",
        "A **DEX** (decentralized exchange) is a smart contract. You trade directly from your "
        "wallet against money sitting in the contract. Nobody holds your funds in between.",
    ])
    s += section("The AMM: a robot market maker")
    s += [P("Most DEXes are **AMMs** (automated market makers). Instead of matching buyers and "
            "sellers, an AMM holds a **pool** of two tokens and quotes prices with a formula. "
            "People who deposit tokens into the pool are **liquidity providers (LPs)**. They earn "
            "the trading **fees**. The total value in the pool is its **liquidity**.")]
    s += [P("The simplest formula is the **constant product**: the pool keeps *x × y = k* "
            "constant, where *x* and *y* are its two reserves. When you sell token X, you add X to "
            "the pool, so the pool must give back enough Y to keep the product unchanged. The "
            "more you sell, the less each extra unit is worth.")]
    s += _amm_curve()
    s += box("example",
             "A pool holds 1,000 ETH and 2,000,000 USDC, so *k* = 2 billion and the price is "
             "2,000 USDC per ETH. You sell 100 ETH. The pool now has 1,100 ETH, so it must keep "
             "2,000,000,000 / 1,100 = 1,818,182 USDC. You receive 2,000,000 − 1,818,182 = "
             "**181,818 USDC**, an average of 1,818 per ETH instead of 2,000. You lost **9.1%** to "
             "**price impact**.")
    s += [P("**Price impact** (or **slippage**) is the gap between the price before the trade and "
            "the average price you actually get. It grows with the size of the trade relative to "
            "the pool. With reserves *R* on each side, selling an amount *x* (in value) costs:")]
    s += formula("price impact ≈ x / (R + x)")
    s += box("code",
             "`amm_exit_cost()` in `src/decision/rule.py` is exactly this formula, with *R* = "
             "liquidity / 2. It is only a **fallback**. The project prefers a **live quote**: it "
             "asks the exchange *\"how much would I get for this amount right now?\"*.",
             "For PT-sUSDe, the pool had 3.82M USD of liquidity. The formula would say selling "
             "1M USD costs 1M / (1.91M + 1M) ≈ **34%**. Pendle's live router quote says "
             "**0.045%**. Pendle's curve is much flatter near the current price and the router "
             "also fills limit orders. Lesson: approximations can be wildly off, so live quotes "
             "matter.")
    s += section("Aggregators and quotes")
    s += [P("A token often trades on many DEXes at once. An **aggregator** such as **KyberSwap** "
            "searches all of them and splits your trade across the best routes. Asking it for a "
            "**quote** (without trading) tells you the real price impact of selling a given "
            "amount today.")]
    s += box("code",
             "`src/data/kyberswap.py` asks KyberSwap to quote selling a collateral token. The "
             "project first quotes a small sale (10,000 USD) to learn the token's price on DEXes. "
             "If even that small sale loses half its value or more (`NO_MARKET_IMPACT = 0.5`), "
             "the token has **no real market**. It then quotes selling what a 5% price drop "
             "would force liquidators to sell (chapter 13). The result is a **\"DEX exit\"** "
             "node in the graph.")
    s += box("check", ["Why does a large sale get a worse average price in an AMM?",
                       "Recompute the example: what do you receive for selling 200 ETH?"])

    # ------------------------------------------------------------------ 12
    s += chapter(12, "Oracles: how contracts learn prices")
    s += [P("A smart contract cannot look at a website. It only knows what is on its own chain. "
            "Yet a lending protocol must know what collateral is worth to decide when to "
            "liquidate. An **oracle** is a contract that publishes prices on-chain, so other "
            "contracts can read them.")]
    s += bullets([
        "**Chainlink** is the largest oracle network. Independent node operators fetch prices "
        "from many exchanges, agree on a value and write it on-chain. A **price feed** (e.g. "
        "ETH/USD) is read through a **proxy** contract that forwards to an **aggregator**, the "
        "contract that actually stores the answers. That is why the project draws "
        "`reads_from` edges between oracle nodes.",
        "A **Morpho oracle** combines up to several feeds (`BASE_FEED_1`, `BASE_FEED_2`, "
        "`QUOTE_FEED_1`…) and sometimes a vault's exchange rate (`BASE_VAULT`) into one "
        "`price()`: the value of 1 collateral token in loan tokens, written with 36 extra "
        "digits of precision.",
    ])
    s += section("Market price vs reported rate")
    s += [P("Some oracles do not report what the token trades at. They report a **rate** computed "
            "or declared by the issuer (*\"1 PST = 1.0123 USDC\"*). That is calm in normal times, "
            "but dangerous in a crisis: if the market price of the token collapses, the oracle "
            "does not move, so **liquidations never start**, and lenders keep lending against "
            "collateral that is worth less than they think.")]
    s += box("real",
             "In the Huma USDC Main vault, the oracle of the PST/USDC market reads a feed called "
             "*\"PST-USDC Exchange Rate (Calculated)\"*. The project flags it: *\"a reported rate, "
             "not a market price: a sell-off on markets does not move it, so liquidations do not "
             "start\"*.")
    s += section("What can go wrong")
    s += bullets([
        "**Manipulation**: an attacker pushes the price on a thin market the oracle reads (often "
        "with a **flash loan**, a huge loan borrowed and repaid within one transaction), then "
        "borrows against overvalued collateral.",
        "**Stale price**: the feed stops updating while the market moves.",
        "**Wrong configuration**: the oracle reads the wrong feed or the wrong decimals.",
    ])
    s += box("code",
             ["`add_oracle()` in `src/graph/common.py` reads the oracle's price **on-chain** and "
              "compares it to the market price. The app's *Oracle checks* table shows the **gap "
              "to market** (−0.09% for PT-sUSDe: healthy) and whether the source is verified.",
              "Oracle failure is a **DATA** row: 3 oracle-manipulation hacks over 40 large "
              "price-consuming protocols in 3 years, about **4.4% per year**, median loss "
              "**3.5%** (`calibration.json`, key `_oracle`)."])
    s += box("check", ["Why can a lending protocol not simply \"look up\" a price?",
                       "Why is an oracle that reports an issuer's rate risky for lenders in a "
                       "crisis?"])

    # ------------------------------------------------------------------ 13
    s += chapter(13, "Lending markets: the heart of the project")
    s += [P("Most positions in this project are, directly or indirectly, **loans**. Understanding "
            "lending well is the single most important step.")]
    s += section("The basic deal")
    s += bullets([
        "**Suppliers** (lenders) deposit a token, say USDC, into the market and earn interest.",
        "**Borrowers** take USDC out. To do so they must first deposit **collateral** worth "
        "*more* than they borrow, for example PT-sUSDe or PST. This is **overcollateralization**: "
        "there is no credit check, the collateral is the only guarantee.",
        "If the collateral loses value, the borrower is **liquidated** before the loan becomes "
        "bigger than the collateral.",
    ])
    s += diagram(TEXT_W, 120, {
        "sup": (5, 64, 105, 40, "Supplier\ndeposits 100 USDC", "position"),
        "mkt": (185, 54, 120, 60, "Lending market\n100 USDC supplied\n90 borrowed, 10 idle",
                "lending"),
        "bor": (380, 64, 100, 40, "Borrower\nborrows 90 USDC", "plain"),
        "col": (380, 8, 100, 36, "Collateral posted\n(worth more than 90)", "asset"),
        "liq": (185, 8, 120, 34, "Liquidator\n(sells collateral if needed)", "venue"),
    }, [("sup", "mkt", "supplies"), ("mkt", "bor", "lends"), ("bor", "col", "locks"),
        ("liq", "col", "", {"dashed": True})],
        caption="A lending market. Utilization here is 90 / 100 = 90%: only 10 USDC can be "
                "withdrawn right now.")
    s += section("LTV, LLTV and the safety buffer")
    s += [P("**LTV** (loan-to-value) is loan ÷ collateral value. Borrow 80 against 100 and your "
            "LTV is 80%. Each market sets a maximum, the **LLTV** (liquidation LTV, Morpho's term) "
            "or **liquidation threshold** (Aave's term). Cross it and you can be liquidated.")]
    s += [P("For the lender, 1 − LLTV is a **buffer**. With LLTV 80%, a borrower at the limit owes "
            "80 for 100 of collateral. The collateral can lose up to 20% and still cover the "
            "loan. Beyond that, the lender starts losing money, if the collateral cannot be sold "
            "in time.")]
    s += diagram(TEXT_W, 70, {
        "debt": (20, 22, 320, 30, "Debt = 80 (LLTV 80%)", "lending"),
        "buf": (340, 22, 80, 30, "Buffer 20", "good"),
    }, texts=[(220, 60, "Collateral value = 100", {"size": 8.5, "color": "#1d2433"}),
              (220, 6, "A price drop eats the buffer first. Only beyond 20% does the lender lose.",
               {"size": 8})])
    s += section("Liquidation, the bonus, and bad debt")
    s += [P("A **liquidation** is done by a **liquidator**, usually an automated bot. It repays "
            "part of the borrower's debt and receives the equivalent collateral **plus a "
            "bonus** (the **liquidation bonus** or *incentive*, typically 2 to 15%). It then "
            "sells that collateral, usually on a DEX. The bonus is its profit, and its reason to "
            "act fast.")]
    s += [P("This only works if selling the collateral costs the liquidator **less than the "
            "bonus**. If the DEX is too shallow and price impact exceeds the bonus, liquidating "
            "loses money, bots stop, and nobody repays the lender. When collateral ends up worth "
            "less than the debt, the difference is **bad debt**, and suppliers absorb it.")]
    s += box("example",
             "Morpho sets the bonus from the LLTV: bonus = 1 / (0.3 × LLTV + 0.7) − 1, capped at "
             "15%. For the Huma market (LLTV 86%) that is 1 / 0.958 − 1 = **4.4%**. Selling PST "
             "collateral on DEXes returned **0%** of its value (no route exists). 100% impact is "
             "far above 4.4%, so liquidators would not step in, and the project marks the "
             "market's liquidation spiral as **\"stalled\"** (chapter 22).")
    s += section("Utilization: the number that decides if you can leave")
    s += formula("utilization = borrowed ÷ supplied")
    s += [P("Money that is lent out is not in the contract. A supplier can only withdraw the "
            "**idle liquidity** (supplied − borrowed). At 100% utilization, **nobody can "
            "withdraw** until borrowers repay or new suppliers arrive. This is the DeFi version "
            "of a bank run.")]
    s += [P("To avoid this, markets use an **interest rate model**: the borrow rate rises with "
            "utilization, slowly up to a **target** (about 90%), then steeply. High rates push "
            "borrowers to repay and attract new suppliers. Morpho uses an *adaptive* curve, "
            "Kamino a *kinked* one (two straight lines with a bend at the target).")]
    s += box("idea",
             "For a lender, utilization measures two things at once. First, **how much of my money "
             "is exposed to the collateral**: only the lent-out part can be lost to bad debt. "
             "Second, **how easily I can leave**: only the idle part can be withdrawn now. That is "
             "why, in the project, the edge from a market to its collateral has **exposure = "
             "utilization**.")
    s += section("Three lending designs in the project")
    s += table([
        ["Protocol", "Design", "How the project models exposure"],
        ["**Morpho** (Morpho Blue)", "**Isolated markets**: each market is one loan token + one "
                                     "collateral token + one oracle + one LLTV, identified by a "
                                     "**market id**.", "Market → collateral = utilization."],
        ["**Aave v3**", "**Pools**: one pool, many tokens. Each supplied token can be borrowed "
                        "against any accepted collateral (liquidation threshold per asset).",
         "Pool → each collateral = utilization × that collateral's share of all collateral "
         "(top 8 kept)."],
        ["**Kamino** (Solana)", "**Markets made of reserves**: one reserve per token, borrowers "
                                "may post any collateral reserve of the market. Like Aave.",
         "Reserve → collateral = utilization × collateral share."],
    ], [0.19, 0.46, 0.35])
    s += box("real",
             "The PT-sUSDe/USDC Morpho market: LLTV **91.5%**, 7.93M USD of PT as collateral, "
             "6.99M USDC borrowed. Morpho's API (`marketCollateralAtRisk`) says how much "
             "collateral would be liquidated after each price drop: **0** at −2%, **3.79M** at "
             "−5%, **7.88M** at −10%. These forced sales feed the PT's exit risk (chapter 15) and "
             "the liquidation-spiral model (chapter 22).")
    s += box("check", ["With LLTV 90%, how far can collateral fall before the lender loses?",
                       "Why would liquidators refuse to liquidate a borrower?",
                       "A market has 50M supplied and 48M borrowed. What is its utilization, and "
                       "how much can suppliers withdraw now?"])

    # ------------------------------------------------------------------ 14
    s += chapter(14, "Vaults and curators")
    s += [P("Choosing among hundreds of lending markets is work. A **vault** does it for you: you "
            "deposit one token (say USDC), receive vault **shares**, and a professional "
            "**curator** spreads the money across several markets according to a strategy. You "
            "earn the blended interest minus a fee. The result is the **net APY** (annual "
            "percentage yield, after fees).")]
    s += section("Morpho vaults")
    s += bullets([
        "**Vault v1 (MetaMorpho)**: the curator sets a **cap** per market (maximum amount) and a "
        "**supply queue** (the order in which new deposits fill markets). An **allocator** moves "
        "money between markets. A **guardian** can veto changes. A **timelock** delays risky "
        "changes (new markets, higher caps) so depositors can leave first.",
        "**Vault V2**: deposits go through **adapters**, plug-ins that connect the vault to a "
        "Morpho market, to another vault, or to other protocols. Caps can be **absolute** (USD) "
        "or **relative** (% of the vault). Each setting has its own timelock.",
    ])
    s += section("Kamino Earn vaults")
    s += [P("The Solana equivalent: a Kamino **Earn vault** allocates deposits across Kamino "
            "**reserves**. Its liquidity is its idle tokens plus what each reserve can pay back "
            "right now.")]
    s += box("idea",
             "A vault adds a **layer of people** (the curator, owner, guardian) on top of a layer "
             "of markets. The vault's exposure to a market is **its share of the vault**. Your "
             "exposure to a collateral is the product along the path: *vault share × market "
             "utilization*. And you can only withdraw what the vault can pull back from its "
             "markets.")
    s += box("real",
             "**Huma USDC Main** (Morpho vault): 100% allocated to one market, PST/USDC, with "
             "utilization **90.6%** and LLTV 86%. Vault size 12.84M USD, idle liquidity 3.59M USD, "
             "net APY **7.34%**. Owner and curator: the same **Safe 4/8**. Path: you → vault "
             "(100%) → market (100%) → PST (90.6%) → Huma → off-chain backing.")
    s += box("check", ["What does a curator decide?",
                       "Why does a timelock on \"add a new market\" protect depositors?"])

    # ------------------------------------------------------------------ 15
    s += chapter(15, "Pendle: splitting yield from principal")
    s += [P("Pendle takes a yield-bearing token and splits it into two pieces that can be traded "
            "separately. To understand it, start with a familiar idea: a **zero-coupon bond**.")]
    s += box("analogy",
             "A zero-coupon bond pays no interest along the way. You buy it **below its face "
             "value** (say 95) and receive the full face value (100) at a fixed date. Your return "
             "is the discount. A Pendle **PT** is exactly that: pay a bit less than 1 today, "
             "receive 1 underlying token at maturity.")
    s += section("SY, PT and YT")
    s += bullets([
        "**SY** (standardized yield): a standard wrapper around a yield-bearing token (here "
        "sUSDe), so Pendle can handle any of them the same way.",
        "**PT** (principal token): redeemable **1:1 for the underlying at maturity** (here: "
        "26 November 2026). Before that, it trades at a discount. Holding a PT to maturity "
        "locks in a **fixed yield**.",
        "**YT** (yield token): receives all the yield the underlying earns until maturity. It is "
        "a bet on future rates. The project does not hold YT.",
    ])
    s += diagram(TEXT_W, 100, {
        "sy": (20, 34, 120, 40, "1 SY (wraps 1 sUSDe)", "asset"),
        "pt": (300, 58, 170, 34, "PT: 1 sUSDe at maturity\n(fixed yield)", "position"),
        "yt": (300, 6, 170, 34, "YT: all the yield until maturity\n(variable)", "plain"),
    }, [("sy", "pt", "split"), ("sy", "yt", "split")],
        caption="Pendle splits a yield-bearing token into principal (PT) and yield (YT).")
    s += section("Discount and implied APY")
    s += [P("If a PT costs *p* (in units of the underlying) and matures in *d* days, the yield you "
            "lock in, expressed per year, is the **implied APY**:")]
    s += formula("implied APY = (1 / p)<super>365 / d</super> − 1")
    s += box("example",
             "PT-sUSDe traded at a **0.61% discount** (p = 0.99385) with **46 days** to maturity. "
             "1 / 0.99385 = 1.00618, raised to the power 365 / 46 = 7.93 gives 1.0501. Implied APY "
             "= **5.0%**, exactly what Pendle's API reported (`implied_apy` = 0.0501).")
    s += section("Selling before maturity: the Pendle AMM")
    s += [P("Before maturity, the only way out is to sell the PT, mainly on **Pendle's own AMM "
            "pool** for that maturity. Its curve is designed for PTs: flat near the current rate, "
            "then steep. Pendle's **router** finds the best execution, including **limit orders** "
            "placed by other traders. That pool is your **exit door**, so its liquidity is a "
            "dependency.")]
    s += section("PT as collateral, and why that matters to you")
    s += [P("Many people deposit PTs as collateral on Morpho, borrow USDC, buy more PT, and repeat. "
            "This is **looping**, a way to multiply the fixed yield with leverage. If the PT price "
            "drops, these looped positions are liquidated, and liquidators **sell PT into the "
            "same Pendle pool** you would use to exit.")]
    s += box("real",
             "A 5% PT price drop would liquidate **3.79M USD** of PT on Morpho. The Pendle pool "
             "had **3.82M USD** of liquidity. Ratio: 3.79 / 3.82 ≈ **0.99**. That is the "
             "`collateral_in` edge exposure of **99%** in the PT-sUSDe graph: in a crisis, forced "
             "sellers would be about as large as the whole exit pool.")
    s += box("check", ["What do you receive when a PT matures?",
                       "Compute the implied APY of a PT at 0.98 with 182 days left.",
                       "Why do liquidations on Morpho affect someone who never borrowed?"])

    # ------------------------------------------------------------------ 16
    s += chapter(16, "Ethena and USDe: a dollar built from hedges")
    s += [P("**USDe** is a synthetic dollar issued by **Ethena**. It is not backed by dollars in a "
            "bank. It is backed by a **hedged crypto position**, also called a **delta-neutral** "
            "or **basis** trade.")]
    s += section("Delta-neutral in one example")
    s += [P("Ethena holds 1 ETH (worth 2,000 USD) and, at the same time, opens a **short** "
            "position of 1 ETH on a derivatives exchange (it gains when ETH falls). If ETH rises "
            "10%, the ETH held gains 200 and the short loses 200. If ETH falls 10%, the reverse. "
            "Either way the total stays near 2,000 USD. That is \"delta-neutral\": no exposure to "
            "the price (\"delta\" = sensitivity to price).")]
    s += [P("Where does the yield come from? From staking rewards on the ETH, and above all from "
            "the **funding rate** that long traders usually pay short traders on perpetual "
            "futures (chapter 17). Users who stake USDe receive **sUSDe**, which collects that "
            "yield.")]
    s += section("The dependencies this creates")
    s += bullets([
        "**Exchanges (venues)**: the short positions live on centralized exchanges. If an "
        "exchange is hacked or fails, the hedge breaks for the share of backing there.",
        "**Funding rates**: if they turn negative for long, the yield turns into a cost.",
        "**Custodians**: Ethena keeps collateral with off-exchange custodians, another "
        "dependency.",
    ])
    s += box("real",
             "Ethena's transparency API, read by `src/data/ethena.py`, shows where the backing "
             "sits. In the cached data: **Binance 13.3%** (638M USD), OKX 4.2%, Bybit 2.3%, "
             "Deribit 0.4%, CDE 0.2%. These become `hedges_on` edges from the Ethena issuer. "
             "The stress engine confirms the intuition: if Binance lost everything, the PT-sUSDe "
             "position would lose **13.3%**.")
    s += box("code",
             "Venues use the calibrated **exchange hack** row: 6 hacks of 10M USD or more on the "
             "18 exchanges holding at least 1B USD over 3 years, about **11% per exchange per "
             "year**, median loss **2.6%** of holdings.")
    s += box("check", ["How can holding ETH and shorting ETH produce a stable dollar value?",
                       "Why does a Binance hack matter to someone holding a Pendle PT?"])

    # ------------------------------------------------------------------ 17
    s += chapter(17, "Perpetual futures and Hyperliquid")
    s += section("Futures, perps, long and short")
    s += bullets([
        "A **future** is a contract to buy or sell an asset later at a price fixed today. A "
        "**perpetual future** (\"perp\") never expires.",
        "**Long** = you gain if the price rises. **Short** = you gain if it falls.",
        "**Margin** = the money you deposit as a guarantee. **Leverage** = position size ÷ "
        "margin. With 1,000 USD of margin and a 5,000 USD position, leverage is 5×.",
        "**Notional** = the full size of the position (5,000 USD here), not just the margin.",
        "**Funding rate**: a small payment exchanged every hour or so between longs and shorts, "
        "which keeps the perp price close to the real (spot) price. When more people want to be "
        "long, longs pay shorts.",
        "If losses eat the margin, the exchange **liquidates** the trader's position.",
    ])
    s += section("Hyperliquid")
    s += [P("**Hyperliquid** is a perp exchange that runs on its **own blockchain** (Hyperliquid "
            "L1): an order-book trading engine (HyperCore) plus an EVM side (HyperEVM, chain 999). "
            "Its **validators** also act as the oracle: they publish prices built from major "
            "exchanges. Users deposit USDC through a **bridge contract on Arbitrum**.")]
    s += [P("A **Hyperliquid vault** lets you deposit USDC with a trader (the **leader**, who "
            "takes a commission) or with **HLP**, the exchange's own market-making and "
            "liquidation vault. Withdrawals have a **lock-up** after deposit: 4 days for HLP, "
            "1 day for user vaults.")]
    s += box("code",
             "`src/graph/perp_vault.py` builds: position → vault → **venue** Hyperliquid (100%) → "
             "Hyperliquid L1 chain. Venue → **bridge** on Arbitrum (custodies the USDC). Venue → "
             "**validator oracle**. Vault → each of its largest perp positions, with exposure = "
             "position notional ÷ vault value. This is the brief's *\"vault deploying into an "
             "external venue\"*.")
    s += box("check", ["What is the difference between margin and notional?",
                       "List three things a Hyperliquid vault depositor depends on."])

    # ------------------------------------------------------------------ 18
    s += chapter(18, "Putting it together: the dependency map of a position")
    s += [P("The hackathon brief describes a position's dependencies in **five layers**. Take "
            "PT-sUSDe and walk down them:")]
    s += numbered([
        "**Settlement chain**: Ethereum. If it halts, nothing moves.",
        "**Yield source and issuer**: sUSDe, issued by Ethena, whose hedges sit on Binance, OKX…",
        "**Oracle**: the Morpho oracle that prices PT-sUSDe for lenders.",
        "**Market / AMM**: the Pendle pool where the PT can be sold before maturity.",
        "**Lending markets**: Morpho markets where the PT is collateral, whose liquidations sell "
        "into that pool.",
    ])
    s += diagram(TEXT_W, 250, {
        "pos": (6, 112, 92, 34, "PT-sUSDe\n(your position)", "position"),
        "chain": (150, 205, 100, 26, "Ethereum", "chain"),
        "pendle": (150, 160, 100, 26, "Pendle V2 (code)", "protocol"),
        "susde": (150, 112, 100, 30, "sUSDe (redeems into)", "asset"),
        "amm": (150, 62, 100, 30, "Pendle AMM pool (exit)", "market"),
        "morpho": (150, 10, 100, 34, "Morpho PT/USDC market", "lending"),
        "ethena": (300, 112, 90, 30, "Ethena (issuer)", "issuer"),
        "bin": (420, 150, 70, 22, "Binance 13%", "venue"),
        "okx": (420, 118, 70, 22, "OKX 4%", "venue"),
        "byb": (420, 86, 70, 22, "Bybit 2% …", "venue"),
        "orc": (300, 14, 90, 26, "Oracle 0xF8b2…", "oracle"),
    }, [("pos", "chain", "100%"), ("pos", "pendle", "100%"), ("pos", "susde", "100%"),
        ("pos", "amm", "100%"), ("pos", "morpho", "99%"), ("susde", "ethena", "issued by"),
        ("ethena", "bin", ""), ("ethena", "okx", ""), ("ethena", "byb", ""),
        ("morpho", "orc", "priced by")],
        caption="The real PT-sUSDe graph found by the project (simplified). Arrows mean "
                "\"depends on\". Percentages are edge exposures.")
    s += box("idea",
             "A position is never \"just a token\". It is a **web of dependencies**, and most of "
             "the risk sits in places you would never look at if you only watched the token's "
             "price. Part 3 turns this map into numbers.")
    return s
