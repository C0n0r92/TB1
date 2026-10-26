"""SOL trend/breakout backtest engine (PAPER). Signals on CLOSED bars of timeframe TF (resampled from Binance-mirror 5m SOLUSDT);
fills on 5m bar opens at (TF close + bot cycle delay). Stops/targets checked either continuously on 5m OHLC (cycle 0 = venue-side
stop/TP order) or only at bot check times (cycle 5/10/15 min, exit at that 5m open -> gaps fill at the worse price naturally).
Stop is checked before target within a bar. Trailing (chandelier) stops update only at TF closes."""
import os, numpy as np, pandas as pd
from numba import njit
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DATA = os.path.join(ROOT, "data")  # Oracle copy: data lives in /workspace/sol-trend/data
TF_MIN = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}

def load5():
    d = pd.read_csv(os.path.join(DATA, "SOLUSDT_5m.csv")); d["t"] = (d.t // 1000).astype("int64"); return d

def resample(d5, tf):
    if tf == "5m": b = d5[["t", "o", "h", "l", "c", "v"]].copy()
    else:
        s = TF_MIN[tf] * 60; g = d5.t // s
        b = d5.groupby(g).agg(t=("t", "first"), o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), v=("v", "sum"), n=("t", "size"))
        b = b[b.n == TF_MIN[tf] // 5].drop(columns="n")       # only complete bars
        b["t"] = b.index.values * s
    b = b.reset_index(drop=True); b["tc"] = b.t + TF_MIN[tf] * 60   # close time (= when the bar is known)
    return b

def indicators(b, piv_k=3):
    c, h, l = b.c, b.h, b.l
    b["ema50"] = c.ewm(span=50, adjust=False).mean(); b["ema200"] = c.ewm(span=200, adjust=False).mean()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    b["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    b["vsma"] = b.v.rolling(20).mean().shift(1)
    for N in (10, 20, 30, 40, 55, 80, 100):
        b[f"hi{N}"] = h.rolling(N).max().shift(1); b[f"lo{N}"] = l.rolling(N).min().shift(1)
    # confirmed pivots (known piv_k bars after the pivot bar)
    k = piv_k; w = 2 * k + 1
    ph = (h.shift(k) == h.rolling(w).max()); pl = (l.shift(k) == l.rolling(w).min())
    phv = h.shift(k).where(ph); plv = l.shift(k).where(pl)
    b["piv_hi"] = phv.ffill(); b["piv_lo"] = plv.ffill()
    b["piv_hi_prev"] = phv.dropna().shift(1).reindex(b.index).ffill(); b["piv_lo_prev"] = plv.dropna().shift(1).reindex(b.index).ffill()
    return b

def signals(b, trend, level, confirm, retest_bars=6):
    """Return (long_sig, short_sig) boolean arrays at bar close. No lookahead: every input is known at bar close."""
    c = b.c.values
    if level == "pivot": hi, lo = b.piv_hi.values, b.piv_lo.values
    else: N = int(level[1:]); hi, lo = b[f"hi{N}"].values, b[f"lo{N}"].values
    c1 = np.r_[np.nan, c[:-1]]; hi1 = np.r_[np.nan, hi[:-1]]; lo1 = np.r_[np.nan, lo[:-1]]
    up = (c > hi) & ~(c1 > hi1); dn = (c < lo) & ~(c1 < lo1)          # fresh close beyond the level
    if confirm == "vol": vk = b.v.values > 1.5 * b.vsma.values; up &= vk; dn &= vk
    if trend == "none": tl = ts = np.ones(len(b), bool)
    elif trend == "ema200": tl = c > b.ema200.values; ts = c < b.ema200.values
    elif trend == "ema50_200": tl = (b.ema50.values > b.ema200.values) & (c > b.ema50.values); ts = (b.ema50.values < b.ema200.values) & (c < b.ema50.values)
    elif trend == "ema200up":   # close above a RISING EMA200 (slope over last 10 bars) - Oracle addition
        sl = b.ema200.values - np.r_[np.full(10, np.nan), b.ema200.values[:-10]]
        tl = (c > b.ema200.values) & (sl > 0); ts = (c < b.ema200.values) & (sl < 0)
    elif trend == "htf":        # higher-timeframe filter: last COMPLETED 4h bar has EMA50>EMA200 (column htf_up/htf_dn added by caller, aligned on close time)
        tl = b.htf_up.values.astype(bool); ts = b.htf_dn.values.astype(bool)
    elif trend == "hhhl":
        tl = (b.piv_hi.values > b.piv_hi_prev.values) & (b.piv_lo.values > b.piv_lo_prev.values)
        ts = (b.piv_hi.values < b.piv_hi_prev.values) & (b.piv_lo.values < b.piv_lo_prev.values)
    L, S = up & tl, dn & ts
    if confirm == "retest":   # breakout bar b0 sets level; enter on the first later bar (<= retest_bars) that dips to level+0.25ATR and closes back beyond it
        L, S = _retest(c, b.l.values, b.h.values, b.atr.values, hi, lo, L, S, retest_bars)
    warm = np.arange(len(b)) < 210
    L[warm] = False; S[warm] = False
    return np.nan_to_num(L).astype(bool), np.nan_to_num(S).astype(bool)

@njit(cache=True)
def _retest(c, l, h, atr, hi, lo, L0, S0, M):
    n = len(c); L = np.zeros(n, np.bool_); S = np.zeros(n, np.bool_)
    for i in range(n):
        if L0[i]:
            lev = hi[i]
            for j in range(i + 1, min(n, i + 1 + M)):
                if c[j] < lev - 0.5 * atr[j]: break
                if l[j] <= lev + 0.25 * atr[j] and c[j] > lev: L[j] = True; break
        if S0[i]:
            lev = lo[i]
            for j in range(i + 1, min(n, i + 1 + M)):
                if c[j] > lev + 0.5 * atr[j]: break
                if h[j] >= lev - 0.25 * atr[j] and c[j] < lev: S[j] = True; break
    return L, S

@njit(cache=True)
def simulate(t5, o5, h5, l5, tc, cc, atr, sigL, sigS, tfclose_at5, side_mode, stop_mult, exit_mode, rr, trail_mult,
             cycle_s, cost, carryL, carryS, max_hold_s):
    """side_mode 0 long-only, 1 long+short. exit_mode 0 fixed R:R target, 1 chandelier trail (highest TF close - trail_mult*ATR).
    carryL/S: per-5m-bar cost fraction (borrow/funding) for longs/shorts (can be negative = received).
    Returns trades array rows: entry_t, exit_t, dir, entry_px, exit_px, net_ret, reason(0 stop,1 target,2 trail,3 time,4 eod)."""
    n5 = len(t5); nb = len(tc); out = np.zeros((nb, 7)); m = 0
    t0 = t5[0]; j = 0; free_t = -1
    while j < nb:
        if tc[j] < free_t or not (sigL[j] or (side_mode == 1 and sigS[j])):
            j += 1; continue
        d = 1.0 if sigL[j] else -1.0
        te = tc[j] + cycle_s
        ke = (te - t0) // 300
        if ke >= n5: break
        if t5[ke] != te:        # data gap: next available bar
            while ke < n5 and t5[ke] < te: ke += 1
            if ke >= n5: break
        pe = o5[ke]; a = atr[j]
        stop = pe - d * stop_mult * a; tgt = pe + d * rr * stop_mult * a
        best = cc[j]; carry = 0.0; px = 0.0; reason = 4; k = ke
        while k < n5:
            jb = tfclose_at5[k]
            if exit_mode == 1 and jb >= 0 and jb != j:
                if d > 0:
                    best = max(best, cc[jb]); stop = max(stop, best - trail_mult * atr[jb])
                else:
                    best = min(best, cc[jb]); stop = min(stop, best + trail_mult * atr[jb])
            if k > ke: carry += carryL[k] if d > 0 else carryS[k]
            if max_hold_s > 0 and t5[k] - te >= max_hold_s:
                px = o5[k]; reason = 3; break
            if cycle_s == 0:
                if d > 0:
                    if o5[k] <= stop: px = o5[k]; reason = 2 if exit_mode == 1 else 0; break
                    if l5[k] <= stop: px = stop; reason = 2 if exit_mode == 1 else 0; break
                    if exit_mode == 0 and o5[k] >= tgt: px = o5[k]; reason = 1; break
                    if exit_mode == 0 and h5[k] >= tgt: px = tgt; reason = 1; break
                else:
                    if o5[k] >= stop: px = o5[k]; reason = 2 if exit_mode == 1 else 0; break
                    if h5[k] >= stop: px = stop; reason = 2 if exit_mode == 1 else 0; break
                    if exit_mode == 0 and o5[k] <= tgt: px = o5[k]; reason = 1; break
                    if exit_mode == 0 and l5[k] <= tgt: px = tgt; reason = 1; break
            elif k > ke and (t5[k] % cycle_s) == 0:
                p = o5[k]
                if d * (p - stop) <= 0: px = p; reason = 2 if exit_mode == 1 else 0; break
                if exit_mode == 0 and d * (p - tgt) >= 0: px = p; reason = 1; break
            k += 1
        if k >= n5: k = n5 - 1; px = o5[k]; reason = 4
        gross = d * (px / pe - 1.0)
        out[m, 0] = te; out[m, 1] = t5[k]; out[m, 2] = d; out[m, 3] = pe; out[m, 4] = px
        out[m, 5] = gross - 2 * cost - carry; out[m, 6] = reason; m += 1
        free_t = t5[k]
        j += 1
    return out[:m]
