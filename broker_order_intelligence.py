from __future__ import annotations
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any
from broker_models import BrokerOrder
from trade_models import TradeRecord

def _dt(v):
    try: return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except Exception: return None

def order_fingerprint(order: dict[str,Any]) -> str:
    raw='|'.join(str(order.get(k,'') or '') for k in ('account_id','order_id','symbol','side','status','quantity','filled_quantity','limit_price','stop_price','created_at','updated_at'))
    return sha256(raw.encode()).hexdigest()

def to_broker_order(order: dict[str,Any]) -> BrokerOrder:
    return BrokerOrder(fingerprint=order_fingerprint(order), account_id=str(order.get('account_id') or ''), order_id=str(order.get('order_id') or ''), client_order_id=str(order.get('client_order_id') or ''), broker_order_id=str(order.get('broker_order_id') or ''), symbol=str(order.get('symbol') or '').upper(), side=str(order.get('side') or '').upper(), status=str(order.get('status') or 'Unknown'), order_type=str(order.get('order_type') or ''), quantity=float(order.get('quantity') or 0), filled_quantity=float(order.get('filled_quantity') or 0), average_price=float(order.get('average_price') or 0), limit_price=float(order.get('limit_price') or 0), stop_price=float(order.get('stop_price') or 0), created_at=str(order.get('created_at') or ''), updated_at=str(order.get('updated_at') or ''), raw=order.get('raw') if isinstance(order.get('raw'),dict) else {})

def merge_orders(existing: list[BrokerOrder], normalized: list[dict[str,Any]]) -> list[BrokerOrder]:
    by_key={(o.account_id,o.order_id):o for o in existing}
    for row in normalized:
        incoming=to_broker_order(row); key=(incoming.account_id,incoming.order_id)
        old=by_key.get(key)
        if old:
            for name in incoming.__dataclass_fields__:
                value=getattr(incoming,name)
                if name not in {'id','matched_trade_id','purpose','purpose_confidence','relationship_group'} and value not in ('',None,0,0.0,{}): setattr(old,name,value)
            old.status=incoming.status or old.status; old.updated_at=incoming.updated_at or old.updated_at
        else: by_key[key]=incoming
    return list(by_key.values())

def link_and_classify_orders(orders: list[BrokerOrder], trades: list[TradeRecord]) -> list[BrokerOrder]:
    for order in orders:
        candidates=[t for t in trades if t.symbol==order.symbol]
        ot=_dt(order.updated_at or order.created_at)
        candidates=[t for t in candidates if not ot or not _dt(t.entry_date) or _dt(t.entry_date) <= ot+timedelta(days=2)]
        candidates.sort(key=lambda t: abs((ot-_dt(t.entry_date)).total_seconds()) if ot and _dt(t.entry_date) else 10**18)
        trade=candidates[0] if candidates else None
        if trade:
            order.matched_trade_id=trade.id; order.relationship_group=trade.id
            if order.order_id and order.order_id not in trade.broker_order_ids: trade.broker_order_ids.append(order.order_id)
        status=order.status.upper().replace(' ','_').replace('-','_')
        typ=order.order_type.upper().replace(' ','_').replace('-','_')
        if order.side=='SELL' and ('STOP' in typ or order.stop_price>0):
            order.purpose='Confirmed Protective Stop' if trade else 'Likely Protective Stop'; order.purpose_confidence=98 if trade else 82
        elif order.side=='SELL' and status in {'CANCELLED','CANCELED'} and trade and order.quantity and abs(order.quantity-trade.remaining_shares) <= max(1,trade.shares*.05):
            order.purpose='Likely Protective Stop'; order.purpose_confidence=84
        elif order.side=='SELL' and order.limit_price>trade.entry_price if trade else False:
            order.purpose='Profit-Taking Order'; order.purpose_confidence=82
        elif status in {'CANCELLED','CANCELED'}:
            order.purpose='Canceled Order — Purpose Unknown'; order.purpose_confidence=35
        else:
            order.purpose='Execution / Position Order'; order.purpose_confidence=90 if order.filled_quantity else 55
    return orders
