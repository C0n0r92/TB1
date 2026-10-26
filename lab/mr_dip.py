#!/usr/bin/env python3
"""Long-only z-score / Bollinger dip-buy study on liquid Solana tokens (PAPER research only; Zero 2026-10-24).
Data: data/mr_candles (mr_fetch.py). Output: out/mean_reversion.md, out/mr_trades_best.csv, out/.mr_rows.json (staging for merge_extra.py MR).
No lookahead: z is computed on CLOSED bars; entries/exits fill at the NEXT bar open; % stop intrabar at the stop price (or the open if it gapped below).
Holdout: last 30% of each timeframe's SOL date range, never used for selection."""
import csv, glob, itertools, json, math, os, sys, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring
LAB = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(LAB, "data", "mr_candles"); OUT = os.path.join(LAB, "out")
DUB = ZoneInfo("Europe/Dublin"); RNG = np.random.default_rng(7)
TICKET = 15.0
COST = {"lo": 0.0015, "hi": 0.0030}           # per side fee (0.3% / 0.6% round trip); 'hi' adds 2*ticket/liq per side and 0.1% stop slippage
LIQ = {"SOL": 30e6}                            # assumed on-chain pool depth for Binance-listed tokens (default 2M); GT tokens use their pool reserve
BARS_DAY = {"5m": 288, "15m": 96, "1h": 24}

def load_tf(tf):
    data = {}
    for p in glob.glob(os.path.join(D, f"*_*_{'5m' if tf == '15m' else tf}.csv")) + glob.glob(os.path.join(D, f"bn_*_{tf}.csv")):
        src, sym = os.path.basename(p).split("_")[:2]
        if tf == "15m" and src == "bn" and p.endswith("_5m.csv"): continue
        df = pd.read_csv(p).drop_duplicates("ts").sort_values("ts")
        if len(df) < 300: continue
        df["t"] = pd.to_datetime(df.ts, unit="ms", utc=True); df = df.set_index("t")[["o", "h", "l", "c", "vq"]].astype(float)
        if tf == "15m" and src == "gt":
            df = df.resample("15min").agg({"o": "first", "h": "max", "l": "min", "c": "last", "vq": "sum"}).dropna()
        if src == "gt":
            m = json.load(open(os.path.join(D, f"gt_{sym}_pool.json"))); LIQ[sym] = float(m["reserve_usd"])
        data[sym] = (src, df)
    return data

def regime_series(sol1h):
    h4 = sol1h.resample("4h").agg({"c": "last"}).dropna()
    e = h4.c.ewm(span=50, adjust=False).mean()
    # value usable from the END of each 4h bar
    up = (h4.c > e); slope = e > e.shift(6)
    idx = h4.index + pd.Timedelta(hours=4)
    return pd.Series(up.values, idx), pd.Series(slope.values, idx)

def dub_hour(ts): return [t.astimezone(DUB).hour for t in ts]

_CACHE = {}
def gen_trades(sym, df, tf, L, zin, N, stop, regime, reg, night, cost):
    c = df.c.values; o = df.o.values; l = df.l.values; idx = df.index
    key = (sym, tf, L)
    if key not in _CACHE:
        m = pd.Series(c).rolling(L).mean().values; s = pd.Series(c).rolling(L).std(ddof=0).values
        _CACHE[key] = (c - m) / np.where(s > 0, s, np.nan)
    z = _CACHE[key]
    if (sym, tf, "h") not in _CACHE: _CACHE[(sym, tf, "h")] = np.array(idx.tz_convert(DUB).hour)
    hrs = _CACHE[(sym, tf, "h")]
    if regime != "off":
        # regime known at decision time = close of bar i -> value stamped <= bar i END (index + one bar)
        if (sym, tf, regime) not in _CACHE:
            _CACHE[(sym, tf, regime)] = reg[regime].reindex(idx + (idx[1] - idx[0]), method="ffill").fillna(False).values.astype(bool)
        rs = _CACHE[(sym, tf, regime)]
    side = COST[cost] + (2 * TICKET / LIQ.get(sym, 2e6) if cost == "hi" else 0.0)
    stop_x = 0.001 if cost == "hi" else 0.0
    out = []; i = L; n = len(c); step = idx[1] - idx[0] if n > 1 else None
    while i < n - 2:
        if not (z[i] <= -zin): i += 1; continue
        e = i + 1                                   # entry bar (open)
        if regime != "off" and not rs[i]: i += 1; continue
        if night and not (hrs[e] >= 20 or hrs[e] < 7): i += 1; continue
        px = o[e]; ex = None; j = e; reason = None
        while j < n:
            if night and j > e and hrs[j] == 8 and hrs[j - 1] != 8: ex, reason = o[j], "eod"; break   # flat at the 08:00 bar open
            if stop == "p5" and l[j] <= px * 0.95: ex, reason = min(o[j], px * 0.95) * (1 - stop_x), "stop"; break
            if j - e + 1 >= N and j + 1 < n: ex, reason = o[j + 1], "time"; j += 1; break
            if z[j] >= 0 and j + 1 < n: ex, reason = o[j + 1], "mean"; j += 1; break
            if stop == "z4" and z[j] <= -4 and j + 1 < n: ex, reason = o[j + 1], "zstop"; j += 1; break
            j += 1
        if ex is None: break
        ret = ex * (1 - side) / (px * (1 + side)) - 1
        out.append({"sym": sym, "t_in": idx[e], "t_out": idx[min(j, n - 1)], "ret": ret, "reason": reason, "z": z[i]})
        i = j + 1 if reason in ("mean", "time", "zstop") else j + 1
    return out

