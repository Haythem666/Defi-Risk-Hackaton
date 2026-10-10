"""HTTP JSON fetch with an on-disk cache in data/cache/.

Every successful response is saved. If the API is down (or DEFI_OFFLINE=1),
the last saved response is used, so the demo survives an outage.
"""

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path

import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
TIMEOUT_S = 20

# Every call is logged (logger "defi.api") and kept in CALLS, so the app and
# `python -m src.trace` can show which API was asked what, and what it said.
log = logging.getLogger("defi.api")
CALLS: list[dict] = []


def _api(url: str) -> str:
    host = re.sub(r"^https?://", "", url).split("/")[0]
    for name in ("morpho", "pendle", "aave", "llama", "ethena", "hyperliquid", "sourcify",
                 "blockscout"):
        if name in host:
            return {"llama": "defillama"}.get(name, name)
    return "rpc" if "rpc" in host or "publicnode" in host else host


def _question(url: str, params: dict | None, body) -> str:
    """Short human-readable form of the request."""
    if isinstance(body, dict) and "query" in body:  # GraphQL: the field asked + its variables
        m = re.search(r"\{\s*(\w+)", body["query"].split(")", 1)[-1] if "query(" in body["query"]
                      else body["query"])
        return f"{m.group(1) if m else 'query'} {json.dumps(body.get('variables') or {})}"
    if isinstance(body, list):  # JSON-RPC batch
        return f"{len(body)} RPC calls ({', '.join(sorted({c['method'] for c in body}))})"
    if isinstance(body, dict) and "method" in body:
        return f"{body['method']} {json.dumps(body.get('params'))[:120]}"
    return url.split("?")[0] + (f" {json.dumps(params)}" if params else "")


def _preview(data, limit: int = 300) -> str:
    text = json.dumps(data)
    return text if len(text) <= limit else text[:limit] + f"... ({len(text):,} chars)"


def _record(url, params, body, source, path, data, t0):
    call = {"api": _api(url), "question": _question(url, params, body), "source": source,
            "ms": round((time.time() - t0) * 1000), "answer": _preview(data),
            "cache_file": os.path.relpath(path, CACHE_DIR.parents[1])}
    CALLS.append(call)
    log.info("[%s] %s <- %s (%d ms): %s", call["api"], call["question"], source,
             call["ms"], call["answer"])


def _key(method: str, url: str, params: dict | None, body: dict | None) -> str:
    raw = json.dumps([method, url, params or {}, body or {}], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def fetch_json(url: str, params: dict | None = None, body: dict | None = None,
               max_age_s: int = 3600, transform=None, cache_dir: Path | None = None):
    """GET (or POST if `body` is given) and return parsed JSON.

    Uses the cache if it is fresher than `max_age_s`, if DEFI_OFFLINE=1,
    or if the request fails. `transform` (optional) slims the response
    before it is cached, for large payloads. `cache_dir` overrides where
    the response is saved (bulky inputs that the demo does not need).
    """
    method = "POST" if body is not None else "GET"
    key = _key(method, url, params, body)
    if transform is not None:
        key += f"-{transform.__name__}"
    path = (cache_dir or CACHE_DIR) / f"{key}.json"
    cached = json.loads(path.read_text()) if path.exists() else None

    offline = os.environ.get("DEFI_OFFLINE") == "1"
    fresh = cached is not None and time.time() - cached["fetched_at"] < max_age_s
    t0 = time.time()
    if cached is not None and (offline or fresh):
        _record(url, params, body, "cache", path, cached["data"], t0)
        return cached["data"]

    try:
        resp = requests.request(method, url, params=params, json=body, timeout=TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        if transform is not None:
            data = transform(data)
    except (requests.RequestException, ValueError):
        if cached is not None:
            _record(url, params, body, "cache (API down)", path, cached["data"], t0)
            return cached["data"]
        raise

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": time.time(), "url": url,
                                "params": params, "body": body, "data": data}))
    _record(url, params, body, "live", path, data, t0)
    return data
