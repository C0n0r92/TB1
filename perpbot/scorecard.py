#!/usr/bin/env python3
"""Per-strategy scorecard from fills.jsonl trade_closed records. Usage: .venv/bin/python scorecard.py [fills.jsonl]"""
import json, sys, os
from collections import defaultdict
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "fills.jsonl")
trades = []
if os.path.exists(path):
    for line in open(path):
        try: r = json.loads(line)
        except Exception: continue
        if r.get("event") == "trade_closed": trades.append(r)
if not trades: print(f"No closed trades yet in {path}"); sys.exit(0)
def stats(ts):
    rs = [t.get("pnl_r") or 0 for t in ts]; usd = [t.get("pnl_usd") or 0 for t in ts]; w = sum(1 for x in usd if x > 0)
    return len(ts), 100*w/len(ts), sum(rs), sum(rs)/len(rs), sum(usd)
by = defaultdict(list)
for t in trades:
    for s in (t.get("strategies_behind") or ["(none)"]): by[s].append(t)
hdr = f"{'strategy':<16}{'trades':>7}{'win%':>7}{'total R':>9}{'avg R':>8}{'P&L $':>10}"
print(hdr); print("-"*len(hdr))
for s in sorted(by, key=lambda k: -stats(by[k])[2]):
    n, wr, tr, ar, u = stats(by[s]); print(f"{s:<16}{n:>7}{wr:>6.0f}%{tr:>9.2f}{ar:>8.2f}{u:>10.2f}")
print("-"*len(hdr)); n, wr, tr, ar, u = stats(trades); print(f"{'ALL TRADES':<16}{n:>7}{wr:>6.0f}%{tr:>9.2f}{ar:>8.2f}{u:>10.2f}")
fees = sum(t.get("fees") or 0 for t in trades); fund = sum(t.get("funding") or 0 for t in trades)
print(f"fees ${fees:.4f}  funding ${fund:+.4f}")
er = defaultdict(list)
for t in trades: er[t.get("exit_reason")].append(t)
print("\nby exit reason:"); [print(f"  {k:<18}{len(v):>4} trades  {sum(x.get('pnl_r') or 0 for x in v):+.2f}R") for k, v in er.items()]
for c in sorted({t["coin"] for t in trades}):
    n, wr, tr, ar, u = stats([t for t in trades if t["coin"] == c]); print(f"  {c}: {n} trades, win {wr:.0f}%, {tr:+.2f}R, ${u:+.2f}")
