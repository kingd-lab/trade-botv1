#!/usr/bin/env python3
"""Paper-trading candidate discovery. No trading or wallet access."""
import time
import requests
from datetime import datetime, timezone

CHAIN = "solana"
MIN_LIQUIDITY_USD = 50_000
MIN_VOLUME_24H_USD = 250_000
MIN_AGE_HOURS = 2
MAX_AGE_HOURS = 72
MIN_PRICE_CHANGE_1H = 2.0
MAX_RESULTS = 25
REQUEST_DELAY_SEC = 0.3

ENABLE_SAFETY_CHECKS = True
REQUIRE_MINT_AUTHORITY_REVOKED = True
REQUIRE_FREEZE_AUTHORITY_REVOKED = True
MAX_TOP10_HOLDER_PCT = 60
MAX_RUGCHECK_SCORE = 60
REJECT_IF_MARKED_RUGGED = True

DEXSCREENER_BASE = "https://api.dexscreener.com"
RUGCHECK_BASE = "https://api.rugcheck.xyz/v1"


def get_latest_boosted_tokens():
    r = requests.get(f"{DEXSCREENER_BASE}/token-boosts/latest/v1", timeout=10)
    r.raise_for_status()
    return r.json() if isinstance(r.json(), list) else []


def get_top_boosted_tokens():
    r = requests.get(f"{DEXSCREENER_BASE}/token-boosts/top/v1", timeout=10)
    r.raise_for_status()
    return r.json() if isinstance(r.json(), list) else []


def search_pairs(query):
    r = requests.get(f"{DEXSCREENER_BASE}/latest/dex/search", params={"q": query}, timeout=10)
    r.raise_for_status()
    return r.json().get("pairs", []) or []


def get_pairs_for_token(chain_id, token_address):
    r = requests.get(f"{DEXSCREENER_BASE}/token-pairs/v1/{chain_id}/{token_address}", timeout=10)
    return r.json() if r.status_code == 200 else []


def get_rugcheck_report(mint_address):
    try:
        r = requests.get(f"{RUGCHECK_BASE}/tokens/{mint_address}/report", timeout=10)
        return r.json() if r.status_code == 200 else None
    except requests.RequestException:
        return None


def summarize_safety(report):
    if report is None:
        return None
    top = report.get("topHolders") or []
    return {
        "mint_authority_active": report.get("mintAuthority") is not None,
        "freeze_authority_active": report.get("freezeAuthority") is not None,
        "rugged": bool(report.get("rugged", False)),
        "risk_score": report.get("score_normalised", report.get("score")),
        "top10_holder_pct": sum(h.get("pct", 0) for h in top[:10]) if top else None,
        "risk_flags": [r.get("name") for r in (report.get("risks") or [])],
    }


def pair_age_hours(pair):
    created_ms = pair.get("pairCreatedAt")
    if not created_ms:
        return None
    created = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds() / 3600


def passes_filters(pair):
    liq = (pair.get("liquidity") or {}).get("usd") or 0
    vol = (pair.get("volume") or {}).get("h24") or 0
    chg = (pair.get("priceChange") or {}).get("h1")
    age = pair_age_hours(pair)
    return (
        liq >= MIN_LIQUIDITY_USD
        and vol >= MIN_VOLUME_24H_USD
        and (chg is None or chg >= MIN_PRICE_CHANGE_1H)
        and (age is None or (MIN_AGE_HOURS <= age <= MAX_AGE_HOURS))
        and pair.get("priceUsd") is not None
    )


def passes_safety_checks(safety):
    if safety is None:
        return False
    if REJECT_IF_MARKED_RUGGED and safety["rugged"]:
        return False
    if REQUIRE_MINT_AUTHORITY_REVOKED and safety["mint_authority_active"]:
        return False
    if REQUIRE_FREEZE_AUTHORITY_REVOKED and safety["freeze_authority_active"]:
        return False
    if safety["top10_holder_pct"] is not None and safety["top10_holder_pct"] > MAX_TOP10_HOLDER_PCT:
        return False
    if safety["risk_score"] is not None and safety["risk_score"] > MAX_RUGCHECK_SCORE:
        return False
    return True


def score(pair):
    liq = (pair.get("liquidity") or {}).get("usd") or 1
    vol = (pair.get("volume") or {}).get("h24") or 0
    chg = (pair.get("priceChange") or {}).get("h1") or 0
    turnover = min(vol / liq, 10)
    return turnover + chg / 100


def discover_candidates():
    seen = set()
    candidates = []
    sources = []
    for fn in (get_latest_boosted_tokens, get_top_boosted_tokens):
        try:
            sources.extend(fn())
        except requests.RequestException as e:
            print(f"[warn] discovery source failed: {e}")

    # Add a small non-boosted search source to reduce dependence on paid boosts.
    try:
        sources.extend({
            "chainId": p.get("chainId"),
            "tokenAddress": (p.get("baseToken") or {}).get("address"),
        } for p in search_pairs("SOL") if p.get("chainId") == CHAIN)
    except requests.RequestException as e:
        print(f"[warn] search source failed: {e}")

    for token in sources:
        if token.get("chainId") != CHAIN:
            continue
        address = token.get("tokenAddress")
        if not address or address in seen:
            continue
        seen.add(address)
        time.sleep(REQUEST_DELAY_SEC)
        for pair in get_pairs_for_token(CHAIN, address):
            if passes_filters(pair):
                candidates.append(pair)

    # Deduplicate by pair address before ranking.
    unique = {}
    for pair in candidates:
        key = pair.get("pairAddress") or f"{pair.get('baseToken', {}).get('address')}:{pair.get('quoteToken', {}).get('address')}"
        unique[key] = pair
    candidates = sorted(unique.values(), key=score, reverse=True)[:MAX_RESULTS * 2]

    if not ENABLE_SAFETY_CHECKS or CHAIN != "solana":
        return candidates[:MAX_RESULTS]

    safe = []
    for pair in candidates:
        mint = pair.get("baseToken", {}).get("address")
        if not mint:
            continue
        time.sleep(REQUEST_DELAY_SEC)
        safety = summarize_safety(get_rugcheck_report(mint))
        if passes_safety_checks(safety):
            pair["_safety"] = safety
            safe.append(pair)
        if len(safe) >= MAX_RESULTS:
            break
    return safe


if __name__ == "__main__":
    results = discover_candidates()
    print(f"{len(results)} candidates passed paper-strategy filters.")
    for p in results:
        print(p.get("baseToken", {}).get("symbol"), p.get("priceUsd"), p.get("url"))
