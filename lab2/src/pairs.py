#!/usr/bin/env python3
"""Track B: pairs mean reversion (Chan, Algorithmic Trading ch.3-4). PAPER ONLY, research only.
Pipeline per (universe, timeframe):
 1. TRAIN window only: Engle-Granger (both orderings, min p) + Johansen trace (r=0 at 95%) on log closes -> keep p<0.05 & Johansen pass
    & positive hedge ratio; rank by EG p; top MAXP pairs.
 2. Parameters picked on TRAIN only: rolling-OLS lookback L in LOOKBACKS; Kalman (delta, Ve) in KGRID. Entry |z|>2, exit z crosses 0 (fixed, Zero spec).
 3. TEST window: trade with frozen pair list + params. Signal at bar close t, fill at close t+1 (1-bar delay). Shares fixed for the trade.
    (a) rolling OLS hedge, (b) Kalman hedge, (c) long-only: hold only the long leg (long-the-laggard), for both hedges.
 4. Costs per side per leg on its notional at entry and exit. Book = equal capital per pair, no compounding, mark-to-market each bar.
 5. Each trade tagged with the regime at entry (src/regime.py). Regime gate = only regimes with TRAIN mean net > 0 and >= 10 train trades.
"""
import itertools, json, os, sys, warnings
import numpy as np, pandas as pd
from statsmodels.tsa.stattools import coint
from statsmodels.tsa.vector_ar.vecm import coint_johansen
import data, regime
warnings.filterwarnings("ignore")
OUT = os.path.join(data.LAB2, "results")
ENTRY, EXIT = 2.0, 0.0
LOOKBACKS = [48, 96, 192, 384]
KGRID = [(1e-5, 1e-4), (1e-5, 1e-3), (1e-4, 1e-4), (1e-4, 1e-3)]
MAXP = 10
MAJOR_03 = set("SOL JUP JTO BONK WIF PYTH RAY W ORCA RENDER PENGU TRUMP".split())   # 0.3%/side; others 1%/side

# ---------------- universes ----------------
def uni_binance(tf):
    syms = "SOL JUP JTO BONK WIF PYTH RAY W BOME ORCA TNSR RENDER PENGU TRUMP PNUT KMNO IO".split()
    px = {s: data.binance(s, tf).c for s in syms if os.path.exists(os.path.join(data.BIN, f"{s}_{tf}.csv"))}
    cost = {s: (0.003 if s in MAJOR_03 else 0.01) for s in px}
    return pd.DataFrame(px), cost
OLD_KEEP = "SOL Pnut PENGU RAY TRUMP POPCAT ZEREBRO Fartcoin Ban CARDS CASH ANTFUN pippin USELESS MOODENG $WIF jellyjelly ALCH MPLX MEW BOME arc".split()
def uni_old(tf):
    u = data.lab_midcap(tf); px = {s: u[s][1].c for s in OLD_KEEP if s in u}
    if "SOL" not in px: px["SOL"] = data.binance("SOL", tf).c
    return pd.DataFrame(px), {s: 0.01 for s in px}          # older coins / memes: 1%/side on every leg
SPLITS = {   # (universe, tf): (data start, train end, test end)
    ("major", "1h"):  ("2025-09-20", "2026-06-30", "2026-10-24"),
    ("major", "15m"): ("2026-04-08", "2026-08-15", "2026-10-24"),
    ("old", "1h"):    ("2026-06-22", "2026-08-31", "2026-10-24"),
    ("old", "15m"):   ("2026-09-12", "2026-10-05", "2026-10-24"),
}

