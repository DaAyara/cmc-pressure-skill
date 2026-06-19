"""
skill.py

Runnable entry point for the CMC Pressure Skill. Fetches live market
data from CMC, runs the confluence scoring engine, and prints a
formatted report matching the SKILL.md output spec.

Usage:
    python skill.py

Requires CMC_API_KEY set in .env (see .env.example).
"""

import sys
from datetime import datetime, timezone

from src.data import fetch_confluence_inputs, DataFetchError
from src.confluence import run_confluence


def format_usd(value: float) -> str:
    """Formats a dollar value with sign and magnitude suffix (K/M/B)."""
    sign = "+" if value >= 0 else "-"
    value = abs(value)
    if value >= 1_000_000_000:
        return f"{sign}${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{sign}${value / 1_000:.1f}K"
    return f"{sign}${value:.2f}"


def build_report(result, inputs: dict) -> str:
    etf_inputs = inputs["etf_inputs"]
    derivatives_inputs = inputs["derivatives_inputs"]
    timestamp = inputs.get("last_updated") or datetime.now(timezone.utc).isoformat()

    lines = []
    lines.append("=== CMC PRESSURE SKILL REPORT ===")
    lines.append("")
    lines.append(f"Date: {timestamp}")
    lines.append("")

    # --- ETF section ---
    lines.append(f"ETF Pressure Score:    {result.etf_score} / 100")
    lines.append(f"  Net Flow 24h (proxy): {format_usd(etf_inputs['net_flow_usd'])}")
    lines.append(f"  Market Cap Change:    {etf_inputs['market_cap_change_pct']:+.2f}%")
    lines.append(f"  Data Source:          {etf_inputs['data_source']}")
    lines.append("")

    # --- Derivatives section ---
    lines.append(f"Derivatives Pressure Score: {result.derivatives_score} / 100")
    lines.append(f"  Derivatives Volume 24h:   ${derivatives_inputs['derivatives_volume_24h'] / 1e9:.2f}B")
    lines.append(f"  Volume Change 24h:        {derivatives_inputs['derivatives_volume_change_pct']:+.2f}%")
    lines.append(f"  BTC Dominance:            {derivatives_inputs['btc_dominance']:.2f}%")
    lines.append(f"  Data Source:              {derivatives_inputs['data_source']}")
    lines.append("")

    # --- Confluence ---
    lines.append(f"Confluence Score:      {result.confluence_score} / 100")
    lines.append(f"Signal:                {result.signal}")
    lines.append("")

    if result.divergence_warning:
        lines.append(f"⚠️  DIVERGENCE WARNING: {result.divergence_warning}")
        lines.append("")

    lines.append("Plain English:")
    lines.append(interpret(result))
    lines.append("")
    lines.append(
        "NOTE: ETF flow figure is a proxy derived from market cap delta "
        "(real ETF flow data requires CMC Pro/Agent Hub access, not available "
        "on this build's plan). Derivatives volume is real CMC data; funding "
        "rate and open interest are unavailable on the current plan."
    )

    return "\n".join(lines)


def interpret(result) -> str:
    signal = result.signal
    if signal == "STRONG BULL":
        return (
            "Both institutional-style flow and derivatives activity point firmly "
            "upward. Conditions favor a higher-conviction long, sized within your "
            "normal risk limits."
        )
    if signal == "BULL":
        return (
            "Conditions lean bullish overall. The signal is positive but not "
            "extreme — a standard-size long bias is reasonable rather than maximum "
            "conviction."
        )
    if signal == "NEUTRAL":
        return (
            "Capital flow and derivatives activity are not telling a consistent "
            "story right now. This is a low-edge environment — staying flat or "
            "running reduced size is the more defensible choice."
        )
    if signal == "BEAR":
        return (
            "Conditions lean bearish. Pressure is tilted toward selling or reduced "
            "risk-taking — this favors trimming long exposure rather than adding to it."
        )
    return (
        "Both flow and derivatives activity point firmly downward. Conditions "
        "favor a defensive or short-biased posture, sized within your normal "
        "risk limits."
    )


def main() -> int:
    try:
        inputs = fetch_confluence_inputs()
    except DataFetchError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    result = run_confluence(inputs["etf_inputs"], inputs["derivatives_inputs"])
    print(build_report(result, inputs))
    return 0


if __name__ == "__main__":
    sys.exit(main())