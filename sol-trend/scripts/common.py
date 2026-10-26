"""Shared setup for study.py and forward.py (PAPER ONLY). Loads 5m SOLUSDT, builds TF bars + indicators, carry arrays and cost table."""
import os, numpy as np, pandas as pd
import engine as E
ROOT = E.ROOT; DATA = E.DATA
H5 = 1 / 12
# ---- venue fees (looked up 2026-10-23, see reports/first-read.md) ----
FEE = {"spot": 0.0002,   # Jupiter Ultra/Swap platform fee SOL<->stable = 2 bps; AMM pool fee/impact treated as part of slippage
       "jup": 0.0006,    # Jupiter Perps base fee 0.06% open and close (+ price-impact fee, small at small size -> inside slippage)
       "drift": 0.0006}  # Drift/Velocity SOL-PERP regular taker: 6 bps (velocity docs); docs.drift.trade shows 4 bps - use the higher
SLIP = {"lo": 0.001, "mid": 0.002, "hi": 0.003}
JUP_BORROW_H = 0.00003    # assumed 0.003%/h both sides (no free history; observed ~0.0016%/h long, ~0.0007%/h short)

def htf_cols(b, b4):
    """Attach last COMPLETED 4h bar's EMA50/EMA200 state to bars of another TF, aligned on close time (tc4 <= tc)."""
    x = pd.merge_asof(b[["tc"]].reset_index(), b4[["tc", "ema50", "ema200"]].rename(columns={"tc": "tc4"}), left_on="tc", right_on="tc4", direction="backward")
    b["htf_up"] = (x.ema50 > x.ema200).fillna(False).values; b["htf_dn"] = (x.ema50 < x.ema200).fillna(False).values
    return b

def load():
    d5 = E.load5(); t5 = d5.t.values.astype(np.int64)
    BARS = {tf: E.indicators(E.resample(d5, tf)) for tf in E.TF_MIN}
    for tf in BARS: BARS[tf] = htf_cols(BARS[tf], BARS["4h"])
    T0 = int(t5[0]); FIX = {}
    for tf, b in BARS.items():
        m = np.full(len(t5), -1, np.int64); idx = ((b.tc.values - T0) // 300).astype(np.int64)
        ok = (idx >= 0) & (idx < len(t5)); ok[ok] &= t5[idx[ok]] == b.tc.values[ok]; m[idx[ok]] = np.where(ok)[0]; FIX[tf] = m
    # carry per 5m bar: Hyperliquid hourly funding as Drift proxy (rate at hour h applies to bars in [h, h+1h)); positive = long pays
    f = pd.read_csv(os.path.join(DATA, "HL_SOL_funding.csv")); fh = dict(zip(f.t.values // 3600, f.rate.values))
    hr = t5 // 3600; fr = np.array([fh.get(h, np.nan) for h in hr]); fr = pd.Series(fr).ffill().fillna(JUP_BORROW_H).values * H5
    z = np.zeros(len(t5)); jb = np.full(len(t5), JUP_BORROW_H * H5)
    CARRY = {"spot": (z, z), "jup": (jb, jb), "drift": (fr, -fr)}
    return d5, t5, BARS, FIX, CARRY

class Sim:
    def __init__(self):
        self.d5, self.t5, self.BARS, self.FIX, self.CARRY = load(); self.sig = {}
    def signals(self, tf, trend, level, confirm):
        k = (tf, trend, level, confirm)
        if k not in self.sig: self.sig[k] = E.signals(self.BARS[tf], trend, level, confirm)
        return self.sig[k]
    def run(self, V, slip=None, cycle=None, venue=None):
        venue = venue or V["venue"]; slip = slip or V.get("slip", "mid"); cycle = V.get("cycle", 5) if cycle is None else cycle
        b = self.BARS[V["tf"]]; L, S = self.signals(V["tf"], V["trend"], V["level"], V["confirm"]); cL, cS = self.CARRY[venue]
        d = self.d5; ex = V["exit"]
        return E.simulate(self.t5, d.o.values, d.h.values, d.l.values, b.tc.values.astype(np.int64), b.c.values, b.atr.values, L, S, self.FIX[V["tf"]],
                          1 if V["side"] == "ls" else 0, float(V["stop"]), 1 if ex.startswith("trail") else 0,
                          float(ex[2:]) if ex.startswith("rr") else 0.0, float(ex[5:]) if ex.startswith("trail") else 0.0,
                          int(cycle) * 60, FEE[venue] + SLIP[slip], cL, cS, 0)

def name(V):
    return "SOLT_{track}_{tf}_{trend}_{level}_{confirm}_s{stop}_{exit}".format(**V)