def book(trades, max_open=3, size=0.10):
    trades = sorted(trades, key=lambda t: t["t_in"]); openp = []; taken = []
    for t in trades:
        openp = [x for x in openp if x["t_out"] > t["t_in"]]
        if len(openp) >= max_open or any(x["sym"] == t["sym"] for x in openp): continue
        openp.append(t); taken.append(t)
    return taken

def night_key(t): return (t.astimezone(DUB) - pd.Timedelta(hours=12)).date().isoformat()

def stats(rets):
    r = np.array(rets)
    if len(r) == 0: return {"n": 0, "mean": None, "lo": None, "hi": None}
    b = RNG.choice(r, (2000, len(r))).mean(1) if len(r) > 1 else np.array([r[0]])
    return {"n": len(r), "mean": r.mean(), "lo": np.percentile(b, 2.5), "hi": np.percentile(b, 97.5), "med": np.median(r), "win": (r > 0).mean()}

def nightly(trades, all_keys, size=0.10, key=night_key):
    d = {k: 0.0 for k in all_keys}
    for t in trades: d[key(t["t_in"])] = d.get(key(t["t_in"]), 0.0) + size * t["ret"]
    v = np.array(list(d.values()))
    return {"nights": len(v), "mean": v.mean(), "p05": np.percentile(v, 5), "p50": np.percentile(v, 50), "p95": np.percentile(v, 95),
            "best": v.max(), "worst": v.min(), "P+10": (v >= 0.10).mean(), "P-20": (v <= -0.20).mean(), "pos": (v > 0).mean(),
            "active": int((v != 0).sum()), "pos_active": float((v > 0).sum() / max(1, (v != 0).sum()))}

def hurst(x, lags=range(2, 100)):
    lags = list(lags); tau = [np.std(x[lag:] - x[:-lag]) for lag in lags]
    return np.polyfit(np.log(lags), np.log(tau), 1)[0]

def vr(r, q):
    r = r - r.mean(); v1 = r.var(); rq = pd.Series(r).rolling(q).sum().dropna().values
    return rq.var() / (q * v1)

def halflife(y):
    dy = np.diff(y); yl = y[:-1] - y[:-1].mean(); b = np.polyfit(yl, dy, 1)[0]
    return -math.log(2) / b if b < 0 else float("inf")

