
## Scanner v2 durable-bootstrap repair
- Removed the repeating automatic-loading fragment timer that was producing invalid-fragment rerun storms in Streamlit.
- Scanner v2 history now persists each successful Massive market day as its own durable Supabase Storage shard before progress is counted.
- Bootstrap resumes from the durable manifest after Streamlit sleep/redeploy instead of depending on one growing in-memory Parquet build.
- Scanner v2 becomes usable at 220 completed sessions, compacts the durable shards once, and immediately launches the first full candidate scan.
- Normal future scans reuse the compact history and only fetch missing completed market sessions.
- Scanner progress now has one authoritative count: durable sessions / 220, plus the latest saved market day.
- Existing persisted scanner results are restored immediately while bootstrap or refresh work continues.
- Added structured scanner logging for Massive fetches, durable saves, rate-limit messages, compaction, and scan completion.


## v0.99 — Scanner v2 Free-Tier Bulk Market Database

- Replaced repeated Alpaca broad-universe history requests with Massive daily market summaries.
- Added a resumable, rate-limited one-time history bootstrap for the Massive free plan.
- Added persistent Parquet storage in private Supabase Storage so history survives Streamlit sleep and redeploys.
- Added daily incremental updates that normally require one grouped-market request.
- Added local whole-market indicator ranking with setup-family diversification before the existing full MomoPro engines.
- Added explicit Scanner v2 database status, setup progress, and failure messages.
- Removed alphabetical and partial-data fallbacks.
# v0.98.4 Final Workflow Stabilization

- Restored the locked startup rule: every browser refresh or cold session opens Dashboard as the home page while preserving the active ticker, stock tabs, chart state, planner drafts, and saved workspace.
- Watchlist technical, Relative Strength, Smart Money, Trading Intelligence, and Market Context snapshots now hydrate automatically; the refresh button remains a force-refresh control.
- Isolated Watchlist intelligence providers so one unavailable API/module cannot block all other snapshots.
- Scanner completion messaging now distinguishes the broad active U.S. equity universe, the ranked best-500 full-analysis set, and the final strategy matches.
- Added internal scan-scope counters without cluttering the visible Scanner table.


## v0.98.4 release-candidate stabilization
- Unified scanner rows and direct ticker analyses through `normalize_stock_payload`; removed remaining dict `.to_dict()` crash paths.
- Rebuilt company metadata as one implementation with SEC, configured providers, Yahoo and Nasdaq fallbacks; incomplete records retry on a shorter TTL.
- Added watchlist-wide refresh for every saved ticker, including direct analysis, metadata, relative strength, Smart Money and Trading Intelligence.
- Replaced collapsed watchlist JSON blobs with readable technical and intelligence status cards.
- Normalized AI Confidence table values to prevent PyArrow mixed-type serialization errors.
- Replaced deprecated Streamlit `use_container_width` calls with `width`.
# v0.98.4 durability hotfix — Cold-start recovery

- Refreshes expired Supabase access tokens before restoring any user data.
- Verifies private cloud access before loading settings, workspaces, plans, journal, integrations, or Webull snapshots.
- Fails closed on a temporary cloud/auth outage so saved data is never silently replaced by defaults.
- Adds retry handling for cloud reads and writes.
- Reduces and paces Webull order-detail requests to avoid the 429 burst shown in the cold-start logs.
- Keeps the v0.98.4 scanner and universal-symbol implementation intact.

# v0.98.4 — Scanner and Symbol Unification

- Any valid ticker entered through universal search can build the complete Stock Workspace without appearing in the market scan.
- Added a canonical on-demand symbol-analysis service using the same scoring, confidence, support/resistance, risk/reward, and target engines as the scanner.
- Added persistent company metadata caching with company, sector, industry, exchange, country, market-cap placeholder, float, and shares outstanding fields.
- Added cached metadata attachment and sector filtering to Scanner.
- Preserved one universal symbol context across Stock Report, News, AI Analysis, Live Chart, Trade Planner, and Journal.
- Added Trade Planner long/short direction support and target-level dollar profit, percentage return, reward per share, and R-multiple calculations.
- Guarded Stock Report selection against symbols missing from the current scanner DataFrame.

