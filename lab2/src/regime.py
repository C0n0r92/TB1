"""Market regime tagger (point-in-time). Reusable for pairs, SMC and older-coins reruns.

regime_at(times) -> DataFrame[regime, sol_slope, btc_slope, atr_pct, sol_ret24] for each timestamp, using only 4h bars
that CLOSED at or before that timestamp (merge_asof backward on close-indexed bars).

Inputs: SOL and BTC 1h closes (Binance public klines), resampled to 4h.
 - slope   = (EMA20_4h now / EMA20_4h 6 bars ago - 1) / (ATR14_4h / close)   -> trend move over 24h in ATR units
 - atr_pct = percentile of SOL ATR14_4h/close within its trailing 90 days (180 x 4h bars... uses 540 bars) - past only
 - sol_ret24 = SOL return over the last 6 closed 4h bars
Labels (priority order):
 crash    : sol_ret24 <= CRASH_RET  OR (atr_pct >= HV_PCT and sol_slope <= -TREND_K)
 high_vol : atr_pct >= HV_PCT
 trending : |sol_slope| >= TREND_K and sign(btc_slope) == sign(sol_slope)   (direction in column 'dir')
 choppy   : everything else
Default thresholds are round numbers, NOT tuned. Any gate built on these must pick thresholds on training data only.
"""
import numpy as np, pandas as pd
from data import binance, resample
DEFAULT = dict(CRASH_RET=-0.08, HV_PCT=0.80, TREND_K=1.0, PCT_WIN=540)

def _feat(c1h):
    d = resample(c1h, "4h")
    ema = d.c.ewm(span=20, adjust=False).mean()
    tr = pd.concat([d.h - d.l, (d.h - d.c.shift()).abs(), (d.l - d.c.shift()).abs()], axis=1).max(axis=1)
    atrn = tr.rolling(14).mean() / d.c
    slope = (ema / ema.shift(6) - 1) / atrn
    return d, slope, atrn

def build(params=None, sol=None, btc=None):
    P = dict(DEFAULT, **(params or {}))
    sol = sol if sol is not None else binance("SOL", "1h"); btc = btc if btc is not None else binance("BTC", "1h")
    d, s_sl, atrn = _feat(sol); _, b_sl, _ = _feat(btc)
    pct = atrn.rolling(P["PCT_WIN"], min_periods=120).apply(lambda a: (a[:-1] < a[-1]).mean(), raw=True)
    r24 = d.c / d.c.shift(6) - 1
    f = pd.DataFrame({"sol_slope": s_sl, "btc_slope": b_sl.reindex(s_sl.index), "atr_pct": pct, "sol_ret24": r24}).dropna()
    lab = np.where((f.sol_ret24 <= P["CRASH_RET"]) | ((f.atr_pct >= P["HV_PCT"]) & (f.sol_slope <= -P["TREND_K"])), "crash",
          np.where(f.atr_pct >= P["HV_PCT"], "high_vol",
          np.where((f.sol_slope.abs() >= P["TREND_K"]) & (np.sign(f.btc_slope) == np.sign(f.sol_slope)), "trending", "choppy")))
    f["regime"] = lab; f["dir"] = np.sign(f.sol_slope).astype(int)
    return f

def regime_at(times, table):
    """times: iterable of tz-aware timestamps (decision times). Backward as-of join -> only closed 4h bars."""
    q = pd.DataFrame({"t": pd.to_datetime(list(times), utc=True)}).sort_values("t")
    tb = table.reset_index().rename(columns={"index": "t"}).sort_values("t")
    tb["t"] = pd.to_datetime(tb["t"], utc=True)
    out = pd.merge_asof(q, tb, on="t", direction="backward")
    return out.set_index("t")

if __name__ == "__main__":
    tb = build(); print(tb.regime.value_counts(normalize=True).round(3)); print(tb.tail())
