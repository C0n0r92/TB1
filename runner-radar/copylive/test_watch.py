#!/usr/bin/env python3
"""offline tests for watch.py/record.py: temp dir, fake clock/prices/wallet; no network, no trading."""
import os, sys, json, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common, watch, record, checks
from common import F, iso, parse_iso

tmp = tempfile.mkdtemp(); sig = os.path.join(tmp, "paper.jsonl")
for kk in F: F[kk] = os.path.join(tmp, os.path.basename(F[kk]))
watch.ingest.__defaults__ = (sig,)
MINT = "TestMint1111111111111111111111111111111pump"
clock = {"t": parse_iso("2026-10-24T00:30:00Z")}      # 01:30 Dublin
price = {"px": 0.0010}; bal = {"sol": 0.928213}
def fake_now(): return clock["t"]
for mod in (common, watch, record): mod.now = fake_now
watch.dex_pairs = record.dex_pairs = lambda ms: {m: dict(mint=m, ticker="TEST", price=price["px"], mcap=2e6, liq=3e5,
    created=clock["t"] - 7200, pair="P", url="https://dexscreener.com/solana/P", m5=1.0) for m in ms}
watch.sol_balance = lambda addr=None: bal["sol"]
watch.sol_usd = record.sol_usd = lambda: 100.0
watch.live_leaders = lambda: ["_benjitrades"]
checks.rug_check = lambda mint, d, t, scout=True: (True, {"rejects": [], "notes": []})
checks.route_check = lambda mint, s, p, x: (True, {"impact": 0.001, "route": "fake"})
st = watch.new_state(); fails = 0
def ev(**kw):
    with open(sig, "a") as f: f.write(json.dumps(kw) + "\n")
def T(name, cond):
    global fails; print(("ok   " if cond else "FAIL ") + name); fails += 0 if cond else 1
def step(dt=5):
    global st
    clock["t"] += dt
    st = {**watch.new_state(), **(common.load(F["state"], None) or st)}
    a = watch.tick(st); common.save(F["state"], st); return a