## v0.98.3 — Completion audit and loading-skeleton restoration
- Audited the current release against the locked v0.98.3 scope.
- Restored the missing visual loading skeletons for Dashboard, Market Context, Scanner, News, Relative Strength, Smart Money, and Trading Intelligence.
- Added an explicit per-resource `loading` state so skeletons appear only while queued work is actively restoring or refreshing data.
- Preserved automatic loading, separated resource persistence, stale detection, configurable refresh windows, refresh-only controls, Dashboard-home startup, Webull snapshot restoration, and global stock-tab behavior.

## v0.98.3 — Global stock workspace close fix

- Fixed stock tabs that reappeared after being closed from Scanner or another permanent page.
- Closing a ticker now removes the workspace tab, clears the shared selected ticker when it matches, removes the ticker from the URL, and persists the closed state.
- Fixed Scanner's Close Report button when the Scanner page tab—not the stock tab—was active.
- Added defensive cleanup for older sessions containing a selected ticker without a matching open stock tab.
- Preserved other open stock tabs and the current ticker when closing a different ticker.

## v0.98.3 — Automatic data loading (complete)

- Added a single application initialization and automatic-loading manager.
- Restores saved market context, scanner results, and news immediately from the private Supabase cache.
- Automatically refreshes missing or stale content using the cache windows configured in Settings.
- Reclassified old Load/Run controls as explicit force-refresh controls.
- Added consistent freshness timestamps and stale/fresh status captions.
- Added loading skeleton placeholders while network-backed content initializes.
- Restores the saved canonical Webull account context at sign-in without requiring a manual sync.
- Prevents duplicate requests during Streamlit reruns and keeps unrelated tabs lazy-loaded.
- Preserves v0.98.2 page, ticker, workspace, settings, and Webull persistence behavior.

## v0.98.2 Canonical Webull Account Integration

- Added one canonical broker account context shared by Settings, Trade Planner, risk sizing, and future journal automation.
- Fixed Webull parsing so zero-valued aliases no longer hide later positive account-value fields.
- Aggregated multiple Webull accounts and reconstructed equity from cash plus positions when needed.
- Persisted the last valid Webull account context in Supabase settings so transient cold-start reads do not revert the app to $10,000.
- Kept the manual account-size value only as an explicit fallback when no Webull value has ever been resolved.

v0.98.2 Tabs v2 — Hybrid Navigation Workspace

Restored top workspace tabs while keeping the permanent sidebar navigation.

Added persistent page tabs and closeable multi-symbol Stock Report tabs.

Scanner row selection and universal ticker search now open reusable stock workspace tabs.

The active tab and open-tab list persist through Supabase workspace storage and browser refresh.

Kept shared ticker context, direct feature navigation, deep links, Trade Planner handoff, and Live Chart restoration from v0.98.2.

Removed the Streamlit warning caused by calling st.rerun() inside the sidebar radio callback.

Dashboard remains pinned and cannot be closed; other page and stock tabs can be closed individually.

No scanner, scoring, AI, journal, performance, Webull, or TradingView engines were changed.

v0.98.2 — Navigation and Workspace Restoration

Replaced the fixed twelve-tab application shell with routed, conditional page rendering controlled by a persistent navigation manager.

Added persistent active-page and selected-symbol restoration through Supabase workspace storage and browser query parameters.

Added one universal ticker context shared by News, AI Analysis, Trade Planner, Journal, and Live Chart.

Added direct cross-feature navigation so Stock Report and Watchlist actions open their destination immediately without requiring the user to search again.

Updated Trade Planner to detect connected Webull buying power, cash, or net liquidation automatically while preserving a manual override.

Updated Live Chart to restore the current or last-viewed ticker, timeframe, candle count, and overlays instead of resetting to SPY after refresh.

Expanded the lightweight workspace record to persist page, ticker, chart controls, planner prefill, journal prefill, active watchlist, Dashboard universe, and last Webull sync reference.

Added shareable query-parameter routes such as ?page=trade-planner&symbol=AAPL while preserving Supabase workspace restoration as the fallback.

Preserved all existing scanner, intelligence, AI, journal, performance, Webull, TradingView, and trading-engine logic.

v0.95C3 — Official Plan Visual Polish + Live Chart Upgrade

Kept the original MomoPro Phase 5.6 indicator unchanged.

Added movable Official Plan dashboard positions so the two TradingView dashboards no longer have to overlap.

Added Full and Compact Official Plan panel modes.

Split Plan Status from Execution Status and added a plain-language reason row.

Replaced large current and historical status labels with small hoverable event symbols.

