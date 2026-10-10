"""What a lending market's collateral itself depends on.

A lender gets repaid as long as the collateral keeps its value and can be
sold when a borrower is liquidated. So behind each collateral token we look
for:
  - who issues it (DeFiLlama yield pools, else the token's website on
    CoinGecko matched to a DeFiLlama protocol with the same website),
  - whether it is a bridged copy (Chainlink CCIP pool, LayerZero OFT) and
    from which chain: a bridge exploit mints tokens backed by nothing,
  - who can change or mint it (upgrade admin, owner, CCIP admin, bridge pool),
  - where liquidators can sell it (KyberSwap quotes over every DEX) and who
    else accepts it as collateral (their liquidations sell into the same DEX
    liquidity).
"""

from src.data import chain, coingecko, defillama, kyberswap, morpho, pendle
from src.graph.common import (_risk_meta, add_asset, add_node, add_offchain_backing, add_protocol,
                              chain_name, explorer)
from src.graph.crawler import BASE_ASSETS  # plain base assets: issuer and bridges well known
from src.schemas import Edge, Node

# Chainlink CCIP: the registry that maps a token to its bridge pool, per chain.
# https://docs.chain.link/ccip/directory/mainnet
CCIP_REGISTRY = {1: "0xb22764f98dD05c789929716D677382Df22C05Cb6",
                 42161: "0x39AE1032cF4B334a1Ed41cdD0833bdD7c7E7751E",
                 8453: "0x6f6C373d09C07425BaAE72317863d7F6bb731e37",
                 56: "0x736Fd8660c443547a85e4Eaf70A49C1b7Bb008fc"}
CCIP_CHAINS = {5009297550715157269: "Ethereum", 4949039107694359620: "Arbitrum",
               15971525489660198786: "Base", 11344663589394136015: "BSC",
               124615329519749607: "Solana", 3734403246176062136: "Optimism",
               4051577828743386545: "Polygon", 6433500567565415381: "Avalanche"}

# keccak256 selectors
SEL = {"name": "0x06fdde03", "owner": "0x8da5cb5b", "getCCIPAdmin": "0x8fd6a6ac",
       "endpoint": "0x5e280f11", "oftVersion": "0x156a0d0f"}
GET_POOL, TYPE_AND_VERSION, SUPPORTED_CHAINS, REMOTE_TOKEN = (
    "0xbbe4f6db", "0x181f5a77", "0xc4bffe2b", "0xb7946580")
IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"

# Collateral that wraps another token (a PT, a vault share) is opened up to
# this many levels: PT-reUSD -> reUSD -> ..., siUSD -> iUSD -> ...
MAX_UNWRAP = 2
_unwrap_depth = [0]  # current nesting, shared by the recursive calls below
ASSET = "0x38d52e0f"  # ERC-4626 asset(): the token a vault share is a claim on
SYMBOL = "0x95d89b41"

# Liquidation stress: the collateral liquidated if its price falls this much
# must be sold by liquidators (same shock as the PT graph uses).
SHOCK = 0.05
SPOT_USD = 10_000  # small sale: the token's price on DEXes
NO_MARKET_IMPACT = 0.5  # a small sale losing half its value or more: no real market


def add_collateral_depth(nodes: list[Node], edges: list[Edge], cid: int, asset_id: str,
                         symbol: str, address: str) -> None:
    """Issuer, bridge and controllers of a collateral token, added once per token."""
    asset = next(n for n in nodes if n.id == asset_id)
    if symbol.upper() in BASE_ASSETS or asset.meta.get("collateral_depth"):
        return
    asset.meta["collateral_depth"] = True
    try:
        token = _read_token(cid, address)
    except Exception:
        token = {}  # RPC down and nothing cached: the asset node stays as it is
    flags = asset.meta.setdefault("flags", [])
    remote = _add_bridge(nodes, edges, cid, asset, token, flags)
    _add_controllers(nodes, edges, cid, asset, token, flags)
    if not any(e.source == asset_id and e.kind == "issued_by" for e in edges):
        _add_issuer_from_website(nodes, edges, cid, asset, token.get("name"), symbol)
    _add_other_holders(asset, cid, address, remote)
    if _unwrap_depth[0] < MAX_UNWRAP:
        _unwrap_depth[0] += 1
        try:
            _unwrap(nodes, edges, cid, asset, symbol, address)
        except Exception:
            pass  # API or RPC down and nothing cached: the token stays a leaf
        finally:
            _unwrap_depth[0] -= 1


