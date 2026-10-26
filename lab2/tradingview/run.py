#!/usr/bin/env python3
"""Run all 20 ports on held-out windows. Majors (Binance vision spot) @0.3%/side; older Solana coins (Lab cache, read-only) @1%/side.
Also reports 0-cost (gross) to show whether there is any edge before costs. Writes out/results.json, out/per_symbol.csv."""
import sys, os, json, datetime as dt
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
from tvlib import backtest, stats
from strategies import STRATS
H = os.path.dirname(os.path.abspath(__file__)); os.makedirs(f"{H}/out", exist_ok=True)
MAJ = "SOL JUP BONK WIF JTO PYTH RAY RENDER BTC".split()
ts = lambda s: int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())
HOLD = {"maj_1h": ts("2026-02-01"), "maj_15m": ts("2026-07-08"), "maj_5m": ts("2026-09-05"), "old_1h": ts("2026-09-01"), "old_15m": ts("2026-09-26")}
COST = {"maj": 0.003, "old": 0.01}
DROP = set("MU SKHY SPCX TTWO GME MPLX CASH STONK hyUSD ONYC".split())

def load_groups():
    G = {}
    for tf, m in (("1h", 60), ("15m", 15), ("5m", 5)):
        L = []
        for s in MAJ:
            p = f"{H}/data/{s}_{tf}.csv"
            if not os.path.exists(p): continue
            df = pd.read_csv(p); L.append((s, dict(t=df.t_ms.values // 1000, o=df.o.values, h=df.h.values, l=df.l.values, c=df.c.values)))
        if L: G[f"maj_{tf}"] = (m, L)
    cwd = os.getcwd(); os.chdir("/workspace/lab"); sys.path.insert(0, "/workspace/lab")
    import oc_backtest as ob
    toks, _ = ob.load(); os.chdir(cwd)
    L1, L15 = [], []
    for mint, k in toks.items():
        s = k["sym"]
        if s in DROP: continue
        C = np.asarray(k["C"], float)
        if len(C) >= 1000 and np.nanmax(C) / np.nanmin(C) > 1.15:
            L1.append((s, dict(t=np.asarray(k["T"]), o=np.asarray(k["O"], float), h=np.asarray(k["H"], float), l=np.asarray(k["L"], float), c=C)))
        m = k.get("m15")
        if m and len(m["T"]) >= 2000 and np.nanmax(m["C"]) / np.nanmin(m["C"]) > 1.15:
            L15.append((s, dict(t=np.asarray(m["T"]), o=np.asarray(m["O"], float), h=np.asarray(m["H"], float), l=np.asarray(m["L"], float), c=np.asarray(m["C"], float))))
    G["old_1h"] = (60, L1); G["old_15m"] = (15, L15)
    return G

def run_group(gname, tfm, L, sname, cost):
    eqs, trades, holds, rows = [], [], [], []
    for sym, d in L:
        i0 = int(np.searchsorted(d["t"], HOLD[gname]))
        if i0 >= len(d["c"]) - 50 or i0 < 300: continue
        sig = STRATS[sname](d, tfm)
        tr, eq = backtest(d, sig, cost, i0); st = stats(tr, eq)
        hold = d["c"][-1] * (1 - cost) / (d["o"][i0] * (1 + cost)) - 1
        eqs.append(eq); trades += tr; holds.append(hold)
        rows.append(dict(group=gname, strat=sname, sym=sym, cost=cost, hold=hold, **st))
    if not eqs: return None, rows
    m = min(len(e) for e in eqs); P = np.mean([e[-m:] for e in eqs], axis=0)  # equal-weight sleeves (aligned on the common tail)
    st = stats(trades, np.r_[1.0, P / P[0]] if False else P)
    st["net"] = float(np.mean([e[-1] for e in eqs]) - 1)
    return dict(group=gname, strat=sname, cost=cost, nsym=len(eqs), hold=float(np.mean(holds)), **{k: float(v) for k, v in st.items()},
                sym_pos=int(sum(e[-1] > 1 for e in eqs)), sym_beat=int(sum(e[-1] - 1 > h for e, h in zip(eqs, holds)))), rows

if __name__ == "__main__":
    G = load_groups(); R, P = [], []
    for g, (tfm, L) in G.items():
        print(g, len(L), "series", flush=True)
        for s in STRATS:
            for cost in (COST[g[:3]], 0.0):
                r, rows = run_group(g, tfm, L, s, cost)
                if r: R.append(r)
                P += rows
    json.dump(R, open(f"{H}/out/results.json", "w"), indent=1); pd.DataFrame(P).to_csv(f"{H}/out/per_symbol.csv", index=False)
    print("done", len(R))
