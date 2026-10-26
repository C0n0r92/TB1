"""Lab 2 / TradingView port: Pine-like indicators + long-only bar-close engine. No look-ahead:
signals use data up to close[i]; fills at open[i+1]; protective stops/TPs are set from data up to the
previous close and checked intrabar (stop before TP; gap through -> fill at open)."""
import numpy as np, pandas as pd

def _s(x): return pd.Series(np.asarray(x, dtype=float))
def sma(x, n): return _s(x).rolling(n, min_periods=n).mean().values
def ema(x, n):
    x = np.asarray(x, float); out = np.full(len(x), np.nan); a = 2.0 / (n + 1); prev = np.nan
    for i, v in enumerate(x):
        if np.isnan(v): out[i] = prev; continue
        prev = v if np.isnan(prev) else a * v + (1 - a) * prev; out[i] = prev
    return out
def rma(x, n):
    x = np.asarray(x, float); out = np.full(len(x), np.nan); prev = np.nan; buf = []
    for i, v in enumerate(x):
        if np.isnan(v): out[i] = prev; continue
        if np.isnan(prev):
            buf.append(v)
            if len(buf) == n: prev = float(np.mean(buf)); out[i] = prev
            continue
        prev = (prev * (n - 1) + v) / n; out[i] = prev
    return out
def stdev(x, n): return _s(x).rolling(n, min_periods=n).std(ddof=0).values
def highest(x, n): return _s(x).rolling(n, min_periods=n).max().values
def lowest(x, n): return _s(x).rolling(n, min_periods=n).min().values
def shift(x, k=1):
    x = np.asarray(x, float); out = np.full(len(x), np.nan)
    if k > 0: out[k:] = x[:-k]
    else: out[:] = x
    return out
def change(x, k=1): return np.asarray(x, float) - shift(x, k)
def rsi(c, n=14):
    d = change(c); up = rma(np.where(np.isnan(d), np.nan, np.maximum(d, 0)), n); dn = rma(np.where(np.isnan(d), np.nan, np.maximum(-d, 0)), n)
    with np.errstate(divide='ignore', invalid='ignore'):
        r = 100 - 100 / (1 + up / dn)
    r = np.where(dn == 0, 100, np.where(up == 0, 0, r)); return r
def tr(h, l, c):
    pc = shift(c); t = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc))); t[0] = h[0] - l[0]; return t
def atr(h, l, c, n): return rma(tr(h, l, c), n)
def stoch(c, h, l, n):
    hh, ll = highest(h, n), lowest(l, n)
    with np.errstate(divide='ignore', invalid='ignore'):
        return 100 * (c - ll) / (hh - ll)
def crossover(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if b.ndim == 0: b = np.full(len(a), float(b))
    return (a > b) & (shift(a) <= shift(b))
def crossunder(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if b.ndim == 0: b = np.full(len(a), float(b))
    return (a < b) & (shift(a) >= shift(b))
def cross(a, b): return crossover(a, b) | crossunder(a, b)

def backtest(d, sig, cost, i0, i1=None):
    """d: dict of np arrays o,h,l,c (+t). sig: dict with bool arrays 'enter','exit' and optional
    'stop_fixed' (level from signal bar, fixed for the trade), 'trail' (candidate stop, ratcheted up),
    'trail_from' ('signal'|'fill'), 'trail_on_close' (exit next open when close < trail instead of intrabar),
    'tp_rr' (TP = fill + rr*(fill - stop_fixed)). Only trades whose ENTRY SIGNAL bar is in [i0, i1) count;
    open position at the end is marked out at the last close. Returns trades list and MTM equity curve over [i0,i1)."""
    o, h, l, c = d['o'], d['h'], d['l'], d['c']; n = len(c) if i1 is None else i1
    en, ex = sig['enter'], sig['exit']; sf = sig.get('stop_fixed'); tc = sig.get('trail')
    tfrom = sig.get('trail_from', 'signal'); ton = sig.get('trail_on_close', False); rr = sig.get('tp_rr')
    trades = []; eq = np.ones(n - i0); E = 1.0; pos = False; i = i0
    entry = stop = tp = trail = np.nan; ebar = -1; pend_exit = False
    while i < n:
        if not pos:
            eq[i - i0] = E
            if en[i] and not ex[i] and i + 1 < n:
                entry = o[i + 1]; ebar = i + 1; pos = True
                stop = sf[i] if sf is not None else np.nan
                trail = (tc[i] if (tc is not None and tfrom == 'signal') else np.nan)
                tp = entry + rr * (entry - stop) if (rr is not None and not np.isnan(stop)) else np.nan
                i += 1; pend_exit = False
                # fall through to process fill bar i (no protective orders active on the fill bar)
            else:
                i += 1; continue
        # in position at bar i
        xp = np.nan
        if i > ebar:
            if pend_exit: xp = o[i]
            else:
                cs = [x for x in ([stop] + ([] if ton else [trail])) if not np.isnan(x)]; S = max(cs) if cs else np.nan
                if not np.isnan(S) and (o[i] <= S or l[i] <= S): xp = min(o[i], S)
                elif not np.isnan(tp) and (o[i] >= tp or h[i] >= tp): xp = max(o[i], tp)
        if not np.isnan(xp):
            r = xp * (1 - cost) / (entry * (1 + cost)) - 1; E *= (1 + r); trades.append((ebar, i, r)); pos = False
            eq[i - i0] = E
            i += 1; continue
        # bar close updates
        if tc is not None and not np.isnan(tc[i]): trail = tc[i] if np.isnan(trail) else max(trail, tc[i])
        eq[i - i0] = E * (c[i] * (1 - cost) / (entry * (1 + cost)))
        pend_exit = bool(ex[i]) or (ton and not np.isnan(trail) and c[i] < trail)
        if i == n - 1:
            r = c[i] * (1 - cost) / (entry * (1 + cost)) - 1; E *= (1 + r); trades.append((ebar, i, r)); eq[i - i0] = E; pos = False
        i += 1
    return trades, eq

def stats(trades, eq):
    r = np.array([t[2] for t in trades]) if trades else np.array([])
    g, ls = r[r > 0].sum(), -r[r < 0].sum()
    pf = g / ls if ls > 0 else (np.inf if g > 0 else np.nan)
    peak = np.maximum.accumulate(eq); dd = (1 - eq / peak).max() if len(eq) else 0
    return dict(n=len(r), net=eq[-1] - 1 if len(eq) else 0, pf=pf, win=(r > 0).mean() if len(r) else np.nan, dd=dd)