# --- what the collateral is made of ------------------------------------------

def _unwrap(nodes, edges, cid, asset: Node, symbol: str, address: str) -> None:
    """Open a collateral that is a claim on another token: a Pendle PT
    (redeems into its underlying at maturity) or a vault share (ERC-4626:
    a claim on the vault's asset; a Morpho vault also lends it out)."""
    if symbol.upper().startswith("PT-"):
        _unwrap_pt(nodes, edges, cid, asset, address)
        return
    from src.graph.crawler import _addr, _string, _words
    inner = _addr((_words(chain.eth_call(cid, address, ASSET)) or [None])[0])
    if not inner or inner == address.lower():
        return
    from src.graph.lending import _add_v1_allocations, _add_v2_vault  # avoid a circular import
    v1 = morpho.vault(cid, address) if cid in morpho.NETWORKS else None
    v2 = None if v1 or cid not in morpho.NETWORKS else morpho.vault_v2(cid, address)
    if v1:  # a Morpho vault share: its markets are what backs it
        vault_id = add_node(nodes, Node(f"vault:{address.lower()}", "vault", v1["name"], chain_name(cid),
                                        {"address": address, "version": 1,
                                         "total_usd": v1["state"]["totalAssetsUsd"]}))
        edges.append(Edge(asset.id, vault_id, "share_of", 1.0, morpho.vault_url(cid, address)))
        _add_v1_allocations(nodes, edges, cid, vault_id, v1)
    elif v2:
        _add_v2_vault(nodes, edges, cid, v2, asset.id, 1.0, "share_of")
    sym = _string(chain.eth_call(cid, inner, SYMBOL)) or inner[:10]
    inner_id = add_asset(nodes, edges, cid, sym, inner)
    asset.meta["wraps"] = inner_id  # its peg risk is the inner token's (risk/assumptions.py)
    edges.append(Edge(asset.id, inner_id, "holds", 1.0,
                      f"asset() on {explorer(cid, address)} returns {inner} ({sym}): the share "
                      f"is a claim on {sym}"))
    add_collateral_depth(nodes, edges, cid, inner_id, sym, inner)


def _unwrap_pt(nodes, edges, cid, asset: Node, address: str) -> None:
    """A Pendle PT: Pendle's API gives its market, and the token it redeems
    into at maturity."""
    m = next((m for m in pendle.active_markets(cid) if pendle._addr(m["pt"]) == address.lower()),
             None)
    if m is None:
        return
    url = f"https://app.pendle.finance/trade/markets/{m['address']}?chain={chain_name(cid).lower()}"
    proto_id = add_protocol(nodes, edges, cid, "pendle-v2", "Pendle", url)
    edges.append(Edge(asset.id, proto_id, "contracts_of", 1.0, f"Pendle PT, market {url}"))
    underlying, sym = pendle._addr(m["underlyingAsset"]), m["name"]
    inner_id = add_asset(nodes, edges, cid, sym, underlying)
    asset.meta.update(wraps=inner_id, pendle_market=m["address"], pendle_sy=pendle._addr(m["sy"]),
                      expiry=m["expiry"][:10])
    edges.append(Edge(asset.id, inner_id, "redeems_into", 1.0,
                      f"Pendle API: this PT redeems 1:1 into {sym} ({explorer(cid, underlying)}) "
                      f"at expiry {m['expiry'][:10]}: {url}"))
    add_collateral_depth(nodes, edges, cid, inner_id, sym, underlying)


