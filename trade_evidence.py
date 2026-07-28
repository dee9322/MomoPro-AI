from __future__ import annotations
from broker_models import BrokerOrder, BrokerExecution
from trade_models import TradeRecord
from trade_classification import classify_trade

def refresh_trade_evidence(trades, orders, executions):
    for t in trades:
        ev=[]
        if t.plan_id: ev.append({'evidence_type':'official_plan','label':'Official Plan snapshot','source':'MomoPro AI','observed_at':t.plan_created_at or t.created_at,'confidence':100,'details':{'plan_id':t.plan_id,'completeness':t.plan_completeness}})
        matched_exec=[e for e in executions if e.matched_trade_id==t.id]
        if matched_exec: ev.append({'evidence_type':'broker_execution','label':f'{len(matched_exec)} broker execution(s)','source':'Webull','observed_at':max(e.executed_at for e in matched_exec),'confidence':100,'details':{'execution_ids':[e.execution_id for e in matched_exec]}})
        matched_orders=[o for o in orders if o.matched_trade_id==t.id]
        stops=[o for o in matched_orders if 'Stop' in o.purpose]
        if stops: ev.append({'evidence_type':'protective_stop','label':f'{len(stops)} protective-stop order(s)','source':'Webull','observed_at':max(o.updated_at for o in stops),'confidence':max(o.purpose_confidence for o in stops),'details':{'orders':[{'order_id':o.order_id,'stop_price':o.stop_price or o.limit_price,'status':o.status,'purpose':o.purpose} for o in stops]}})
        t.evidence=ev; classify_trade(t)
    return trades
