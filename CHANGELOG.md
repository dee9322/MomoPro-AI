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

## v0.4.1 — Smart Money Polish

- Removed the Alpha Vantage premium options call and raw provider messages.
- Added a clean unavailable state for options flow on current free plans.
- Added Finnhub-first insider transaction coverage with FMP fallback.
- Added Smart Money data coverage, preliminary labeling, and module availability indicators.
- Excluded incomplete Smart Money reads from integrated confidence until coverage reaches 50%.
- Added preliminary-data warnings to Momo Engine commentary.
- Reformatted float, shares outstanding, and monetary values into compact K/M/B notation.
- Reworked the Smart Money layout to prevent truncated verdicts and oversized values.
- Missing short-interest and squeeze fields now display as unavailable rather than misleading zeroes.
- Provider failures are converted into clean user-facing messages instead of raw API errors.
