"""Calibrate incident probabilities and severities from historical data.

Run `python -m src.risk.calibration` to (re)build data/calibration.json.
Every number written there carries the event count, the population and the
window it comes from, so it can be checked and challenged.

Sources (public, no key):
- DeFiLlama hacks database (https://defillama.com/hacks): date, amount,
  technique and target of every recorded exploit.
- DeFiLlama protocols: category and TVL, and each protocol's TVL history
  (to know how much a protocol held just before it was hacked).
- DeFiLlama stablecoins: daily prices and circulating supply history.

Method
- Hack rate (per protocol-year) = hacks >= MIN_HACK_USD on protocols that
  held >= LARGE_TVL just before the hack, over the window, divided by the
  number of protocols holding >= LARGE_TVL today. Computed per DeFiLlama
  category when the category has enough protocols, else for all of DeFi.
  Hacks DeFiLlama could not link to a protocol are spread like the linked ones.
- Hack severity = median of (amount stolen - funds returned) / TVL just
  before the hack, over the same hacks.
- Oracle failure = same, restricted to 'Oracle Manipulation' hacks, over the
  protocols that consume prices (lending, CDP, derivatives).
- Exchange (venue) failure = CEX hacks >= 10M USD per year over exchanges
  holding >= 1B USD; severity = amount / exchange holdings before the hack.
- Stablecoin depeg = episodes where a USD stablecoin with >= 100M USD in
  circulation trades below 0.97 for at least 2 consecutive days, per
  coin-year since 2021; severity = median of the episode's worst drop.
"""

import bisect
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from src.data.cache import fetch_json

DATA = Path(__file__).resolve().parents[2] / "data"
OUT = DATA / "calibration.json"
RAW = DATA / "raw"  # bulky inputs, not committed (see .gitignore)
LLAMA = "https://api.llama.fi"
STABLES = "https://stablecoins.llama.fi"

WINDOW_YEARS = 3          # hacks: last 3 years (recent security practice)
DEPEG_SINCE = 1609459200  # 2021-01-01: depegs are rare, need a longer window
MIN_HACK_USD = 1e6
LARGE_TVL = 1e8           # the size of protocols an institutional book uses
MIN_CATEGORY_PROTOCOLS = 8
PRIOR_PROTOCOLS = 10      # category rates are pulled toward all-DeFi as if 10
                          # extra protocols had the all-DeFi rate (avoids 0% / 2-case extremes)
MIN_SEVERITY_HACKS = 3
CEX_MIN_HACK_USD = 1e7
CEX_MIN_HOLDINGS = 1e9
CEX_ALIASES = {"huobi": "htx", "binance": "binance cex", "crypto.com": "crypto-com"}
DEPEG_LEVEL, RECOVERED_LEVEL, DEPEG_MIN_DAYS = 0.97, 0.99, 2
STABLE_MIN_CIRC = 1e8
PRICE_CONSUMERS = ("Lending", "CDP", "Derivatives")


# --- data, slimmed before caching ------------------------------------------

def _hacks_slim(raw):
    keep = ("date", "name", "classification", "technique", "amount", "targetType",
            "returnedFunds", "defillamaId")
    return [{k: h.get(k) for k in keep} for h in raw]


def _protocols_slim(raw):
    keep = ("id", "slug", "name", "category", "tvl", "parentProtocol")
    return [{k: p.get(k) for k in keep} for p in raw]


def _tvl_series(raw):
    return [(pt["date"], pt["totalLiquidityUSD"]) for pt in raw.get("tvl", [])]


def _stables_slim(raw):
    keep = ("id", "symbol", "gecko_id", "pegType", "pegMechanism")
    return [{k: a.get(k) for k in keep} for a in raw["peggedAssets"]]


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _prices_since_2021(raw):
    """Daily prices since 2021; some prices come as strings or junk."""
    return [{"date": d["date"],
             "prices": {k: round(x, 4) for k, v in d["prices"].items() if (x := _num(v))}}
            for d in raw if d["date"] >= DEPEG_SINCE]


def _circ_series(raw):
    return [(int(r["date"]), (r.get("totalCirculatingUSD") or {}).get("peggedUSD") or 0)
            for r in raw]


def hacks():
    return fetch_json(f"{LLAMA}/hacks", max_age_s=7 * 86400, transform=_hacks_slim, cache_dir=RAW)


def protocols():
    return fetch_json(f"{LLAMA}/protocols", max_age_s=7 * 86400, transform=_protocols_slim,
                      cache_dir=RAW)


