"""Show what each API is asked and what it answers while a graph is built.

    python -m src.trace morpho_vault 1 0xD6d4b804014EF27836dBe9f8f6Bf6c71251548Ec
    python -m src.trace morpho_vault 1 0xD6d4... --api morpho      # only Morpho calls
    python -m src.trace morpho_vault 1 0xD6d4... --api morpho --full  # whole answers

Each line: which API, what was asked, whether the answer came live or from
data/cache/, and the start of the answer. The full answer is in the cache
file named on the line. Then the edges the graph was built from.
"""

import argparse
import json
from pathlib import Path

from src.data import cache
from src.graph.build import build_graph
from src.schemas import Position

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("kind", help="morpho_vault, morpho_supply, aave_supply, pendle_pt, ...")
    ap.add_argument("chain_id", type=int)
    ap.add_argument("address")
    ap.add_argument("--asset", help="asset address (aave_supply only)")
    ap.add_argument("--api", help="only show calls to this API (morpho, defillama, rpc, ...)")
    ap.add_argument("--full", action="store_true", help="print each whole answer")
    a = ap.parse_args()

    cache.CALLS.clear()
    g = build_graph(Position(a.chain_id, a.address, 1e6, kind=a.kind, asset_address=a.asset))

    calls = [c for c in cache.CALLS if not a.api or c["api"] == a.api]
    print(f"\n=== {len(calls)} API calls" + (f" to {a.api}" if a.api else "")
          + f" (of {len(cache.CALLS)} in total) ===")
    for i, c in enumerate(calls, 1):
        print(f"\n[{i}] {c['api'].upper()}  {c['question']}")
        print(f"    from {c['source']} in {c['ms']} ms, saved in {c['cache_file']}")
        if a.full:
            data = json.loads((ROOT / c["cache_file"]).read_text())["data"]
            print("    " + json.dumps(data, indent=2).replace("\n", "\n    "))
        else:
            print(f"    -> {c['answer']}")

    names = {n.id: n.name for n in g.nodes}
    print(f"\n=== Graph: {len(g.nodes)} nodes, {len(g.edges)} edges ===")
    for e in g.edges:
        print(f"{names[e.source]:<40} --{e.kind} {e.exposure:.0%}--> {names[e.target]}")


if __name__ == "__main__":
    main()
