"""Proxy cash-out simulation. NO World bid data exists (API gated), so the market bid is SIMULATED as
fair P (Phi model, 1h realised vol) minus half-spread, with Phantom sell fee 0.1p(1-p).
Re-check granularity = 60s (Binance 1m), not 10-15s. Entry: at window open, side = mean-reversion of prior
15m (best opening rule), cost 0.5 + half-spread + fee. 5m and 15m windows; OOS = Jul-Oct 2026."""
import glob, json, numpy as np, pandas as pd
from math import erf
fs=sorted(glob.glob('/workspace/sol-trend/track-c/data/spot/*.csv'))
df=pd.concat([pd.read_csv(f,header=None,usecols=[0,1,4]) for f in fs]); df.columns=['t','o','c']
df['t']=np.where(df.t>1e14,df.t//1000,df.t); df=df.drop_duplicates('t').sort_values('t')
df.index=pd.to_datetime(df.t,unit='ms',utc=True); c=df.c
vol=np.log(c).diff().rolling(60).std()
Phi=lambda x:0.5*(1+np.vectorize(erf)(x/np.sqrt(2)))
fee=lambda p:0.1*p*(1-p)
OOS=pd.Timestamp('2026-07-01',tz='UTC'); rows=[]; ledger=[]
for W in [5,15]:
    S=df.index[df.index.minute%W==0]
    S=pd.DatetimeIndex([s for s in S if s+pd.Timedelta(minutes=W) in df.index and s-pd.Timedelta(minutes=16) in df.index])
    tgt=df.o.reindex(S).values; fin=c.reindex(S+pd.Timedelta(minutes=W-1)).values; up=fin>tgt
    mom=np.log(c.reindex(S-pd.Timedelta(minutes=1)).values/c.reindex(S-pd.Timedelta(minutes=16)).values)
    side_up=mom<0   # mean reversion
    win=np.where(side_up,up,~up)
    # fair P(side) at each minute k=1..W-1 elapsed
    F=[]
    for k in range(1,W):
        t=S+pd.Timedelta(minutes=k-1); tl=W-k
        p=Phi(np.log(c.reindex(t).values/tgt)/(vol.reindex(t).values*np.sqrt(tl)))
        F.append(np.where(side_up,p,1-p))
    F=np.array(F).T  # n x (W-1)
    for hs in [0.01,0.02]:
        cost=0.5+hs+fee(0.5)
        rules={'hold':None}
        for m in [0.0,0.02,0.05]: rules[f'a_bid>fair+{m}']=('a',m)
        for th in [0.85,0.90]: rules[f'b_bid>={th}']=('b',th)
        for th in [0.2,0.3]: rules[f'c_cut_fair<{th}']=('c',th)
        for name,r in rules.items():
            pnl=np.where(win,1.0,0.0)-cost; exited=np.zeros(len(S),bool)
            if r:
                for k in range(F.shape[1]):
                    f=F[:,k]; bid=np.clip(f-hs,0.01,0.99)   # simulated: market = fair
                    if r[0]=='a': cond=bid>f+r[1]
                    elif r[0]=='b': cond=bid>=r[1]
                    else: cond=(f<r[1])&(bid>f)
                    cond&=~exited&~np.isnan(f)
                    pnl=np.where(cond,bid-fee(bid)-cost,pnl); exited|=cond
            for smp,mask in [('IS',S<OOS),('OOS',S>=OOS)]:
                x=pnl[mask]; mon=pd.Series(x,index=S[mask]).resample('MS').sum()
                rows.append(dict(window=W,half_spread=hs,rule=name,sample=smp,n=len(x),exit_rate=float(exited[mask].mean()),
                    ev_per_contract=float(x.mean()),total=float(x.sum()),pos_months=f"{int((mon>0).sum())}/{len(mon)}"))
R=pd.DataFrame(rows); R.to_csv('/workspace/sol-trend/track-c/reports/cashout_sim.csv',index=False)
pd.set_option('display.width',200); print(R[R['sample']=='OOS'].round(4).to_string())