Added independent toggles for current events, historical events, historical lookback, entry, max chase, official stop, tactical stop, targets, support, resistance, and level symbols.

Added hoverable right-edge symbols for all plan levels.

Added EXIT WATCH and EXIT TRIGGERED management states and alerts.

Changed missing Opportunity and AI values from misleading zeroes to N/A.

Improved parent timeframe display by showing both state and resolved parent timeframe.

Rebuilt the MomoPro AI Live Chart with clearer spacing, future right margin, hoverable plan symbols, thinner plan lines, an entry band, improved zoom/crosshair behavior, and user-controlled overlays.

v0.95C2 — Official Plan Validation Foundation

Replaced the obsolete Linked Plan wording with Official Plan Mode.

Added a versioned 18-field Official Plan packet with reference entry and maximum chase.

Added MomoPro_Official_Plan_Validation_v0.95C2.pine as a lightweight companion that runs beside the unchanged Phase 5.6 indicator.

Added live validation for entry-zone location, maximum chase, EMA21/50/200 structure, EMA slopes, RSI, MACD, RVOL, candle confirmation, parent timeframe, SPY/QQQ market context, resistance proximity, tactical stop, targets, and invalidation.

Added clear states: packet required, plan loaded, waiting for entry, entry area/wait, entry confirmed, too extended, target reached, and plan invalidated.

Preserved the original MomoPro indicator as the complete standalone execution and trade-management engine.

Removed old UI instructions referring to MomoPro AI Link Companion and Enable Linked Plan Mode.

v0.95B — Native Live Chart & TradingView Bridge

Added a native multi-timeframe candlestick workspace using Alpaca market data.

Added EMA21/50/200, volume, RSI, MACD, RVOL, and Official MomoPro Plan overlays.

Added TradingView chart launch, canonical plan JSON export, Pine input export, and stable trade IDs.

Preserved all existing TradingView indicator functionality; Pine changes remain deferred to v0.95C.

Added integration-event storage helpers for the upcoming webhook phase.

MomoPro AI Changelog

v0.85 Package 2 — Webull Historical Import & Reconciliation

Added Webull CSV execution-history import with flexible column detection.

Added stable execution fingerprints and safe duplicate-import prevention.

Added broker execution and import-history persistence inside trade_data.json schema v2.

Added chronological FIFO reconciliation for buys, partial exits, and full exits.

Added safe unmatched-execution handling when historical exports begin mid-position.

Added Journal Broker Import & Reconcile workspace with preview, mapping, import history, and unmatched rows.

Added Dashboard Webull import status.

Preserved separate Trade Plan, Broker Execution, and Reconciled Trade layers.

Reserved official read-only Webull API synchronization for v0.95 Ecosystem Integration.

v0.7 — Watchlist & Alert Intelligence

Added persistent living watchlist profiles and multiple named watchlists.

Added personal thesis, entry, stop, target, tags, notes, timeline, and research snapshots.

Added scanner-driven technical/intelligence snapshots and Opportunity Score.

Added AI thesis status, recommendation, priority queue, and Morning Brief.

Added traditional and AI-state smart alerts with cooldowns and alert inbox.

Added portfolio-ready object storage and modular watchlist architecture.

Changelog

v0.6.0 — AI Research Workstation

Rebuilt the AI Analysis tab as the full independent research workstation.

Added executive summary, independent sentiment, confidence, conviction, time horizon, risk level, and final AI rating.

Added Momo Engine versus Independent AI comparison with disagreement analysis.

Added dedicated Technical, Market, News & Catalysts, Smart Money, Trading Intelligence, Bull/Bear, Risk/Thesis, and Confidence Trace sections.

Added confidence-component transparency.

Added blind spots, confirmation conditions, invalidation conditions, and suggested follow-up questions.

Added optional comparison against another ticker from the latest scan.

Added Ask Momo AI conversational research grounded in the current Stock Report evidence.

Added persistent per-symbol chat history and report caching.

AI responses distinguish verified, calculated, inferred, delayed, and unavailable evidence.

The AI forms its own opinion and may disagree with the deterministic Momo Engine.

v0.4 Final — Smart Money Audit

Corrected Finnhub/FMP insider-provider key ordering.

Added paginated Alpaca indicative option-chain loading.

Preserved v0.4.1 missing-data and compact-display behavior.

Added honest module coverage and preliminary/full read status.

Prevented missing short-interest values from becoming zero.

Added short-risk classification and gated squeeze scoring.

