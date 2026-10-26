"""Track C proxy backtest on Binance SOLUSDT 1m spot (no World prices available: API gated).
Target = window open price (Binance proxy for Chainlink start price). Result = close at window end > target.
Tests: (2) fair-value Phi model calibration by checkpoint vs coin flip;
       (1) opening-window direction model (prev 5-30m momentum + 1h/4h EMA trend) vs 50/50 after fees.
In-sample Jan-Jun 2026, out-of-sample Jul-Oct 22 2026."""
import glob, json, math, numpy as np, pandas as pd
from math import erf
fs=sorted(glob.glob('/workspace/sol-trend/track-c/data/spot/*.csv'))
df=pd.concat([pd.read_csv(f,header=None,usecols=[0,1,4]) for f in fs]); df.columns=['t','o','c']
df['t']=np.where(df.t>1e14,df.t//1000,df.t); df=df.drop_duplicates('t').sort_values('t').reset_index(drop=True)
df['ts']=pd.to_datetime(df.t,unit='ms',utc=True); df=df.set_index('ts')
c=df.c; lr=np.log(c).diff()
vol1m=lr.rolling(60).std()             # 1h realised vol per minute
Phi=lambda x: 0.5*(1+np.vectorize(erf)(x/np.sqrt(2)))
ema1h=c.ewm(span=60*20).mean(); ema4h=c.ewm(span=240*20).mean()  # ~20-bar EMAs on 1h/4h
OOS=pd.Timestamp('2026-07-01',tz='UTC')
fee=lambda p: 0.1*p*(1-p)   # Phantom per-contract fee
out={'rows':len(df),'start':str(df.index[0]),'end':str(df.index[-1])}
res=[]; open_res=[]
for W in [5,15,60]:
    starts=df.index[(df.index.minute% W==0) if W<60 else (df.index.minute==0)]
    starts=[s for s in starts if s+pd.Timedelta(minutes=W) in df.index and s-pd.Timedelta(minutes=30) in df.index]
    S=pd.DatetimeIndex(starts)
    tgt=df.o.reindex(S).values      # window open
    fin=c.reindex(S+pd.Timedelta(minutes=W-1)).values
    up=(fin>tgt).astype(int)
    for cp in [10,5,3,2,1]:
        if cp>=W: continue
        tl=cp; obs=S+pd.Timedelta(minutes=W-cp-1)  # close of minute leaving cp minutes
        spot=c.reindex(obs).values; sg=vol1m.reindex(obs).values
        p=Phi(np.log(spot/tgt)/(sg*np.sqrt(tl)))
        for name,mask in [('IS',S<OOS),('OOS',S>=OOS)]:
            m=mask&~np.isnan(p); y=up[m]; pp=np.clip(p[m],1e-4,1-1e-4)
            res.append(dict(window=W,checkpoint_min=cp,sample=name,n=int(m.sum()),
              brier_model=float(np.mean((pp-y)**2)),brier_coin=0.25,
              acc_fav=float(np.mean((pp>0.5)==y)),
              mean_fav_prob=float(np.mean(np.maximum(pp,1-pp))),
              calib_gap=float(np.mean(np.maximum(pp,1-pp))-np.mean((pp>0.5)==y))))
    # (1) opening entry: signal at window open using prior momentum & EMA trend
    prev=S-pd.Timedelta(minutes=1)
    for lb in [5,10,15,30]:
        mom=np.log(c.reindex(prev).values/c.reindex(S-pd.Timedelta(minutes=lb)).values)
        tr=np.sign(ema1h.reindex(prev).values-ema4h.reindex(prev).values)
        for rule in ['mom','trend','mom+trend','meanrev']:
            if rule=='mom': sig=np.sign(mom)
            elif rule=='trend': sig=tr
            elif rule=='meanrev': sig=-np.sign(mom)
            else: sig=np.where(np.sign(mom)==tr,tr,0)
            for name,mask in [('IS',S<OOS),('OOS',S>=OOS)]:
                m=mask&(sig!=0); y=up[m]; s_=sig[m]
                win=((s_>0)&(y==1))|((s_<0)&(y==0))
                # pay 0.50 + half spread 0.01 + fee at 0.5 -> cost 0.535 per $1 payout
                cost=0.50+0.01+fee(0.5)
                pnl=win*1.0-cost
                # worst losing streak
                ls=mx=0
                for w in win:
                    ls=0 if w else ls+1; mx=max(mx,ls)
                open_res.append(dict(window=W,lookback=lb,rule=rule,sample=name,n=int(m.sum()),
                   hit=float(win.mean()),breakeven=cost,ev_per_contract=float(pnl.mean()),
                   worst_streak=mx))
R=pd.DataFrame(res); O=pd.DataFrame(open_res)
R.to_csv('/workspace/sol-trend/track-c/reports/fairvalue_calibration.csv',index=False)
O.to_csv('/workspace/sol-trend/track-c/reports/opening_entry.csv',index=False)
pd.set_option('display.width',200)
print(json.dumps(out)); print(R.round(4).to_string()); 
print(O[O['sample']=='OOS'].sort_values('hit',ascending=False).round(4).head(12).to_string())
print(O.groupby(['window','sample']).hit.agg(['min','max']).round(4))
