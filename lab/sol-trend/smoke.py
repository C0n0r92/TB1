"""Quick smoke test: the pre-registered default settings only (no tuning). Not a scored result."""
import numpy as np, pandas as pd, engine as E
d5 = E.load5(); t5 = d5.t.values.astype(np.int64); T0, T1 = t5[0], t5[-1]
HOLD = T0 + int(0.6 * (T1 - T0)); z = np.zeros(len(t5)); jb = np.full(len(t5), 0.00003 / 12)
for tf, trend, lev in [("1h", "ema50_200", "n20"), ("4h", "ema200", "n55")]:
    b = E.indicators(E.resample(d5, tf)); fix = np.full(len(t5), -1, np.int64)
    idx = ((b.tc.values - T0) // 300).astype(np.int64); ok = idx < len(t5); fix[idx[ok]] = np.where(ok)[0]
    L, S = E.signals(b, trend, lev, "close")
    for track, side, cost, cl in [("A spot long", 0, 0.002, z), ("B perp L+S (Jup)", 1, 0.0016, jb)]:
        tr = E.simulate(t5, d5.o.values, d5.h.values, d5.l.values, b.tc.values.astype(np.int64), b.c.values, b.atr.values, L, S, fix,
                        side, 2.0, 1, 0.0, 3.0, 300, cost, cl, cl, 0)
        r = tr[:, 5]; o = tr[:, 0] >= HOLD
        print(f"{track:18s} {tf} {trend} {lev} stop2ATR trail3 cy5: n={len(r)} (oos {o.sum()}) win={np.mean(r>0):.2f} mean={r.mean()*100:+.2f}% "
              f"sum_in={r[~o].sum()*100:+.1f}% sum_oos={r[o].sum()*100:+.1f}% cum_oos={np.prod(1+r[o])-1:+.1%}")
i = np.searchsorted(t5, HOLD); print(f"buy&hold OOS (from {pd.to_datetime(HOLD,unit='s').date()}): {d5.c.values[-1]/d5.o.values[i]-1:+.1%}; full: {d5.c.values[-1]/d5.o.values[0]-1:+.1%}")
