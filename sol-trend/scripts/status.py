"""Print forward-test health, paper trades per strategy, top backtest scores and blockers. Read-only."""
import os, json, time, pandas as pd
R = "/workspace/sol-trend"; L = R + "/logs"
def alive(f):
    try: p = int(open(f).read().strip()); os.kill(p, 0); return p, True
    except Exception: return None, False
blk = []
for n in ("supervisor", "forward"):
    p, ok = alive(f"{L}/{n}.pid"); print(f"{n:10s} pid={p} alive={ok}"); ok or blk.append(f"{n} not running (start: scripts/start_forward.sh)")
try:
    hb = json.load(open(f"{L}/forward.heartbeat")); age = time.time() - hb["ts"]
    print(f"heartbeat {age/60:.1f} min ago | last 5m candle open {hb['last_candle_open']} | cadence 5 min")
    if age > 1200: blk.append(f"heartbeat stale {age/60:.0f} min")
    lc = pd.Timestamp(hb["last_candle_open"]).timestamp()
    if time.time() - lc > 1500: blk.append("candles stale (>25 min) - data-api.binance.vision unreachable?")
except Exception as e: blk.append(f"no heartbeat ({e})")
ev = [json.loads(x) for x in open(R + "/ledger.jsonl")] if os.path.exists(R + "/ledger.jsonl") else []
st = next((e for e in ev if e["event"] == "forward_start"), None)
print("forward start:", st and st["t"]); rows = {}
for c in (st or {}).get("configs", []): rows[c.rsplit("_", 1)[0]] = {"opened": 0, "closed": 0, "open_now": 0, "net_pct": 0.0, "wins": 0}
for e in ev:
    if e["event"] not in ("open", "close"): continue
    r = rows.setdefault(e["strategy"], {"opened": 0, "closed": 0, "open_now": 0, "net_pct": 0.0, "wins": 0})
    if e["event"] == "open": r["opened"] += 1
    else: r["closed"] += 1; r["net_pct"] += e["net_ret_pct"]; r["wins"] += e["net_ret_pct"] > 0
for r in rows.values(): r["open_now"] = r["opened"] - r["closed"]; r["net_pct"] = round(r["net_pct"], 2)
print("\nPAPER forward trades (mid 0.2% slip; nothing is traded for real):"); print(pd.DataFrame(rows).T.astype({"opened":int,"closed":int,"open_now":int,"wins":int}).to_string() if rows else "  none")
try:
    lb = pd.read_csv(R + "/leaderboard.csv"); cols = [c for c in ["track", "id", "role", "sc_total", "trades_12m", "pnl_12m_pct", "pnl_oos", "pnl_pre", "nbr_pos", "candidate"] if c in lb.columns]
    print("\nTop backtest scores (25-pt):"); print(lb.sort_values("sc_total", ascending=False).groupby("track").head(3)[cols].to_string(index=False))
    if not lb.get("candidate", pd.Series([False])).any(): blk.append("no config reached 18/25 with stable neighbours - nothing to hand to Zero (Lab reviews first)")
except Exception as e: blk.append(f"leaderboard unreadable ({e})")
try:
    errs = [x for x in open(f"{L}/forward.log").read().splitlines()[-50:] if "error" in x.lower()]
    if errs: blk.append(f"{len(errs)} recent errors in forward.log, last: {errs[-1][:200]}")
except Exception: pass
print("\nBLOCKERS:" if blk else "\nBLOCKERS: none"); [print(" -", b) for b in blk]