Added provider/source and data-quality labels.

Excluded incomplete Smart Money reads from integrated confidence.

Removed raw provider exceptions from the user interface.

Changelog

v0.4.2 — Basic Options Activity

Replaced the unavailable premium options-flow dependency with Alpaca's free indicative option-chain feed.

Added delayed call-versus-put trade-size activity, implied volatility, expiration concentration, and active-contract candidates.

Clearly labels the module as delayed/indicative and avoids claiming true real-time institutional flow.

Updated the Stock Report Options Flow layout and Smart Money scoring integration.

MomoPro AI Changelog

v0.3.0 — News & Catalyst Intelligence

Added

Dedicated News tab between Scanner and AI Analysis

Broad market news feed with sentiment, impact, category, and symbol filters

Ticker search for any symbol, even outside scanner results

Stock-specific headline research

Bullish, bearish, mixed, and neutral headline classification

High-impact and breaking-catalyst prioritization

Earnings and guidance headline detection

Analyst upgrade/downgrade and price-target detection

Official SEC filing lookup for priority forms

openFDA drug-enforcement and recall lookup

On-demand AI catalyst analysis

Top-five stock-news section in each Stock Report

Dashboard market-headline snapshot

Verified news context supplied to Momo Engine and independent AI decisions

Preserved

v0.2 Market Context system

Scanner ranking and stock-specific columns

Support and Resistance Engine v2

Structural risk/reward and T1/T2/T3

Technical and market-adjusted confidence

Existing tab order, with News inserted after Scanner

v0.2.0 — Market Intelligence

Added

Dedicated Market Context tab

Broad-market trend engine for SPY, QQQ, IWM, DIA, and VIXY proxy

Market breadth engine

Momo Fear & Greed and put/call sentiment engine

Sector strength and rotation engine

Market-level and stock-level relative strength

Dashboard market snapshot

Stock Report market backdrop

Market-adjusted confidence

Market-aware Momo Engine and independent AI decisions

Market-context data flow into the AI Analysis workspace

v0.1.0 — Scanner Foundation

Market universe and pre-screening

EMA21, EMA50, EMA200, RSI, MACD, ATR, and RVOL

Momo Score, Dee Fit, grade, setup, and reasons

Clickable Stock Report

v0.3.1 — Multi-Source News Coverage

Added Alpha Vantage News & Sentiment as a supplemental source.

Added Finnhub company and market news.

Added Financial Modeling Prep stock news, general news, and company press releases.

Merged all providers with Alpaca/Benzinga into one normalized feed.

Added duplicate removal across providers.

Added provider-aware ranking and source coverage counts.

Added graceful fallback when a provider is unavailable or rate-limited.

v0.4.0 — Smart Money Intelligence

Added

Stock Report Smart Money section with on-demand loading.

Institutional-style accumulation/distribution detection from OHLCV.

Options flow screening with call/put bias and unusual volume/open-interest candidates when provider access permits.

Reported insider transaction summaries and net-buying/net-selling assessment.

Institutional ownership trend and reported ownership percentages when available.

Float, shares outstanding, short-interest, days-to-cover, and squeeze-risk context.

Combined Smart Money score and verdict.

Integrated

Smart Money becomes an optional component of market-adjusted confidence.

Momo Engine Decision and Independent AI Decision can use available Smart Money context.

Notes

Smart Money data loads on demand to conserve free API limits.

OHLCV accumulation signals are inferred behavior, not proof of a specific institution's trades.

Options, ownership, insider, and short-interest availability depends on connected provider entitlements and may be delayed.

v0.5.0 — Trading Intelligence

Added

Deterministic pattern recognition for EMA21 reclaims/retests, higher-low continuations, tight consolidations, ascending triangles, cup-like bases, and above-average-volume breakouts.

Overall trend-health scoring from EMA alignment, slope, price location, and higher-low structure.

On-demand Daily, 4H, 1H, and 15-minute confirmation with alignment scoring.

Entry-quality grading using EMA21 location, volume, risk/reward, target quality, pattern quality, trend health, and timeframe alignment.

Aggressive, standard, and conservative adaptive stop references.

Intelligent target table combining structural resistance with ATR fallback and measured-move context.

Exit and management warnings for extension, weak volume, limited target room, trend weakness, and timeframe conflict.

Same-symbol historical setup analogue framework with sample size, win rate, average return, and average drawdown.

