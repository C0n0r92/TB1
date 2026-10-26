import sys, json, time, pickle, os
sys.argv = ["scalper.py", "--dry-run"]; sys.path.insert(0, "/workspace/hlscalp"); os.chdir("/workspace/hlscalp")
import scalper as S
import pandas as pd
from multiprocessing import Pool
N = 288; M15 = 900_000; H1 = 3_600_000
uni = [u["coin"] for u in json.load(open("/workspace/hlscalp/state.json"))["universe"]]
cache = "/workspace/review/swing/cndl.pkl"
def fetch(coin, iv, bars):
    ms = {"15m": M15, "1h": H1}[iv]; end = S.nms()
    for k in range(5):
        try:
            raw = S.info.candles_snapshot(coin, iv, end - bars * ms, end); df = pd.DataFrame(raw)
            for c in "ohlcv": df[c] = df[c].astype(float)
            return df[df["T"] < end].reset_index(drop=True)
        except Exception as x: time.sleep(3 * (k + 1))
    raise RuntimeError(coin)
if os.path.exists(cache): D = pickle.load(open(cache, "rb"))
else:
    D = {}
    for c in ["BTC"] + uni:
        D[c] = (fetch(c, "15m", N + 262), fetch(c, "1h", 72 + 125)); time.sleep(1.2)
    pickle.dump(D, open(cache, "wb"))
base = list(S.cfg["trigger_strats"]); B = [s for s in base if s != "VPROFILE"] + ["SWING_BRK"]
def run(coin):
    m, h = D[coin]; bm, bh = D["BTC"]; out = []
    for k in range(len(m) - N, len(m)):
        m15 = m.iloc[max(0, k - 249):k + 1].reset_index(drop=True); tc = int(m15["T"].iloc[-1]) + 1
        h1 = h[h["T"] < tc].iloc[-120:].reset_index(drop=True)
        if len(m15) < 210 or len(h1) < 60: continue
        b15 = bm[bm["T"] < tc].iloc[-100:].reset_index(drop=True); b1 = bh[bh["T"] < tc].iloc[-120:].reset_index(drop=True)
        btc = S.btc_state(b15, b1); r = {"coin": coin, "t": tc}
        for nm, tr in (("A", base), ("B", B)):
            S.cfg["trigger_strats"] = tr
            d = S.decide(m15, h1, coin, False, btc)
            r[nm] = {"sig": d["signal"], "prim": d["primary"], "strats": d["strategies"], "block": d.get("block"), "bprim": d.get("blocked_primary"),
                     "vp": d["votes"]["VPROFILE"], "sw": d["votes"]["SWING_BRK"]}
        out.append(r)
    return out
if __name__ == "__main__":
    with Pool(6) as p: R = sum(p.map(run, uni), [])
    pickle.dump(R, open("/workspace/review/swing/res.pkl", "wb"))
    def summ(nm, key, strat):
        raw = sum(1 for r in R if r[nm][key]); 
        sig = [r for r in R if r[nm]["sig"]]
        inv = sum(1 for r in sig if strat in r[nm]["strats"]); prim = sum(1 for r in sig if r[nm]["prim"] == strat)
        blocks = {}
        for r in R:
            if r[nm]["bprim"] == strat: b = (r[nm]["block"] or "").split(":")[0].split(" ")[0]; blocks[b] = blocks.get(b, 0) + 1
        return dict(raw_fires=raw, passed_gate_confirmers_involved=inv, passed_as_primary=prim, total_signals_config=len(sig), blocked_as_primary=blocks)
    print("coins", len(uni), "bars/coin", N, "evals", len(R), "window", S.iso(min(r["t"] for r in R)), "->", S.iso(max(r["t"] for r in R)))
    print("A (current, VPROFILE):", json.dumps(summ("A", "vp", "VPROFILE")))
    print("B (new, SWING_BRK):  ", json.dumps(summ("B", "sw", "SWING_BRK")))
    print("SWING_BRK raw fires in A-run (inactive):", sum(1 for r in R if r["A"]["sw"]))
