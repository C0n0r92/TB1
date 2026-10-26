"""Track A: SMC long-only setups (rules in results/smc_rules.md, written before testing). PAPER ONLY.
python src/smc.py  -> results/smc_summary.md, smc_trades.csv, smc_params_train.json"""
import json, os, sys, math
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import data, regime

MAJ = "SOL JUP JTO BONK WIF PYTH RAY W ORCA RENDER PENGU TRUMP BOME".split()
OLD = "Pnut PENGU RAY TRUMP POPCAT ZEREBRO Fartcoin Ban CARDS ANTFUN pippin USELESS MOODENG $WIF jellyjelly ALCH MPLX MEW BOME arc".split()
T = pd.Timestamp
CELLS = {  # name: (universe, tf, train_start, split, cost/side)
    "maj_5m":  ("maj", "5m",  T("2026-05-27", tz="UTC"), T("2026-08-15", tz="UTC"), 0.003),
    "maj_15m": ("maj", "15m", T("2026-04-08", tz="UTC"), T("2026-08-15", tz="UTC"), 0.003),
    "maj_1h":  ("maj", "1h",  T("2025-09-20", tz="UTC"), T("2026-08-15", tz="UTC"), 0.003),
    "old_15m": ("old", "15m", T("2026-09-12", tz="UTC"), T("2026-10-05", tz="UTC"), 0.01),
    "old_1h":  ("old", "1h",  T("2026-06-22", tz="UTC"), T("2026-08-31", tz="UTC"), 0.01),
}
SETUPS = ["FVG", "IFVG", "OB", "BREAKER", "VI"]
RGRID = [1.5, 2.0, 3.0]
EXPIRE, TIMEOUT, MINW, STOPB, BOSN, BOSLB = 100, 48, 0.25, 0.25, 3, 10

def load(cell):
    un, tf = CELLS[cell][:2]
    if un == "maj": return {s: data.binance(s, tf) for s in MAJ if os.path.exists(os.path.join(data.BIN, f"{s}_{tf}.csv"))}
    u = data.lab_midcap(tf); return {s: u[s][1] for s in OLD if s in u}

def ema(x, n): return pd.Series(x).ewm(span=n, adjust=False).mean().values

def zones(setup, O, H, L, C, A):
    """yield (confirm_index, zb, zt). Only uses bars <= confirm_index."""
    n = len(C); out = []
    if setup == "FVG":
        for i in range(2, n):
            if L[i] > H[i-2]: out.append((i, H[i-2], L[i]))
    elif setup == "VI":
        for i in range(1, n):
            if C[i-1] > O[i-1] and C[i] > O[i] and O[i] > C[i-1]: out.append((i, C[i-1], O[i]))
    elif setup == "IFVG":
        for i in range(2, n):
            if H[i] < L[i-2]:
                zb, zt = H[i], L[i-2]
                for k in range(i+1, min(n, i+1+EXPIRE)):
                    if C[k] > zt: out.append((k, zb, zt)); break
    elif setup == "OB":
        for k in range(BOSLB, n-1):
            if not C[k] < O[k]: continue
            ref = H[k-BOSLB:k+1].max()
            for m in range(k+1, min(n, k+1+BOSN)):
                if C[m] < O[m] and m > k: break          # a later down bar would be the 'last' down candle instead
                if C[m] > ref: out.append((m, L[k], H[k])); break
    elif setup == "BREAKER":
        for k in range(BOSLB, n-1):
            if not C[k] > O[k]: continue
            ref = L[k-BOSLB:k+1].min(); brk = None
            for m in range(k+1, min(n, k+1+BOSN)):
                if C[m] > O[m]: break
                if C[m] < ref: brk = m; break
            if brk is None: continue
            for q in range(brk+1, min(n, brk+1+EXPIRE)):
                if C[q] > H[k]: out.append((q, L[k], H[k])); break
    return out

def events(df, setup):
    O, H, L, C = (df[k].values for k in "ohlc")
    tr = np.maximum(H - L, np.maximum(abs(H - np.r_[C[0], C[:-1]]), abs(L - np.r_[C[0], C[:-1]])))
    A = pd.Series(tr).rolling(14).mean().values; e50, e200 = ema(C, 50), ema(C, 200)
    ev = []; seen = set()
    for (i, zb, zt) in zones(setup, O, H, L, C, A):
        if not (A[i] > 0) or zt - zb < MINW * A[i] or i < 200: continue
        for j in range(i+1, min(len(C)-1, i+1+EXPIRE)):
            if C[j] < zb: break                                  # dead before retest
            if L[j] <= zt:                                       # retest, closed >= zb
                if (j, round(zb, 12)) in seen: break
                seen.add((j, round(zb, 12)))
                ev.append(dict(j=j, zb=zb, zt=zt, stop=zb - STOPB * A[j], trend=bool(C[j] > e200[j] and e50[j] > e200[j])))
                break
    return ev

def simulate(df, ev, R, cost, trend, t0, t1):
    O, H, L, C = (df[k].values for k in "ohlc"); idx = df.index; out = []; free = -1
    for e in sorted(ev, key=lambda x: x["j"]):
        j = e["j"]
        if idx[j] < t0 or idx[j] >= t1 or j + 1 >= len(C) or j + 1 <= free: continue
        if trend and not e["trend"]: continue
        ent = O[j+1]; st = e["stop"]; risk = ent - st
        if risk <= 0 or risk / ent < 4 * cost or risk / ent > 0.10: continue
        tp = ent + R * risk; x = None
        for k in range(j+1, min(len(C), j+1+TIMEOUT)):
            if k > j+1 and O[k] <= st: x = (k, O[k], "stop"); break
            if L[k] <= st: x = (k, st, "stop"); break
            if k > j+1 and O[k] >= tp: x = (k, tp, "tp"); break
            if H[k] >= tp: x = (k, tp, "tp"); break
        if x is None:
            k = min(len(C)-1, j+TIMEOUT); x = (k, C[k], "time")
        k, px, why = x
        ret = (px * (1 - cost)) / (ent * (1 + cost)) - 1
        out.append(dict(t_sig=idx[j], t_exit=idx[k], entry=ent, exit=px, why=why, ret=ret, gross=px/ent - 1)); free = k
    return out