def tvl_history(slug: str) -> list[tuple[int, float]]:
    try:
        return fetch_json(f"{LLAMA}/protocol/{slug}", max_age_s=30 * 86400,
                          transform=_tvl_series, cache_dir=RAW)
    except Exception:
        return []


def value_before(series: list, ts: int) -> float | None:
    """Last recorded value strictly before `ts` (within 7 days)."""
    dates = [d for d, _ in series]
    i = bisect.bisect_left(dates, ts) - 1
    if i < 0 or ts - dates[i] > 7 * 86400:
        return None
    return series[i][1]


# --- hacks ------------------------------------------------------------------

def _resolver(protos):
    by_id = {str(p["id"]): p for p in protos}
    children = defaultdict(list)
    for p in protos:
        if p.get("parentProtocol"):
            children[p["parentProtocol"]].append(p)

    def resolve(hid):
        """(category, slug) of the protocol a hack points to."""
        if hid is None:
            return None, None
        hid = str(hid)
        if hid in by_id:
            return by_id[hid].get("category"), by_id[hid]["slug"]
        if hid.startswith("parent#") and children.get(hid):
            biggest = max(children[hid], key=lambda p: p.get("tvl") or 0)
            return biggest.get("category"), hid.split("#", 1)[1]
        return None, None
    return resolve


def _rate(n_events: float, years: float, population: int) -> float:
    return n_events / years / population if population else 0.0


def hack_stats(now: float | None = None) -> dict:
    now = now or time.time()
    start = now - WINDOW_YEARS * 365.25 * 86400
    protos = protocols()
    resolve = _resolver(protos)

    window = [h for h in hacks() if h["date"] >= start and (h["amount"] or 0) >= MIN_HACK_USD
              and h["targetType"] == "DeFi Protocol"]
    linked = []
    for h in window:
        cat, slug = resolve(h["defillamaId"])
        if not slug:
            continue
        tvl = value_before(tvl_history(slug), h["date"])
        net = max(0.0, (h["amount"] or 0) - (h.get("returnedFunds") or 0))
        linked.append({**h, "category": cat, "slug": slug, "tvl_before": tvl,
                       "loss_share": min(1.0, net / tvl) if tvl else None})
    unlinked_factor = len(window) / len(linked) if linked else 1.0

    large = [h for h in linked if (h["tvl_before"] or 0) >= LARGE_TVL]
    pop = Counter(p.get("category") for p in protos
                  if (p.get("tvl") or 0) >= LARGE_TVL and p.get("category") not in ("CEX", "Chain"))
    pop_all = sum(pop.values())

    def summary(events, population, label, prior_rate=None, prior_severity=None):
        sev = [h["loss_share"] for h in events if h["loss_share"] is not None]
        n = len(events) * unlinked_factor
        raw = _rate(n, WINDOW_YEARS, population)
        rate = raw
        shrink = ""
        if prior_rate is not None:
            rate = (n + PRIOR_PROTOCOLS * WINDOW_YEARS * prior_rate) / \
                (WINDOW_YEARS * (population + PRIOR_PROTOCOLS))
            shrink = (f"; raw {raw:.1%}/y pulled toward all-DeFi as if {PRIOR_PROTOCOLS} more "
                      f"protocols had the all-DeFi rate")
        severity = statistics.median(sev) if len(sev) >= MIN_SEVERITY_HACKS else prior_severity
        if prior_severity is not None and len(sev) < MIN_SEVERITY_HACKS:
            shrink += f"; fewer than {MIN_SEVERITY_HACKS} losses measured, all-DeFi severity used"
        return {
            "annual_p": rate, "annual_p_raw": raw,
            "severity": severity if severity is not None else (statistics.median(sev) if sev else None),
            "n_hacks": len(events), "n_with_severity": len(sev),
            "unlinked_factor": round(unlinked_factor, 2), "population": population,
            "years": WINDOW_YEARS,
            "rationale": (f"{len(events)} hacks >= {MIN_HACK_USD / 1e6:.0f}M USD on {label} "
                          f"holding >= {LARGE_TVL / 1e6:.0f}M USD, last {WINDOW_YEARS}y "
                          f"(x{unlinked_factor:.2f} for hacks DeFiLlama did not link), over "
                          f"{population} such protocols today; severity = median loss / TVL "
                          f"before the hack over {len(sev)} hacks (DeFiLlama hacks + TVL history)"
                          f"{shrink}"),
            "examples": [f"{h['name']} {time.strftime('%Y-%m', time.gmtime(h['date']))} "
                         f"{(h['amount'] or 0) / 1e6:.0f}M" for h in
                         sorted(events, key=lambda h: -(h["amount"] or 0))[:3]],
        }

    out = {"_all": summary(large, pop_all, "DeFi protocols")}
    base_p, base_sev = out["_all"]["annual_p"], out["_all"]["severity"]
    by_cat = defaultdict(list)
    for h in large:
        by_cat[h["category"]].append(h)
    for cat, n_protocols in pop.items():
        if n_protocols >= MIN_CATEGORY_PROTOCOLS:
            out[cat] = summary(by_cat.get(cat, []), n_protocols, f"{cat} protocols",
                               base_p, base_sev)

    oracle = [h for h in large if h["classification"] == "Oracle Manipulation"]
    consumers = sum(pop.get(c, 0) for c in PRICE_CONSUMERS)
    out["_oracle"] = summary(oracle, consumers, "price-consuming protocols (oracle manipulation)",
                             None, base_sev)
    return out


