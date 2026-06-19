# CMC Pressure Skill

## Overview
This Skill detects **cross-asset confluence** between crypto ETF demand flow and derivatives market positioning using the CoinMarketCap Agent Hub. When institutional ETF flows and derivatives traders agree on direction, the signal is high-conviction. When they disagree, the Skill flags caution or a fade opportunity.

## Trigger
Invoke this Skill when the user asks any of the following:
- "Is the market bullish or bearish right now?"
- "Should I go long or stay flat?"
- "What does ETF flow say about market direction?"
- "Are derivatives and ETF flows aligned?"
- "Give me a confluence signal"
- "Run CMC pressure check"

## Data Sources (CMC Agent Hub MCP Tools)
1. `get_global_metrics_latest` — retrieves ETF net flow (inflows/outflows), Fear & Greed index, total market cap, BTC dominance
2. `get_global_crypto_derivatives_metrics` — retrieves total open interest, aggregated funding rates, 24h liquidations (long vs short)

## Signal Logic

### Step 1 — ETF Pressure Score (0 to 100)
- ETF net inflow > $500M in 24h → score 80–100 (strong institutional buying)
- ETF net inflow $0–$500M → score 50–79 (mild bullish)
- ETF net outflow $0 to -$500M → score 20–49 (mild bearish)
- ETF net outflow > -$500M → score 0–19 (strong institutional selling)

### Step 2 — Derivatives Pressure Score (0 to 100)
- Funding rate > +0.02% AND open interest rising → score 75–100 (leveraged longs dominant)
- Funding rate +0.01% to +0.02% → score 55–74 (mild long bias)
- Funding rate -0.01% to +0.01% → score 40–54 (neutral)
- Funding rate < -0.01% AND open interest rising → score 0–39 (leveraged shorts dominant)
- Liquidations: if long liquidations > short liquidations by 2x → subtract 10 points (longs getting wrecked)
- Liquidations: if short liquidations > long liquidations by 2x → add 10 points (shorts getting squeezed)

### Step 3 — Confluence Score (final)
confluence_score = (etf_score * 0.55) + (derivatives_score * 0.45)

ETF flow is weighted slightly higher because it represents real capital commitment, not leveraged positioning.

### Step 4 — Signal Output
| Confluence Score | Signal | Recommended Action |
|---|---|---|
| 75–100 | STRONG BULL | High-conviction long. Size up. |
| 60–74 | BULL | Bullish bias. Standard position size. |
| 45–59 | NEUTRAL | No edge. Stay flat or reduce size. |
| 30–44 | BEAR | Bearish bias. Reduce longs or short. |
| 0–29 | STRONG BEAR | High-conviction short. Size up on short side. |

### Divergence Flag
If `abs(etf_score - derivatives_score) > 30`, add a **DIVERGENCE WARNING**:
- ETF score >> Derivatives score: institutions buying but leverage not following — early accumulation, not yet confirmed
- Derivatives score >> ETF score: leverage building without institutional backing — likely a pump, fade risk high

## Output Format
Always return:
1. ETF Pressure Score with raw data (net flow $, direction)
2. Derivatives Pressure Score with raw data (funding rate %, OI $, liquidation ratio)
3. Confluence Score (the weighted final number)
4. Signal label (STRONG BULL / BULL / NEUTRAL / BEAR / STRONG BEAR)
5. Divergence warning if triggered
6. One-paragraph plain-English interpretation for non-technical users

## Example Output
=== CMC PRESSURE SKILL REPORT ===

Date: 2026-06-19 UTC
ETF Pressure Score:    72 / 100

Net Flow 24h:        +$823M (inflow)

Direction:           BULLISH
Derivatives Score:     48 / 100

Funding Rate:        +0.008% (near neutral)

Open Interest:       $42.3B (stable)

Liquidation Ratio:   Long $180M / Short $210M (slight short squeeze)
Confluence Score:      61.8 / 100

Signal:                BULL
⚠️  DIVERGENCE WARNING: ETF flow is bullish (+72) but derivatives are neutral (48).

Institutions are buying but leveraged traders are not yet following.

Interpretation: Early accumulation phase. Momentum may build in 24–48h

if derivatives catch up. Do not over-leverage yet.
Plain English: Institutional money is flowing into crypto ETFs at a healthy

pace, suggesting real buying interest. However, derivatives traders are sitting

on the fence with near-zero funding rates. This split suggests the move is

early and not yet crowded — a cautiously bullish setup with room to grow if

leverage starts piling in.
## Error Handling
- If CMC API returns no ETF data: set ETF score to 50 (neutral) and flag "ETF data unavailable — score defaulted to neutral"
- If funding rate data missing: use open interest change direction as proxy
- Always complete the report even with partial data; flag missing fields clearly

## Stack
- Data: CoinMarketCap Agent Hub MCP (`get_global_metrics_latest`, `get_global_crypto_derivatives_metrics`)
- Runtime: Python 3.10+
- Compatible with: Claude, GPT-4, any MCP-enabled agent