# 1. fresh first buy + entry from LIVE leader -> BUY
lt = iso(clock["t"] - 10)
ev(ts=iso(clock["t"] - 5), event="leader_swap", leader="_benjitrades", side="buy", mint=MINT, usd=500, fill_px=0.00098, pre_bal=0, detect_lag_s=5)
ev(ts=iso(clock["t"] - 1), event="entry", pos="p1", leader="_benjitrades", mint=MINT, leader_px=0.00098, chase=0.01, mcap=2e6, liq=3e5, forced=False)
a = step(); T("BUY emitted", a and a["type"] == "BUY" and a["size_sol"] == 0.092 and abs(a["chase_pct"] - 2.04) < 0.1)
T("night-start written", common.load(F["night"], {}).get("sol") == 0.928213)
T("no duplicate BUY", step() is None)
# skip: not live leader
ev(ts=iso(clock["t"]), event="leader_swap", leader="bystevenr", side="buy", mint="M2", usd=500, fill_px=1, pre_bal=0, detect_lag_s=1)
ev(ts=iso(clock["t"]), event="entry", pos="p2", leader="bystevenr", mint="M2", leader_px=1, chase=0, mcap=2e6, liq=3e5)
step(); sk = [json.loads(l) for l in open(F["skips"])]
T("non-live leader skipped+logged", sk[-1]["reason"] == "leader_not_live")
# record fill
record.main(["buy", MINT, "0.092", "92", "0.001", "_benjitrades", "0.00098", lt])
T("position open", common.load(F["positions"], {})[MINT]["status"] == "open")
# 2. leader adds, price +45% -> TP deferred
ev(ts=iso(clock["t"]), event="leader_swap", leader="_benjitrades", side="buy", mint=MINT, usd=200, fill_px=0.0012, pre_bal=1, detect_lag_s=1)
price["px"] = 0.00145
T("TP1 deferred while leader adds", step() is None)
clock["t"] += 600
a = step(); T("TP1 after 10 min without adds", a and a["kind"] == "tp1" and a["fraction"] == 0.25 and a["sell_pct_of_holding"] == 25.0)
T("TP1 not re-emitted within 3 min", step(60) is None)
a = step(200); T("TP1 re-emitted after 3 min without fill", a and a["kind"] == "tp1" and a.get("reemit_of"))
record.main(["sell", MINT, "0.25", "0.03", "tp_+40%_25%"])
# 3. peak 1.8 then trail
price["px"] = 0.0018; T("no action at 1.8x", step() is None)
price["px"] = 0.00134; a = step(); T("trail 25% below peak", a and a["kind"] == "trail" and a["fraction"] == 0.75 and a["sell_pct_of_holding"] == 100)
record.main(["clear", MINT])
# 4. leader sells -> mirror (keep 10%); priority over trail? trail is a stop -> sl first; set price back up
price["px"] = 0.0016
ev(ts=iso(clock["t"]), event="leader_swap", leader="_benjitrades", side="sell", mint=MINT, usd=900, fill_px=0.0016, pre_bal=5, detect_lag_s=1)
a = step(); T("leader-sold mirror: sell 65% of original (keep 10%)", a and a["kind"] == "leader_sold" and a["fraction"] == 0.65)
record.main(["sell", MINT, "0.65", "0.1", "leader_sold_keep10"])
T("leftover ignores trail", step() is None)
price["px"] = 0.0061; a = step(); T("moonbag at +500%", a and a["kind"] == "moon" and a["fraction"] == 0.1)
record.main(["sell", MINT, "0.1", "0.05", "tp_leftover_+500%"])
P = common.load(F["positions"], {}); T("closed with pnl", any(v["status"] == "closed" and v.get("pnl_sol") for v in P.values()))
# 5. stop -15% + halt
M3 = "Mint3"; price["px"] = 0.001
ev(ts=iso(clock["t"]), event="leader_swap", leader="_benjitrades", side="buy", mint=M3, usd=100, fill_px=0.001, pre_bal=0, detect_lag_s=1)
ev(ts=iso(clock["t"]), event="entry", pos="p3", leader="_benjitrades", mint=M3, leader_px=0.001, chase=0)
a = step(); T("second BUY", a and a["type"] == "BUY")
record.main(["buy", M3, "0.09", "9000", "0.001", "_benjitrades", "0.001", iso(clock["t"])])
price["px"] = 0.00084; a = step(); T("stop -15%", a and a["kind"] == "sl" and a["reason"] == "sl_-15%")
record.main(["clear", M3])
bal["sol"] = 0.60; st["bal_cache"] = {}; common.save(F["state"], st)
a = step(31); T("night halt -> SELL_ALL", a and a["type"] == "SELL_ALL" and a["reason"].startswith("night_halt"))
ev(ts=iso(clock["t"]), event="leader_swap", leader="_benjitrades", side="buy", mint="M4", usd=100, fill_px=0.001, pre_bal=0, detect_lag_s=1)
ev(ts=iso(clock["t"]), event="entry", pos="p4", leader="_benjitrades", mint="M4", leader_px=0.001, chase=0)
step(); sk = [json.loads(l) for l in open(F["skips"])]
T("no BUY after halt", any(s.get("reason") == "night_halt" and s.get("pos") == "p4" for s in sk))
record.main(["sell", M3, "1", "0.07", "night_halt_-20%"])
# 6. 07:45 close + entry window
common.save(F["night"], {}); st = {**watch.new_state()}; common.save(F["state"], {**st, "cursor": os.path.getsize(sig)})
bal["sol"] = 0.9
clock["t"] = parse_iso("2026-10-24T06:40:00Z")   # 07:40 Dublin (IST+1 in Oct)
price["px"] = 0.001
ev(ts=iso(clock["t"]), event="leader_swap", leader="_benjitrades", side="buy", mint="M5", usd=100, fill_px=0.001, pre_bal=0, detect_lag_s=1)
ev(ts=iso(clock["t"]), event="entry", pos="p5", leader="_benjitrades", mint="M5", leader_px=0.001, chase=0)
a = step(); T("BUY at 07:40 Dublin", a and a["type"] == "BUY")
record.main(["buy", "M5", "0.09", "90", "0.001", "_benjitrades", "0.001", iso(clock["t"])])
clock["t"] = parse_iso("2026-10-24T06:45:10Z"); a = step(1)
T("SELL_ALL at 07:45 Dublin", a and a["type"] == "SELL_ALL" and a["reason"] == "close_0745_dublin")
ev(ts=iso(clock["t"]), event="leader_swap", leader="_benjitrades", side="buy", mint="M6", usd=100, fill_px=0.001, pre_bal=0, detect_lag_s=1)
ev(ts=iso(clock["t"]), event="entry", pos="p6", leader="_benjitrades", mint="M6", leader_px=0.001, chase=0)
step(); sk = [json.loads(l) for l in open(F["skips"])]
T("no entry 07:45-08:00", any(s.get("pos") == "p6" and s["reason"] == "outside_entry_hours" for s in sk))
# 7. late signal & chase
clock["t"] = parse_iso("2026-10-24T01:00:00Z")
ev(ts=iso(clock["t"] - 200), event="leader_swap", leader="_benjitrades", side="buy", mint="M7", usd=100, fill_px=0.001, pre_bal=0, detect_lag_s=1)
ev(ts=iso(clock["t"] - 190), event="entry", pos="p7", leader="_benjitrades", mint="M7", leader_px=0.001, chase=0)
ev(ts=iso(clock["t"]), event="leader_swap", leader="_benjitrades", side="buy", mint="M8", usd=100, fill_px=0.0009, pre_bal=0, detect_lag_s=1)
ev(ts=iso(clock["t"]), event="entry", pos="p8", leader="_benjitrades", mint="M8", leader_px=0.0009, chase=0)
record.main(["sell", "M5", "1", "0.09", "close_0745_dublin"])
step(); sk = {s.get("pos"): s["reason"] for s in map(json.loads, open(F["skips"])) if s.get("pos")}
T("late >3 min skipped", sk.get("p7") == "too_late_gt_3min"); T("chase 11% skipped", sk.get("p8") == "chase_gt_8pct")
T("size rule", common.size_sol(0.928213) == 0.092 and common.size_sol(0.025) == 0.0 and common.size_sol(0.1) == 0.01)
print("tmp:", tmp); print("FAILURES:", fails); sys.exit(1 if fails else 0)
