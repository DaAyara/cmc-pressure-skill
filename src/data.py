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


def get_global_metrics():
    """
    Fetches global crypto market metrics from CMC.
    Returns ETF flow context, Fear & Greed, dominance, volume.
    """
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


def get_derivatives_metrics():
    """
    Fetches global derivatives market data from CMC.
    Returns open interest, funding rates, liquidations.
    """
    url = f"{BASE_URL}/v1/global-metrics/quotes/latest"
    params = {"convert": "USD"}

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("data", {})
    except requests.exceptions.RequestException as e:
        print(f"[data.py] Error fetching derivatives metrics: {e}")
        return {}


def get_btc_dominance():
    """
    Returns BTC dominance percentage from global metrics.
    Used as a secondary regime filter.
    """
    metrics = get_global_metrics()
    return metrics.get("btc_dominance", None)


def get_fear_and_greed():
    """
    Returns Fear & Greed index value and label from global metrics.
    """
    metrics = get_global_metrics()
    quote = metrics.get("quote", {}).get("USD", {})
    return {
        "value": metrics.get("fear_greed_value", None),
        "label": metrics.get("fear_greed_label", "Unknown"),
        "total_market_cap": quote.get("total_market_cap", None),
        "total_volume_24h": quote.get("total_volume_24h", None),
    }


def get_etf_flow_simulated(global_data: dict) -> dict:
    """
    Derives ETF flow proxy from global metrics when direct ETF
    endpoint is unavailable on the free/basic CMC tier.

    Logic: uses 24h volume change + market cap change as institutional
    flow proxy. Real ETF flow data is available on CMC Pro via
    /v1/global-metrics/quotes/historical with etf_flow fields.
    """
    quote = global_data.get("quote", {}).get("USD", {})

    total_market_cap = quote.get("total_market_cap", 0)
    market_cap_change_24h = quote.get("total_market_cap_yesterday_percentage_change", 0)
    volume_24h = quote.get("total_volume_24h", 0)
    volume_change_24h = quote.get("total_volume_24h_yesterday_percentage_change", 0)

    # Estimate net flow: positive market cap change + rising volume = inflow proxy
    # Scale to a dollar figure for scoring
    estimated_flow = (market_cap_change_24h / 100) * total_market_cap * 0.05

    return {
        "estimated_net_flow_usd": estimated_flow,
        "market_cap_change_pct": market_cap_change_24h,
        "volume_24h": volume_24h,
        "volume_change_pct": volume_change_24h,
        "data_source": "proxy (market cap + volume delta)",
    }


def get_derivatives_simulated(global_data: dict) -> dict:
    """
    Derives derivatives proxy from global metrics.

    For a full implementation, use:
    - /v1/global-metrics/quotes/latest (derivatives fields)
    - /v1/exchange/market-pairs/latest for funding rates per exchange

    Here we use total_volume and dominance as leverage proxies.
    """
    quote = global_data.get("quote", {}).get("USD", {})

    total_volume = quote.get("total_volume_24h", 0)
    volume_change = quote.get("total_volume_24h_yesterday_percentage_change", 0)
    btc_dominance = global_data.get("btc_dominance", 50)
    eth_dominance = global_data.get("eth_dominance", 15)
    active_cryptos = global_data.get("active_cryptocurrencies", 0)

    # Altcoin season proxy: low BTC dominance = risk-on = bullish derivatives
    alt_season_score = max(0, 60 - btc_dominance)

    # Volume surge = leverage building
    volume_surge = max(-50, min(50, volume_change))

    return {
        "btc_dominance": btc_dominance,
        "eth_dominance": eth_dominance,
        "total_volume_24h": total_volume,
        "volume_change_pct": volume_change,
        "alt_season_proxy": alt_season_score,
        "volume_surge_score": volume_surge,
        "active_cryptos": active_cryptos,
        "data_source": "proxy (dominance + volume dynamics)",
    }
