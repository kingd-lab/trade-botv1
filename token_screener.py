#!/usr/bin/env python3
"""Paper-trading candidate discovery. No trading or wallet access."""

import time
import requests
from datetime import datetime, timezone


# ============================================================
# CONFIG
# ============================================================

CHAIN = "solana"

# Risk-first paper strategy filters
MIN_LIQUIDITY_USD = 50_000
MIN_VOLUME_24H_USD = 250_000
MIN_AGE_HOURS = 2
MAX_AGE_HOURS = 72
MIN_PRICE_CHANGE_1H = 2.0

MAX_RESULTS = 25
REQUEST_DELAY_SEC = 0.3

# Safety filters
ENABLE_SAFETY_CHECKS = True
REQUIRE_MINT_AUTHORITY_REVOKED = True
REQUIRE_FREEZE_AUTHORITY_REVOKED = True
MAX_TOP10_HOLDER_PCT = 60
MAX_RUGCHECK_SCORE = 60
REJECT_IF_MARKED_RUGGED = True

DEXSCREENER_BASE = "https://api.dexscreener.com"
RUGCHECK_BASE = "https://api.rugcheck.xyz/v1"


# ============================================================
# DATA FETCHING
# ============================================================

def get_latest_boosted_tokens():
    r = requests.get(
        f"{DEXSCREENER_BASE}/token-boosts/latest/v1",
        timeout=10,
    )
    r.raise_for_status()

    data = r.json()
    return data if isinstance(data, list) else []


def get_top_boosted_tokens():
    r = requests.get(
        f"{DEXSCREENER_BASE}/token-boosts/top/v1",
        timeout=10,
    )
    r.raise_for_status()

    data = r.json()
    return data if isinstance(data, list) else []


def search_pairs(query):
    """Search DexScreener for non-boosted pairs."""
    r = requests.get(
        f"{DEXSCREENER_BASE}/latest/dex/search",
        params={"q": query},
        timeout=10,
    )
    r.raise_for_status()

    return r.json().get("pairs", []) or []


def get_pairs_for_token(chain_id, token_address):
    """Get all pairs for a token."""
    r = requests.get(
        f"{DEXSCREENER_BASE}/token-pairs/v1/{chain_id}/{token_address}",
        timeout=10,
    )

    if r.status_code != 200:
        return []

    data = r.json()
    return data if isinstance(data, list) else []


def get_rugcheck_report(mint_address):
    """Get RugCheck safety information.

    Failure is treated as unsafe rather than safe.
    """
    try:
        r = requests.get(
            f"{RUGCHECK_BASE}/tokens/{mint_address}/report",
            timeout=10,
        )

        if r.status_code != 200:
            return None

        return r.json()

    except requests.RequestException:
        return None


# ============================================================
# SAFETY DATA
# ============================================================

def summarize_safety(report):
    if report is None:
        return None

    top_holders = report.get("topHolders") or []

    return {
        "mint_authority_active": (
            report.get("mintAuthority") is not None
        ),

        "freeze_authority_active": (
            report.get("freezeAuthority") is not None
        ),

        "rugged": bool(
            report.get("rugged", False)
        ),

        "risk_score": report.get(
            "score_normalised",
            report.get("score"),
        ),

        "top10_holder_pct": (
            sum(
                h.get("pct", 0)
                for h in top_holders[:10]
            )
            if top_holders
            else None
        ),

        "risk_flags": [
            r.get("name")
            for r in (report.get("risks") or [])
        ],
    }


# ============================================================
# PAIR METRICS
# ============================================================

def pair_age_hours(pair):
    created_ms = pair.get("pairCreatedAt")

    if not created_ms:
        return None

    try:
        created = datetime.fromtimestamp(
            created_ms / 1000,
            tz=timezone.utc,
        )

        return (
            datetime.now(timezone.utc) - created
        ).total_seconds() / 3600

    except (ValueError, TypeError, OverflowError):
        return None


def passes_filters(pair):
    """Apply basic market filters."""

    liquidity = (
        pair.get("liquidity") or {}
    ).get("usd") or 0

    volume_24h = (
        pair.get("volume") or {}
    ).get("h24") or 0

    change_1h = (
        pair.get("priceChange") or {}
    ).get("h1")

    age = pair_age_hours(pair)

    if liquidity < MIN_LIQUIDITY_USD:
        return False

    if volume_24h < MIN_VOLUME_24H_USD:
        return False

    if (
        change_1h is not None
        and change_1h < MIN_PRICE_CHANGE_1H
    ):
        return False

    if age is not None:
        if age < MIN_AGE_HOURS:
            return False

        if age > MAX_AGE_HOURS:
            return False

    if pair.get("priceUsd") is None:
        return False

    return True