# ---------------- selection ----------------
def select(lp_tr):
    rows = []
    vol = lp_tr.diff().std() * np.sqrt(len(lp_tr) / max((lp_tr.index[-1] - lp_tr.index[0]).days, 1))   # daily vol of log price
    lp_tr = lp_tr[[c for c in lp_tr.columns if lp_tr[c].std() > 0.05]]    # drop stablecoin-like series (e.g. CASH: log-price std < 5% over train)
    for a, b in itertools.combinations(lp_tr.columns, 2):
        d = lp_tr[[a, b]].dropna()
        if len(d) < 0.9 * len(lp_tr): continue
        p1 = coint(d[a], d[b])[1]; p2 = coint(d[b], d[a])[1]
        y, x = (a, b) if p1 <= p2 else (b, a)
        beta, alpha = np.polyfit(d[x], d[y], 1)
        try:
            j = coint_johansen(d[[a, b]].values, 0, 1); joh = bool(j.lr1[0] > j.cvt[0, 1])
        except Exception: joh = False
        res = d[y] - alpha - beta * d[x]; dr = res.diff().dropna(); lag = res.shift().dropna()
        k = np.polyfit(lag.values, dr.values, 1)[0]; hl = -np.log(2) / k if k < 0 else np.inf
        rows.append(dict(y=y, x=x, eg_p=min(p1, p2), johansen=joh, beta=beta, half_life_bars=hl, n=len(d)))
    S = pd.DataFrame(rows).sort_values("eg_p")
    S["selected"] = False
    cnt = {}; ok = []
    for i, r in S[(S.eg_p < 0.05) & S.johansen & (S.beta > 0)].iterrows():   # max 2 pairs per token (else one stationary-looking coin dominates)
        if len(ok) >= MAXP or cnt.get(r.y, 0) >= 2 or cnt.get(r.x, 0) >= 2: continue
        ok.append(i); cnt[r.y] = cnt.get(r.y, 0) + 1; cnt[r.x] = cnt.get(r.x, 0) + 1
    S.loc[ok, "selected"] = True
    return S

# ---------------- hedge / z ----------------
def rolling_ols(ly, lx, L):
    mx, my = lx.rolling(L).mean(), ly.rolling(L).mean()
    beta = (lx * ly).rolling(L).mean().sub(mx * my).div(lx.rolling(L).var(ddof=0))
    alpha = my - beta * mx
    s = ly - alpha - beta * lx                        # residual with today's beta (only data <= t)
    z = (s - s.rolling(L).mean()) / s.rolling(L).std()
    return beta, z

def kalman(ly, lx, delta, Ve):
    n = len(ly); y = ly.values; x = lx.values
    th = np.zeros(2); R = np.eye(2); Vw = delta / (1 - delta) * np.eye(2); P = np.zeros(2)
    beta = np.full(n, np.nan); z = np.full(n, np.nan); init = False
    for t in range(n):
        if np.isnan(y[t]) or np.isnan(x[t]): continue
        F = np.array([x[t], 1.0])
        if not init: th = np.array([y[t] / x[t] if x[t] else 1.0, 0.0]); init = True
        R = R + Vw
        e = y[t] - F @ th; Q = F @ R @ F + Ve
        z[t] = e / np.sqrt(Q); beta[t] = th[0]               # beta known BEFORE seeing y[t]
        K = R @ F / Q; th = th + K * e; R = R - np.outer(K, F) @ R
    return pd.Series(beta, ly.index), pd.Series(z, ly.index)

# ---------------- simulation ----------------
def simulate(py, px, beta, z, cy, cx, t0, t1, mode):
    """mode 'pair' (both legs) or 'long' (only the long leg). Signal at close t -> fill at close t+1.
    Returns closed trades and per-bar P&L (fraction of the pair's capital, gross exposure 1)."""
    idx = py.index; n = len(idx); Y, X, B, Z = py.values, px.values, beta.values, z.values
    i0 = idx.searchsorted(t0); i1 = min(idx.searchsorted(t1), n)
    pnl = np.zeros(n); trades = []; cur = None; pend = None
    def exit_cost(c, t): return c["cy"] * abs(c["wy"]) * Y[t] / c["py"] + c["cx"] * abs(c["wx"]) * X[t] / c["px"]
    for t in range(i0, i1):
        if cur and cur["i"] < t:                                   # mark to market
            r = _mark(cur, Y[t], X[t])
            if np.isfinite(r): pnl[t] += r - cur["last"]; cur["last"] = r
        if pend == "exit" and cur and np.isfinite(_mark(cur, Y[t], X[t])):
            xc = exit_cost(cur, t); pnl[t] -= xc
            cur.update(t_exit=idx[t], gross=cur["last"], net=cur["last"] - cur["c_in"] - xc, bars=t - cur["i"]); trades.append(cur); cur = None; pend = None
        elif pend in (1, -1) and not cur:
            b = B[t - 1]; side = pend; pend = None
            if np.isfinite(b) and b > 0 and np.isfinite(Y[t]) and np.isfinite(X[t]):
                wy, wx = side / (1 + b), -side * b / (1 + b)
                if mode == "long": wy, wx = (1.0, 0.0) if side == 1 else (0.0, 1.0)
                c_in = cy * abs(wy) + cx * abs(wx); pnl[t] -= c_in
                cur = dict(i=t, t_entry=idx[t], side=side, beta=b, wy=wy, wx=wx, py=Y[t], px=X[t], cy=cy, cx=cx, c_in=c_in, last=0.0)
        if t + 1 >= i1 or not np.isfinite(Z[t]): continue        # signal at close t, executes next bar
        if not cur and pend is None:
            if Z[t] <= -ENTRY: pend = 1
            elif Z[t] >= ENTRY: pend = -1
        elif cur and pend is None:
            if (cur["side"] == 1 and Z[t] >= EXIT) or (cur["side"] == -1 and Z[t] <= -EXIT): pend = "exit"
    if cur:                                                        # forced exit at the last bar of the window
        t = i1 - 1; xc = exit_cost(cur, t) if np.isfinite(Y[t]) and np.isfinite(X[t]) else cur["c_in"]; pnl[t] -= xc
        cur.update(t_exit=idx[t], gross=cur["last"], net=cur["last"] - cur["c_in"] - xc, bars=t - cur["i"], forced=True); trades.append(cur)
    return trades, pd.Series(pnl[i0:i1], idx[i0:i1])