Functional Trade Planner with manual entry/stop/T1-T3 overrides, position sizing, risk budget, live R multiples, and session saving.

Send-to-Trade-Planner handoff from each Stock Report.

Integrated

Trading Intelligence becomes an optional integrated-confidence component.

Momo Engine Decision and Independent AI Decision can consume Trading Intelligence context.

Existing v0.1-v0.4 functionality and tab order are preserved.

Notes

Historical setup statistics are descriptive same-symbol analogues, not predictive guarantees or a full portfolio backtest.

Multi-timeframe and Trading Intelligence data load on demand to protect API limits and scan speed.

v0.6.1 — AI Research Workstation startup repair

Restored the complete v0.5.3 Streamlit application after the v0.6 package accidentally replaced app.py with the AI chat module.

Integrated the full AI Research Workstation into the existing AI Analysis tab.

Preserved Scanner, Market Context, News, Smart Money, Trading Intelligence, Trade Planner, and Position Sizing Engine behavior.

Added guarded, on-demand AI research and chat so no OpenAI request runs during app startup.

v0.6.0 — Complete AI Research Workstation

Built from the latest uploaded project checkpoint.

Fixed full AI research evidence parsing for news, SEC filings and FDA records.

Added responsive AI Analysis cards that wrap long text.

Added on-demand comparison research for any ticker or company.

Ask Momo AI now researches comparison companies mentioned naturally in questions.

Added independent AI action, strategy fit and practical action plan.

Added Bull AI vs Bear AI debate and debate winner.

Added readiness checklist, evidence quality and missing-evidence disclosure.

Added earnings and filing interpretation.

Added complete confidence trace.

Added chart and screenshot analysis.

Preserved all completed v0.1–v0.5.3 functionality.

v0.6 Final — Global Independent AI

Added always-available Global Ask Momo AI to the AI Analysis tab.

Global AI works with or without a selected scanner stock.

Added independent broad-market candidate discovery from external market feeds.

Added current multi-source market news and direct ticker/company research.

Added OpenAI web-search research with a provider-data fallback.

MomoPro scanner and market context are optional references, not the AI's boundary.

Added persistent global conversation memory and a clear-chat control.

Added transparent research-scope and source-status indicators.

Preserved the selected-stock research report, Ask Momo AI, comparisons and screenshot analysis.

v0.7.9 — Watchlist Intelligence Completion

Corrected Watchlist AI Confidence to use Full Independent AI Research only.

Persisted independent AI reports into living profiles and research history.

Kept Momo Confidence separate inside the technical snapshot.

Added automatic SEC company and industry enrichment with safe failure handling.

Corrected Opportunity Score to use Distance EMA21 %, scanner risk fields, and optional independent AI confidence.

Synced current market, smart-money, and trading-intelligence context during refresh when available.

Corrected AI-confidence alerts and Morning Brief confidence display.

Clarified automatic profile fields versus personal thesis/planning fields.

v0.8 — Dashboard / Morning Command Center

Rebuilt the existing Dashboard as the morning command center.

Added market-health, trend, risk, breadth, Fear & Greed, and sector-leadership summary metrics.

Added SPY, QQQ, IWM, DIA, and VIXY intelligence table.

Added breadth participation and sector leader/laggard panels.

Added required universe controls: Entire Market, Watchlist, Top Gainers, Recent IPOs, AI Stocks, Biotech, and Semiconductors.

Added ranked scanner highlights with Stock Report handoff.

Added unread watchlist-alert summary.

Added future-compatible open-trade panel that automatically reads Journal storage when available.

Added macro/breaking market news feed.

Added recent Independent AI recommendations.

Added a synthesized Today’s Trading Plan and risk posture.

Added dedicated dashboard modules so command-center logic remains outside the growing app.py

v0.85 — Journal & Open Trade Management

Added persistent trade records backed by trade_data.json.

Added manual trade creation with entry, shares, stop, targets, setup, grade, Momo Score, Dee Fit, Opportunity Score, and Independent AI Confidence.

Added Trade Planner-to-Journal and Watchlist-to-Journal handoffs.

Added open-trade dashboard with remaining shares, stops, targets, context, thesis, management updates, and partial exits.

Added persistent management updates, current-price snapshots, stop adjustments, and notes.

Added partial and final exit recording with exit reasons and automatic open/partial/closed status changes.

Added realized P/L, unrealized P/L support, realized R, average exit, and days-held calculations.