def passes_safety_checks(safety):
    """Apply RugCheck safety filters.

    Missing safety information fails closed.
    """

    if safety is None:
        return False

    if (
        REJECT_IF_MARKED_RUGGED
        and safety["rugged"]
    ):
        return False

    if (
        REQUIRE_MINT_AUTHORITY_REVOKED
        and safety["mint_authority_active"]
    ):
        return False

    if (
        REQUIRE_FREEZE_AUTHORITY_REVOKED
        and safety["freeze_authority_active"]
    ):
        return False

    if (
        safety["top10_holder_pct"] is not None
        and safety["top10_holder_pct"]
        > MAX_TOP10_HOLDER_PCT
    ):
        return False

    if (
        safety["risk_score"] is not None
        and safety["risk_score"]
        > MAX_RUGCHECK_SCORE
    ):
        return False

    return True


# ============================================================
# SCORING
# ============================================================

def score(pair):
    """Heuristic ranking only.

    This is NOT a prediction.
    """

    liquidity = (
        pair.get("liquidity") or {}
    ).get("usd") or 1

    volume_24h = (
        pair.get("volume") or {}
    ).get("h24") or 0

    change_1h = (
        pair.get("priceChange") or {}
    ).get("h1") or 0

    turnover = min(
        volume_24h / liquidity,
        10,
    )

    return turnover + (
        change_1h / 100
    )


# ============================================================
# DIAGNOSTIC HELPERS
# ============================================================

def print_filter_config():
    print(
        "[diagnostic] filters: "
        f"liquidity >= ${MIN_LIQUIDITY_USD:,.0f}, "
        f"volume24h >= ${MIN_VOLUME_24H_USD:,.0f}, "
        f"age {MIN_AGE_HOURS}-{MAX_AGE_HOURS}h, "
        f"1h change >= {MIN_PRICE_CHANGE_1H}%"
    )

    print(
        "[diagnostic] safety: "
        f"mint_revoked={REQUIRE_MINT_AUTHORITY_REVOKED}, "
        f"freeze_revoked={REQUIRE_FREEZE_AUTHORITY_REVOKED}, "
        f"top10 <= {MAX_TOP10_HOLDER_PCT}%, "
        f"risk <= {MAX_RUGCHECK_SCORE}"
    )


# ============================================================
# DISCOVERY PIPELINE
# ============================================================