def cex_stats(now: float | None = None) -> dict:
    now = now or time.time()
    start = now - WINDOW_YEARS * 365.25 * 86400
    protos = protocols()
    cexes = [p for p in protos if p.get("category") == "CEX"]
    big = {p["name"].lower(): p for p in cexes if (p.get("tvl") or 0) >= CEX_MIN_HOLDINGS}

    def big_exchange(h):
        name = h["name"].split(":")[0].strip().lower()
        return big.get(CEX_ALIASES.get(name, name))

    # Only hacks on the large exchanges, so numerator and population match.
    events = [h for h in hacks() if h["date"] >= start and h["targetType"] == "CEX"
              and (h["amount"] or 0) >= CEX_MIN_HACK_USD and big_exchange(h)]
    sev = []
    for h in events:
        p = big_exchange(h)
        tvl = value_before(tvl_history(p["slug"]), h["date"])
        if tvl:
            sev.append(min(1.0, h["amount"] / tvl))
    return {
        "annual_p": _rate(len(events), WINDOW_YEARS, len(big)),
        "severity": statistics.median(sev) if sev else None,
        "n_hacks": len(events), "n_with_severity": len(sev), "population": len(big),
        "years": WINDOW_YEARS,
        "rationale": (f"{len(events)} hacks >= {CEX_MIN_HACK_USD / 1e6:.0f}M USD on the "
                      f"{len(big)} exchanges holding >= {CEX_MIN_HOLDINGS / 1e9:.0f}B USD, last "
                      f"{WINDOW_YEARS}y, over those "
                      f"exchanges; severity = median hack / exchange "
                      f"holdings before it over {len(sev)} hacks (upper bound: exchanges often "
                      f"cover customers, e.g. Bybit 2025)"),
        "examples": [f"{h['name']} {time.strftime('%Y-%m', time.gmtime(h['date']))} "
                     f"{h['amount'] / 1e6:.0f}M" for h in sorted(events, key=lambda h: -h["amount"])[:3]],
    }


# --- stablecoin depegs -------------------------------------------------------