Added closed-trade post-review fields for plan adherence, rule-following score, strengths, mistakes, lessons, and AI coaching notes.

Added optional chart screenshot persistence in journal_attachments/.

Activated the Morning Command Center Open Trades panel using the Journal database.

Preserved all completed v0.1-v0.8 systems and existing tab order.

v0.85 Package 2 — Webull Historical Import & Reconciliation

Added Webull CSV import with stable duplicate fingerprints.

Added filled-order parsing for Webull's Filled, Avg Price, Filled Time, EST and EDT formats.

Added automatic reconciliation of buys, partial exits, full exits and weighted average entries.

Added unmatched-execution preservation and import diagnostics.

Added broker import status to the Journal and Dashboard.

v0.9 — Performance Analytics

Replaced the Performance placeholder with a complete analytics workstation.

Added lifetime and filtered net P/L, win rate, average winner/loser, profit factor, expectancy, average R, hold time, fees, best/worst trades and streaks.

Added source filtering for all trades, Webull/broker imports, MomoPro-planned trades and manual-only records.

Added symbol and date-range filtering.

Added equity curve and monthly P/L visualizations.

Added performance breakdowns by setup, grade, hold time, price range, trade source, Momo Score, Opportunity Score, Independent AI Confidence, market regime and sector.

Added planned-versus-actual exit, rule-following, mistake, target-hit and stop-hit analytics.

Added Independent AI action accuracy and coverage reporting.

Added complete trade-history table and chronological trade timeline review.

Added Webull reconciliation and analytics-data coverage reporting.

Added rule-based Performance Intelligence that surfaces strengths, risks and next improvements without inventing unavailable metadata.

Preserved one source of truth by reading the existing Journal and reconciled broker records directly.

v0.92 — Settings & Personalization

Replaced the Settings placeholder with a complete persistent personalization workstation.

Added centralized settings models, validation, atomic JSON storage, section updates, backup, restore and reset.

Added strategy profile, preferred setups, sectors and universes.

Added risk defaults for account size, risk per trade, position limits, loss limits, minimum risk/reward, stops and partial profits.

Added scanner preferences for price, liquidity, RVOL, ATR, EMA21 extension, Momo Score, grade, universe and exclusions.

Added indicator preferences for EMA, RSI, MACD, ATR, RVOL and timeframes.

Added AI behavior controls, evidence weights, response depth, thesis challenge and confidence thresholds.

Added Dashboard widget and default-universe preferences.

Added Journal, Performance, Alert, cache and integration preferences.

Added data-provider/configuration status for Alpaca, OpenAI, Webull CSV, future Webull OpenAPI and TradingView.

Trade Planner now uses the saved account-size and risk-per-trade defaults.

Performance Analytics now uses the saved default source filter.

Preserved all v0.1-v0.9 functionality and persistent trading data.

v0.94 — Learning Engine

Added personalized edge detection from the reconciled Journal and Webull trade history.

Added evidence labels: Insufficient Data, Early Signal, Moderate Evidence and Strong Evidence.

Added strengths and weaknesses by setup, grade, market regime, sector, price range, hold duration, score bands and source.

Added Independent AI Confidence, Momo Score and Opportunity Score calibration against actual outcomes.

Added recurring mistake and behavior detection using post-trade review fields.

Added weekly and monthly coaching summaries with a single next-improvement priority.

Added persistent learning snapshots and human-approved strategy rules.

Prevented silent self-modification: learning recommendations never rewrite scanner, risk or AI settings without explicit approval.

Expanded pattern recognition to pennants, descending and symmetrical triangles, rising and falling wedges, VCP and cup-and-handle candidates.

Added exact EMA21 reclaim freshness when detectable.

Preserved one source of truth by deriving learning directly from existing TradeRecord and Performance Analytics data.

v0.95A — Canonical Analysis & Trade Plan

Added a persistent MomoAnalysis model as the official single analysis record for each ticker.

Added one canonical trade-plan resolver for entry zone, stop, targets, support/resistance, and risk references.

Stock Report now displays an Official MomoPro Plan sourced from that canonical object.

Stock Report → Trade Planner handoff now uses the canonical plan rather than repeating fallback logic.

Trade Planner identifies the saved official plan while preserving personal sizing and execution notes.

Added persistent analysis and integration storage foundations for Live Chart, TradingView, and Webull packages.