def _mark(c, y, x):
    if not (np.isfinite(y) and np.isfinite(x)): return np.nan
    return c["wy"] * (y / c["py"] - 1) + c["wx"] * (x / c["px"] - 1)

def stats(pnl_book, trades, tf):
    eq = 1 + pnl_book.cumsum(); daily = eq.resample("1D").last().ffill().pct_change().dropna()
    sh = daily.mean() / daily.std() * np.sqrt(365) if daily.std() > 0 else 0.0
    dd = (eq / eq.cummax() - 1).min()
    nets = np.array([t["net"] for t in trades]) if trades else np.array([])
    ci = (np.nan, np.nan)
    if len(nets) >= 5:
        rng = np.random.default_rng(7); bs = rng.choice(nets, (5000, len(nets))).mean(1); ci = (np.percentile(bs, 2.5), np.percentile(bs, 97.5))
    return dict(trades=len(nets), net_ret=eq.iloc[-1] - 1, sharpe=sh, max_dd=dd, mean_trade=nets.mean() if len(nets) else np.nan,
                ci_lo=ci[0], ci_hi=ci[1], win=(nets > 0).mean() if len(nets) else np.nan,
                gross_mean=np.mean([t["gross"] for t in trades]) if trades else np.nan)

def run_book(lp, P, sel, method, prm, t0, t1, cost, mode, tf, gate=None, rtab=None):
    pnls, trades = [], []
    for _, r in sel.iterrows():
        ly, lx = lp[r.y], lp[r.x]; d = pd.concat([ly, lx], axis=1).dropna(); ly, lx = d.iloc[:, 0], d.iloc[:, 1]
        beta, z = rolling_ols(ly, lx, prm) if method == "ols" else kalman(ly, lx, *prm)
        if gate is not None:                             # regime gate: blank z where entry regime not allowed (exits still allowed)
            rg = regime.regime_at(z.index, rtab)["regime"].values
            zz = z.copy(); bad = ~np.isin(rg, list(gate))
            zz[bad & (z.abs() >= ENTRY).values] = np.sign(z[bad & (z.abs() >= ENTRY).values]) * (ENTRY - 1e-9)
            z = zz
        tr, pn = simulate(np.exp(ly), np.exp(lx), beta, z, cost[r.y], cost[r.x], t0, t1, mode)
        for t in tr: t.update(pair=f"{r.y}/{r.x}", y=r.y, x=r.x)
        trades += tr; pnls.append(pn)
    book = pd.concat(pnls, axis=1).fillna(0).mean(axis=1) if pnls else pd.Series(dtype=float)
    return book, trades

def tag(trades, rtab):
    if not trades: return
    rg = regime.regime_at([t["t_entry"] for t in trades], rtab)
    order = np.argsort(np.array([t["t_entry"] for t in trades], dtype="datetime64[ns]"), kind="stable")
    vals = rg["regime"].values
    for k, j in enumerate(order): trades[j]["regime"] = vals[k]