# --- on-chain reads ---------------------------------------------------------

def _read_token(cid: int, address: str) -> dict:
    from src.graph.crawler import _addr, _string, _words
    calls = [("eth_getStorageAt", [address, IMPL_SLOT, "latest"]),
             ("eth_getStorageAt", [address, ADMIN_SLOT, "latest"])]
    calls += [("eth_call", [{"to": address, "data": s}, "latest"]) for s in SEL.values()]
    if cid in CCIP_REGISTRY:
        calls.append(("eth_call", [{"to": CCIP_REGISTRY[cid],
                                    "data": GET_POOL + "0" * 24 + address[2:].lower()}, "latest"]))
    res = chain.batch(cid, calls)
    word = lambda r: _addr((_words(r) or [None])[0])  # noqa: E731
    out = {"impl": _addr((res[0] or "")[2:]), "upgrade_admin": _addr((res[1] or "")[2:]),
           "name": _string(res[2]), "owner": word(res[3]), "ccip_admin": word(res[4]),
           "oft_endpoint": word(res[5]) if res[6] and res[6] != "0x" else None,
           "ccip_pool": word(res[7]) if len(res) > 7 else None}
    if out["ccip_pool"]:
        p = out["ccip_pool"]
        kind, chains, pool_owner = chain.batch(cid, [
            ("eth_call", [{"to": p, "data": s}, "latest"])
            for s in (TYPE_AND_VERSION, SUPPORTED_CHAINS, SEL["owner"])])
        w = _words(chains)
        selectors = [int(x, 16) for x in w[2:2 + int(w[1], 16)]] if len(w) >= 2 else []
        out.update(ccip_pool_type=_string(kind), ccip_pool_owner=word(pool_owner),
                   ccip_remote={s: _remote_token(cid, p, s) for s in selectors})
    return out


def _remote_token(cid: int, pool: str, selector: int) -> str | None:
    """The token's address on the other chain (bytes: an EVM address, or a
    Solana mint written in base58)."""
    from src.graph.crawler import _words
    w = _words(chain.eth_call(cid, pool, REMOTE_TOKEN + f"{selector:064x}"))
    if len(w) < 3:
        return None
    raw = bytes.fromhex("".join(w[2:]))[:int(w[1], 16)]
    if CCIP_CHAINS.get(selector) == "Solana":
        return _base58(raw)
    return "0x" + raw[-20:].hex()