def depeg_stats() -> dict:
    coins = [a for a in fetch_json(f"{STABLES}/stablecoins", max_age_s=7 * 86400,
                                   transform=_stables_slim, cache_dir=RAW)
             if a["pegType"] == "peggedUSD" and a.get("gecko_id")]
    prices = defaultdict(list)
    for day in fetch_json(f"{STABLES}/stablecoinprices", max_age_s=7 * 86400,
                          transform=_prices_since_2021, cache_dir=RAW):
        if day["date"] < DEPEG_SINCE:
            continue
        for gid, px in day["prices"].items():
            if px:
                prices[gid].append((day["date"], px))

    episodes, coin_years = [], 0.0
    years_by_mech: dict = defaultdict(float)
    symbols = {}
    for a in coins:
        series = sorted(prices.get(a["gecko_id"], []))
        if len(series) < 60:
            continue
        circ = fetch_json(f"{STABLES}/stablecoincharts/all", params={"stablecoin": a["id"]},
                          max_age_s=30 * 86400, transform=_circ_series, cache_dir=RAW)
        if not circ or max(v for _, v in circ) < STABLE_MIN_CIRC:
            continue
        circ_dates = [d for d, _ in circ]

        def big_on(ts):
            i = bisect.bisect_right(circ_dates, ts) - 1
            return i >= 0 and circ[i][1] >= STABLE_MIN_CIRC

        days = [(d, px) for d, px in series if big_on(d)]
        coin_years += len(days) / 365.25
        years_by_mech[a.get("pegMechanism")] += len(days) / 365.25
        symbols[a["symbol"].upper()] = {"mechanism": a.get("pegMechanism"),
                                        "coin_years": round(len(days) / 365.25, 2),
                                        "n_episodes": 0}
        i = 0
        while i < len(days):
            if days[i][1] < DEPEG_LEVEL:
                j, low = i, days[i][1]
                while j < len(days) and days[j][1] < RECOVERED_LEVEL:
                    low = min(low, days[j][1])
                    j += 1
                below = sum(1 for _, px in days[i:j] if px < DEPEG_LEVEL)
                if below >= DEPEG_MIN_DAYS:
                    symbols[a["symbol"].upper()]["n_episodes"] += 1
                    episodes.append({"coin": a["symbol"], "mechanism": a.get("pegMechanism"),
                                     "start": time.strftime("%Y-%m-%d", time.gmtime(days[i][0])),
                                     "worst_drop": round(1 - low, 3), "days": j - i,
                                     "recovered": j < len(days)})
                i = max(j, i + 1)
            else:
                i += 1

    drops = [e["worst_drop"] for e in episodes]
    by_mech = Counter(e["mechanism"] for e in episodes)
    per_mechanism = {}
    for mech, years in years_by_mech.items():
        mech_drops = [e["worst_drop"] for e in episodes if e["mechanism"] == mech]
        per_mechanism[mech] = {
            "annual_p": by_mech.get(mech, 0) / years if years else 0.0,
            "severity": statistics.median(mech_drops) if len(mech_drops) >= 3 else
            (statistics.median(drops) if drops else None),
            "n_episodes": by_mech.get(mech, 0), "coin_years": round(years, 1),
            "rationale": (f"{by_mech.get(mech, 0)} depeg episodes (< {DEPEG_LEVEL} for >= "
                          f"{DEPEG_MIN_DAYS} days) of {mech} USD stablecoins with >= "
                          f"{STABLE_MIN_CIRC / 1e6:.0f}M USD in circulation, over {years:.0f} "
                          f"coin-years since 2021; severity = median worst drop"
                          + ("" if len(mech_drops) >= 3 else " (all stablecoins: < 3 episodes)")
                          + " (DeFiLlama stablecoin prices + circulating history)"),
            "examples": [f"{e['coin']} {e['start']} -{e['worst_drop']:.0%}" for e in
                         sorted([e for e in episodes if e["mechanism"] == mech],
                                key=lambda e: -e["worst_drop"])[:3]],
        }
    return {
        "per_mechanism": per_mechanism, "symbols": symbols,
        "annual_p": len(episodes) / coin_years if coin_years else 0.0,
        "severity": statistics.median(drops) if drops else None,
        "severity_mean": statistics.mean(drops) if drops else None,
        "n_episodes": len(episodes), "coin_years": round(coin_years, 1),
        "never_recovered": [e for e in episodes if not e["recovered"]],
        "by_mechanism": dict(by_mech),
        "rationale": (f"{len(episodes)} episodes of a USD stablecoin with >= "
                      f"{STABLE_MIN_CIRC / 1e6:.0f}M USD in circulation trading below "
                      f"{DEPEG_LEVEL} for >= {DEPEG_MIN_DAYS} days, over {coin_years:.0f} "
                      f"coin-years since 2021; severity = median worst drop "
                      f"(DeFiLlama stablecoin prices + circulating history)"),
        "worst": sorted(episodes, key=lambda e: -e["worst_drop"])[:5],
    }


def calibrate() -> dict:
    now = time.time()
    return {"generated_at": time.strftime("%Y-%m-%d", time.gmtime(now)),
            "hacks": hack_stats(now), "cex": cex_stats(now), "depeg_usd": depeg_stats()}


if __name__ == "__main__":
    result = calibrate()
    OUT.write_text(json.dumps(result, indent=1))
    print(json.dumps({k: v for k, v in result["hacks"].items()
                      if k in ("_all", "_oracle", "Lending", "Liquid Staking", "Basis Trading")},
                     indent=1)[:3000])
    print(json.dumps({k: result[k] for k in ("cex", "depeg_usd")}, indent=1)[:3000])
