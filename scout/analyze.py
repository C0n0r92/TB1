"""Rebuild round trips from cached swap legs (data/w/<wallet>.json). Read-only."""
import json,os,time,statistics as st,datetime
from zoneinfo import ZoneInfo
SOL="So11111111111111111111111111111111111111112"
USD={"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}
SKIP=USD|{SOL,"mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So","J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn","jupSoLaHXQiZZTSfEWMTRRgpnyFm8f6sZdosWBjx93v","bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1","7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj"}
PX=json.load(open('/workspace/onchain-intel/data/solusd.json'))
def solpx(ts):
    d=time.strftime("%Y-%m-%d",time.gmtime(ts)); return float(PX.get(d) or PX[max(PX)])
iso=lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(t))
DUB=ZoneInfo("Europe/Dublin")
def night(ts):
    h=datetime.datetime.fromtimestamp(ts,DUB).hour; return h>=21 or h<8
def swaps(txs):
    out=[]
    for x in sorted(txs,key=lambda x:x['ts']):
        d=x['d']; toks=[(m,a) for m,a in d.items() if m not in SKIP and abs(a)>0]
        if len(toks)!=1: continue
        m,a=toks[0]; p=solpx(x['ts'])
        qsol=d.get(SOL,0)+sum(d.get(u,0) for u in USD)/p
        # ignore pure fee/rent movements: require quote moved opposite to token by > 0.001 SOL
        if a>0 and qsol< -0.001: out.append(dict(ts=x['ts'],mint=m,side='buy',tok=a,sol=-qsol,usd=-qsol*p,sig=x['sig'],pump=x.get('pump')))
        elif a<0 and qsol>0.001: out.append(dict(ts=x['ts'],mint=m,side='sell',tok=-a,sol=qsol,usd=qsol*p,sig=x['sig'],pump=x.get('pump')))
    return out
def rounds(sw):
    pos={}; R=[]
    for s in sw:
        m=s['mint']
        if s['side']=='buy':
            p=pos.setdefault(m,dict(t0=s['ts'],bought=0,sold=0,cin=0,cout=0,uin=0,uout=0,nb=0,ns=0,pump=s['pump'],sig=s['sig']))
            p['bought']+=s['tok']; p['cin']+=s['sol']; p['uin']+=s['usd']; p['nb']+=1
        elif m in pos:
            p=pos[m]; p['sold']+=s['tok']; p['cout']+=s['sol']; p['uout']+=s['usd']; p['ns']+=1; p['t1']=s['ts']; p['sig1']=s['sig']
            if p['sold']>=0.95*p['bought']:
                R.append(dict(mint=m,entry_ts=p['t0'],exit_ts=p['t1'],size_in_sol=p['cin'],size_out_sol=p['cout'],size_in_usd=p['uin'],size_out_usd=p['uout'],
                    entry_price_usd=p['uin']/p['bought'],exit_price_usd=p['uout']/p['sold'],n_buys=p['nb'],n_sells=p['ns'],entry_via_pumpfun=p['pump'],entry_sig=p['sig'],exit_sig=p['sig1']))
                pos.pop(m)
    return R,len(pos)
def stats(R,days):
    if not R: return {}
    g=[r['size_out_sol']/r['size_in_sol']-1 for r in R]
    out={'n_closed':len(R)}
    for c in (0,3,5):
        net=[x-c/100 for x in g]; sol=[r['size_out_sol']-r['size_in_sol']*(1+c/100) for r in R]
        out[f'win_{c}']=round(sum(1 for x in net if x>0)/len(net),3); out[f'med_pct_{c}']=round(st.median(net)*100,2); out[f'avg_pct_{c}']=round(st.mean(net)*100,2); out[f'sum_sol_{c}']=round(sum(sol),3)
        # worst drawdown of cumulative SOL pnl
        eq=pk=dd=0
        for x in sorted(zip([r['exit_ts'] for r in R],sol)):
            eq+=x[1]; pk=max(pk,eq); dd=min(dd,eq-pk)
        out[f'maxdd_sol_{c}']=round(dd,3)
    holds=[(r['exit_ts']-r['entry_ts'])/60 for r in R]
    win=[h for h,x in zip(holds,g) if x>0.05]
    out['med_hold_min']=round(st.median(holds),1); out['win_hold_lt2m']=round(sum(1 for h in win if h<2)/len(win),3) if win else None
    out['win_hold_gt3d']=round(sum(1 for h in win if h>4320)/len(win),3) if win else None
    out['night_trades_per_night']=round(sum(1 for r in R if night(r['entry_ts']))/days,2)
    out['pump_entry_share']=round(sum(1 for r in R if r['entry_via_pumpfun'])/len(R),3)
    out['med_size_sol']=round(st.median([r['size_in_sol'] for r in R]),3)
    out['n_mints']=len({r['mint'] for r in R})
    return out
if __name__=='__main__':
    import sys,glob
    res={}
    for fn in glob.glob('data/w/*.json'):
        w=os.path.basename(fn)[:-5]; o=json.load(open(fn))
        if 'tx' not in o: res[w]={'skip':'too_many %s'%o.get('too_many')}; continue
        R,op=rounds(swaps(o['tx'])); s=stats(R,30); s['open']=op; res[w]=s
    json.dump(res,open('data/stats.json','w'),indent=0)
    for w,s in sorted(res.items(),key=lambda x:-(x[1].get('sum_sol_5') or -1e9)):
        print(w[:8],{k:s.get(k) for k in ('skip','n_closed','win_5','med_pct_5','avg_pct_5','sum_sol_5','med_hold_min','win_hold_lt2m','pump_entry_share','med_size_sol')})