def _base58(raw: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n, out = int.from_bytes(raw, "big"), ""
    while n:
        n, r = divmod(n, 58)
        out = alphabet[r] + out
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + out


# --- graph pieces -----------------------------------------------------------

def _chain_node(nodes: list[Node], name: str) -> str:
    return add_node(nodes, Node(f"chain:{name.lower()}", "chain", name, name, {}))


def _add_bridge(nodes, edges, cid, asset: Node, t: dict, flags: list) -> dict[str, str]:
    """Bridge that mints this copy of the token. Returns {chain: token address there}."""
    remote: dict[str, str] = {}
    if t.get("ccip_pool"):
        pool, kind = t["ccip_pool"], t.get("ccip_pool_type") or "CCIP token pool"
        names = {s: CCIP_CHAINS.get(s, f"CCIP chain {s}") for s in t.get("ccip_remote") or {}}
        remote = {names[s]: a for s, a in (t.get("ccip_remote") or {}).items() if a}
        why = (f"Chainlink CCIP TokenAdminRegistry {explorer(cid, CCIP_REGISTRY[cid])} getPool() "
               f"returns {pool}, a '{kind}' linked to {', '.join(names.values()) or 'no chain'}")
        asset.meta.update(bridge="Chainlink CCIP", bridge_pool=pool, bridge_pool_type=kind,
                          bridged_with=list(names.values()), remote_tokens=remote)
        if "BurnMint" in kind:  # a lock/release pool only holds tokens leaving this chain
            proto_id = add_protocol(nodes, edges, cid, "ccip", "Chainlink CCIP", explorer(cid, pool))
            edges.append(Edge(asset.id, proto_id, "bridged_by", 1.0,
                              f"{why}: the pool mints this token when it arrives from another chain"))
            flags.append(f"bridged copy: minted by the CCIP pool {pool[:10]}; a bridge exploit "
                         f"mints tokens backed by nothing")
            if len(names) == 1:  # one other chain: that is where the backing lives
                home = next(iter(names.values()))
                edges.append(Edge(asset.id, _chain_node(nodes, home), "backed_on", 1.0,
                                  f"{why}; the original token is {remote.get(home)} on {home}"))
    elif t.get("oft_endpoint"):
        proto_id = add_protocol(nodes, edges, cid, "layerzero-v2", "LayerZero",
                                explorer(cid, t["oft_endpoint"]))
        asset.meta.update(bridge="LayerZero OFT", bridge_endpoint=t["oft_endpoint"])
        edges.append(Edge(asset.id, proto_id, "bridged_by", 1.0,
                          f"oftVersion() answers and endpoint() on {explorer(cid, asset.meta['address'])} "
                          f"returns {t['oft_endpoint']}: a LayerZero OFT, minted and burned "
                          f"when it moves between chains"))
        flags.append("bridged copy (LayerZero OFT): a bridge exploit or bad peer config "
                     "mints tokens backed by nothing")
    return remote


def _add_controllers(nodes, edges, cid, asset: Node, t: dict, flags: list) -> None:
    """Who can replace the code, mint, or reconfigure the bridge of the token."""
    from src.graph.crawler import control_flags, controller
    roles: dict[str, list[str]] = {}
    if t.get("impl"):
        who = t.get("upgrade_admin") or t.get("owner")
        flags.append("upgradeable proxy: its code can be replaced" + (f" by {who[:10]}" if who else ""))
        if who:
            roles.setdefault(who, []).append("upgrade admin")
    keys = [("owner", "owner"), ("ccip_admin", "CCIP admin")]
    if "BurnMint" in (t.get("ccip_pool_type") or ""):  # that pool can mint the token
        keys.append(("ccip_pool_owner", "bridge pool owner"))
    for key, role in keys:
        if t.get(key):
            roles.setdefault(t[key], []).append(role)
    # One node per final controller: a ProxyAdmin owned by a timelock is that timelock.
    address, by_ctrl = asset.meta["address"], {}
    for who, rs in roles.items():
        ctrl = controller(cid, who)
        c = by_ctrl.setdefault(ctrl["address"], {"ctrl": ctrl, "why": []})
        c["why"].append(f"{' + '.join(rs)} of {explorer(cid, address)} is {who}"
                        + (f" (owned by {ctrl['address']})" if ctrl.get("via") else ""))
        for r in rs:
            flags += control_flags(r, ctrl)
    for a, c in by_ctrl.items():
        label = c["ctrl"]["label"].split(" via ")[0]
        add_node(nodes, Node(f"admin:{a}", "admin", label, chain_name(cid), c["ctrl"]))
        edges.append(Edge(asset.id, f"admin:{a}", "controlled_by", 1.0,
                          "; ".join(c["why"]) + " (read on-chain)"))


def _add_issuer_from_website(nodes, edges, cid, asset: Node, name: str | None, symbol: str) -> None:
    """Issuer of a token DeFiLlama yield pools do not cover: the DeFiLlama
    protocol whose website is the token's website on CoinGecko."""
    if not name:
        return
    try:
        coin = coingecko.find_coin(name, symbol)
        proto = defillama.protocol_by_site(coin["homepage"]) if coin and coin["homepage"] else None
    except Exception:
        return
    if not proto:
        return
    slug = proto["slug"]
    new = all(n.id != f"issuer:{slug}" for n in nodes)
    issuer_id = add_node(nodes, Node(f"issuer:{slug}", "issuer", proto["name"], chain_name(cid),
                                     {**_risk_meta(slug), "website": coin["homepage"]}))
    edges.append(Edge(asset.id, issuer_id, "issued_by", 1.0,
                      f"CoinGecko lists {coin['homepage']} as the website of {name} "
                      f"({coingecko.coin_url(coin['id'])}); DeFiLlama protocol {slug} has the same "
                      f"website ({defillama.protocol_url(slug)})"))
    if new:
        add_offchain_backing(nodes, edges, issuer_id, slug)


def _add_other_holders(asset: Node, cid: int, address: str, remote: dict[str, str]) -> None:
    """Every DeFiLlama pool holding the token, here and on the chains it is
    bridged to: single-token pools are lenders taking it as collateral (their
    liquidations sell it too), multi-token pools are DEX pools."""
    try:
        pools = defillama.yield_pools()
    except Exception:
        return
    found = defillama.token_pools(pools, chain_name(cid), address)
    for ch, a in remote.items():
        found += defillama.token_pools(pools, ch, a)
    rows = [{"project": p["project"], "chain": p["chain"], "symbol": p["symbol"],
             "tvl_usd": p["tvlUsd"], "url": defillama.pool_url(p["pool"])} for p in found]
    lenders = [r for r, p in zip(rows, found) if len(p.get("underlyingTokens") or []) == 1]
    dexes = [r for r, p in zip(rows, found) if len(p.get("underlyingTokens") or []) > 1]
    asset.meta.update(posted_as_collateral=lenders, dex_pools=dexes,
                      posted_as_collateral_usd=sum(r["tvl_usd"] for r in lenders),
                      dex_pools_usd=sum(r["tvl_usd"] for r in dexes))


# Contagion: other lenders holding the same collateral. When its price drops
# they liquidate too, and every liquidator sells into the same DEX liquidity.
MAX_CONTAGION = 5            # largest other lenders shown per collateral
MIN_CONTAGION_USD = 100_000  # smaller holders are left out
LENDING_CATEGORIES = {"Lending", "CDP"}


def add_contagion(nodes: list[Node], edges: list[Edge]) -> None:
    """For each collateral in the graph, the other lending protocols that hold
    it (DeFiLlama single-token pools, here and on the chains it is bridged to),
    as nodes. Run once the graph is built, so the markets already in it are
    not counted twice.

    Exposure of the collateral to one of them = their forced sales if SHOCK of
    their collateral is liquidated, over the token's DEX liquidity, capped at
    1 (1 when no DEX pool holds the token). Only lending protocols count
    (DeFiLlama category): a Pendle pool or the issuer's own staking pool also
    hold the token but do not liquidate anyone."""
    try:
        category = {p["slug"]: p.get("category") for p in defillama.protocols()}
    except Exception:
        return
    for asset in [n for n in nodes if n.type == "asset" and n.meta.get("posted_as_collateral")]:
        own = {}  # collateral of this token already in the graph, per chain (Morpho markets)
        for e in edges:
            if e.kind == "secured_by" and e.target == asset.id:
                lend = next(n for n in nodes if n.id == e.source)
                own[lend.chain] = own.get(lend.chain, 0) + (lend.meta.get("collateral_usd") or 0)
        by_lender: dict[tuple, dict] = {}
        for r in asset.meta["posted_as_collateral"]:
            if category.get(r["project"]) not in LENDING_CATEGORIES:
                continue
            key = (r["project"], r["chain"])
            row = by_lender.setdefault(key, {"usd": 0.0, "urls": []})
            row["usd"] += r["tvl_usd"] or 0
            row["urls"].append(r["url"])
        for (project, ch), row in by_lender.items():
            if project.startswith("morpho"):  # minus the markets already drawn
                row["usd"] = max(0.0, row["usd"] - own.get(ch, 0))
        dex = asset.meta.get("dex_pools_usd") or 0.0
        exit_node = next((n for n in nodes if n.id == f"market:dex-exit-{asset.name}"), None)
        no_market = exit_node is not None and exit_node.meta.get("has_market") is False
        if not dex and not no_market:
            # DeFiLlama lists no DEX pool but a DEX route exists: depth unknown, not drawn
            asset.meta["contagion_unmeasured"] = True
            continue
        top = sorted(((k, r) for k, r in by_lender.items() if r["usd"] >= MIN_CONTAGION_USD),
                     key=lambda kr: -kr[1]["usd"])[:MAX_CONTAGION]
        for (project, ch), row in top:
            exposure = min(1.0, SHOCK * row["usd"] / dex) if dex else 1.0
            node_id = add_node(nodes, Node(
                f"lending:contagion-{project}-{ch}-{asset.name}".lower(), "lending",
                f"{project} ({ch}): {asset.name} as collateral", ch,
                {"role": "contagion", "collateral_usd": row["usd"], "dex_liquidity_usd": dex}))
            edges.append(Edge(asset.id, node_id, "also_collateral_in", round(exposure, 3),
                              f"{project} on {ch} holds {row['usd']:,.0f} USD of {asset.name} "
                              f"(DeFiLlama {', '.join(row['urls'][:2])}); liquidating {SHOCK:.0%} of "
                              f"it sells {SHOCK * row['usd']:,.0f} USD into {dex:,.0f} USD of DEX "
                              f"pools holding {asset.name}"))


def add_liquidation_exit(nodes: list[Node], edges: list[Edge], cid: int, lend_id: str,
                         m: dict, util: float, oracle_price_usd: float | None) -> None:
    """Can liquidators sell the collateral of a Morpho market? Quote selling
    what a SHOCK price drop liquidates (Morpho marketCollateralAtRisk) over
    every DEX of the chain. If the price impact eats the liquidation bonus,
    liquidators lose money, liquidations stall and lenders take bad debt.

    Exposure of the market to this exit = utilization x (impact / bonus),
    capped at utilization: the lent-out share relies on it fully when
    selling costs more than the bonus pays."""
    coll, loan = m["collateralAsset"], m["loanAsset"]
    p_coll = (coll.get("price") or {}).get("usd")
    p_loan = (loan.get("price") or {}).get("usd")
    if cid not in kyberswap.CHAINS or not p_coll or not p_loan or coll["symbol"].upper() in BASE_ASSETS:
        return
    # A PT trades in its Pendle pool, which DEX aggregators do not route through.
    pt = next((n.meta for n in nodes if n.type == "asset" and n.meta.get("pendle_market")
               and n.meta.get("address", "").lower() == coll["address"].lower()), None)
    try:
        forced = morpho.liquidated_at(morpho.collateral_at_risk(cid, m["marketId"]), 1 - SHOCK)
        spot = _impact(cid, coll, loan, SPOT_USD, p_coll, p_loan, pt)
        impact = _impact(cid, coll, loan, forced, p_coll, p_loan, pt) if forced >= SPOT_USD else None
    except Exception:
        return
    lltv = int(m["lltv"]) / 1e18
    bonus = min(1.15, 1 / (0.3 * lltv + 0.7)) - 1  # Morpho liquidation incentive factor
    # No market at all: even a small sale finds no buyer, whatever the price drop.
    no_market = spot >= NO_MARKET_IMPACT
    lend = next(n for n in nodes if n.id == lend_id)
    lend.meta.update(liquidated_at_shock_usd=forced, liquidation_bonus=bonus,
                     liquidation_price_impact=impact, collateral_has_market=not no_market)
    if no_market:
        exposure = util
    else:
        exposure = util * min(1.0, impact / bonus) if impact is not None and bonus else 0.0
    if exposure < 0.01:  # nothing to liquidate, or DEXes absorb it well within the bonus
        return
    url = (f"Pendle router quote, market {pt['pendle_market']}" if pt
           else kyberswap.route_url(cid, coll["address"], loan["address"]))
    venue = "its Pendle pool" if pt else "the best KyberSwap route"
    exit_id = f"market:dex-exit-{coll['symbol']}"
    meta = {"role": "liquidation_exit", "token": coll["address"], "sell_to": loan["symbol"],
            "dex_price_usd": None if no_market else (1 - spot) * p_coll,
            "has_market": not no_market, "flags": []}
    add_node(nodes, Node(exit_id, "market", f"DEX exit for {coll['symbol']}", chain_name(cid), meta))
    node = next(n for n in nodes if n.id == exit_id)
    node.meta.setdefault("quotes", {})[lend_id] = {"sell_usd": forced, "price_impact": impact,
                                                   "spot_impact": spot, "liquidation_bonus": bonus}
    if no_market:
        msg = f"no DEX market for {coll['symbol']}: selling even {SPOT_USD:,.0f} USD returns " \
              f"{1 - spot:.0%} of its value, so liquidators cannot sell it whatever the price " \
              f"drop and the lent-out share relies on borrowers repaying"
        if msg not in node.meta["flags"]:
            node.meta["flags"].append(msg)
    elif impact is not None and impact > bonus:
        cost = (f"no DEX route can absorb it (the best returns {1 - impact:.0%} of its value)"
                if impact > 0.5 else f"costs {impact:.1%} on DEXes")
        node.meta["flags"].append(
            f"selling the {forced:,.0f} USD of {coll['symbol']} a {SHOCK:.0%} drop liquidates "
            f"(market {m['marketId'][:10]}): {cost}, more than the {bonus:.1%} liquidation "
            f"bonus, so liquidators would not step in")
    if oracle_price_usd and node.meta["dex_price_usd"]:
        gap = oracle_price_usd / node.meta["dex_price_usd"] - 1
        node.meta["oracle_gap_to_dex"] = gap
        if abs(gap) > 0.02:
            node.meta["flags"].append(f"oracle price is {gap:+.1%} away from the DEX price")
    if no_market:
        why = (f"Selling {SPOT_USD:,.0f} USD of {coll['symbol']} for {loan['symbol']} returns "
               f"{1 - spot:.0%} of its value on {venue} (no DEX trades it): "
               f"liquidations cannot be executed, so {util:.0%} lent out relies on repayment: {url}")
    else:
        why = (f"A {SHOCK:.0%} {coll['symbol']} price drop liquidates {forced:,.0f} USD "
               f"(Morpho marketCollateralAtRisk); selling it for {loan['symbol']} costs "
               f"{impact:.1%} on {venue} vs a {bonus:.1%} liquidation bonus: {url}")
    edges.append(Edge(lend_id, exit_id, "liquidated_via", round(exposure, 3), why))


def _impact(cid: int, coll: dict, loan: dict, usd: float, p_coll: float, p_loan: float,
            pt: dict | None = None) -> float:
    """Price impact of selling `usd` worth of collateral for the loan token.
    The amount is rounded to 2 significant digits so the cached quote is
    reused while the price barely moves. A PT is quoted on its Pendle pool
    (PT -> SY, Pendle router), where liquidators would sell it."""
    tokens = float(f"{usd / p_coll:.2g}")
    if pt:
        q = pendle.sell_quote(cid, pt["pendle_market"], coll["address"], pt["pendle_sy"],
                              int(tokens * 10 ** coll["decimals"]))
        return abs(q["priceImpact"])
    q = kyberswap.sell_quote(cid, coll["address"], loan["address"], int(tokens * 10 ** coll["decimals"]))
    out = int((q or {}).get("amountOut") or 0) / 10 ** loan["decimals"]
    return max(0.0, 1 - out * p_loan / (tokens * p_coll))
