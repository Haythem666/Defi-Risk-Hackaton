"""Part 1: blockchains from scratch."""

from kit import *  # noqa: F401,F403


def content():
    s = []
    s += part(1, "Blockchains from scratch",
              "What a blockchain is, why it exists, and the pieces this project reads every day: "
              "chains, wallets, smart contracts, tokens and bridges.")

    # ------------------------------------------------------------------ 1
    s += chapter(1, "Why blockchains exist", new_page=False)
    s += [P("Before any technology, start with a simple observation: **money is a record**. "
            "When your bank says you have 1,000 euros, there is no pile of notes with your name on "
            "it. There is a line in the bank's books (its **ledger**) that says *this person is owed "
            "1,000 euros*. When you pay someone, the bank edits two lines: yours goes down, theirs "
            "goes up.")]
    s += [P("This works because everyone **trusts the bank** to keep the ledger honestly, not to "
            "lose it, and not to edit it in its own favour. Most of the time that trust is "
            "deserved. But it has costs: the bank decides who may open an account, can freeze it, "
            "works office hours across borders, and if the bank fails, its ledger fails with it.")]
    s += section("The problem a blockchain solves")
    s += [P("Could we keep a ledger that **nobody owns** and that **nobody can cheat**? Digital "
            "information is easy to copy. If money were just a file, you could send the same file "
            "to two people. This is called the **double-spending problem**. A bank solves it by "
            "being the single referee. A blockchain solves it without a referee.")]
    s += box("analogy",
             "Imagine a village where every family keeps an identical notebook listing who owns "
             "what. When Alice pays Bob, she announces it in the square. Every family writes it "
             "down. If Alice later claims she never paid, the whole village can show her the line. "
             "If one family tries to secretly edit its notebook, it no longer matches the thousands "
             "of other copies, and everyone ignores it.",
             "A blockchain is that notebook, copied on thousands of computers around the world, "
             "with strict rules for adding new lines.")
    s += [P("Bitcoin (2009) was the first working blockchain. Its ledger only tracks one thing: who "
            "owns which bitcoins. **Ethereum** (2015) went further: its ledger can also store "
            "**programs** that hold money and follow rules automatically. These programs are "
            "called **smart contracts** (chapter 6). Everything in this project, and all of "
            "\"DeFi\", is built on that idea.")]
    s += box("idea",
             "A blockchain is a **shared ledger** that nobody owns, that anyone can read, and that "
             "cannot be edited after the fact. It replaces *trust in a referee* with *rules "
             "enforced by thousands of computers*.")
    s += box("check",
             ["Why is \"money is a record\" the right starting point to understand blockchains?",
              "What is double spending, and how does a bank prevent it?"])

    # ------------------------------------------------------------------ 2
    s += chapter(2, "How a blockchain works")
    s += section("Transactions and blocks")
    s += [P("A **transaction** is one instruction for the ledger, for example *send 100 USDC from "
            "address A to address B*. Transactions are not added one by one. They are grouped into "
            "**blocks**, like pages of the notebook. On Ethereum a new block appears roughly every "
            "12 seconds. On Solana it is a fraction of a second.")]
    s += section("Fingerprints that chain the blocks")
    s += [P("Each block carries a **hash** of the block before it. A hash is a *digital "
            "fingerprint*: a short code (for example `0x9f2c…e41a`) computed from any amount of "
            "data. Two key properties:")]
    s += bullets(["The same data always gives the same fingerprint.",
                  "Changing even one comma in the data gives a completely different fingerprint."])
    s += [P("Because block 101 contains the fingerprint of block 100, which contains the "
            "fingerprint of block 99, and so on, editing an old block would change its "
            "fingerprint, which would break every block after it. That is the \"chain\" in "
            "blockchain: a tamper-evident sequence of pages.")]
    s += diagram(TEXT_W, 92, {
        "b1": (20, 18, 120, 58, "Block 99\nfingerprint of 98\ntransactions…", "blue"),
        "b2": (180, 18, 120, 58, "Block 100\nfingerprint of 99\ntransactions…", "blue"),
        "b3": (340, 18, 120, 58, "Block 101\nfingerprint of 100\ntransactions…", "blue"),
    }, [("b2", "b1", "points to"), ("b3", "b2", "points to")],
        caption="Each block stores the fingerprint (hash) of the previous one. Change an old block "
                "and every later fingerprint stops matching.")
    s += section("Who adds the next block? Validators and consensus")
    s += [P("Someone must decide which transactions go into the next block. On modern chains like "
            "Ethereum this job belongs to **validators**: computers run by people who have locked "
            "up (\"staked\") their own money as a guarantee of good behaviour. If a validator "
            "cheats, part of its stake is destroyed (\"slashed\"). This system is called **proof "
            "of stake**. Bitcoin uses an older system, **proof of work**, where computers compete "
            "to solve puzzles.")]
    s += [P("The rules by which validators agree on the next block are called **consensus**. Once "
            "enough validators have agreed on a block, it is considered **final**: it will not be "
            "undone.")]
    s += section("When things go wrong: a chain halt")
    s += [P("If validators stop agreeing (a software bug, a crash, a network attack), no new "
            "blocks are produced. The chain **halts**. Nobody can move money until it restarts. "
            "Solana halted several times in 2022, for hours each time. A halt rarely destroys "
            "money, but you are frozen while prices keep moving elsewhere.")]
    s += box("code",
             "Every position in the project has an edge to a **chain** node (\"settles_on\"). In "
             "`src/risk/assumptions.py`, a chain halt is a **JUDGEMENT** scenario (an expert "
             "estimate, because no public dataset of halts exists): **1% chance per year**, "
             "costing **2%** of the value (the price move while you are stuck).")
    s += box("check",
             ["What would happen to block 101 if someone edited a transaction inside block 99?",
              "Why does a validator have money at stake?",
              "Why is a chain halt usually a small loss rather than a total loss?"])

    # ------------------------------------------------------------------ 3
    s += chapter(3, "Wallets, keys and addresses")
    s += [P("On a blockchain there are no names or bank accounts. There are **addresses**, and "
            "whoever holds the matching **private key** controls what is at that address.")]
    s += section("Private key, address, signature")
    s += bullets([
        "**Private key**: a huge secret number, created randomly. Whoever knows it controls the "
        "money. It is never shared. It is often written down as a **seed phrase** of 12 or 24 "
        "ordinary words.",
        "**Address**: a public identifier computed from the key, like an account number. On "
        "Ethereum-style chains it looks like `0x47ad2cd1dd15739a7a035b9d3b7828d916fef77e`: "
        "\"0x\" followed by 40 characters. On Solana it looks different, for example "
        "`DWSXb18xZApz29vnQpgR2m6MynCT7PznaXt7Ut7M7KaP`.",
        "**Signature**: proof, attached to a transaction, that it was approved by the owner of "
        "the private key. Anyone can check a signature. Nobody can forge one without the key.",
    ])
    s += box("analogy",
             "An address is like a glass mailbox in a public square: everyone can see what is "
             "inside and anyone can drop money in. Only the owner of the key can take money out. "
             "Lose the key and the money is stuck forever. Let someone steal it and they can empty "
             "the box, with no bank to call.")
    s += section("Hexadecimal, in one minute")
    s += [P("Addresses and blockchain data are written in **hexadecimal** (\"hex\"): a way of "
            "writing numbers with 16 digits, 0-9 then a-f. The prefix `0x` just means \"what "
            "follows is hex\". So `0x10` is 16, `0xff` is 255. You do not need to compute in hex. "
            "You just need to recognise it.")]
    s += section("Who can hold a key: wallets, multisigs and contracts")
    s += [P("Not every address belongs to a person. The project distinguishes:")]
    s += table([
        ["Kind of controller", "What it is", "Risk intuition"],
        ["**EOA** (externally owned account)", "An ordinary wallet: one private key.",
         "One stolen or lost key = full control lost. The project flags it."],
        ["**Multisig** (e.g. a \"Safe 4/8\")",
         "A smart contract that needs *k* of *n* keyholders to approve. \"4/8\" means 4 of 8 "
         "people must sign.",
         "Much safer: an attacker must steal several keys. A low threshold (1 or 2) is flagged."],
        ["**Timelock**", "A contract that delays every action, e.g. by 2 days, before it takes "
                         "effect.", "Gives users time to see a change coming and withdraw."],
        ["**Contract**", "Another program that holds the role.", "Look at who controls *that* "
                                                                 "program."],
    ], [0.24, 0.42, 0.34])
    s += box("code",
             "`src/graph/crawler.py`, function `controller()`, asks an address a few questions "
             "on-chain. Does it have code? If not, it is a plain wallet (EOA). Does it answer "
             "`getThreshold()` and `getOwners()`? Then it is a Safe multisig. Does it answer "
             "`getMinDelay()`? Then it is a timelock. `control_flags()` then writes the red flags "
             "you see in the app, for example *\"owner is a single wallet: one stolen key controls "
             "it\"*.")
    s += box("check",
             ["What is the difference between a private key and an address?",
              "Why is a 4-of-8 multisig safer than a single wallet as the owner of a vault?"])

    # ------------------------------------------------------------------ 4
    s += chapter(4, "Transactions, gas, nodes and explorers")
    s += section("Writing costs gas, reading is free")
    s += [P("Changing the ledger (sending tokens, depositing in a vault) requires a **transaction**: "
            "a signed instruction broadcast to the network. The sender pays a fee called **gas**, "
            "which pays validators for the computing work. Gas is paid in the chain's own coin "
            "(ETH on Ethereum, SOL on Solana).")]
    s += [P("**Reading** the ledger is free. Anyone can ask *what is the balance of this address?* "
            "or *what price does this oracle report?* without paying, because nothing changes. "
            "This project only ever **reads**. It never sends a transaction or moves any money.")]
    s += section("Nodes and RPC: how a program asks the blockchain a question")
    s += [P("A **node** is a computer that keeps a full copy of the ledger. To ask a question, a "
            "program sends a message to a node over the internet in a standard format called "
            "**JSON-RPC** (RPC = *remote procedure call*, \"run this function on your computer and "
            "send me the answer\"). Public providers run free nodes. The project uses "
            "`ethereum-rpc.publicnode.com` and similar.")]
    s += table([
        ["RPC method", "Plain meaning", "Used by the project for"],
        ["`eth_call`", "Run a read-only function of a contract and return the answer.",
         "Read an oracle's price, a vault's `asset()`, an owner's address…"],
        ["`eth_getCode`", "Return the program code stored at an address (empty for a wallet).",
         "Tell a wallet (EOA) from a contract; detect minimal proxies."],
        ["`eth_getStorageAt`", "Read one raw memory slot of a contract.",
         "Find who can upgrade a contract (proxy admin slot, chapter 7)."],
    ], [0.2, 0.42, 0.38])
    s += box("code",
             "`src/data/chain.py` holds the RPC addresses per chain and a `batch()` helper that "
             "sends many questions in **one** request (faster and kinder to free nodes). Every "
             "answer goes through `src/data/cache.py`, which stores it in `data/cache/`. If the "
             "node is down during a demo, the stored answer is used. `DEFI_OFFLINE=1` forces this.")
    s += section("Block explorers: the public window")
    s += [P("A **block explorer** is a website that shows the ledger in a readable form: every "
            "transaction, every balance, every contract. **Etherscan** for Ethereum, **Arbiscan** "
            "for Arbitrum, **Basescan**, **BscScan**, **Solscan** for Solana… The project uses "
            "explorer links as **evidence** on graph edges. Anyone can click and check that a "
            "dependency is real.")]
    s += box("check",
             ["Why does this project never pay gas?",
              "What does `eth_getCode` return for an ordinary wallet, and why is that useful?"])

    # ------------------------------------------------------------------ 5
    s += chapter(5, "The chains in this project")
    s += [P("There is not one blockchain but many. Each is a separate ledger with its own "
            "validators, fees and speed. Money on one chain does not automatically exist on "
            "another (moving it requires a **bridge**, chapter 9).")]
    s += section("Layer 1, Layer 2, and the EVM")
    s += bullets([
        "**Layer 1 (L1)**: an independent blockchain with its own validators (Ethereum, Solana, "
        "BSC, Hyperliquid L1).",
        "**Layer 2 (L2)**: a faster, cheaper chain that runs on top of an L1 and regularly posts "
        "summaries of its activity to it, inheriting much of its security. Arbitrum and Base are "
        "L2s of Ethereum (\"rollups\").",
        "**EVM** (Ethereum Virtual Machine): the \"computer\" that runs smart contracts on "
        "Ethereum. Many chains copy it, so the same contracts, addresses format and tools work "
        "there too. These are **EVM chains**. Solana is not an EVM chain: different programs, "
        "different address format, different tools.",
        "**Chain ID**: a number that identifies an EVM chain (1 = Ethereum). The project uses it "
        "everywhere to know which node to ask.",
    ])
    s += table([
        ["Chain", "Chain ID", "Type", "Why it is in the project"],
        ["Ethereum", "1", "L1, EVM", "The main DeFi chain: Pendle, Morpho, Aave, Ethena."],
        ["Arbitrum", "42161", "L2 of Ethereum, EVM",
         "Pendle and Aave markets. Also holds the USDC deposited on Hyperliquid (its bridge)."],
        ["Base", "8453", "L2 of Ethereum (run by Coinbase), EVM", "Morpho and Aave markets."],
        ["BSC (BNB Smart Chain)", "56", "L1 linked to Binance, EVM", "Pendle and Aave markets."],
        ["HyperEVM / Hyperliquid L1", "999", "L1, EVM side + trading engine",
         "Hyperliquid perp vaults (chapter 17)."],
        ["Plasma", "9745", "L1 for stablecoin payments, EVM", "Pendle and Aave markets."],
        ["Solana", "101 (project's own label)", "L1, **not** EVM",
         "Kamino vaults and reserves. Solana has no EVM chain ID, so the project uses 101."],
    ], [0.2, 0.13, 0.24, 0.43])
    s += box("warn",
             "The same token name on two chains can be two very different things. \"USDC on "
             "Arbitrum\" is issued natively by Circle. A token copied to another chain by a bridge "
             "is only as good as that bridge. The project tracks this with `bridged_by` and "
             "`backed_on` edges.")
    s += box("check",
             ["What is the difference between Ethereum and Arbitrum?",
              "Why can't the project read Solana with the same RPC helpers it uses for Base?"])

    # ------------------------------------------------------------------ 6
    s += chapter(6, "Smart contracts")
    s += [P("A **smart contract** is a program stored at an address on the blockchain. It can hold "
            "money and it follows its code exactly, automatically, for anyone who calls it. Nobody "
            "can stop it or make an exception, unless the code itself allows it.")]
    s += box("analogy",
             "A vending machine: insert 2 euros, press B4, get a drink. No shopkeeper decides. The "
             "rules are built into the machine. A lending protocol is a vending machine that says "
             "*deposit collateral worth 100, take out at most 80 in loans*. A bug in the machine is "
             "a way to get drinks without paying, and on a blockchain, anyone in the world can try "
             "it.")
    s += section("Code is public, but not always readable")
    s += [P("The blockchain stores a contract's **bytecode**: machine instructions, unreadable for "
            "humans. Developers write contracts in a language such as **Solidity**, then "
            "*compile* it to bytecode. To let people check what a contract does, a developer can "
            "publish the original source code. A service like **Sourcify** or Etherscan "
            "recompiles it and confirms it matches: the source is **verified**.")]
    s += box("code",
             "`chain.is_verified()` asks Sourcify whether an oracle's source code is published. "
             "The app's *Oracle checks* table shows \"source verified: yes / NO\". In the PT-sUSDe "
             "example, the Morpho oracle `0xF8b2…` shows **NO**. That does not mean it is "
             "malicious, only that you cannot read what it does.")
    s += section("Functions and how the project calls them")
    s += [P("A contract exposes **functions**. Some change things (`deposit`, `withdraw`), others "
            "only answer questions (`price()`, `owner()`, `asset()`). To call a function, you send "
            "its **selector**: the first 4 bytes of the fingerprint (keccak-256 hash) of its "
            "name. For example `price()` becomes `0xa035b1fe`. The answer comes back as a row of "
            "32-byte \"words\" in hex, following a standard layout called the **ABI** "
            "(application binary interface).")]
    s += table([
        ["Function", "Selector", "What the answer means"],
        ["`price()`", "`0xa035b1fe`", "Morpho oracle: price of 1 collateral token in loan tokens."],
        ["`asset()`", "`0x38d52e0f`", "ERC-4626 vault: the token it holds (chapter 8)."],
        ["`owner()`", "`0x8da5cb5b`", "Who owns (controls) the contract."],
        ["`SY()`", "`0xafd27bf5`", "Pendle PT: the wrapped token it redeems into (chapter 15)."],
        ["`getThreshold()`", "`0xe75235b8`", "Safe multisig: how many signatures are needed."],
    ], [0.2, 0.17, 0.63])
    s += box("code",
             "This is exactly what `src/graph/crawler.py` does for \"Any contract\" positions. It "
             "sends a contract every standard question at once. Every answer that is an address "
             "becomes a new **edge** in the graph, then it asks the same questions to that new "
             "address, up to 4 hops away and 40 contracts. Following links like this, from page to "
             "page, is called a **breadth-first crawl**.")
    s += section("Standards: ERC and EIP")
    s += [P("An **EIP** (Ethereum Improvement Proposal) is a published design. An **ERC** (Ethereum "
            "Request for Comments) is an EIP that defines a standard interface. Standards make "
            "contracts predictable: every ERC-20 token has `balanceOf()`, every ERC-4626 vault "
            "has `asset()`. That predictability is what makes automatic dependency discovery "
            "possible.")]
    s += section("Audits and hacks")
    s += [P("An **audit** is a paid review of a contract's code by a security firm. It reduces risk "
            "but never removes it. Many hacked protocols were audited. A **hack** (or *exploit*) "
            "is when someone uses a flaw (a code bug, a manipulated price, a stolen admin key) to "
            "take money out of a contract.")]
    s += box("real",
             "From `data/calibration.json`: over the last 3 years, DeFi protocols holding at least "
             "100M USD suffered **22 hacks of 1M USD or more**. Across the 221 such protocols "
             "(after adjusting for hacks DeFiLlama could not link to a protocol), that is about "
             "**5.9% chance per protocol per year**, and a typical (median) hack took **4.1% of "
             "the protocol's money**.")
    s += box("check",
             ["What does \"source verified\" prove, and what does it not prove?",
              "How does the crawler turn a contract's answers into graph edges?"])

    # ------------------------------------------------------------------ 7
    s += chapter(7, "Who controls a contract: proxies, owners, timelocks")
    s += [P("\"Code is law\" is only half true. Many contracts keep a **back door for their team**: "
            "the ability to change settings or even replace the code. That is useful for fixing "
            "bugs, and dangerous if the wrong person holds it. Knowing *who* holds it is a core "
            "part of dependency discovery.")]
    s += section("Upgradeable contracts and proxies")
    s += [P("Code stored on a blockchain cannot be edited. To make a contract upgradeable, "
            "developers split it in two:")]
    s += bullets([
        "a **proxy**: the permanent address users interact with, which holds the money;",
        "an **implementation**: the contract with the actual logic, which the proxy forwards "
        "every call to.",
    ])
    s += [P("An **admin** can point the proxy to a new implementation, that is, change the rules "
            "while keeping the money and the address. The standard **EIP-1967** says where the "
            "proxy stores these two addresses: in two fixed memory slots. The project reads those "
            "slots with `eth_getStorageAt` to learn who can upgrade.")]
    s += diagram(TEXT_W, 120, {
        "user": (10, 44, 90, 34, "You (deposit)", "position"),
        "proxy": (160, 44, 120, 34, "Proxy\n(fixed address, holds funds)", "protocol"),
        "impl": (350, 74, 120, 34, "Implementation v1\n(logic)", "plain"),
        "impl2": (350, 10, 120, 34, "Implementation v2\n(new logic)", "plain"),
        "admin": (160, 92, 120, 22, "Admin (who can upgrade)", "admin"),
    }, [("user", "proxy", "calls"), ("proxy", "impl", "forwards to"),
        ("proxy", "impl2", "after upgrade", {"dashed": True}), ("admin", "proxy", "")],
        caption="An upgradeable contract: your money sits in the proxy. The admin can swap the "
                "logic behind it.")
    s += [P("A **minimal proxy** (EIP-1167) is a cheap copy of another contract, used to deploy "
            "many identical vaults or oracles. It is *not* upgradeable. It just forwards. "
            "`chain.proxy_implementation()` recognises it from its code.")]
    s += section("Roles you will see in the graph")
    s += table([
        ["Role", "Plain meaning"],
        ["**owner**", "Can change the contract's settings, sometimes everything."],
        ["**admin**", "Can upgrade the code (proxy admin)."],
        ["**curator**", "In a vault: decides which markets the money goes to and how much."],
        ["**guardian**", "Can veto or pause dangerous changes (an emergency brake)."],
        ["**timelock**", "A mandatory delay between deciding a change and applying it."],
    ], [0.22, 0.78])
    s += box("code",
             ["In the graph these roles are **admin** nodes (pink), linked by `owned_by`, "
              "`administered_by`, `curated_by`, `guarded_by` or `controlled_by` edges.",
              "Morpho **Vault V2** (`src/graph/lending.py`) reads a timelock *per setting*. If the "
              "settings that decide where money can go (`addAdapter`, `increaseAbsoluteCap`, "
              "`increaseRelativeCap`) have **no timelock**, the curator could send deposits to a "
              "new market before depositors can react. The project flags this.",
              "Admin nodes carry no incident of their own. Key theft is already inside the hack "
              "rate of the contract they control, so counting it twice would overstate the risk."])
    s += box("real",
             "In the whole-book demo, the same **Safe 4/8** multisig (`0xbbac…f918`) and the same "
             "**Safe 4/9** (`0x21f7…73ca`) each control parts of **three different pockets**. If "
             "those signers were compromised, three pockets would be hit at once. Only a "
             "book-level view (chapter 26) can show this.")
    s += box("check",
             ["Why would a team make its contract upgradeable, and why does that create a risk?",
              "What does a timelock give depositors that an instant change does not?"])

    # ------------------------------------------------------------------ 8
    s += chapter(8, "Tokens")
    s += [P("A **token** is a unit of value managed by a smart contract. Inside, the token "
            "contract is simply a table: *address → balance*. Sending tokens means asking the "
            "contract to lower one balance and raise another. Creating new tokens is **minting**. "
            "Destroying them is **burning**. Whoever is allowed to mint (the **minter**) can "
            "create value out of thin air, so the project looks for it (`minted_by` edges).")]
    s += section("ERC-20: the standard token")
    s += [P("Almost every token follows **ERC-20**: `balanceOf`, `transfer`, `symbol` (\"USDC\"), "
            "`decimals`. **Decimals** is how many digits are after the decimal point, because "
            "blockchains only store whole numbers. USDC has 6 decimals: 1 USDC is stored as "
            "1,000,000. Most tokens have 18 decimals: 1 token is stored as 10<super>18</super>.")]
    s += box("example",
             "To sell 1,000,000 USD of PT-sUSDe priced at about 0.993 USD, the project computes "
             "1,000,000 / 0.993 ≈ 1,007,000 PT, then multiplies by 10<super>18</super> before "
             "asking Pendle for a quote (`src/decision/exit_cost.py`, `pt_amount`). Forget the "
             "decimals and you ask for a quote on a trillion times the wrong amount.")
    s += section("Stablecoins")
    s += [P("A **stablecoin** is a token designed to stay worth a fixed amount, usually 1 US "
            "dollar. Its **peg** is that target. When the price falls clearly below, it has "
            "**depegged**. How a stablecoin keeps its peg depends on what backs it:")]
    s += table([
        ["Family", "How it is backed", "Examples", "Depeg history (project data)"],
        ["**Fiat-backed**", "A company holds real dollars or treasury bills in a bank, 1 for 1.",
         "USDC (Circle), USDT (Tether)", "8.7% per coin-year, median drop 8.3%"],
        ["**Crypto-backed**", "Locked crypto worth more than the coins issued, or a hedged "
                              "crypto position.", "DAI, USDe (Ethena)",
         "38% per coin-year, median drop 6.4%"],
        ["**Algorithmic**", "Mostly a mechanism and confidence, little hard backing.",
         "UST (collapsed in 2022)", "123% per coin-year, median drop 17.6%"],
    ], [0.17, 0.33, 0.2, 0.3])
    s += [P("\"Per coin-year\" means: if you held one such coin for one year, how many depeg "
            "episodes would you expect. Above 100% means more than one per year on average. The "
            "project defines a depeg as **trading below 0.97 for at least 2 days in a row**, for "
            "coins with at least 100M USD in circulation, since 2021.")]
    s += section("Tokens that grow: yield-bearing tokens and vault shares")
    s += bullets([
        "**Yield-bearing token**: a token whose value in its base asset grows over time because "
        "the money behind it earns interest. **sUSDe** (\"staked USDe\") is worth slowly more "
        "and more USDe. The ratio is its **exchange rate**.",
        "**Vault share (ERC-4626)**: when you deposit in a standard vault, you receive *shares*. "
        "The vault's `asset()` function says which token it holds, and each share is a claim on "
        "a slice of it. The project uses `asset()` to look \"inside\" wrapped collateral, e.g. "
        "siUSD → iUSD.",
        "**Cooldown**: some tokens make you wait before redeeming (sUSDe has a cooldown period). "
        "The project reads `cooldownDuration()` and shows it in the exit cost explanation.",
    ])
    s += section("Wrapped and staked tokens")
    s += bullets([
        "**Wrapped token**: a token that represents another one 1:1 in a standard form. WETH is "
        "ETH wrapped as an ERC-20. WBTC is bitcoin represented on Ethereum (held by a custodian).",
        "**Staking**: locking ETH to help validate the chain, which earns rewards (chapter 2).",
        "**Liquid staking token (LST)**: a token you receive for staked ETH, so you can still use "
        "it (stETH from Lido, wstETH its wrapped form). It should be worth 1 ETH, but in June "
        "2022 stETH traded about 5% below ETH. That is the basis of the project's JUDGEMENT "
        "*\"asset_non_usd\"* depeg row: 3% per year, 5% severity.",
    ])
    s += section("Real-world assets (RWA) and off-chain backing")
    s += [P("An **RWA token** represents something outside the blockchain: a loan portfolio, a "
            "bond, euros in a bank. Examples in this project: **EURCV** (a euro stablecoin from "
            "Société Générale-FORGE), **PST** (from Huma, backed by payment-financing loans), "
            "**ONyc** (from OnRe, reinsurance). The blockchain can show the tokens, but not the "
            "assets behind them. You must trust the issuer's reports.")]
    s += box("code",
             "When an issuer's DeFiLlama category means off-chain assets (RWA, RWA Lending, Basis "
             "Trading, CeDeFi, Off-Chain Credit), `add_offchain_backing()` adds an **\"Off-chain "
             "backing\"** box to the graph, flagged *\"not verifiable on-chain\"*. It marks "
             "**where the visible graph stops**. It carries no separate incident, because its risk "
             "is the issuer's.")
    s += box("check",
             ["What does it mean for USDC to have 6 decimals?",
              "Why is a crypto-backed stablecoin more likely to depeg than a fiat-backed one, "
              "according to the data?",
              "What can the blockchain prove about an RWA token, and what can it not?"])

    # ------------------------------------------------------------------ 9
    s += chapter(9, "Bridges: moving tokens between chains")
    s += [P("Chains are separate ledgers. Ethereum cannot see Solana's balances. To use a token on "
            "another chain, a **bridge** creates a representative copy there. Two common designs:")]
    s += bullets([
        "**Lock and mint**: the original tokens are locked in a contract on chain A, and the "
        "bridge mints the same amount of copies on chain B. To go back, copies are burned and "
        "originals unlocked.",
        "**Burn and mint**: the token is burned on chain A and minted on chain B. The issuer "
        "authorises the bridge to mint on every chain.",
    ])
    s += diagram(TEXT_W, 120, {
        "a": (10, 60, 140, 46, "Chain A (home)\n100 tokens locked in bridge", "chain"),
        "bridge": (190, 60, 110, 46, "Bridge\nmessages + minting rights", "protocol"),
        "b": (340, 60, 140, 46, "Chain B\n100 copies minted", "chain"),
        "hack": (190, 6, 110, 34, "Bridge hacked: copies minted with nothing locked", "bad"),
    }, [("a", "bridge", "lock"), ("bridge", "b", "mint"), ("hack", "b", "", {"color": "#c0392b"})],
        caption="A copy is only as good as the bridge. A bridge exploit can mint copies backed by "
                "nothing, and every lender that accepts the copy as collateral is exposed.")
    s += [P("Bridges hold huge pools of locked tokens and have been some of the largest hacks in "
            "history (Ronin in 2022, more than 600M USD. Wormhole, about 320M USD).")]
    s += section("The two bridge systems the project recognises")
    s += bullets([
        "**Chainlink CCIP** (Cross-Chain Interoperability Protocol): a registry contract on each "
        "chain (`TokenAdminRegistry`) maps a token to its **token pool**, the contract that "
        "locks/burns and mints it. The project asks the registry `getPool(token)`, then asks the "
        "pool which chains it is connected to.",
        "**LayerZero OFT** (Omnichain Fungible Token): a token that knows how to move itself "
        "across chains through a LayerZero **endpoint**. The project detects it by asking for "
        "`endpoint()` and `oftVersion()`.",
    ])
    s += box("real",
             "In the Huma USDC Main vault, the collateral **PST** on Ethereum is a **bridged copy**: "
             "minted by the CCIP pool `0xfd34…`, with its home on **Solana**. The project adds "
             "edges `PST → Chainlink CCIP (bridged_by)` and `PST → Solana (backed_on)`, and the "
             "flag: *\"a bridge exploit mints tokens backed by nothing\"*.")
    s += box("check",
             ["In lock-and-mint, where are the original tokens while the copies circulate?",
              "Why does a bridge hack hurt lenders on the destination chain?"])
    return s
