# v0.4 Final — Smart Money Audit

- Corrected Finnhub/FMP insider-provider key ordering.
- Added paginated Alpaca indicative option-chain loading.
- Preserved v0.4.1 missing-data and compact-display behavior.
- Added honest module coverage and preliminary/full read status.
- Prevented missing short-interest values from becoming zero.
- Added short-risk classification and gated squeeze scoring.
- Added provider/source and data-quality labels.
- Excluded incomplete Smart Money reads from integrated confidence.
- Removed raw provider exceptions from the user interface.

# Changelog

## v0.4.2 — Basic Options Activity

- Replaced the unavailable premium options-flow dependency with Alpaca's free indicative option-chain feed.
- Added delayed call-versus-put trade-size activity, implied volatility, expiration concentration, and active-contract candidates.
- Clearly labels the module as delayed/indicative and avoids claiming true real-time institutional flow.
- Updated the Stock Report Options Flow layout and Smart Money scoring integration.

# MomoPro AI Changelog

## v0.3.0 — News & Catalyst Intelligence

### Added
- Dedicated News tab between Scanner and AI Analysis
- Broad market news feed with sentiment, impact, category, and symbol filters
- Ticker search for any symbol, even outside scanner results
- Stock-specific headline research
- Bullish, bearish, mixed, and neutral headline classification
- High-impact and breaking-catalyst prioritization
- Earnings and guidance headline detection
- Analyst upgrade/downgrade and price-target detection
- Official SEC filing lookup for priority forms
- openFDA drug-enforcement and recall lookup
- On-demand AI catalyst analysis
- Top-five stock-news section in each Stock Report
- Dashboard market-headline snapshot
- Verified news context supplied to Momo Engine and independent AI decisions

### Preserved
- v0.2 Market Context system
- Scanner ranking and stock-specific columns
- Support and Resistance Engine v2
- Structural risk/reward and T1/T2/T3
- Technical and market-adjusted confidence
- Existing tab order, with News inserted after Scanner

## v0.2.0 — Market Intelligence

### Added
- Dedicated Market Context tab
- Broad-market trend engine for SPY, QQQ, IWM, DIA, and VIXY proxy
- Market breadth engine
- Momo Fear & Greed and put/call sentiment engine
- Sector strength and rotation engine
- Market-level and stock-level relative strength
- Dashboard market snapshot
- Stock Report market backdrop
- Market-adjusted confidence
- Market-aware Momo Engine and independent AI decisions
- Market-context data flow into the AI Analysis workspace

## v0.1.0 — Scanner Foundation

- Market universe and pre-screening
- EMA21, EMA50, EMA200, RSI, MACD, ATR, and RVOL
- Momo Score, Dee Fit, grade, setup, and reasons
- Clickable Stock Report

## v0.3.1 — Multi-Source News Coverage

- Added Alpha Vantage News & Sentiment as a supplemental source.
- Added Finnhub company and market news.
- Added Financial Modeling Prep stock news, general news, and company press releases.
- Merged all providers with Alpaca/Benzinga into one normalized feed.
- Added duplicate removal across providers.
- Added provider-aware ranking and source coverage counts.
- Added graceful fallback when a provider is unavailable or rate-limited.

## v0.4.0 — Smart Money Intelligence

### Added
- Stock Report Smart Money section with on-demand loading.
- Institutional-style accumulation/distribution detection from OHLCV.
- Options flow screening with call/put bias and unusual volume/open-interest candidates when provider access permits.
- Reported insider transaction summaries and net-buying/net-selling assessment.
- Institutional ownership trend and reported ownership percentages when available.
- Float, shares outstanding, short-interest, days-to-cover, and squeeze-risk context.
- Combined Smart Money score and verdict.

### Integrated
- Smart Money becomes an optional component of market-adjusted confidence.
- Momo Engine Decision and Independent AI Decision can use available Smart Money context.

### Notes
- Smart Money data loads on demand to conserve free API limits.
- OHLCV accumulation signals are inferred behavior, not proof of a specific institution's trades.
- Options, ownership, insider, and short-interest availability depends on connected provider entitlements and may be delayed.

## v0.5.0 — Trading Intelligence

### Added
- Deterministic pattern recognition for EMA21 reclaims/retests, higher-low continuations, tight consolidations, ascending triangles, cup-like bases, and above-average-volume breakouts.
- Overall trend-health scoring from EMA alignment, slope, price location, and higher-low structure.
- On-demand Daily, 4H, 1H, and 15-minute confirmation with alignment scoring.
- Entry-quality grading using EMA21 location, volume, risk/reward, target quality, pattern quality, trend health, and timeframe alignment.
- Aggressive, standard, and conservative adaptive stop references.
- Intelligent target table combining structural resistance with ATR fallback and measured-move context.
- Exit and management warnings for extension, weak volume, limited target room, trend weakness, and timeframe conflict.
- Same-symbol historical setup analogue framework with sample size, win rate, average return, and average drawdown.
- Functional Trade Planner with manual entry/stop/T1-T3 overrides, position sizing, risk budget, live R multiples, and session saving.
- Send-to-Trade-Planner handoff from each Stock Report.

### Integrated
- Trading Intelligence becomes an optional integrated-confidence component.
- Momo Engine Decision and Independent AI Decision can consume Trading Intelligence context.
- Existing v0.1-v0.4 functionality and tab order are preserved.

### Notes
- Historical setup statistics are descriptive same-symbol analogues, not predictive guarantees or a full portfolio backtest.
- Multi-timeframe and Trading Intelligence data load on demand to protect API limits and scan speed.
