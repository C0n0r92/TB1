#!/usr/bin/env python3
"""Print radar mints (data/tokens.txt 'radar' rows) whose first runner-radar signal is within the last N days (default 2).
Mints with no parsable signal time are printed too (fail open). Read-only."""
import json, os, sys, time
from datetime import datetime
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
days = float(sys.argv[1]) if len(sys.argv) > 1 else 2
radar = [l.split()[0] for l in open(os.path.join(B, "data", "tokens.txt")) if l.strip().endswith("radar")]
first = {}
def ts(v):
    if isinstance(v, (int, float)): return v / 1000 if v > 1e12 else v
    try: return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except Exception: return None
for l in open("/workspace/runner-radar/signals.jsonl"):
    try: j = json.loads(l)
    except Exception: continue
    m = j.get("mint") or j.get("token") or j.get("token_address") or j.get("address")
    t = ts(j.get("ts") or j.get("time") or j.get("timestamp") or j.get("at"))
    if m and t and (m not in first or t < first[m]): first[m] = t
for m in radar:
    if m not in first or first[m] >= time.time() - days * 86400: print(m)