def stats(tr, toks):
    if not tr: return dict(n=0)
    r = np.array([t["ret"] for t in tr]); w, l = r[r > 0].sum(), -r[r < 0].sum()
    rng = np.random.default_rng(7); bs = rng.choice(r, (5000, len(r))).mean(1)
    # book: capital split equally across tokens, each token compounds its own trades; equity marked at exits
    df = pd.DataFrame(tr).sort_values("t_exit"); n = max(1, len(toks))
    eq = 1.0 + (df.groupby("sym")["ret"].transform(lambda s: (1 + s).cumprod()) - 1)
    lvl = {s: 1.0 for s in toks}; curve = []
    for s, v in zip(df.sym, eq): lvl[s] = v; curve.append(sum(lvl.values()) / n)
    c = np.array([1.0] + curve); dd = (c / np.maximum.accumulate(c) - 1).min()
    return dict(n=len(r), mean=r.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), win=(r > 0).mean(),
                pf=(w / l if l > 0 else float("inf")), book=c[-1] - 1, dd=dd, sumret=r.sum())

def hold(px, t0, t1, cost):
    """equal-weight buy&hold of the tokens over [t0,t1), one round trip of cost."""
    v = []
    for s, df in px.items():
        x = df.c[(df.index >= t0) & (df.index < t1)]
        if len(x) > 10: v.append(x.iloc[-1] / x.iloc[0] * (1 - cost) / (1 + cost) - 1)
    return float(np.mean(v)) if v else float("nan")

def main():
    only = os.environ.get("CELLS")
    if only:
        for c in list(CELLS):
            if c not in only.split(","): CELLS.pop(c)
    rtab = regime.build(); sol1h = data.binance("SOL", "1h")
    rows, trades_out, params = [], [], {}
    nvar = 0
    for cell, (un, tf, t0, split, cost) in CELLS.items():
        px = load(cell); end = data.CUTOFF
        print(cell, len(px), "tokens", flush=True)
        EV = {(s, st): events(df, st) for s, df in px.items() for st in SETUPS}
        h_test = hold(px, split, end, cost); h_sol = hold({"SOL": sol1h}, split, end, 0.003)
        for st in SETUPS:
            for trend in (False, True):
                nvar += 1
                def run(R, a, b):
                    tr = []
                    for s, df in px.items():
                        for t in simulate(df, EV[(s, st)], R, cost, trend, a, b): t["sym"] = s; tr.append(t)
                    return tr
                tr_train = {R: run(R, t0, split) for R in RGRID}
                def score(tr): return np.mean([t["ret"] for t in tr]) if len(tr) >= 20 else -9
                R = max(RGRID, key=lambda r: score(tr_train[r]))
                trn, tst = tr_train[R], run(R, split, end)
                for lst in (trn, tst):
                    if lst:
                        g = regime.regime_at(pd.DatetimeIndex([t["t_sig"] for t in lst]), rtab)
                        lab = dict(zip(g.index, g["regime"]))
                        for t in lst: t["regime"] = lab.get(t["t_sig"], "na")
                key = f"{cell}|{st}|trend={'on' if trend else 'off'}"
                params[key] = R
                rec = dict(cell=cell, setup=st, trend="on" if trend else "off", R=R, cost=cost, tokens=len(px),
                           train=stats(trn, px), test=stats(tst, px), hold=h_test, hold_sol=h_sol, by_regime={}, gate=None)
                for rg in ("trending", "choppy", "high_vol", "crash"):
                    a = [t for t in trn if t["regime"] == rg]; b = [t for t in tst if t["regime"] == rg]
                    rec["by_regime"][rg] = dict(train=stats(a, px), test=stats(b, px))
                good = [rg for rg, v in rec["by_regime"].items() if v["train"]["n"] >= 20 and v["train"]["mean"] > 0]
                if good and len(good) < 4:
                    nvar += 1
                    g = [t for t in tst if t["regime"] in good]
                    rec["gate"] = dict(regimes=good, test=stats(g, px))
                rows.append(rec)
                for lst, oos in ((trn, False), (tst, True)):
                    for t in lst: trades_out.append(dict(variant=key, R=R, is_oos=oos, **{k: (str(v) if k.startswith("t_") else v) for k, v in t.items()}))
                te = rec["test"]
                print(key, "R", R, "train n/mean", rec["train"].get("n"), round(rec["train"].get("mean", 0)*100, 2),
                      "test n/mean", te.get("n"), round(te.get("mean", 0)*100, 2), "gate", good, flush=True)
    os.makedirs(os.path.join(data.LAB2, "results"), exist_ok=True)
    pd.DataFrame(trades_out).to_csv(os.path.join(data.LAB2, "results", f"smc_trades{os.environ.get('TAG','')}.csv"), index=False)
    json.dump(params, open(os.path.join(data.LAB2, "results", f"smc_params_train{os.environ.get('TAG','')}.json"), "w"), indent=1)
    json.dump(dict(rows=rows, variants=nvar, train_configs=50 * len(RGRID)), open(os.path.join(data.LAB2, "results", f"smc_rows{os.environ.get('TAG','')}.json"), "w"), indent=1, default=float)
    print("variants", nvar)

if __name__ == "__main__":
    main()
