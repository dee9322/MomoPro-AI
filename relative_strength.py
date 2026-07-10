from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd
import requests
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


HISTORY_DAYS = 350
MINIMUM_BARS = 80
SEC_HEADERS = {
    "User-Agent": "MomoProAI/1.0 dbardwell9322@gmail.com",
    "Accept-Encoding": "gzip, deflate",
}


def _pct_change(series: pd.Series, periods: int) -> float | None:
    if series is None or len(series) <= periods:
        return None

    earlier = float(series.iloc[-(periods + 1)])
    latest = float(series.iloc[-1])

    if earlier == 0:
        return None

    return ((latest / earlier) - 1) * 100


def _difference(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


@lru_cache(maxsize=1)
def _sec_ticker_map() -> dict[str, int]:
    response = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers=SEC_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()

    mapping: dict[str, int] = {}
    for item in payload.values():
        ticker = str(item.get("ticker", "")).upper().strip()
        cik = item.get("cik_str")
        if ticker and cik is not None:
            mapping[ticker] = int(cik)

    return mapping


@lru_cache(maxsize=512)
def _sic_for_symbol(symbol: str) -> tuple[int | None, str | None]:
    try:
        cik = _sec_ticker_map().get(symbol.upper())
        if cik is None:
            return None, None

        response = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
            headers=SEC_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()

        sic_raw = payload.get("sic")
        sic = int(sic_raw) if sic_raw not in (None, "") else None
        description = payload.get("sicDescription")
        return sic, description
    except Exception:
        return None, None


def _sector_from_sic(sic: int | None) -> tuple[str | None, str | None]:
    if sic is None:
        return None, None

    # More specific classifications first.
    if 1300 <= sic <= 1389 or 2900 <= sic <= 2999:
        return "XLE", "Energy"
    if 2830 <= sic <= 2836 or 3840 <= sic <= 3851 or 8000 <= sic <= 8099:
        return "XLV", "Health Care"
    if 3570 <= sic <= 3579 or 3650 <= sic <= 3699 or 7370 <= sic <= 7379:
        return "XLK", "Technology"
    if 4800 <= sic <= 4899:
        return "XLC", "Communication Services"
    if 4900 <= sic <= 4999:
        return "XLU", "Utilities"
    if 6000 <= sic <= 6797:
        return "XLF", "Financials"
    if 6798 <= sic <= 6799:
        return "XLRE", "Real Estate"
    if 6500 <= sic <= 6599:
        return "XLRE", "Real Estate"
    if 2000 <= sic <= 2199:
        return "XLP", "Consumer Staples"
    if 5400 <= sic <= 5499 or 5900 <= sic <= 5999:
        return "XLP", "Consumer Staples"
    if 2200 <= sic <= 2399 or 2500 <= sic <= 2599 or 3100 <= sic <= 3199:
        return "XLY", "Consumer Discretionary"
    if 5200 <= sic <= 5399 or 5500 <= sic <= 5899 or 7000 <= sic <= 7099:
        return "XLY", "Consumer Discretionary"
    if 1000 <= sic <= 1299 or 1400 <= sic <= 1499:
        return "XLB", "Materials"
    if 2400 <= sic <= 2499 or 2600 <= sic <= 2899 or 3000 <= sic <= 3399:
        return "XLB", "Materials"
    if 1500 <= sic <= 1799 or 3400 <= sic <= 3569 or 3580 <= sic <= 3649:
        return "XLI", "Industrials"
    if 3700 <= sic <= 3839 or 3860 <= sic <= 4799 or 5000 <= sic <= 5199:
        return "XLI", "Industrials"
    if 7300 <= sic <= 7369 or 7380 <= sic <= 7999 or 8700 <= sic <= 8999:
        return "XLI", "Industrials"

    return None, None


def _empty_result(symbol: str, message: str) -> dict[str, Any]:
    return {
        "status": "Unavailable",
        "symbol": symbol,
        "score": None,
        "verdict": "Unavailable",
        "trend": "Unavailable",
        "summary": message,
        "sector_etf": None,
        "sector_name": None,
        "sector_source": "SEC SIC mapping",
        "sic": None,
        "sic_description": None,
        "stock_return_5d": None,
        "stock_return_20d": None,
        "stock_return_60d": None,
        "vs_spy_5d": None,
        "vs_spy_20d": None,
        "vs_spy_60d": None,
        "vs_qqq_5d": None,
        "vs_qqq_20d": None,
        "vs_qqq_60d": None,
        "vs_sector_5d": None,
        "vs_sector_20d": None,
        "vs_sector_60d": None,
    }


def get_relative_strength(
    api_key: str,
    secret_key: str,
    symbol: str,
) -> dict[str, Any]:
    symbol = symbol.upper().strip()

    try:
        sic, sic_description = _sic_for_symbol(symbol)
        sector_etf, sector_name = _sector_from_sic(sic)

        symbols = [symbol, "SPY", "QQQ"]
        if sector_etf and sector_etf not in symbols:
            symbols.append(sector_etf)

        client = StockHistoricalDataClient(api_key, secret_key)
        end = datetime.now()
        start = end - timedelta(days=HISTORY_DAYS)

        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )

        bars = client.get_stock_bars(request).df
        if bars.empty:
            return _empty_result(symbol, "No relative-strength market data was returned.")

        all_bars = bars.reset_index()

        def close_series(ticker: str) -> pd.Series | None:
            frame = all_bars[all_bars["symbol"] == ticker].copy()
            if len(frame) < MINIMUM_BARS:
                return None
            return frame.sort_values("timestamp")["close"].reset_index(drop=True)

        stock_close = close_series(symbol)
        spy_close = close_series("SPY")
        qqq_close = close_series("QQQ")
        sector_close = close_series(sector_etf) if sector_etf else None

        if stock_close is None or spy_close is None or qqq_close is None:
            return _empty_result(
                symbol,
                "Not enough daily history was available for the stock and benchmarks.",
            )

        stock_returns = {
            "5d": _pct_change(stock_close, 5),
            "20d": _pct_change(stock_close, 20),
            "60d": _pct_change(stock_close, 60),
        }
        spy_returns = {
            "5d": _pct_change(spy_close, 5),
            "20d": _pct_change(spy_close, 20),
            "60d": _pct_change(spy_close, 60),
        }
        qqq_returns = {
            "5d": _pct_change(qqq_close, 5),
            "20d": _pct_change(qqq_close, 20),
            "60d": _pct_change(qqq_close, 60),
        }
        sector_returns = {
            "5d": _pct_change(sector_close, 5) if sector_close is not None else None,
            "20d": _pct_change(sector_close, 20) if sector_close is not None else None,
            "60d": _pct_change(sector_close, 60) if sector_close is not None else None,
        }

        vs_spy = {
            period: _difference(stock_returns[period], spy_returns[period])
            for period in ("5d", "20d", "60d")
        }
        vs_qqq = {
            period: _difference(stock_returns[period], qqq_returns[period])
            for period in ("5d", "20d", "60d")
        }
        vs_sector = {
            period: _difference(stock_returns[period], sector_returns[period])
            for period in ("5d", "20d", "60d")
        }

        score = 50

        weighted_inputs = [
            (vs_spy["20d"], 16),
            (vs_qqq["20d"], 14),
            (vs_sector["20d"], 18),
            (vs_spy["60d"], 10),
            (vs_qqq["60d"], 8),
            (vs_sector["60d"], 10),
        ]

        for value, maximum in weighted_inputs:
            if value is None:
                continue
            contribution = max(-maximum, min(maximum, value * 2.2))
            score += contribution

        # Reward improving short-term leadership and penalize deterioration.
        short_average = [value for value in (vs_spy["5d"], vs_qqq["5d"], vs_sector["5d"]) if value is not None]
        medium_average = [value for value in (vs_spy["20d"], vs_qqq["20d"], vs_sector["20d"]) if value is not None]

        short_rs = sum(short_average) / len(short_average) if short_average else 0
        medium_rs = sum(medium_average) / len(medium_average) if medium_average else 0

        if short_rs >= medium_rs + 1.5:
            score += 8
            trend = "Improving"
        elif short_rs <= medium_rs - 1.5:
            score -= 8
            trend = "Weakening"
        elif medium_rs > 0:
            trend = "Holding Leadership"
        elif medium_rs < 0:
            trend = "Holding Weakness"
        else:
            trend = "Stable"

        score = round(max(0, min(score, 100)))

        if score >= 80:
            verdict = "Strong Outperformance"
        elif score >= 65:
            verdict = "Outperforming"
        elif score >= 45:
            verdict = "Neutral"
        elif score >= 30:
            verdict = "Underperforming"
        else:
            verdict = "Strong Underperformance"

        sector_text = (
            f" and its {sector_name} sector proxy ({sector_etf})"
            if sector_etf and sector_name
            else ""
        )

        summary = (
            f"{symbol} is {verdict.lower()} its major benchmarks{sector_text}. "
            f"The relative-strength trend is {trend.lower()}."
        )

        return {
            "status": "Available",
            "symbol": symbol,
            "score": score,
            "verdict": verdict,
            "trend": trend,
            "summary": summary,
            "sector_etf": sector_etf,
            "sector_name": sector_name,
            "sector_source": "SEC SIC mapping (approximate sector ETF)",
            "sic": sic,
            "sic_description": sic_description,
            "stock_return_5d": round(stock_returns["5d"], 2) if stock_returns["5d"] is not None else None,
            "stock_return_20d": round(stock_returns["20d"], 2) if stock_returns["20d"] is not None else None,
            "stock_return_60d": round(stock_returns["60d"], 2) if stock_returns["60d"] is not None else None,
            "vs_spy_5d": round(vs_spy["5d"], 2) if vs_spy["5d"] is not None else None,
            "vs_spy_20d": round(vs_spy["20d"], 2) if vs_spy["20d"] is not None else None,
            "vs_spy_60d": round(vs_spy["60d"], 2) if vs_spy["60d"] is not None else None,
            "vs_qqq_5d": round(vs_qqq["5d"], 2) if vs_qqq["5d"] is not None else None,
            "vs_qqq_20d": round(vs_qqq["20d"], 2) if vs_qqq["20d"] is not None else None,
            "vs_qqq_60d": round(vs_qqq["60d"], 2) if vs_qqq["60d"] is not None else None,
            "vs_sector_5d": round(vs_sector["5d"], 2) if vs_sector["5d"] is not None else None,
            "vs_sector_20d": round(vs_sector["20d"], 2) if vs_sector["20d"] is not None else None,
            "vs_sector_60d": round(vs_sector["60d"], 2) if vs_sector["60d"] is not None else None,
        }

    except Exception as error:
        return _empty_result(
            symbol,
            f"Relative strength could not be calculated: {error}",
        )
