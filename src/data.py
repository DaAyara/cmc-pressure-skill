"""
src/data.py

Fetches live market data from the CoinMarketCap (CMC) API and derives the
two inputs the confluence engine needs:
  1. ETF / institutional flow pressure
  2. Derivatives positioning pressure

IMPORTANT — DATA HONESTY NOTE
------------------------------
CMC's direct ETF net-flow endpoint and per-exchange funding-rate /
open-interest endpoints are gated behind the Pro / Agent Hub tier and
were not available for this build (free Basic tier only, see README
for upgrade path).

This module is explicit about that gap rather than faking it:

- ETF flow is PROXIED from total market cap % change (24h), scaled to a
  dollar estimate. This is a reasonable directional proxy for net capital
  flow but is NOT a real ETF flow figure.
- Derivatives positioning uses `derivatives_volume_24h` and
  `derivatives_24h_percentage_change`, which ARE real fields returned by
  CMC's /v1/global-metrics/quotes/latest endpoint (confirmed in basic
  tier response). This is real derivatives market activity data, not a
  synthetic guess — but it is volume/activity, not funding rate or open
  interest, so it's treated as a fallback signal in confluence.py
  (see score_derivatives_pressure's fallback branch).

Every value returned by this module is labeled with `data_source` so
downstream consumers (skill.py, the printed report) can be transparent
about what's real vs. estimated.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

CMC_API_KEY = os.getenv("CMC_API_KEY")
BASE_URL = "https://pro-api.coinmarketcap.com"

HEADERS = {
    "Accepts": "application/json",
    "X-CMC_PRO_API_KEY": CMC_API_KEY,
}


class DataFetchError(Exception):
    """Raised when CMC API data cannot be retrieved."""


def get_global_metrics() -> dict:
    """
    Fetches global crypto market metrics from CMC.
    This is the single real endpoint this project uses (free Basic tier).
    Returns the raw `data` payload from CMC, or {} on failure.
    """
    if not CMC_API_KEY:
        print("[data.py] WARNING: CMC_API_KEY not set. Check your .env file.")
        return {}

    url = f"{BASE_URL}/v1/global-metrics/quotes/latest"
    params = {"convert": "USD"}

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("data", {})
    except requests.exceptions.RequestException as e:
        print(f"[data.py] Error fetching global metrics: {e}")
        return {}


def get_fear_and_greed(global_data: dict) -> dict:
    """
    CMC's free global-metrics endpoint does not include Fear & Greed
    directly (that's a separate endpoint, also Pro-gated in some plans).
    This returns market cap / volume context instead and is labeled
    accordingly. Kept as a stub for future upgrade to the real F&G
    endpoint (/v3/fear-and-greed/latest).
    """
    quote = global_data.get("quote", {}).get("USD", {})
    return {
        "total_market_cap": quote.get("total_market_cap"),
        "total_volume_24h": quote.get("total_volume_24h"),
        "data_source": "real (CMC global-metrics)",
        "note": "Fear & Greed index not available on current plan; omitted rather than faked.",
    }


def get_etf_flow_proxy(global_data: dict) -> dict:
    """
    PROXY — not real ETF flow data.

    Derives an estimated net institutional flow from 24h total market
    cap % change. Real ETF net-flow data requires CMC Pro's
    /v1/global-metrics/quotes/historical (etf_flow fields) or a
    dedicated ETF flow provider (e.g. Farside, SoSoValue).

    The scaling factor (5% of market cap moves attributed to flow) is a
    rough heuristic, not a calibrated model — documented here so it's
    never mistaken for ground truth.
    """
    quote = global_data.get("quote", {}).get("USD", {})

    total_market_cap = quote.get("total_market_cap", 0) or 0
    market_cap_change_24h = quote.get("total_market_cap_yesterday_percentage_change", 0) or 0
    volume_24h = quote.get("total_volume_24h", 0) or 0
    volume_change_24h = quote.get("total_volume_24h_yesterday_percentage_change", 0) or 0

    estimated_flow = (market_cap_change_24h / 100) * total_market_cap * 0.05

    return {
        "net_flow_usd": estimated_flow,
        "market_cap_change_pct": market_cap_change_24h,
        "volume_24h": volume_24h,
        "volume_change_pct": volume_change_24h,
        "data_source": "proxy (estimated from market cap delta — NOT real ETF flow)",
    }


def get_derivatives_pressure_inputs(global_data: dict) -> dict:
    """
    Uses REAL derivatives market data from CMC's global-metrics endpoint:
    `derivatives_volume_24h` and `derivatives_24h_percentage_change`.

    This is genuine aggregate derivatives trading volume across tracked
    exchanges — not a synthetic guess. It is a volume/activity signal,
    not funding rate or open interest, so confluence.py treats it as the
    fallback scoring path (see score_derivatives_pressure).

    Upgrading to CMC Pro / Agent Hub would add real funding rate and OI
    fields, which confluence.py already supports as the primary path.
    """
    derivatives_volume_24h = global_data.get("derivatives_volume_24h", 0) or 0
    derivatives_volume_change_pct = global_data.get("derivatives_24h_percentage_change", 0) or 0
    btc_dominance = global_data.get("btc_dominance", 50)
    btc_dominance_change = global_data.get("btc_dominance_24h_percentage_change", 0)

    return {
        "derivatives_volume_24h": derivatives_volume_24h,
        "derivatives_volume_change_pct": derivatives_volume_change_pct,
        "btc_dominance": btc_dominance,
        "btc_dominance_change_pct": btc_dominance_change,
        # No real liquidation data on this tier — left at 0 so confluence.py
        # skips the liquidation-skew adjustment rather than faking a ratio.
        "long_liquidations_usd": 0.0,
        "short_liquidations_usd": 0.0,
        "data_source": "real (CMC global-metrics derivatives_volume_24h) — funding rate/OI unavailable on current plan",
    }


def fetch_confluence_inputs() -> dict:
    """
    Single entry point for skill.py: fetches global metrics once and
    returns both the ETF and derivatives input dicts confluence.py needs,
    plus the raw market context for the report.
    """
    global_data = get_global_metrics()
    if not global_data:
        raise DataFetchError(
            "Could not fetch CMC global metrics. Check CMC_API_KEY in .env "
            "and your network connection."
        )

    return {
        "etf_inputs": get_etf_flow_proxy(global_data),
        "derivatives_inputs": get_derivatives_pressure_inputs(global_data),
        "market_context": get_fear_and_greed(global_data),
        "last_updated": global_data.get("last_updated"),
    }