Existing scanner, Trading Intelligence, AI Research, Watchlist, Journal, Performance, and Learning engines remain intact.

v0.95C — Pine Linked Plan Mode

Added an optional MomoPro AI Linked Plan layer to the existing TradingView indicator.

Preserved every existing indicator calculation, visual, signal, alert, lifecycle, S/R, and exit-management feature.

Added official entry zone, stop, T1/T2/T3, support, and resistance overlays from the canonical app plan.

Added official setup, grade, Momo Score, Opportunity Score, and Independent AI Confidence display.

Added symbol/timeframe mismatch warnings.

Added structured JSON webhook events for entry-zone, targets, manage, trim, exit, hard-exit, and stop events.

Updated the app's Pine Input Block labels to match the indicator inputs exactly.

## v0.98.2 Stabilization Patch — 2026-07-29
- Persist page, active ticker, open stock tabs, and chart controls immediately before navigation reruns.
- Restore Live Chart symbol/timeframe/candle/overlay state from the private workspace after refresh, login, or app wake.
- Use the connected Webull balance for the Settings account-size summary when available, with a clearly labeled manual fallback.
- Clarify that Supabase is the primary settings store and local JSON is only backup/export storage.
- Preserve the latest cloud-backed Webull snapshot and workspace context across fresh Streamlit runtimes.

## v0.98.2 lifecycle stabilization — 2026-07-29
- Removed Webull snapshot loading from the critical workspace persistence path so optional broker-data errors cannot prevent page, ticker, or stock-tab saves.
- Made the restored shared ticker authoritative over stale Live Chart defaults such as SPY.
- Kept the Live Chart widget, selected symbol, URL state, and cloud workspace synchronized on every symbol change.
- Added authenticated access-token propagation for all Supabase document loads/saves, improving refresh, sign-in, and sleep/wake recovery for workspace and settings.
- Added a unified Webull account-value resolver that supports normalized and nested/raw API response shapes.
- Updated Trade Planner and Settings to use the same Webull account-value source and label the source shown.

## v0.98.3 Automatic Loading — Phase 1 — 2026-07-29
- Added page-aware lazy loading so opening Dashboard, Market Context, Scanner, News, AI Analysis, or Watchlist immediately begins loading the data that page needs.
- Dashboard now automatically loads market context, ranked market news, and scanner results when missing.
- Market Context now automatically loads on first open; its button is now a force-refresh action rather than a required first step.
- Scanner now automatically runs on first open; its button is now a force-refresh action rather than a required first step.
- News begins loading automatically when opened while preserving manual refresh controls.
- Added per-resource loading locks and status metadata to prevent duplicate requests during Streamlit reruns.
- Preserved all v0.98.2 page, ticker, workspace, settings, and canonical Webull persistence behavior.

## v0.98.3 Final — Dashboard speed and complete Stock Report auto-loading
- Dashboard restores cached market, scanner, and news content before any expensive refresh work.
- Dashboard no longer blocks initial rendering on a full scanner run and news request every time it opens.
- Relative Strength now loads automatically when a Stock Report opens; its button is refresh-only.
- Smart Money Intelligence now loads automatically per ticker and persists in the automatic-data cache.
- Trading Intelligence now loads automatically per ticker and persists in the automatic-data cache.
- Returning to a recently opened ticker reuses its saved analysis until the configured refresh window expires.
- Manual controls remain available only to force an immediate refresh.

## v0.98.3 Scanner Regression Hotfix

- Removed blocking live requests from the Dashboard render path so saved Dashboard data paints immediately.
- Removed the automatic full-market scan from Scanner page initialization.
- Restored an explicit primary **Run New Market Scan** action that always starts a fresh scan.
- Prevented Dashboard news from silently refreshing during normal page rendering.
- Preserved automatic Stock Report intelligence loading after a stock is selected.

## v0.98.3 Loading Architecture Repair

- Removed the blocking Supabase read from application startup.
- Replaced the combined market/news/scanner cache document with one document per resource.
- Added a timed Streamlit fragment worker so page shells render before cloud restore or live provider work begins.
- Restored automatic loading for Dashboard, Market Context, Scanner, News, AI Analysis, Watchlist, and Journal.
- Restored automatic per-ticker loading for Relative Strength, Smart Money, and Trading Intelligence through the same non-blocking queue.
- Scanner snapshots now save independently and never rewrite unrelated market/news cache data.
- Scanner refresh is queued and no longer holds the full page render hostage.
- News now renders the automatic-loading snapshot instead of issuing a second synchronous provider request on every rerun.
- Manual controls remain force-refresh actions only.
- Added legacy combined-cache migration so existing saved data can be restored once and rewritten into the separated resource documents.

