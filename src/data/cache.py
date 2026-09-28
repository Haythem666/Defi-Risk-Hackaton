"""HTTP JSON fetch with an on-disk cache in data/cache/.

Every successful response is saved. If the API is down (or DEFI_OFFLINE=1),
the last saved response is used, so the demo survives an outage.
"""

import hashlib
import json
import os
import time
from pathlib import Path

import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
TIMEOUT_S = 20


def _key(method: str, url: str, params: dict | None, body: dict | None) -> str:
    raw = json.dumps([method, url, params or {}, body or {}], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def fetch_json(url: str, params: dict | None = None, body: dict | None = None,
               max_age_s: int = 3600):
    """GET (or POST if `body` is given) and return parsed JSON.

    Uses the cache if it is fresher than `max_age_s`, if DEFI_OFFLINE=1,
    or if the request fails.
    """
    method = "POST" if body is not None else "GET"
    path = CACHE_DIR / f"{_key(method, url, params, body)}.json"
    cached = json.loads(path.read_text()) if path.exists() else None

    offline = os.environ.get("DEFI_OFFLINE") == "1"
    fresh = cached is not None and time.time() - cached["fetched_at"] < max_age_s
    if cached is not None and (offline or fresh):
        return cached["data"]

    try:
        resp = requests.request(method, url, params=params, json=body, timeout=TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        if cached is not None:
            return cached["data"]
        raise

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": time.time(), "url": url,
                                "params": params, "body": body, "data": data}))
    return data
