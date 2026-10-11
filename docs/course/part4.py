"""Part 4: decisions."""

from kit import *  # noqa: F401,F403

KAPPA = 0.2 * 0.1 ** 2


def _snell_plot():
    def curve(H):
        return [(u / 1000, KAPPA / (1 - u / 1000) ** 2 * H) for u in range(700, 991, 3)]
    return plot(TEXT_W, 185, [
        (curve(0.906), "#c0392b", "Huma: freeze cost/yr"),
        ([(0.7, 0.0734), (0.99, 0.0734)], "#f0a59c", "Huma: yield"),
        (curve(0.063), "#2a5bd7", "Steakhouse: freeze cost/yr"),
        ([(0.7, 0.0402), (0.99, 0.0402)], "#9db8f0", "Steakhouse: yield"),
    ], (0.7, 0.99), (0, 0.165), "utilization u", "per year", [0.7, 0.8, 0.9, 0.99],
        [0, 0.04, 0.08, 0.12, 0.16], xfmt=lambda v: f"{v:.0%}", yfmt=lambda v: f"{v:.0%}",
        marks=[(0.843, 0.0734, "Huma u* = 84.3% (now 90.6%: EXIT)", -6, 6, "end"),
               (0.944, 0.0402, "Steakhouse u* = 94.4% (now 85.6%)", -6, 6, "end")],
        caption="Exit when the expected cost of a freeze, h(u) × (H − C), overtakes the yield r. "
                "A big haircut H (Huma) moves the trigger far to the left.")


