from __future__ import annotations
from datetime import datetime
from trade_models import TradeRecord

def _dt(v):
    try: return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except Exception: return None

def plan_completeness(trade: TradeRecord) -> float:
    fields=[trade.entry_price, trade.shares, trade.initial_stop, trade.t1, trade.t2, trade.t3, trade.setup, trade.thesis, trade.invalidation]
    return round(100*sum(v not in (None,"",0,0.0) for v in fields)/len(fields),1)

def classify_trade(trade: TradeRecord) -> TradeRecord:
    completeness=max(float(trade.plan_completeness or 0), plan_completeness(trade) if trade.plan_id else 0)
    trade.plan_completeness=completeness
    entry=_dt(trade.entry_date); created=_dt(trade.plan_created_at)
    pre_entry=bool(trade.plan_id and created and entry and created <= entry)
    managed=bool(trade.updates and pre_entry)
    if managed:
        mode,reason='live_managed','A pre-entry Official Plan exists and management events were recorded.'
    elif pre_entry and completeness >= 75:
        mode,reason='verified_plan','A sufficiently complete Official Plan was saved before the first entry.'
    elif pre_entry:
        mode,reason='partial_plan','A pre-entry plan exists, but some planning evidence is incomplete.'
    elif trade.broker_execution_ids:
        mode,reason='historical_reconstruction','Broker executions exist without a qualifying pre-entry Official Plan.'
    else:
        mode,reason='imported_only','There is not enough verified planning or broker evidence for reconstruction.'
    trade.review_mode=mode; trade.classification_reason=reason
    base={'live_managed':98,'verified_plan':94,'partial_plan':80,'historical_reconstruction':65,'imported_only':35}[mode]
    evidence_bonus=min(len(trade.evidence)*2,10)
    trade.intelligence_score=min(100,base+evidence_bonus)
    return trade

def classification_label(mode: str) -> str:
    return {'live_managed':'Live Managed','verified_plan':'Verified Plan','partial_plan':'Partial Plan','historical_reconstruction':'Historical Reconstruction','imported_only':'Imported