def discover_candidates():

    seen_addresses = set()
    candidates = []

    stats = {
        "boosted_tokens": 0,
        "search_pairs": 0,
        "unique_tokens": 0,
        "pairs_checked": 0,
        "passed_basic_filters": 0,
        "safety_checked": 0,
        "passed_safety": 0,
    }

    print_filter_config()

    # --------------------------------------------------------
    # Boosted sources
    # --------------------------------------------------------

    sources = []

    try:
        latest = get_latest_boosted_tokens()
        sources.extend(latest)

    except requests.RequestException as e:
        print(
            f"[warn] latest boosted source failed: {e}"
        )

    try:
        top = get_top_boosted_tokens()
        sources.extend(top)

    except requests.RequestException as e:
        print(
            f"[warn] top boosted source failed: {e}"
        )

    boosted_sources = [
        token
        for token in sources
        if token.get("chainId") == CHAIN
    ]

    stats["boosted_tokens"] = len(
        boosted_sources
    )

    # --------------------------------------------------------
    # Non-boosted search source
    # --------------------------------------------------------

    try:
        search_results = search_pairs("SOL")

        stats["search_pairs"] = len(
            [
                p
                for p in search_results
                if p.get("chainId") == CHAIN
            ]
        )

        for pair in search_results:

            if pair.get("chainId") != CHAIN:
                continue

            address = (
                pair.get("baseToken") or {}
            ).get("address")

            if not address:
                continue

            sources.append(
                {
                    "chainId": CHAIN,
                    "tokenAddress": address,
                }
            )

    except requests.RequestException as e:
        print(
            f"[warn] non-boosted search failed: {e}"
        )

    # --------------------------------------------------------
    # Fetch token pairs
    # --------------------------------------------------------

    for token in sources:

        if token.get("chainId") != CHAIN:
            continue

        address = token.get("tokenAddress")

        if not address:
            continue

        if address in seen_addresses:
            continue

        seen_addresses.add(address)

        stats["unique_tokens"] += 1

        time.sleep(REQUEST_DELAY_SEC)

        try:
            pairs = get_pairs_for_token(
                CHAIN,
                address,
            )

        except requests.RequestException as e:
            print(
                f"[warn] pair lookup failed "
                f"for {address}: {e}"
            )
            continue

        for pair in pairs:

            stats["pairs_checked"] += 1

            if passes_filters(pair):

                stats["passed_basic_filters"] += 1

                candidates.append(pair)

    # --------------------------------------------------------
    # Diagnostic output
    # --------------------------------------------------------

    print(
        "[diagnostic] "
        f"boosted={stats['boosted_tokens']} "
        f"search_pairs={stats['search_pairs']} "
        f"unique_tokens={stats['unique_tokens']} "
        f"pairs_checked={stats['pairs_checked']} "
        f"basic_pass={stats['passed_basic_filters']}"
    )

    # --------------------------------------------------------
    # Deduplicate pairs
    # --------------------------------------------------------

    unique_pairs = {}

    for pair in candidates:

        key = (
            pair.get("pairAddress")
            or (
                f"{pair.get('baseToken', {}).get('address')}:"
                f"{pair.get('quoteToken', {}).get('address')}"
            )
        )

        unique_pairs[key] = pair

    candidates = list(
        unique_pairs.values()
    )

    # --------------------------------------------------------
    # Rank candidates
    # --------------------------------------------------------

    candidates.sort(
        key=score,
        reverse=True,
    )

    candidates = candidates[
        :MAX_RESULTS * 2
    ]

    # --------------------------------------------------------
    # Safety checks
    # --------------------------------------------------------

    if (
        not ENABLE_SAFETY_CHECKS
        or CHAIN != "solana"
    ):
        print(
            "[diagnostic] safety checks disabled; "
            f"returning {len(candidates[:MAX_RESULTS])} candidates"
        )

        return candidates[:MAX_RESULTS]

    safe_candidates = []

    for pair in candidates:

        mint = (
            pair.get("baseToken") or {}
        ).get("address")

        if not mint:
            continue

        stats["safety_checked"] += 1

        time.sleep(REQUEST_DELAY_SEC)

        try:
            report = get_rugcheck_report(
                mint
            )

            safety = summarize_safety(
                report
            )

        except Exception as e:
            print(
                f"[warn] safety lookup failed "
                f"for {mint}: {e}"
            )
            continue

        if passes_safety_checks(safety):

            pair["_safety"] = safety

            safe_candidates.append(pair)

            stats["passed_safety"] += 1

        if len(safe_candidates) >= MAX_RESULTS:
            break

    # --------------------------------------------------------
    # Final diagnostic
    # --------------------------------------------------------

    print(
        "[diagnostic] "
        f"safety_checked={stats['safety_checked']} "
        f"safety_pass={stats['passed_safety']}"
    )

    return safe_candidates


# ============================================================
# OUTPUT
# ============================================================

def fmt_usd(value):
    if value is None:
        return "-"

    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"

    if value >= 1_000:
        return f"${value / 1_000:.1f}K"

    return f"${value:.2f}"


def print_report(candidates):

    if not candidates:

        print(
            "No tokens passed the current filters."
        )

        return

    print(
        f"\n{'SYMBOL':<10}"
        f"{'PRICE':<12}"
        f"{'1H %':<8}"
        f"{'24H %':<8}"
        f"{'LIQ':<10}"
        f"{'VOL24H':<10}"
        f"{'AGE(h)':<8}"
        f"{'TOP10%':<8}"
        f"{'RISK':<8}"
        f"URL"
    )

    print("-" * 130)

    for pair in candidates:

        base = pair.get(
            "baseToken",
            {},
        )

        symbol = (
            base.get("symbol", "?")
        )[:9]

        price = pair.get(
            "priceUsd",
            "-",
        )

        change_1h = (
            pair.get("priceChange") or {}
        ).get("h1")

        change_24h = (
            pair.get("priceChange") or {}
        ).get("h24")

        liquidity = (
            pair.get("liquidity") or {}
        ).get("usd")

        volume = (
            pair.get("volume") or {}
        ).get("h24")

        age = pair_age_hours(pair)

        url = pair.get(
            "url",
            "",
        )

        safety = pair.get(
            "_safety"
        ) or {}

        top10 = safety.get(
            "top10_holder_pct"
        )

        risk = safety.get(
            "risk_score"
        )

        print(
            f"{symbol:<10}"
            f"${price:<11}"
            f"{f'{change_1h:.1f}' if change_1h is not None else '-':<8}"
            f"{f'{change_24h:.1f}' if change_24h is not None else '-':<8}"
            f"{fmt_usd(liquidity):<10}"
            f"{fmt_usd(volume):<10}"
            f"{f'{age:.1f}' if age is not None else '-':<8}"
            f"{f'{top10:.0f}' if top10 is not None else '-':<8}"
            f"{f'{risk:.0f}' if risk is not None else '-':<8}"
            f"{url}"
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    results = discover_candidates()

    print(
        f"[result] {len(results)} candidates "
        "passed paper-strategy filters."
    )

    print_report(results)
