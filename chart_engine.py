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


def _enabled(options: Mapping[str, bool], key: str, default: bool = True) -> bool:
    value = options.get(key, default)
    return bool(value)


def _add_level(
    figure: go.Figure,
    *,
    x_value: Any,
    value: float | None,
    name: str,
    symbol: str,
    dash: str,
    line_color: str,
    marker_color: str,
    visible: bool,
) -> None:
    if not visible or value is None:
        return

    figure.add_hline(
        y=value,
        line_dash=dash,
        line_width=1.25,
        line_color=line_color,
        opacity=0.85,
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=[x_value],
            y=[value],
            mode="markers+text",
            marker={"size": 13, "color": marker_color, "line": {"width": 1, "color": "white"}},
            text=[symbol],
            textposition="middle center",
            textfont={"size": 9, "color": "white"},
            name=name,
            customdata=[[name, value]],
            hovertemplate="<b>%{customdata[0]}</b><br>$%{customdata[1]:,.2f}<extra></extra>",
            showlegend=False,
            cliponaxis=False,
        ),
        row=1,
        col=1,
    )


def build_live_chart(
    frame: pd.DataFrame,
    symbol: str,
    timeframe: str,
    plan: Mapping[str, Any] | None = None,
    display_options: Mapping[str, bool] | None = None,
) -> go.Figure:
    """Build the MomoPro research chart with clean hover-first plan overlays.

    Price levels use thin lines plus small hoverable symbols at the latest candle.
    This avoids the overlapping right-edge annotations used by the earlier chart.
    """
    if frame is None or frame.empty:
        return go.Figure()

    plan = dict(plan or {})
    options = dict(display_options or {})
    chart = frame.copy()
    chart["timestamp"] = pd.to_datetime(chart["timestamp"])
    latest_x = chart["timestamp"].iloc[-1]

    figure = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.018,
        row_heights=[0.64, 0.14, 0.13, 0.09],
        specs=[[{"secondary_y": True}], [{}], [{}], [{}]],
    )

    figure.add_trace(
        go.Candlestick(
            x=chart["timestamp"],
            open=chart["open"],
            high=chart["high"],
            low=chart["low"],
            close=chart["close"],
            name=symbol,
            increasing_line_color="#19b394",
            decreasing_line_color="#ef5350",
            increasing_fillcolor="#19b394",
            decreasing_fillcolor="#ef5350",
            hovertext=[
                (
                    f"<b>{symbol}</b><br>{stamp:%Y-%m-%d %H:%M}<br>"
                    f"Open ${open_:,.2f}<br>High ${high:,.2f}<br>"
                    f"Low ${low:,.2f}<br>Close ${close:,.2f}"
                )
                for stamp, open_, high, low, close in zip(
                    chart["timestamp"], chart["open"], chart["high"], chart["low"], chart["close"]
                )
            ],
            hoverinfo="text",
        ),
        row=1,
        col=1,
        secondary_y=False,
    )

    ema_colors = {"ema21": "#4ea1ff", "ema50": "#ff5d73", "ema200": "#b96cff"}
    for column, label in (("ema21", "EMA21"), ("ema50", "EMA50"), ("ema200", "EMA200")):
        if column in chart.columns and _enabled(options, column, True):
            figure.add_trace(
                go.Scatter(
                    x=chart["timestamp"],
                    y=chart[column],
                    name=label,
                    mode="lines",
                    line={"width": 1.7, "color": ema_colors[column]},
                    hovertemplate=f"<b>{label}</b><br>$%{{y:,.2f}}<extra></extra>",
                ),
                row=1,
                col=1,
            )

    volume_colors = ["#19b394" if close >= open_ else "#ef5350" for open_, close in zip(chart["open"], chart["close"])]
    figure.add_trace(
        go.Bar(
            x=chart["timestamp"],
            y=chart["volume"],
            name="Volume",
            marker_color=volume_colors,
            opacity=0.28,
            hovertemplate="<b>Volume</b><br>%{y:,.0f}<extra></extra>",
        ),
        row=1,
        col=1,
        secondary_y=True,
    )

    if _enabled(options, "rsi", True):
        figure.add_trace(
            go.Scatter(
                x=chart["timestamp"], y=chart["rsi14"], name="RSI 14", mode="lines",
                line={"width": 1.5, "color": "#7bd88f"},
                hovertemplate="<b>RSI 14</b><br>%{y:.1f}<extra></extra>",
            ),
            row=2, col=1,
        )
        figure.add_hrect(y0=30, y1=70, fillcolor="rgba(120,120,120,0.05)", line_width=0, row=2, col=1)
        figure.add_hline(y=70, line_dash="dot", line_width=1, opacity=0.55, row=2, col=1)
        figure.add_hline(y=30, line_dash="dot", line_width=1, opacity=0.55, row=2, col=1)

    if _enabled(options, "macd", True):
        figure.add_trace(
            go.Scatter(
                x=chart["timestamp"], y=chart["macd"], name="MACD", mode="lines",
                line={"width": 1.4, "color": "#4ea1ff"},
                hovertemplate="<b>MACD</b><br>%{y:.4f}<extra></extra>",
            ),
            row=3, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=chart["timestamp"], y=chart["macd_signal"], name="Signal", mode="lines",
                line={"width": 1.3, "color": "#ff8a65"},
                hovertemplate="<b>MACD Signal</b><br>%{y:.4f}<extra></extra>",
            ),
            row=3, col=1,
        )
        hist_colors = ["#19b394" if value >= 0 else "#ef5350" for value in chart["macd_hist"]]
        figure.add_trace(
            go.Bar(
                x=chart["timestamp"], y=chart["macd_hist"], name="MACD Hist",
                marker_color=hist_colors, opacity=0.35,
                hovertemplate="<b>MACD Histogram</b><br>%{y:.4f}<extra></extra>",
            ),
            row=3, col=1,
        )

    if _enabled(options, "rvol", True):
        rvol_colors = ["#19b394" if value >= 1.0 else "#8b95a5" for value in chart["rvol"].fillna(0)]
        figure.add_trace(
            go.Bar(
                x=chart["timestamp"], y=chart["rvol"], name="RVOL",
                marker_color=rvol_colors, opacity=0.65,
                hovertemplate="<b>RVOL</b><br>%{y:.2f}x<extra></extra>",
            ),
            row=4, col=1,
        )
        figure.add_hline(y=1.0, line_dash="dot", line_width=1, opacity=0.55, row=4, col=1)

    entry_low = _number(plan.get("entry_low"))
    entry_high = _number(plan.get("entry_high"))
    if _enabled(options, "entry", True) and entry_low is not None and entry_high is not None:
        low, high = sorted((entry_low, entry_high))
        figure.add_hrect(
            y0=low, y1=high,
            fillcolor="rgba(78,161,255,0.13)",
            line={"width": 1, "color": "rgba(78,161,255,0.65)"},
            row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=[latest_x], y=[(low + high) / 2.0], mode="markers+text",
                marker={"size": 15, "color": "#4ea1ff", "line": {"width": 1, "color": "white"}},
                text=["E"], textposition="middle center", textfont={"size": 9, "color": "white"},
                customdata=[[low, high]],
                hovertemplate="<b>Official Entry Zone</b><br>$%{customdata[0]:,.2f} – $%{customdata[1]:,.2f}<extra></extra>",
                showlegend=False, cliponaxis=False,
            ),
            row=1, col=1,
        )

    _add_level(
        figure, x_value=latest_x, value=_number(plan.get("max_chase")), name="Maximum Chase",
        symbol="M", dash="dot", line_color="#f5a623", marker_color="#f5a623",
        visible=_enabled(options, "max_chase", True),
    )
    _add_level(
        figure, x_value=latest_x, value=_number(plan.get("stop")), name="Official Stop",
        symbol="S", dash="dash", line_color="#ef5350", marker_color="#ef5350",
        visible=_enabled(options, "stop", True),
    )
    _add_level(
        figure, x_value=latest_x, value=_number(plan.get("t1")), name="Official T1",
        symbol="1", dash="dot", line_color="#d8b800", marker_color="#d8b800",
        visible=_enabled(options, "t1", True),
    )
    _add_level(
        figure, x_value=latest_x, value=_number(plan.get("t2")), name="Official T2",
        symbol="2", dash="dot", line_color="#ce5cff", marker_color="#ce5cff",
        visible=_enabled(options, "t2", True),
    )
    _add_level(
        figure, x_value=latest_x, value=_number(plan.get("t3")), name="Official T3",
        symbol="3", dash="dot", line_color="#37c5d6", marker_color="#37c5d6",
        visible=_enabled(options, "t3", True),
    )
    _add_level(
        figure, x_value=latest_x, value=_number(plan.get("support")), name="Official Support",
        symbol="D", dash="dashdot", line_color="#42c77a", marker_color="#42c77a",
        visible=_enabled(options, "support", True),
    )
    _add_level(
        figure, x_value=latest_x, value=_number(plan.get("resistance")), name="Official Resistance",
        symbol="R", dash="dashdot", line_color="#ff7043", marker_color="#ff7043",
        visible=_enabled(options, "resistance", True),
    )

    # Add future whitespace so hover symbols and the latest candle are not pressed against the edge.
    median_step = chart["timestamp"].diff().median()
    if pd.isna(median_step) or median_step <= pd.Timedelta(0):
        median_step = pd.Timedelta(days=1)
    right_edge = latest_x + median_step * 12

    figure.update_layout(
        title={"text": f"{symbol} · {timeframe}", "x": 0.01, "xanchor": "left"},
        height=980,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        hoverdistance=80,
        spikedistance=-1,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "left", "x": 0},
        margin={"l": 48, "r": 85, "t": 72, "b": 30},
        dragmode="pan",
        uirevision=f"{symbol}-{timeframe}",
        modebar_add=["drawline", "drawrect", "eraseshape"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"size": 12},
    )
    figure.update_xaxes(
        range=[chart["timestamp"].iloc[0], right_edge],
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikethickness=1,
        showline=True,
        linewidth=1,
        mirror=False,
        rangeslider_visible=False,
    )
    figure.update_yaxes(
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikethickness=1,
        automargin=True,
        fixedrange=False,
    )
    figure.update_yaxes(title_text="Price", tickformat="$.2f", row=1, col=1, secondary_y=False)
    figure.update_yaxes(title_text="Vol", showgrid=False, showticklabels=False, row=1, col=1, secondary_y=True)
    figure.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    figure.update_yaxes(title_text="MACD", row=3, col=1)
    figure.update_yaxes(title_text="RVOL", row=4, col=1)
    return figure