def main():
    from statsmodels.tsa.stattools import adfuller
    TF = {"1h": [4, 8, 16, 32], "15m": [4, 8, 16, 32], "5m": [6, 12, 24, 48]}
    res = {}; hurst_rows = []; rows_stage = []; configs = []; best = {}
    sol1h = load_tf("1h")["SOL"][1]; up, slope = regime_series(sol1h); reg = {"ema50": up, "slope": slope}
    for tf, Ns in TF.items():
        data = load_tf(tf)
        sol = data["SOL"][1]; split = sol.index[0] + 0.7 * (sol.index[-1] - sol.index[0])
        # sanity: Hurst / VR / half-life / ADF on IN-SAMPLE log prices and on 1-bar returns
        for sym, (src, df) in sorted(data.items()):
            ins = df[df.index < split]
            if len(ins) < 500: continue
            y = np.log(ins.c.values); r = np.diff(y)
            dev = y - pd.Series(y).rolling(50).mean().values; dev = dev[~np.isnan(dev)]
            hurst_rows.append({"tf": tf, "sym": sym, "src": src, "bars_is": len(ins), "H": hurst(y), "VR2": vr(r, 2), "VR4": vr(r, 4), "VR16": vr(r, 16),
                               "hl_price_bars": halflife(y), "adf_p": adfuller(y, maxlag=int(BARS_DAY[tf]), autolag=None)[1] if len(y) < 40000 else None,
                               "hl_dev50": halflife(dev)})
        all_nights_is = sorted({night_key(t) for t in sol.index if t < split}); all_nights_oos = sorted({night_key(t) for t in sol.index if t >= split})
        days = lambda t: t.astimezone(DUB).date().isoformat()
        all_days_is = sorted({days(t) for t in sol.index if t < split}); all_days_oos = sorted({days(t) for t in sol.index if t >= split})
        for L, zin, N, stop, regime in itertools.product([20, 50], [2.0, 2.5], Ns, ["z4", "p5"], ["off", "ema50", "slope"]):
            name = f"MR_dip_{tf}_L{L}_z{zin}_N{N}_{stop}_{regime}"
            cfg = {"family": "mr_dip", "tf": tf, "L": L, "zin": zin, "N": N, "stop": stop, "regime": regime, "name": name}; configs.append(cfg)
            out = {}
            for night in (True, False):
                for cost in ("lo", "hi"):
                    tr = []
                    for sym, (src, df) in data.items(): tr += gen_trades(sym, df, tf, L, zin, N, stop, regime, reg, night, cost)
                    for t in tr: t["is_oos"] = t["t_in"] >= split
                    out[(night, cost)] = tr
            res[name] = (cfg, out, split, (all_nights_is, all_nights_oos, all_days_is, all_days_oos))
        print("done", tf, len(data), flush=True)
    # ---- selection: in-sample only, night window, hi cost, all signals, >= 50 IS trades
    fam = {}
    for name, (cfg, out, split, nk) in res.items():
        tr = out[(True, "hi")]; ins = [t["ret"] for t in tr if not t["is_oos"]]
        cfg["is_mean_hi"] = np.mean(ins) if len(ins) >= 50 else -9
        fam.setdefault(cfg["tf"], []).append(name)
    for tf, names in fam.items():
        best[tf] = max(names, key=lambda n: res[n][0]["is_mean_hi"])
    # lucky flags: neighbours differing in one parameter
    def neighbours(cfg):
        TFN = TF[cfg["tf"]]; nb = []
        for k, vals in {"L": [20, 50], "zin": [2.0, 2.5], "N": TFN, "stop": ["z4", "p5"], "regime": ["off", "ema50", "slope"]}.items():
            i = vals.index(cfg[k])
            for j in (i - 1, i + 1):
                if 0 <= j < len(vals) and not (k in ("stop", "regime") and False):
                    c2 = dict(cfg); c2[k] = vals[j]
                    nb.append(f"MR_dip_{c2['tf']}_L{c2['L']}_z{c2['zin']}_N{c2['N']}_{c2['stop']}_{c2['regime']}")
        return nb
    json.dump({"configs": [{k: v for k, v in c.items()} for c, *_ in res.values()]}, open(os.path.join(D, ".mr_last_run.json"), "w"), default=str)
    return res, best, hurst_rows, neighbours

def summarize(res, best, hurst_rows, neighbours):
    lines = []; rows = []
    allcfg = [dict(name=c["name"], **{k: c[k] for k in ("family", "tf", "L", "zin", "N", "stop", "regime")}) for c, *_ in res.values()]
    def row_for(name, label_extra=""):
        cfg, out, split, (nis, noos, dis, doos) = res[name]
        r = {}
        for cost in ("lo", "hi"):
            tr = out[(True, cost)]; tr24 = out[(False, cost)]
            bk = book(tr); bk24 = book(tr24)
            r[cost] = {"all_is": stats([t["ret"] for t in tr if not t["is_oos"]]), "all_oos": stats([t["ret"] for t in tr if t["is_oos"]]),
                       "all": stats([t["ret"] for t in tr]), "bk_is": stats([t["ret"] for t in bk if not t["is_oos"]]),
                       "bk_oos": stats([t["ret"] for t in bk if t["is_oos"]]),
                       "n_is": nightly([t for t in bk if not t["is_oos"]], nis), "n_oos": nightly([t for t in bk if t["is_oos"]], noos),
                       "d_is": nightly([t for t in bk24 if not t["is_oos"]], dis, key=lambda t: t.astimezone(DUB).date().isoformat()),
                       "d_oos": nightly([t for t in bk24 if t["is_oos"]], doos, key=lambda t: t.astimezone(DUB).date().isoformat()),
                       "a24_is": stats([t["ret"] for t in tr24 if not t["is_oos"]]), "a24_oos": stats([t["ret"] for t in tr24 if t["is_oos"]]),
                       "bk": bk, "tr": tr}
        return cfg, r
    return row_for

if __name__ == "__main__":
    res, best, hurst_rows, neighbours = main()
    import pickle
    pickle.dump({"best": best, "hurst": hurst_rows}, open(os.path.join(D, ".mr_best.pkl"), "wb"))
    import mr_report; mr_report.write(res, best, hurst_rows, neighbours, summarize(res, best, hurst_rows, neighbours))
