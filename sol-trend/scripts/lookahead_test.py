"""Lookahead check: signals computed on data truncated at T must equal full-data signals for all bars closed before T."""
import numpy as np, pandas as pd, itertools, engine as E, common as C
d5 = E.load5(); full = {}; bad = 0; checked = 0
for tf in ["15m", "1h", "4h"]:
    bF = C.htf_cols(E.indicators(E.resample(d5, tf)), E.indicators(E.resample(d5, "4h")))
    for cut in (0.35, 0.6, 0.85):
        T = int(d5.t.iloc[int(len(d5) * cut)]); dT = d5[d5.t < T]
        bT = C.htf_cols(E.indicators(E.resample(dT, tf)), E.indicators(E.resample(dT, "4h")))
        for trend, level, conf in itertools.product(["none", "ema200up", "ema50_200", "htf"], ["n20", "n55", "pivot"], ["close", "vol", "retest"]):
            LF, SF = E.signals(bF, trend, level, conf); LT, ST = E.signals(bT, trend, level, conf); n = len(bT)
            # retest looks forward from the breakout bar only to set the signal ON the later retest bar, so compare all bars < n
            d = (LF[:n] != LT).sum() + (SF[:n] != ST).sum(); bad += d; checked += 1
            if d: print("MISMATCH", tf, cut, trend, level, conf, d)
print(f"lookahead test: {checked} signal sets checked, mismatching bars = {bad}")
