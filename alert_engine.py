from __future__ import annotations

import json, os, tempfile, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from alert_rules import evaluate_rule

PATH = Path(os.getenv("MOMOPRO_ALERT_PATH", "alert_data.json"))
DEFAULT = {"rules": [], "events": []}

def _now(): return datetime.now(timezone.utc)
def _iso(): return _now().isoformat()

def load_alerts():
    if not PATH.exists(): save_alerts(DEFAULT)
    try:
        data=json.loads(PATH.read_text(encoding="utf-8"))
    except Exception:
        data=json.loads(json.dumps(DEFAULT)); save_alerts(data)
    data.setdefault("rules",[]); data.setdefault("events",[]); return data

def save_alerts(data):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=PATH.name,suffix=".tmp",dir=str(PATH.parent))
    with os.fdopen(fd,"w",encoding="utf-8") as f: json.dump(data,f,indent=2)
    os.replace(tmp,PATH)

def create_rule(name, symbols, rule_type, value, cooldown_hours=24):
    data=load_alerts(); rule={"id":uuid.uuid4().hex,"name":name.strip() or rule_type,"symbols":sorted(set(symbols)),"type":rule_type,"value":value,"enabled":True,"cooldown_hours":int(cooldown_hours),"last_triggered":{},"created_at":_iso()}; data["rules"].append(rule); save_alerts(data); return rule

def set_rule_enabled(rule_id, enabled):
    data=load_alerts()
    for rule in data["rules"]:
        if rule["id"]==rule_id: rule["enabled"]=bool(enabled)
    save_alerts(data)

def delete_rule(rule_id):
    data=load_alerts(); data["rules"]=[r for r in data["rules"] if r["id"]!=rule_id]; save_alerts(data)

def evaluate_alerts(items_by_symbol: Dict[str,Any]) -> List[Dict[str,Any]]:
    data=load_alerts(); triggered=[]
    for rule in data["rules"]:
        if not rule.get("enabled",True): continue
        for symbol in rule.get("symbols",[]):
            item=items_by_symbol.get(symbol)
            if not item: continue
            last=rule.get("last_triggered",{}).get(symbol)
            if last:
                try:
                    if _now()-datetime.fromisoformat(last) < timedelta(hours=int(rule.get("cooldown_hours",24))): continue
                except ValueError: pass
            snap=item.to_dict() if hasattr(item,"to_dict") else item
            met,details=evaluate_rule(rule,snap)
            if met:
                event={"id":uuid.uuid4().hex,"timestamp":_iso(),"rule_id":rule["id"],"rule_name":rule["name"],"symbol":symbol,"details":details,"read":False,"snapshot":snap}
                data["events"].insert(0,event); triggered.append(event); rule.setdefault("last_triggered",{})[symbol]=event["timestamp"]
                item.timeline.append({"timestamp":event["timestamp"],"event":"Alert triggered","details":f"{rule['name']}: {details}"})
    save_alerts(data); return triggered

def mark_event_read(event_id=None):
    data=load_alerts()
    for event in data["events"]:
        if event_id is None or event["id"]==event_id: event["read"]=True
    save_alerts(data)

def clear_events():
    data=load_alerts(); data["events"]=[]; save_alerts(data)
