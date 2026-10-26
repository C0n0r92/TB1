import sys; sys.dont_write_bytecode=True
import numpy as np, pandas as pd
from run import load_groups, ts, MAJ
from tvlib import backtest, stats
from strategies import STRATS
import os
H=os.path.dirname(os.path.abspath(__file__))
L=[]
for s in MAJ:
    df=pd.read_csv(f"{H}/data/{s}_1h.csv"); L.append((s,dict(t=df.t_ms.values//1000,o=df.o.values,h=df.h.values,l=df.l.values,c=df.c.values)))
for name in ("rsi_trend","stochastic_trend","flawless_victory"):
  for lab,a,b in (("pre 2025-01-01..2026-02-01",ts("2025-01-01"),ts("2026-02-01")),("held 2026-02-01..",ts("2026-02-01"),None)):
    for cost in (0.001,0.003,0.01):
        nets=[];holds=[];T=[]
        for s,d in L:
            i0=int(np.searchsorted(d["t"],a)); i1=None if b is None else int(np.searchsorted(d["t"],b))
            tr,eq=backtest(d,STRATS[name](d,60),cost,i0,i1); 
            nets.append(eq[-1]-1); T+=tr
            j=(i1 or len(d["c"]))-1; holds.append(d["c"][j]/d["o"][i0]-1-2*cost)
        r=np.array([t[2] for t in T]); pf=r[r>0].sum()/-r[r<0].sum()
        print(f"{name:17s} {lab:28s} c={cost:.3f} n={len(T):4d} mean={np.mean(nets):+.3f} median={np.median(nets):+.3f} pf={pf:.2f} hold_mean={np.mean(holds):+.3f} hold_med={np.median(holds):+.3f}")
