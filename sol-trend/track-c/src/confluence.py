"""Track C confluence test (main: SOL 15m Up/Down; second: 1h).
Bet only when trend filter on window TF and next-higher TF agree, a recent S/R break confirmed by close beyond level
+ above-avg volume, momentum agrees, and the chop filter (ADX) passes. Concepts mirror Tracks A/B (EMA trend, pivot/level
break, volume confirm), recomputed from Binance 1m (data.binance.vision) so windows align exactly.
Market price is NOT available (World API gated): at window open assume 0.50; at +2m/+5m assume the market = model fair value
(efficient proxy). Cost = price + half-spread + Phantom fee 0.1p(1-p). IS = Jan-Jun 2026, OOS = Jul-22 Oct 2026."""
import glob, json, itertools, numpy as np, pandas as pd
from math import erf
fs=sorted(glob.glob('/workspace/sol-trend/track-c/data/spot/*.csv'))
d=pd.concat([pd.read_csv(f,header=None,usecols=[0,1,2,3,4,5]) for f in fs]); d.columns=['t','o','h','l','c','v']
d['t']=np.where(d.t>1e14,d.t//1000,d.t); d=d.drop_duplicates('t').sort_values('t')
d.index=pd.to_datetime(d.t,unit='ms',utc=True); c1=d.c
vol1m=np.log(c1).diff().rolling(60).std()
Phi=lambda x:0.5*(1+np.vectorize(erf)(x/np.sqrt(2)))
fee=lambda p:0.1*p*(1-p)
OOS=pd.Timestamp('2026-07-01',tz='UTC')
def bars(rule):
    return d.resample(rule,label='left',closed='left').agg({'o':'first','h':'max','l':'min','c':'last','v':'sum'}).dropna()
def adx(b,n=14):
    up=b.h.diff(); dn=-b.l.diff()
    pdm=np.where((up>dn)&(up>0),up,0.); mdm=np.where((dn>up)&(dn>0),dn,0.)
    tr=pd.concat([b.h-b.l,(b.h-b.c.shift()).abs(),(b.l-b.c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/n).mean(); pdi=100*pd.Series(pdm,b.index).ewm(alpha=1/n).mean()/atr; mdi=100*pd.Series(mdm,b.index).ewm(alpha=1/n).mean()/atr
    return (100*(pdi-mdi).abs()/(pdi+mdi)).ewm(alpha=1/n).mean()
def feats(b,lvl,volm):
    f=pd.DataFrame(index=b.index); e=b.c.ewm(span=50).mean()
    f['tr']=np.where((b.c>e)&(e.diff(3)>0),1,np.where((b.c<e)&(e.diff(3)<0),-1,0))
    f['adx']=adx(b)
    res=b.h.rolling(lvl).max().shift(1); sup=b.l.rolling(lvl).min().shift(1); va=b.v.rolling(20).mean().shift(1)
    brk=np.where((b.c>res)&(b.v>volm*va),1,np.where((b.c<sup)&(b.v>volm*va),-1,0))
    f['brk']=pd.Series(brk,b.index).replace(0,np.nan).ffill(limit=2).fillna(0)
    f['mom']=np.sign(b.c-b.c.shift(3))
    return f
BW={15:bars('15min'),60:bars('1h')}; BH={'1h':bars('1h'),'4h':bars('4h')}
def run(W,HT,lvl,volm,adx_min,offsets):
    bw=BW[W]; bh=BH[HT]
    fw=feats(bw,lvl,volm); fh=feats(bh,lvl,volm)
    fwS=fw.shift(1)
    fh_known=fh.copy(); fh_known.index=fh_known.index+pd.Timedelta(HT)  # available after HTF bar closes
    fhS=fh_known.reindex(bw.index,method='ffill')
    sig=np.where((fwS.tr==fhS.tr)&(fwS.tr!=0)&(fwS.brk==fwS.tr)&(fwS.mom==fwS.tr)&(fwS.adx>adx_min),fwS.tr,0)
    S=bw.index; tgt=bw.o.values; up=(bw.c.values>tgt)
    out=[]
    for off in offsets:
        if off==0: price_up=np.full(len(S),0.5)
        else:
            t=S+pd.Timedelta(minutes=off-1); tl=W-off
            price_up=Phi(np.log(c1.reindex(t).values/tgt)/(vol1m.reindex(t).values*np.sqrt(tl)))
        out.append((off,price_up))
    return S,sig,up,out,tgt
def score(x,S,win):
    ls=mx=0
    for w in win: ls=0 if w else ls+1; mx=max(mx,ls)
    mon=pd.Series(x,index=S).resample('MS').sum()
    return dict(n=len(x),hit=float(np.mean(win)) if len(x) else np.nan,ev=float(np.mean(x)) if len(x) else np.nan,total=float(np.sum(x)),
                worst_streak=mx,pos_months=f"{int((mon>0).sum())}/{len(mon)}")
rows=[]; ledger=[]; HS=0.01
grid=list(itertools.product([20,48],[1.2,1.5],[20,25]))
for W,HT,offs in [(15,'1h',[0,2,5]),(60,'4h',[0,5,10])]:
    for lvl,volm,am in grid:
        S,sig,up,outs,tgt=run(W,HT,lvl,volm,am,offs)
        for off,pu in outs:
            ok=(sig!=0)&~np.isnan(pu)
            p_side=np.where(sig>0,pu,1-pu); win=np.where(sig>0,up,~up)
            cost=p_side+HS+fee(p_side); pnl=win-cost
            pnl_b=pnl.copy(); pnl_c=pnl.copy()
            done_b=np.zeros(len(S),bool); done_c=np.zeros(len(S),bool)
            for k in range(off+1,W):
                t=S+pd.Timedelta(minutes=k-1); f=Phi(np.log(c1.reindex(t).values/tgt)/(vol1m.reindex(t).values*np.sqrt(W-k)))
                fs_=np.where(sig>0,f,1-f); bid=np.clip(fs_-HS,0.01,0.99)
                cb=(bid>=0.90)&~done_b&ok; pnl_b=np.where(cb,bid-fee(bid)-cost,pnl_b); done_b|=cb
                cc=(fs_<0.2)&(bid>fs_)&~done_c&ok; pnl_c=np.where(cc,bid-fee(bid)-cost,pnl_c); done_c|=cc
            for smp,mask in [('IS',S<OOS),('OOS',S>=OOS)]:
                m=ok&mask
                for var,arr in [('hold',pnl),('cashout_lock90',pnl_b),('cashout_cut20',pnl_c)]:
                    r=dict(window=W,lvl=lvl,volm=volm,adx=am,entry_min=off,variant=var,sample=smp); r.update(score(arr[m],S[m],win[m])); rows.append(r)
                if (lvl,volm,am)==grid[0]:
                    allm=mask&~np.isnan(pu)
                    rng=np.random.default_rng(0); cf=rng.random(len(S))<0.5
                    ps=np.where(cf,pu,1-pu); w=np.where(cf,up,~up); x=w-(ps+HS+fee(ps))
                    r=dict(window=W,lvl='-',volm='-',adx='-',entry_min=off,variant='BASE_coinflip',sample=smp); r.update(score(x[allm],S[allm],w[allm])); rows.append(r)
                    fav=pu>=0.5; ps=np.where(fav,pu,1-pu); w=np.where(fav,up,~up); x=w-(ps+HS+fee(ps))
                    r=dict(window=W,lvl='-',volm='-',adx='-',entry_min=off,variant='BASE_follow_market',sample=smp); r.update(score(x[allm],S[allm],w[allm])); rows.append(r)
            if (lvl,volm,am)==(20,1.5,20) and off==0:
                for i in np.where(ok)[0]:
                    ledger.append(dict(track='C',kind='PROXY_PAPER(no World price)',market=f'SOL-{W}m',window_start=str(S[i]),side='UP' if sig[i]>0 else 'DOWN',
                        entry_min=0,assumed_price=float(p_side[i]),cost=float(cost[i]),target=float(tgt[i]),won=bool(win[i]),pnl_per_contract=float(pnl[i]),
                        sample='OOS' if S[i]>=OOS else 'IS',params=dict(lvl=lvl,volm=volm,adx=am)))
        if W==15 and (lvl,volm,am)==(20,1.5,20):
            hrs=pd.DatetimeIndex(S[sig!=0]).tz_convert('Europe/Dublin').hour
            days=(S[-1]-S[0]).days
            per_hour=pd.Series(hrs).value_counts().sort_index()/days
            json.dump(dict(days=days,bets_per_day=float((sig!=0).sum()/days),night_18_02=float(per_hour[[h for h in per_hour.index if h>=18 or h<2]].sum()),
                per_hour_dublin={int(k):round(float(v),3) for k,v in per_hour.items()}),open('/workspace/sol-trend/track-c/reports/bets_per_hour_15m.json','w'),indent=1)
R=pd.DataFrame(rows); R.to_csv('/workspace/sol-trend/track-c/reports/confluence_results.csv',index=False)
with open('/workspace/sol-trend/track-c/ledger.jsonl','w') as f:
    for l in ledger: f.write(json.dumps(l)+'\n')
pd.set_option('display.width',250); pd.set_option('display.max_rows',500)
print(R[(R['sample']=='OOS')&(R.variant.isin(['hold','BASE_coinflip','BASE_follow_market']))].round(4).to_string())