## v0.98.3 — Streamlit-safe global stock close hotfix
- Deferred universal ticker widget clearing until the next rerun, before widget creation.
- Prevented StreamlitAPIException when closing a stock workspace from any page.
- Preserved global tab removal, selected-symbol clearing, and URL cleanup behavior.

## v0.98.4 final shared-intelligence completion
- Watchlist profiles now hydrate automatically from Scanner rows, saved canonical Stock Reports, company metadata, AI research, Smart Money, Trading Intelligence, and market context.
- Watchlist no longer requires a separate manual refresh before showing already-known stock data.
- Scanner metadata enrichment now processes the current result set, isolates provider failures, uses a single batch cache write, and adds SEC shares-outstanding fallback.
- Market cap is estimated from scanner close × reported shares outstanding only when the provider did not return market cap.
- Fixed the remaining direct-symbol canonical-analysis `.to_dict()` crash by using the normalized dictionary payload.

## v0.98.5 — UI Design System and Responsive Polish

- Added a shared visual design system with reusable spacing, card, border, typography, and status tokens.
- Unified button hierarchy, navigation tabs, inputs, metric cards, alerts, forms, and expanders.
- Standardized table presentation with sticky headers, alternating rows, compact density, clearer borders, and responsive scrolling.
- Added responsive layouts for desktop, tablet, and smaller screens, including stacked columns and full-width mobile actions.
- Added reusable polished empty states so missing data is explained rather than shown as an unexplained blank section.
- Added historical reconstruction chart thumbnails using frozen pre-entry daily data.
- Added AI Coach Summary cards for reconstructed historical trades, covering verdict, setup read, strengths, and coaching focus.
- Preserved the existing scanner, intelligence, Webull, persistence, scoring, and trading-engine logic.

## v0.98.6 — Performance and maintainability

- Began decomposing the monolithic Streamlit entry point by extracting shared formatting helpers and cached provider adapters.
- Added one central cache/freshness policy for market context, scanner, news, metadata, intelligence, AI research, historical candles, and Webull snapshots.
- Added a reusable UI component layer for diagnostics and graceful error surfaces.
- Added structured JSON logging with automatic redaction of secret-bearing fields.
- Added startup diagnostics covering Supabase configuration, required Python packages, provider secrets, and runtime directory access.
- Added a private System Health panel with startup timings and dependency status.
- Added lightweight startup profiling and categorized fallback logging.
- Added release regression checks for syntax, required maintainability modules, deprecated Streamlit calls, and known direct-symbol crash patterns.
- Preserved all existing trading engines, scoring, broker integration, cloud persistence, navigation, and page behavior.

## v0.99 Scanner Candidate-Recall Repair

- Replaced the rigid IEX pre-screen gates that discarded symbols below 500,000 average shares or $5 million latest-day dollar volume before full MomoPro analysis.
- Added a strategy-aware pre-ranking model aligned with MomoPro's swing methodology: EMA21/50 structure, EMA21 entry proximity, RSI health, ATR suitability, recent-high room, recent return, liquidity and relative volume.
- Liquidity is now a weighted ranking input instead of an absolute exclusion rule, preserving quieter high-quality setups such as clean pullbacks and fresh EMA21 reclaims.
- Expanded the pre-screen history window and introduced strict, standard and expanded-liquidity diagnostics.
- The scanner now targets the strongest 500 eligible symbols whenever sufficient market data exists and reports the actual universe, eligible, selected and final-candidate counts accurately.
- Added hidden scanner diagnostics so future candidate-recall issues can be traced without guessing.

## v0.99 Scanner v2 runtime isolation hotfix
- Scanner v2 no longer runs inside the generic Streamlit automatic-loading queue.
- One-time Massive free-tier history bootstrap runs in an isolated background worker and cannot block Dashboard/navigation.
- Scanner history progress is resumable and periodically persisted to the private scanner-data bucket.
- Current scan calculations run in the same isolated worker; saved candidates remain visible while refresh runs.
- Scanner opens with latest saved results and automatically refreshes stale results; the manual button is force-refresh only.
- Added explicit scanner stages/progress so long operations are observable rather than appearing frozen.
