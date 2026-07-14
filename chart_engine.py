from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if pd.notna(number) else None
    except (TypeError, ValueError):
        return None


def build_live_chart(
    frame: pd.DataFrame,
    symbol: str,
    timeframe: str,
    plan: Mapping[str, Any] | None = None,
) -> go.Figure:
    if frame is None or frame.empty:
        return go.Figure()

    plan = dict(plan or {})
    figure = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.58, 0.16, 0.14, 0.12],
        specs=[[{"secondary_y": True}], [{}], [{}], [{}]],
    )

    figure.add_trace(
        go.Candlestick(
            x=frame["timestamp"], open=frame["open"], high=frame["high"],
            low=frame["low"], close=frame["close"], name=symbol,
        ),
        row=1, col=1, secondary_y=False,
    )
    for column, label in (("ema21", "EMA21"), ("ema50", "EMA50"), ("ema200", "EMA200")):
        if column in frame.columns:
            figure.add_trace(go.Scatter(x=frame["timestamp"], y=frame[column], name=label, mode="lines"), row=1, col=1)

    figure.add_trace(go.Bar(x=frame["timestamp"], y=frame["volume"], name="Volume", opacity=0.35), row=1, col=1, secondary_y=True)
    figure.add_trace(go.Scatter(x=frame["timestamp"], y=frame["rsi14"], name="RSI 14", mode="lines"), row=2, col=1)
    figure.add_hline(y=70, line_dash="dot", row=2, col=1)
    figure.add_hline(y=30, line_dash="dot", row=2, col=1)
    figure.add_trace(go.Scatter(x=frame["timestamp"], y=frame["macd"], name="MACD", mode="lines"), row=3, col=1)
    figure.add_trace(go.Scatter(x=frame["timestamp"], y=frame["macd_signal"], name="Signal", mode="lines"), row=3, col=1)
    figure.add_trace(go.Bar(x=frame["timestamp"], y=frame["macd_hist"], name="MACD Hist", opacity=0.45), row=3, col=1)
    figure.add_trace(go.Bar(x=frame["timestamp"], y=frame["rvol"], name="RVOL"), row=4, col=1)
    figure.add_hline(y=1.0, line_dash="dot", row=4, col=1)

    entry_low = _number(plan.get("entry_low"))
    entry_high = _number(plan.get("entry_high"))
    if entry_low is not None and entry_high is not None:
        low, high = sorted((entry_low, entry_high))
        figure.add_hrect(y0=low, y1=high, opacity=0.16, line_width=0, annotation_text="Official Entry", row=1, col=1)

    levels = [
        ("stop", "Official Stop", "dash"),
        ("t1", "Official T1", "dot"),
        ("t2", "Official T2", "dot"),
        ("t3", "Official T3", "dot"),
        ("support", "Support", "dashdot"),
        ("resistance", "Resistance", "dashdot"),
    ]
    for key, label, dash in levels:
        value = _number(plan.get(key))
        if value is not None:
            figure.add_hline(y=value, line_dash=dash, annotation_text=label, row=1, col=1)

    figure.update_layout(
        title=f"{symbol} · {timeframe}",
        height=900,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend_orientation="h",
        margin=dict(l=20, r=20, t=65, b=20),
    )
    figure.update_yaxes(title_text="Price", row=1, col=1, secondary_y=False)
    figure.update_yaxes(title_text="Volume", showgrid=False, row=1, col=1, secondary_y=True)
    figure.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    figure.update_yaxes(title_text="MACD", row=3, col=1)
    figure.update_yaxes(title_text="RVOL", row=4, col=1)
    return figure