def content():
    s = []
    s += part(4, "Decisions: STAY or EXIT",
              "Turning risk numbers into an answer a risk manager can act on, for one pocket and "
              "for the whole book.")

    # ------------------------------------------------------------------ 24
    s += chapter(24, "The STAY / EXIT rule", new_page=False)
    s += section("The intuition: insurance")
    s += [P("Leaving a position has a **certain** cost. Staying has an **uncertain** cost. The "
            "rule compares the two, on average:")]
    s += formula("EXIT  if  expected loss over the horizon  >  exit cost + yield given up")
    s += bullets([
        "**Expected loss**: from the Monte Carlo simulation (chapter 20), with each incident's "
        "loss computed by the stress engine and increased by the late-exit cost (chapter 23).",
        "**Exit cost**: today's quote to leave (slippage + fee for a PT, ~0 for a loan with idle "
        "liquidity).",
        "**Yield given up** (also called *forgone yield*): what you stop earning by holding "
        "cash instead. APY × days ÷ 365. With 6% APY over 30 days, that is 0.49%.",
    ])
    s += box("warn",
             "Why the yield given up matters: withdrawing from a vault costs ~0%. Without this "
             "term, any expected loss above zero said EXIT, for every loan. Leaving is never free: "
             "you lose the yield you came for. Adding it is what made the verdicts differ between "
             "vaults.")
    s += section("The breakeven probability p*")
    s += [P("A risk manager often has their own view of how likely an incident is. The project "
            "gives them a threshold to compare it with:")]
    s += formula("p* = cost of leaving ÷ loss if hit   (for the worst scenario)")
    s += box("example",
             "The brief's reference case: exiting costs **11%** slippage. If the worst incident "
             "would cost the pocket **50%**, p* = 11 ÷ 50 = **22%**. If you believe the incident "
             "has more than a 22% chance of happening within the horizon, exit. Below that, stay. "
             "At the book level: with 10 pockets of 10%, unwinding one pocket at 11% costs "
             "0.1 × 11% = **1.1% of the book**.")
    s += section("The exit trigger overrides the average")
    s += [P("For lending positions there is a second, independent reason to leave: utilization "
            "has crossed the **exit trigger** u* (chapter 25), meaning withdrawals risk freezing "
            "with a large haircut. In that case the verdict is EXIT whatever the average says.")]
    s += section("Real verdicts")
    s += box("real",
             "The six pockets of the whole-book demo, 1M USD each, 30-day horizon, computed by the "
             "latest code on the repository's cached snapshots:",
             Spacer(1, 2))
    s += table([
        ["Pocket", "Expected loss", "Cost of leaving (exit + yield)", "Utilization / u*",
         "Verdict"],
        ["PT-sUSDe 26NOV2026", "0.35%", "0.46% (0.04% + 0.41%)", "n/a (not a loan)", "**STAY**"],
        ["RockawayX USDC Yield", "0.13%", "0.52% (0 + 0.52%)", "86.3% / 92.1%", "**STAY**"],
        ["Huma USDC Main", "0.18%", "0.60% (0 + 0.60%)", "90.6% / **84.3%**", "**EXIT** (trigger)"],
        ["Belem RWA EURCV", "0.15%", "0.22% (0 + 0.22%)", "90.8% / **75.7%**", "**EXIT** (trigger)"],
        ["Kamino Steakhouse HY USDC", "0.09%", "0.33% (0 + 0.33%)", "85.6% / 94.4%", "**STAY**"],
        ["Kamino RWA USDC", "0.09%", "0.49% (0 + 0.49%)", "92.8% / **92.5%**", "**EXIT** (trigger)"],
    ], [0.27, 0.13, 0.25, 0.18, 0.17])
    s += [P("Notice that no pocket exits because of its *average* loss. The three EXITs all come "
            "from the freeze trigger: the risk that matters most for these vaults is **being "
            "stuck**, not a slow average loss.")]
    s += section("The What if? control")
    s += [P("In the app, *What if?* lets you pick any dependency and say how much it loses (e.g. "
            "\"Binance loses 50%\"). The stress engine immediately shows what your position "
            "loses, in % and USD. A second slider sets the **chance it happens within the "
            "horizon**. Above 0, the hit is added as an extra scenario, so the expected loss, the "
            "verdict and p* react to it. This is how a risk manager injects their own view "
            "(*\"I think there is a 10% chance Ethena depegs 20% this month\"*).")]
    s += box("check",
             ["A loan pays 8% APY. What is the yield given up over 45 days?",
              "Exit costs 2% and the worst incident costs 40%. What is p*?",
              "Why can a pocket get EXIT even when its expected loss is below its cost of "
              "leaving?"])

    # ------------------------------------------------------------------ 25
    s += chapter(25, "When to leave a loan: the exit trigger")
    s += [P("For a lender, the nightmare is not a small loss. It is a **freeze**: utilization hits "
            "100%, withdrawals stop, and you are trapped while the collateral crashes. The "
            "question becomes one of **timing**: at what utilization should you leave, while you "
            "still can?")]
    s += section("The ingredients")
    s += bullets([
        "**r**: the yield you earn per year by staying (the vault's net APY).",
        "**C**: the cost of leaving now (exit cost, usually ~0 for loans).",
        "**H**: the **haircut if trapped**: what you lose if you sit through a crisis. The stress "
        "engine computes it as your loss if your worst collateral falls **50%** (JUDGEMENT).",
        "**h(u)**: the **hazard** of a freeze, the expected number of freezes per year at "
        "utilization *u*. It explodes as *u* approaches 100%:",
    ])
    s += formula("h(u) = κ ÷ (1 − u)<super>γ</super>    with γ = 2, and κ chosen so that h(90%) = "
                 "0.2 per year")
    s += [P("The anchor (JUDGEMENT): interest-rate curves keep markets near **90%** utilization on "
            "purpose, and a market sitting at that target is assumed to freeze about **once every "
            "five years** (0.2 per year). That gives κ = 0.2 × (1 − 0.9)<super>2</super> = "
            "0.002. At 95%, h = 0.8 per year. At 99%, h = 20 per year.")]
    s += section("The rule: leave when one more day costs more than it pays")
    s += [P("Over a short time, staying earns *r* × time. It also risks a freeze with probability "
            "*h(u)* × time, which would cost you *H* instead of the *C* you would pay by leaving "
            "now. So staying a little longer is worth it as long as:")]
    s += formula("r  >  h(u) × (H − C)")
    s += [P("Because the hazard only grows with utilization, this simple \"one step ahead\" "
            "comparison is the **optimal** rule (a result of optimal-stopping theory: the *Snell "
            "envelope*, solved here in closed form, per Chow, Robbins and Siegmund, 1971). "
            "Solving for *u* gives the threshold:")]
    s += formula("u* = 1 − ( κ (H − C) ÷ r )<super>1/γ</super>")
    s += _snell_plot()
    s += box("example",
             "**Huma USDC Main**: r = 7.34%, C = 0, H = **90.6%** (PST falls 50%, no DEX to sell "
             "it, so the lender recovers nothing on the 90.6% lent out). u* = 1 − √(0.002 × 0.906 "
             "÷ 0.0734) = 1 − √0.0247 = 1 − 0.157 = **84.3%**. Current utilization **90.6%**: "
             "above the trigger, so **EXIT**. Freeze hazard now: 0.002 ÷ 0.094² ≈ 0.23 per year.")
    s += box("example",
             "**Kamino Steakhouse HY USDC**: r = 4.02%, H = only **6.3%** (good collateral, "
             "sellable). u* = 1 − √(0.002 × 0.063 ÷ 0.0402) = 1 − 0.056 = **94.4%**. Now 85.6%: "
             "**STAY**. A small haircut means you can afford to wait much longer.")
    s += box("idea",
             "The trigger combines three facts into one actionable number. How bad is it to be "
             "trapped (H)? How well am I paid to wait (r)? How fast is the door closing (u)? A "
             "risk manager can monitor utilization live and act the moment it crosses u*.")
    s += box("check",
             ["Why does a bigger haircut H lower the trigger u*?",
              "Compute u* for r = 5%, H = 20%, C = 0.",
              "If H ≤ C, what does the project set u* to, and why?"])

    # ------------------------------------------------------------------ 26
    s += chapter(26, "The whole book: what pockets share")
    s += [P("Belem manages a **book**: several pockets, e.g. 10 pockets of 10% each. Judging each "
            "pocket alone misses something crucial: pockets can **share dependencies**. Two vaults "
            "on Ethereum, both lending USDC through Morpho, controlled by the same multisig, are "
            "not two independent bets. One failure can hit both.")]
    s += section("How the project finds shared dependencies")
    s += [P("Node ids are the same across graphs: `chain:ethereum`, `asset:USDC`, "
            "`protocol:morpho-blue`, an admin's address… So after building each pocket's graph, "
            "the book simply counts in how many pockets each node id appears.")]
    s += box("real",
             "Shared dependencies in the six-pocket demo book: **Ethereum** (4 pockets), **USDC** "
             "(4), **Morpho** (3), **Safe 4/8 multisig** (3), **Safe 4/9 multisig** (3), "
             "**Solana** (3), Kamino (2), reUSD (2), cbBTC (2), and an off-chain backing box (2). "
             "Even across chains: **PST** is collateral both behind Huma (on Ethereum, as a "
             "bridged copy) and behind Kamino RWA USDC (on Solana, its home).")
    s += section("Correlated vs independent: the book Monte Carlo")
    s += [P("The book simulation draws **each incident once** and hits every pocket that depends "
            "on that node in the same run. For comparison, it also runs the naive version, where "
            "every pocket draws its own incidents, as if the pockets were independent. The "
            "difference is the risk a pocket-by-pocket view **hides**.")]
    s += diagram(TEXT_W, 120, {
        "p1": (10, 80, 110, 28, "Pocket: Huma vault", "position"),
        "p2": (10, 44, 110, 28, "Pocket: Belem EURCV", "position"),
        "p3": (10, 8, 110, 28, "Pocket: RockawayX", "position"),
        "safe": (200, 62, 120, 30, "Same Safe 4/8 multisig", "admin"),
        "morpho": (200, 16, 120, 30, "Morpho (code)", "protocol"),
        "eth": (380, 40, 100, 30, "Ethereum", "chain"),
    }, [("p1", "safe", ""), ("p2", "safe", ""), ("p3", "safe", ""), ("p1", "morpho", ""),
        ("p2", "morpho", ""), ("p3", "morpho", ""), ("morpho", "eth", "")],
        caption="Real, from the demo book: Huma, Belem RWA EURCV and RockawayX share the same Safe "
                "4/8 multisig and Morpho. One compromised multisig or one Morpho bug hits all three.")
    s += box("real",
             "Six pockets of 1M USD, 30 days. Expected book loss: **10,111 USD** with shared "
             "draws vs 9,786 USD if independent (averages barely change). **Worst 5%**: "
             "**116,707 USD** with shared draws vs **100,911 USD** if independent. Pretending the "
             "pockets are independent **hides about 15,800 USD of tail risk (+16%)**. Shared "
             "dependencies do not change the average much, but they make bad days much worse.")
    s += section("What the Whole book view shows")
    s += bullets([
        "A **headline**: how many pockets should EXIT, the book size, the expected and tail "
        "losses, and the hidden tail.",
        "**Pocket cards**: verdict, expected loss, cost of leaving, a one-line reason and the "
        "**action** (e.g. *\"Withdraw all 1.00M USD now (no slippage)\"* or *\"Sell the PT on "
        "Pendle now\"*).",
        "A **shared-dependency heatmap** (which pocket relies on which node) and a **network** "
        "picture of the book.",
        "A **book stress test**: pick a node and a severity, see each pocket's loss.",
        "An **action plan** listing what to do pocket by pocket.",
        "An editable table to build your own book: add a row, paste an address.",
    ])
    s += box("warn",
             "The book simulation still treats **different** nodes as independent. A market-wide "
             "crash that hits Ethena, Morpho and Pendle at once is not modelled as one event. "
             "CLAUDE.md lists this as a known gap.")
    s += box("check",
             ["Why can the average book loss stay almost the same while the worst 5% rises?",
              "Name two kinds of dependency that two pockets on different chains could still "
              "share."])
    return s
