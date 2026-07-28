from __future__ import annotations
from datetime import datetime, timedelta, timezone
import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from indicators import calculate_indicators
from trade_models import TradeRecord

def _dt(v):
    d=datetime.fromisoformat(str(v).replace('Z','+00:00')); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def _grade(score): return 'A' if score>=90 else 'A-' if score>=85 else 'B+' if score>=80 else 'B' if score>=75 else 'B-' if score>=70 else 'C+' if score>=65 else 'C' if score>=55 else 'D'

def reconstruct_trade(trade: TradeRecord, api_key: str, secret_key: str) -> dict:
    entry=_dt(trade.entry_date); start=entry-timedelta(days=420); end=entry+timedelta(days=3)
    client=StockHistoricalDataClient(api_key,secret_key)
    raw=client.get_stock_bars(StockBarsRequest(symbol_or_symbols=trade.symbol,timeframe=TimeFrame.Day,start=start,end=end,feed=DataFeed.IEX)).df
    if raw is None or raw.empty: raise RuntimeError('No historical candles were returned for this trade.')
    frame=raw.reset_index(); frame=frame[frame['symbol'].astype(str).str.upper()==trade.symbol] if 'symbol' in frame else frame
    frame['timestamp']=pd.to_datetime(frame['timestamp'],utc=True); frame=calculate_indicators(frame.sort_values('timestamp'))
    frozen=frame[frame['timestamp'] <= pd.Timestamp(entry)].copy()
    if frozen.empty: raise RuntimeError('No candle existed at or before the entry timestamp.')
    r=frozen.iloc[-1]; price=float(trade.entry_price); ema21=float(r.get('ema21') or price); ema50=float(r.get('ema50') or price); ema200=float(r.get('ema200') or price)
    dist=(price-ema21)/ema21*100 if ema21 else 0; score=50
    score += 12 if price>ema21 else -8; score += 10 if ema21>ema50 else -5; score += 8 if ema50>ema200 else 0
    rsi=float(r.get('rsi14') or 50); score += 8 if 45<=rsi<=68 else 2 if 35<=rsi<=75 else -6
    rvol=float(r.get('rvol') or 0); score += 7 if rvol>=1.1 else 2 if rvol>=0.8 else -3
    score += 7 if abs(dist)<=3 else 2 if abs(dist)<=6 else -8
    score=max(0,min(100,score))
    setup='EMA21 Reclaim / Continuation' if price>=ema21 and abs(dist)<=3 else 'Trend Continuation' if price>ema21>ema50 else 'Pullback / Reversal Candidate'
    result={'as_of':pd.Timestamp(r['timestamp']).isoformat(),'objective_entry_score':round(score,1),'objective_entry_grade':_grade(score),'likely_setup':setup,'setup_confidence':round(min(95,55+abs(score-50)),1),'entry_context':{'entry_price':price,'ema21':round(ema21,4),'ema50':round(ema50,4),'ema200':round(ema200,4),'distance_from_ema21_pct':round(dist,2),'rsi14':round(rsi,2),'rvol':round(rvol,2),'atr_pct':round(float(r.get('atr_pct') or 0),2)},'personal_thesis':'Unknown — not recorded','planned_targets':'Unknown — not recorded' if not any([trade.t1,trade.t2,trade.t3]) else 'Available from journal','rule_following':'Not gradable without a verified pre-entry plan','hindsight_guard':'Entry analysis used only candles available at or before the entry timestamp.'}
    trade.reconstruction=result; return result
