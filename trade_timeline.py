from __future__ import annotations
from trade_models import TradeRecord

def build_trade_timeline(trade, orders, executions):
    events=[]
    if trade.plan_id: events.append({'event_at':trade.plan_created_at or trade.created_at,'event_type':'plan','title':'Official Plan Saved','description':f'Plan {trade.plan_id}','source':'MomoPro AI','confidence':100})
    for e in executions:
        if e.matched_trade_id==trade.id: events.append({'event_at':e.executed_at,'event_type':'execution','title':f'{e.side.title()} Filled','description':f'{e.quantity:g} shares at ${e.price:.4f}','source':'Webull','confidence':100})
    for o in orders:
        if o.matched_trade_id==trade.id and o.status.upper().replace('LED','LLED') in {'CANCELLED','CANCELED'}: events.append({'event_at':o.updated_at,'event_type':'order_cancelled','title':o.purpose,'description':f'{o.side} {o.order_type} order canceled; stop ${o.stop_price or o.limit_price:.4f}' if (o.stop_price or o.limit_price) else f'{o.side} {o.order_type} order canceled','source':'Webull','confidence':o.purpose_confidence})
    for u in trade.updates: events.append({'event_at':u.date,'event_type':'management','title':u.update_type,'description':u.note,'source':'Journal','confidence':100})
    events.sort(key=lambda x:str(x.get('event_at') or ''))
    trade.timeline=events; return events
