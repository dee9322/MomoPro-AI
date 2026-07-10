import gc
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from confidence import calculate_confidence
from indicators import calculate_indicators
from levels import calculate_levels
from market_universe import get_market_universe
from pre_screener import select_best_symbols
from risk_reward import calculate_risk_reward
from scoring import score_stock
from targets import calculate_targets


HISTORY_CALENDAR_DAYS = 350
MINIMUM_DAILY_BARS = 220
SCAN_LIMIT = 500
CHUNK_SIZE = 25


def run_scan():
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_SECRET_KEY"]

    client = StockHistoricalDataClient(
        api_key,
        secret_key,
    )

    end = datetime.now()
    start = end - timedelta(
        days=HISTORY_CALENDAR_DAYS
    )

    results = []

    all_symbols = get_market_universe(
        limit=None
    )

    symbols = select_best_symbols(
        api_key,
        secret_key,
        all_symbols,
        limit=SCAN_LIMIT,
    )

    for batch_start in range(
        0,
        len(symbols),
        CHUNK_SIZE,
    ):
        chunk = symbols[
            batch_start:
            batch_start + CHUNK_SIZE
        ]

        request = None
        bars = None
        all_bars = None

        try:
            request = StockBarsRequest(
                symbol_or_symbols=chunk,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed=DataFeed.IEX,
            )

            bars = client.get_stock_bars(
                request
            ).df

            if bars.empty:
                continue

            all_bars = bars.reset_index()

            for symbol in chunk:
                symbol_df = None

                try:
                    symbol_df = all_bars[
                        all_bars["symbol"]
                        == symbol
                    ].copy()

                    if (
                        len(symbol_df)
                        < MINIMUM_DAILY_BARS
                    ):
                        continue

                    symbol_df = (
                        calculate_indicators(
                            symbol_df
                        )
                    )

                    latest = symbol_df.iloc[-1]
                    previous = symbol_df.iloc[-2]

                    required_values = [
                        latest.get("ema200"),
                        latest.get("rsi14"),
                        latest.get("macd_hist"),
                        latest.get("atr_pct"),
                        latest.get("rvol"),
                        latest.get(
                            "prior_120_high"
                        ),
                    ]

                    if any(
                        pd.isna(value)
                        for value
                        in required_values
                    ):
                        continue

                    # Support & Resistance Engine v2
                    # uses the full stock history.
                    levels = calculate_levels(
                        symbol_df
                    )

                    risk_reward = (
                        calculate_risk_reward(
                            latest["close"],
                            levels,
                        )
                    )

                    targets = calculate_targets(
                        entry=risk_reward[
                            "Reference Entry"
                        ],
                        risk_per_share=(
                            risk_reward[
                                "Risk Per Share"
                            ]
                        ),
                        levels=levels,
                    )

                    (
                        score,
                        dee_fit,
                        momo_score,
                        modules,
                        grade,
                        setup,
                        reasons,
                    ) = score_stock(
                        latest,
                        previous,
                    )

                    confidence = calculate_confidence(
                        modules=modules,
                        risk_reward_data=risk_reward,
                        levels=levels,
                    )

                    results.append(
                        {
                            "Symbol": symbol,
                            "Close": round(
                                float(
                                    latest[
                                        "close"
                                    ]
                                ),
                                2,
                            ),
                            "Score": score,
                            "Dee Fit": dee_fit,
                            "Setup": setup,
                            "ATR %": round(
                                float(
                                    latest[
                                        "atr_pct"
                                    ]
                                ),
                                2,
                            ),
                            "RVOL": round(
                                float(
                                    latest["rvol"]
                                ),
                                2,
                            ),
                            "Distance EMA21 %": (
                                round(
                                    float(
                                        latest[
                                            "distance_from_ema21"
                                        ]
                                    ),
                                    2,
                                )
                            ),
                            "Reasons": reasons,
                            "Grade": grade,
                            "Momo Score": momo_score,
                            "Momo Confidence": confidence[
                                "Momo Confidence"
                            ],
                            "Confidence Rating": confidence[
                                "Confidence Rating"
                            ],
                            "Trend Confidence": confidence[
                                "Confidence Breakdown"
                            ]["Trend"],
                            "Location Confidence": confidence[
                                "Confidence Breakdown"
                            ]["Location"],
                            "Momentum Confidence": confidence[
                                "Confidence Breakdown"
                            ]["Momentum"],
                            "Volume Confidence": confidence[
                                "Confidence Breakdown"
                            ]["Volume"],
                            "Opportunity Confidence": confidence[
                                "Confidence Breakdown"
                            ]["Opportunity"],
                            "Risk Confidence": confidence[
                                "Confidence Breakdown"
                            ]["Risk"],
                            "Structure Confidence": confidence[
                                "Confidence Breakdown"
                            ]["Structure"],

                            "Support 1": levels[
                                "Support 1"
                            ],
                            "Support 2": levels[
                                "Support 2"
                            ],
                            "Support 3": levels[
                                "Support 3"
                            ],

                            "Resistance 1": levels[
                                "Resistance 1"
                            ],
                            "Resistance 2": levels[
                                "Resistance 2"
                            ],
                            "Resistance 3": levels[
                                "Resistance 3"
                            ],

                            "Support 1 Quality": (
                                levels[
                                    "Support 1 Quality"
                                ]
                            ),
                            "Support 2 Quality": (
                                levels[
                                    "Support 2 Quality"
                                ]
                            ),
                            "Support 3 Quality": (
                                levels[
                                    "Support 3 Quality"
                                ]
                            ),

                            "Resistance 1 Quality": (
                                levels[
                                    "Resistance 1 Quality"
                                ]
                            ),
                            "Resistance 2 Quality": (
                                levels[
                                    "Resistance 2 Quality"
                                ]
                            ),
                            "Resistance 3 Quality": (
                                levels[
                                    "Resistance 3 Quality"
                                ]
                            ),

                            "Support 1 Touches": (
                                levels[
                                    "Support 1 Touches"
                                ]
                            ),
                            "Support 2 Touches": (
                                levels[
                                    "Support 2 Touches"
                                ]
                            ),
                            "Support 3 Touches": (
                                levels[
                                    "Support 3 Touches"
                                ]
                            ),

                            "Resistance 1 Touches": (
                                levels[
                                    "Resistance 1 Touches"
                                ]
                            ),
                            "Resistance 2 Touches": (
                                levels[
                                    "Resistance 2 Touches"
                                ]
                            ),
                            "Resistance 3 Touches": (
                                levels[
                                    "Resistance 3 Touches"
                                ]
                            ),

                            "Reference Entry": (
                                risk_reward[
                                    "Reference Entry"
                                ]
                            ),
                            "Risk Reference": (
                                risk_reward[
                                    "Risk Reference"
                                ]
                            ),
                            "Reward Reference": (
                                risk_reward[
                                    "Reward Reference"
                                ]
                            ),
                            "Risk Per Share": (
                                risk_reward[
                                    "Risk Per Share"
                                ]
                            ),
                            "Reward Per Share": (
                                risk_reward[
                                    "Reward Per Share"
                                ]
                            ),
                            "Risk Reward": (
                                risk_reward[
                                    "Risk Reward"
                                ]
                            ),
                            "Risk Reward Status": (
                                risk_reward[
                                    "Risk Reward Status"
                                ]
                            ),

                            "T1": targets["T1"],
                            "T1 Upside %": targets[
                                "T1 Upside %"
                            ],
                            "T1 R": targets["T1 R"],

                            "T2": targets["T2"],
                            "T2 Upside %": targets[
                                "T2 Upside %"
                            ],
                            "T2 R": targets["T2 R"],

                            "T3": targets["T3"],
                            "T3 Upside %": targets[
                                "T3 Upside %"
                            ],
                            "T3 R": targets["T3 R"],
                        }
                    )

                except Exception:
                    continue

                finally:
                    if symbol_df is not None:
                        del symbol_df

        except Exception:
            continue

        finally:
            if all_bars is not None:
                del all_bars

            if bars is not None:
                del bars

            if request is not None:
                del request

            gc.collect()

    preferred_columns = [
        "Symbol",
        "Grade",
        "Momo Score",
        "Dee Fit",
        "Score",
        "Setup",
        "Close",
        "ATR %",
        "RVOL",
        "Distance EMA21 %",
        "Reasons",
    ]

    hidden_report_columns = [
        "Momo Confidence",
        "Confidence Rating",
        "Trend Confidence",
        "Location Confidence",
        "Momentum Confidence",
        "Volume Confidence",
        "Opportunity Confidence",
        "Risk Confidence",
        "Structure Confidence",

        "Support 1",
        "Support 2",
        "Support 3",

        "Resistance 1",
        "Resistance 2",
        "Resistance 3",

        "Support 1 Quality",
        "Support 2 Quality",
        "Support 3 Quality",

        "Resistance 1 Quality",
        "Resistance 2 Quality",
        "Resistance 3 Quality",

        "Support 1 Touches",
        "Support 2 Touches",
        "Support 3 Touches",

        "Resistance 1 Touches",
        "Resistance 2 Touches",
        "Resistance 3 Touches",

        "Reference Entry",
        "Risk Reference",
        "Reward Reference",
        "Risk Per Share",
        "Reward Per Share",
        "Risk Reward",
        "Risk Reward Status",

        "T1",
        "T1 Upside %",
        "T1 R",

        "T2",
        "T2 Upside %",
        "T2 R",

        "T3",
        "T3 Upside %",
        "T3 R",
    ]

    all_columns = (
        preferred_columns
        + hidden_report_columns
    )

    if not results:
        return pd.DataFrame(
            columns=all_columns
        )

    result_df = pd.DataFrame(results)

    result_df = result_df.sort_values(
        ["Dee Fit", "Score"],
        ascending=[False, False],
    )

    return result_df[all_columns]
