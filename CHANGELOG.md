# MomoPro AI Changelog

## v0.85 Package 2 — Webull Historical Import & Reconciliation
- Added Webull CSV execution-history import with flexible column detection.
- Added stable execution fingerprints and safe duplicate-import prevention.
- Added broker execution and import-history persistence inside trade_data.json schema v2.
- Added chronological FIFO reconciliation for buys, partial exits, and full exits.
- Added safe unmatched-execution handling when historical exports begin mid-position.
- Added Journal Broker Import & Reconcile workspace with preview, mapping, import history, and unmatched rows.
- Added Dashboard Webull import status.
- Preserved separate Trade Plan, Broker Execution, and Reconciled Trade layers.
- Reserved official read-only Webull API synchronization for v0.95 Ecosystem Integration.

## v0.7 — Watchlist & Alert Intelligence
- Added persistent living watchlist profiles and multiple named watchlists.
- Added personal thesis, entry, stop, target, tags, notes, timeline, and research snapshots.
- Added scanner-driven technical/intelligence snapshots and Opportunity Score.
- Added AI thesis status, recommendation, priority queue, and Morning Brief.
- Added traditional and AI-state smart alerts with cooldowns and alert inbox.
- Added portfolio-ready object storage and modular watchlist architecture.

# Changelog

## v0.6.0 — AI Research Workstation

- Rebuilt the AI Analysis tab as the full independent research workstation.
- Added executive summary, independent sentiment, confidence, conviction, time horizon, risk level, and final AI rating.
- Added Momo Engine versus Independent AI comparison with disagreement analysis.
- Added dedicated Technical, Market, News & Catalysts, Smart Money, Trading Intelligence, Bull/Bear, Risk/Thesis, and Confidence Trace sections.
- Added confidence-component transparency.
- Added blind spots, confirmation conditions, invalidation conditions, and suggested follow-up questions.
- Added optional comparison against another ticker from the latest scan.
- Added Ask Momo AI conversational research grounded in the current Stock Report evidence.
- Added persistent per-symbol chat history and report caching.
- AI responses distinguish verified, calculated, inferred, delayed, and unavailable evidence.
- The AI forms its own opinion and may disagree with the deterministic Momo Engine.

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


## v0.6.1 — AI Research Workstation startup repair

- Restored the complete v0.5.3 Streamlit application after the v0.6 package accidentally replaced `app.py` with the AI chat module.
- Integrated the full AI Research Workstation into the existing AI Analysis tab.
- Preserved Scanner, Market Context, News, Smart Money, Trading Intelligence, Trade Planner, and Position Sizing Engine behavior.
- Added guarded, on-demand AI research and chat so no OpenAI request runs during app startup.

## v0.6.0 — Complete AI Research Workstation

- Built from the latest uploaded project checkpoint.
- Fixed full AI research evidence parsing for news, SEC filings and FDA records.
- Added responsive AI Analysis cards that wrap long text.
- Added on-demand comparison research for any ticker or company.
- Ask Momo AI now researches comparison companies mentioned naturally in questions.
- Added independent AI action, strategy fit and practical action plan.
- Added Bull AI vs Bear AI debate and debate winner.
- Added readiness checklist, evidence quality and missing-evidence disclosure.
- Added earnings and filing interpretation.
- Added complete confidence trace.
- Added chart and screenshot analysis.
- Preserved all completed v0.1–v0.5.3 functionality.

## v0.6 Final — Global Independent AI

- Added always-available Global Ask Momo AI to the AI Analysis tab.
- Global AI works with or without a selected scanner stock.
- Added independent broad-market candidate discovery from external market feeds.
- Added current multi-source market news and direct ticker/company research.
- Added OpenAI web-search research with a provider-data fallback.
- MomoPro scanner and market context are optional references, not the AI's boundary.
- Added persistent global conversation memory and a clear-chat control.
- Added transparent research-scope and source-status indicators.
- Preserved the selected-stock research report, Ask Momo AI, comparisons and screenshot analysis.

## v0.7.9 — Watchlist Intelligence Completion

- Corrected Watchlist AI Confidence to use Full Independent AI Research only.
- Persisted independent AI reports into living profiles and research history.
- Kept Momo Confidence separate inside the technical snapshot.
- Added automatic SEC company and industry enrichment with safe failure handling.
- Corrected Opportunity Score to use Distance EMA21 %, scanner risk fields, and optional independent AI confidence.
- Synced current market, smart-money, and trading-intelligence context during refresh when available.
- Corrected AI-confidence alerts and Morning Brief confidence display.
- Clarified automatic profile fields versus personal thesis/planning fields.

## v0.8 — Dashboard / Morning Command Center
- Rebuilt the existing Dashboard as the morning command center.
- Added market-health, trend, risk, breadth, Fear & Greed, and sector-leadership summary metrics.
- Added SPY, QQQ, IWM, DIA, and VIXY intelligence table.
- Added breadth participation and sector leader/laggard panels.
- Added required universe controls: Entire Market, Watchlist, Top Gainers, Recent IPOs, AI Stocks, Biotech, and Semiconductors.
- Added ranked scanner highlights with Stock Report handoff.
- Added unread watchlist-alert summary.
- Added future-compatible open-trade panel that automatically reads Journal storage when available.
- Added macro/breaking market news feed.
- Added recent Independent AI recommendations.
- Added a synthesized Today’s Trading Plan and risk posture.
- Added dedicated dashboard modules so command-center logic remains outside the growing app.py

## v0.85 — Journal & Open Trade Management
- Added persistent trade records backed by `trade_data.json`.
- Added manual trade creation with entry, shares, stop, targets, setup, grade, Momo Score, Dee Fit, Opportunity Score, and Independent AI Confidence.
- Added Trade Planner-to-Journal and Watchlist-to-Journal handoffs.
- Added open-trade dashboard with remaining shares, stops, targets, context, thesis, management updates, and partial exits.
- Added persistent management updates, current-price snapshots, stop adjustments, and notes.
- Added partial and final exit recording with exit reasons and automatic open/partial/closed status changes.
- Added realized P/L, unrealized P/L support, realized R, average exit, and days-held calculations.
- Added closed-trade post-review fields for plan adherence, rule-following score, strengths, mistakes, lessons, and AI coaching notes.
- Added optional chart screenshot persistence in `journal_attachments/`.
- Activated the Morning Command Center Open Trades panel using the Journal database.
- Preserved all completed v0.1-v0.8 systems and existing tab order.
