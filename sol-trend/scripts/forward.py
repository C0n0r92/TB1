"""Live PAPER forward test (no orders, no accounts, no keys). Every 5 min: append newly closed SOLUSDT 5m bars (data-api.binance.vision, public),
refresh Hyperliquid funding hourly, re-run the same engine for the selected configs, and log NEW paper trades that ENTER after the forward start
into ../ledger.jsonl (events: open / close). Same fill model as the backtest: entry at the 5m open after TF close + 5-min bot cycle, fee+0.2% slip/side."""
import os, sys, json, time, urllib.request, traceback
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
ROOT = C.ROOT; LOG = os.path.join(ROOT, "logs"); LEDGER = os.path.join(ROOT, "ledger.jsonl"); STATE = os.path.join(LOG, "forward_state.json")
CADENCE = int(os.environ.get("CADENCE_S", "300")); UA = {"User-Agent": "sol-trend-paper-research/0.1"}
REASON = {0: "stop", 1: "target", 2: "trail", 3: "time", 4: "open"}
# Top configs by 25-pt score per track (NONE is a candidate - forward run is for monitoring/out-of-sample evidence only)
CONFIGS = [
    dict(track="A", side="long", venue="spot", tf="1h", trend="ema200up", level="pivot", confirm="vol", stop=1.5, exit="rr2"),
    dict(track="A", side="long", venue="spot", tf="1h", trend="ema50_200", level="pivot", confirm="vol", stop=1.5, exit="rr2"),
    dict(track="A", side="long", venue="spot", tf="1h", trend="ema50_200", level="n20", confirm="close", stop=2.5, exit="trail3"),
    dict(track="B", side="ls", venue="jup", tf="1h", trend="ema50_200", level="n20", confirm="close", stop=2.5, exit="rr3"),
    dict(track="B", side="ls", venue="jup", tf="1h", trend="htf", level="n20", confirm="vol", stop=2.5, exit="rr2"),
    dict(track="B", side="ls", venue="jup", tf="4h", trend="ema200up", level="n55", confirm="close", stop=2.5, exit="trail3"),
]
def log(*a): print(time.strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)
def get(url, data=None, hdr=UA):
    req = urllib.request.Request(url, data=data, headers=hdr)
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
def update_candles():
    p = os.path.join(C.DATA, "SOLUSDT_5m.csv"); d = pd.read_csv(p); last = int(d.t.iloc[-1]); new = []
    while True:
        k = get(f"https://data-api.binance.vision/api/v3/klines?symbol=SOLUSDT&interval=5m&startTime={last + 300000}&limit=1000")
        k = [r for r in k if r[0] + 300000 <= time.time() * 1000]       # closed bars only
        if not k: break
        new += k; last = int(k[-1][0])
        if len(k) < 999: break
    if new:
        df = pd.DataFrame(new, columns="t o h l c v ct qv n tbv tqv x".split())[["t", "o", "h", "l", "c", "v", "qv", "n"]].astype(float); df["t"] = df.t.astype("int64")
        df.to_csv(p, mode="a", header=False, index=False)
    return len(new), last
def update_funding():
    p = os.path.join(C.DATA, "HL_SOL_funding.csv"); f = pd.read_csv(p); last = int(f.t.iloc[-1])
    if time.time() - last < 3700: return 0
    d = get("https://api.hyperliquid.xyz/info", json.dumps({"type": "fundingHistory", "coin": "SOL", "startTime": (last + 1) * 1000}).encode(), {**UA, "Content-Type": "application/json"})
    rows = [(int(x["time"] // 1000), float(x["fundingRate"])) for x in d if x["time"] // 1000 > last]
    if rows: pd.DataFrame(rows, columns=["t", "rate"]).to_csv(p, mode="a", header=False, index=False)
    return len(rows)
def cycle(state):
    n5, last = update_candles()
    try: nf = update_funding()
    except Exception as e: nf = f"funding err {e}"
    S = C.Sim(); start = state["fwd_start"]; out = []
    for V in CONFIGS:
        nm = C.name(V); tr = S.run(dict(V, cycle=5)); tr = tr[tr[:, 0] >= start]
        for row in tr:
            et, xt, d, pe, px, net, rs = row; key = f"{nm}|{int(et)}"
            ev = {"strategy": nm, "track": V["track"], "venue": V["venue"], "side": "long" if d > 0 else "short", "entry_t": pd.to_datetime(int(et), unit="s").isoformat() + "Z",
                  "entry_px": round(float(pe), 4), "paper": True, "cost_model": f"fee {C.FEE[V['venue']]*100:.2f}% + slip 0.20%/side", "logged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            if key + "|open" not in state["seen"]:
                out.append({"event": "open", **ev}); state["seen"].append(key + "|open")
            if int(rs) != 4 and key + "|close" not in state["seen"]:
                out.append({"event": "close", **ev, "exit_t": pd.to_datetime(int(xt), unit="s").isoformat() + "Z", "exit_px": round(float(px), 4),
                            "net_ret_pct": round(float(net) * 100, 3), "reason": REASON[int(rs)]}); state["seen"].append(key + "|close")
    with open(LEDGER, "a") as f:
        for e in out: f.write(json.dumps(e) + "\n")
    hb = {"ts": int(time.time()), "last_candle_open": pd.to_datetime(last // 1000, unit="s").isoformat() + "Z", "new_bars": n5, "funding_new": nf, "events": len(out), "pid": os.getpid()}
    json.dump(hb, open(os.path.join(LOG, "forward.heartbeat"), "w")); json.dump(state, open(STATE, "w"))
    log("cycle ok", hb)
def main():
    open(os.path.join(LOG, "forward.pid"), "w").write(str(os.getpid()))
    if os.path.exists(STATE): state = json.load(open(STATE))
    else:
        state = {"fwd_start": int(time.time()) // 300 * 300, "seen": []}
        with open(LEDGER, "a") as f:
            f.write(json.dumps({"event": "forward_start", "t": pd.to_datetime(state["fwd_start"], unit="s").isoformat() + "Z", "paper": True,
                                "configs": [C.name(V) + f"_{V['venue']}" for V in CONFIGS], "note": "no config met the 18/25 bar; monitoring only"}) + "\n")
        json.dump(state, open(STATE, "w"))
    while True:
        t0 = time.time()
        try: cycle(state)
        except Exception: log("cycle error", traceback.format_exc().replace("\n", " | "))
        nxt = (int(time.time()) // CADENCE + 1) * CADENCE + 20   # 20 s after each 5-min boundary
        time.sleep(max(5, nxt - time.time()))
if __name__ == "__main__": main()