def main():
    rtab = regime.build(); summary = []; alltr = []; sels = []; params = {}
    for (un, tf), (s0, tr_end, te_end) in SPLITS.items():
        P, cost = (uni_binance if un == "major" else uni_old)(tf)
        P = P[(P.index >= s0) & (P.index < te_end)]
        lp = np.log(P); tr_mask = lp.index < tr_end
        sel_all = select(lp[tr_mask]); sel_all.insert(0, "tf", tf); sel_all.insert(0, "universe", un); sels.append(sel_all)
        sel = sel_all[sel_all.selected]
        print(f"== {un} {tf}: {lp.shape[1]} tokens, {len(sel_all)} pairs tested, {len(sel)} selected", flush=True)
        if sel.empty: continue
        T0, TR1 = lp.index[0], pd.Timestamp(tr_end, tz="UTC"); TE1 = lp.index[-1] + pd.Timedelta(seconds=1)
        trs = pd.Timestamp(lp.index[min(400, len(lp) // 4)])     # train trading starts after warm-up
        for method, grid in (("ols", LOOKBACKS), ("kalman", KGRID)):
            # pick param on TRAIN (pair mode, net mean/trade, >= 20 trades, else best available)
            best = None
            for prm in grid:
                b, t = run_book(lp, P, sel, method, prm, trs, TR1, cost, "pair", tf)
                st = stats(b, t, tf); key = (st["trades"] >= 20, st["net_ret"])
                if best is None or key > best[0]: best = (key, prm, st)
            prm = best[1]; params[f"{un}_{tf}_{method}"] = dict(param=prm, train=best[2])
            for mode in ("pair", "long"):
                btr, ttr = run_book(lp, P, sel, method, prm, trs, TR1, cost, mode, tf); tag(ttr, rtab)
                bte, tte = run_book(lp, P, sel, method, prm, TR1, TE1, cost, mode, tf); tag(tte, rtab)
                # regime gate from TRAIN trades
                g = pd.DataFrame(ttr)
                gate = set(g.groupby("regime").net.agg(["mean", "size"]).query("mean > 0 and size >= 10").index) if len(g) else set()
                variants = [("", bte, tte, btr, ttr)]
                if gate and len(gate) < 4:
                    bg, tg = run_book(lp, P, sel, method, prm, TR1, TE1, cost, mode, tf, gate=gate, rtab=rtab); tag(tg, rtab)
                    variants.append((f"+gate{sorted(gate)}", bg, tg, None, None))
                for suf, bb, tt, b_tr, t_tr in variants:
                    st = stats(bb, tt, tf); name = f"{un}_{tf}_{method}_{mode}{suf}"
                    st_tr = stats(b_tr, t_tr, tf) if b_tr is not None else {}
                    summary.append(dict(variant=name, universe=un, tf=tf, method=method, mode=mode, param=str(prm), gate=suf,
                                        train_trades=st_tr.get("trades"), train_net=st_tr.get("net_ret"), **{f"oos_{k}": v for k, v in st.items()}))
                    for t in tt: alltr.append(dict(variant=name, **{k: t.get(k) for k in ("pair", "side", "t_entry", "t_exit", "bars", "beta", "gross", "net", "regime")}))
                    print(f"  {name:45s} prm={prm} train n={st_tr.get('trades')} net={st_tr.get('net_ret', float('nan')):+.3f} | OOS n={st['trades']} net={st['net_ret']:+.3f} sh={st['sharpe']:+.2f} dd={st['max_dd']:+.3f} mean/tr={st['mean_trade']:+.4f}", flush=True)
        # buy & hold over the test window
        te = P[(P.index >= TR1)]
        legs = set(sel.y) | set(sel.x) | {"SOL"}
        for s in sorted(legs):
            c = te[s].dropna(); eq = c / c.iloc[0]; daily = eq.resample("1D").last().pct_change().dropna()
            summary.append(dict(variant=f"{un}_{tf}_HOLD_{s}", universe=un, tf=tf, method="hold", mode="hold",
                                oos_trades=1, oos_net_ret=eq.iloc[-1] - 1 - 2 * cost.get(s, 0.003),
                                oos_sharpe=daily.mean() / daily.std() * np.sqrt(365), oos_max_dd=(eq / eq.cummax() - 1).min()))
        summary.append(dict(variant=f"{un}_{tf}_WINDOWS", universe=un, tf=tf, method="info", mode=f"train {lp.index[0]:%Y-%m-%d}..{tr_end}, test {tr_end}..{lp.index[-1]:%Y-%m-%d %H:%M}"))
    pd.concat(sels).to_csv(os.path.join(OUT, "pairs_selection_train.csv"), index=False)
    pd.DataFrame(summary).to_csv(os.path.join(OUT, "pairs_summary.csv"), index=False)
    pd.DataFrame(alltr).to_csv(os.path.join(OUT, "pairs_trades_oos.csv"), index=False)
    json.dump(params, open(os.path.join(OUT, "pairs_params_train.json"), "w"), default=str, indent=1)

if __name__ == "__main__":
    main()
