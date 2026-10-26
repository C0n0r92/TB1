"""Scorer v2: what a 0.08 SOL copier actually gets (read-only, free: DexScreener + GeckoTerminal via fetchlayer).
Per BG-filtered leader buy (mcap>=$30k, age>=5min, buy>=$20; fsim rules), last 24h, most recent MAXC copies:
 entry  = 1-min candle HIGH of minute(fill+5s) (qf.py fallback model; if >50% off fill use fill*1.01) x (1+impact), impact=0.08 SOL / pool SOL reserve
 exit   = first of: leader sell (proportional; candle LOW of minute(sell+5s), same 50% guard) / -30% stop (first minute candle with low<=0.7E;
          priced at that candle's OPEN if it gapped through, else 0.7E) / 2.5h time stop (close of minute t+9000) ; still-open = marked at last close
 costs  = 2% round trip + 2x0.0005 SOL priority (=1.25% of 0.08) + sell impact
Score = 100*(0.4*median + 0.4*recency-weighted(8h half-life) winsorized(p90) mean + 0.2*mean ex-top2) * min(1,n/15) * concentration penalty.
Hard gates: median>0, sum ex-best>0, n>=8, closed_or_timestopped>=5, median hold>=1min, no flags, not in known_ruggers/custodial_ignore."""
import json,sys,os,time,statistics as st
sys.path.insert(0,'/workspace/onchain-intel/bg'); sys.path.insert(0,'/workspace/scout')
import analyze as A, fsim as F
from fetchlayer import get
CUT=9000; SIZE=0.08; COST=0.02+0.001/SIZE; STOP=0.7; HL=8*3600; MAXC=int(os.environ.get('MAXC','25'))
GT='https://api.geckoterminal.com/api/v2/networks/solana/'
CC='an/v2_candles.json'; CCache=json.load(open(CC)) if os.path.exists(CC) else {}
PAIR={}
def pairs(ms):
    for i in range(0,len(ms),30):
        for p in get('https://api.dexscreener.com/tokens/v1/solana/'+','.join(ms[i:i+30])) or []:
            m=p['baseToken']['address']; liq=(p.get('liquidity') or {}).get('usd') or 0
            if m not in PAIR or liq>PAIR[m]['liq']:
                pu=float(p.get('priceUsd') or 0); pn=float(p.get('priceNative') or 0)
                PAIR[m]=dict(pair=p['pairAddress'],px=pu,liq=liq,solusd=(pu/pn if pn and p.get('quoteToken',{}).get('symbol')=='SOL' else 190.0))
def candles(m,t0,t1):
    k=f"{m}:{int(t0)//60}:{int(t1)//60}"
    if k in CCache: return CCache[k]
    if m not in PAIR: return None
    lim=min(1000,int((t1-t0)/60)+3)
    d=get(f"{GT}pools/{PAIR[m]['pair']}/ohlcv/minute?aggregate=1&before_timestamp={int(t1)+60}&limit={lim}&currency=usd&token=base")
    try: L=sorted(c for c in d['data']['attributes']['ohlcv_list'] if c[0]>=int(t0)//60*60-60)
    except Exception: L=None
    if L is not None: CCache[k]=L
    return L
def guard(cpx,fill): return cpx if cpx and 0.5<=cpx/fill<=1.5 else None
def run(w):
    now=time.time()
    L=[json.loads(l) for l in open(f'tx/{w}.jsonl')]; L=[x for x in L if 'err' not in x and x['ts']>=now-86400]
    L.sort(key=lambda x:(x['slot'],x['ts'])); sw=A.swaps(L)
    F.meta(sorted({s['mint'] for s in sw if s['side']=='buy'}))
    def ok(s):
        m=s['mint']; c=F.M.get(m,{}); cr=c.get('created') or (F.TC.get(m) or {}).get('created')
        sup=1e9 if (m.endswith('pump') or s.get('pump')) else c.get('supply')
        if s['usd']<F.MINUSD or cr is None or not sup or not s['tok']: return False
        return s['ts']-cr>=F.MINAGE and s['usd']/s['tok']*sup>=F.MINMCAP
    cps=[]; pos={}
    for s in sw:   # leader position bookkeeping -> list of sell events per copy
        m=s['mint']; p=pos.setdefault(m,dict(tb=0,ts=0,c=[]))
        if s['side']=='buy':
            p['tb']+=s['tok']
            if ok(s): c=dict(m=m,t=s['ts'],fill=s['usd']/s['tok'],sells=[]); p['c'].append(c); cps.append(c)
        else:
            if p['tb']-p['ts']<=0: continue
            frac=min(1.0,s['tok']/max(p['tb']-p['ts'],1e-12)); p['ts']+=s['tok']; full=p['ts']>=0.95*p['tb']
            for c in p['c']: c['sells'].append((s['ts'],1.0 if full else frac,s['usd']/s['tok']))
            if full: p['c']=[]; p['tb']=p['ts']=0
    nfilt=len(cps); cps=cps[-MAXC:]
    pairs(sorted({c['m'] for c in cps}))
    R=[]; unp=0
    for c in cps:
        P=PAIR.get(c['m']); t=c['t']; end=min(t+CUT,now)
        cl=candles(c['m'],t,end) if P else None
        if not cl: unp+=1; continue
        rsol=max(P["liq"]/2/P["solusd"],1e-9); imp=min(SIZE/rsol,0.5)
        em=(t+5)//60*60; ec=[x for x in cl if x[0]==em]
        E=(guard(ec[0][2],c['fill']) if ec else None) or c['fill']*1.01
        E*=1+imp; rem=1.0; proc=0.0; how='open'; tex=None
        sells=[x for x in c['sells'] if x[0]<=t+CUT]; si=0
        for x in cl:
            if x[0]<=em: continue
            while si<len(sells) and sells[si][0]+5<x[0]+60 and rem>1e-9:
                st_,fr,lp=sells[si]; px=guard(x[3],lp) or lp*0.99; q=rem*fr; proc+=q*px*(1-imp); rem-=q; si+=1
                if rem<=1e-6: how='leader'; tex=st_
            if rem<=1e-6: break
            if x[3]<=STOP*E:
                px=x[1] if x[1]<=STOP*E else STOP*E; proc+=rem*px*(1-imp); rem=0; how='stop'; tex=x[0]; break
            if x[0]>=t+CUT-60:
                proc+=rem*x[4]*(1-imp); rem=0; how='time'; tex=t+CUT; break
        if rem>1e-6:
            last=cl[-1][4] if cl else P['px']; proc+=rem*(P['px'] if end>=now-120 else last)*(1-imp); how='open' if t+CUT>now else 'time'; tex=tex or end
        r=proc/E-1-COST
        if r>20: unp+=1; continue   # >2000%: price-unit glitch (candle vs fill), treat as unpriced
        R.append(dict(m=c['m'],t=t,ret=round(r,4),how=how,hold_min=round(((tex or now)-t)/60,1),impact=round(imp,4)))
    o=dict(wallet=w,filtered_buys_24h=nfilt,copies_scored=len(R),unpriced=unp,computed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    if not R: o.update(score=None,pass_=False,fails=['no priced copies']); return o
    r=sorted(x['ret'] for x in R); n=len(r)
    p90=r[min(n-1,int(0.9*n))]; wts=[0.5**((now-x['t'])/HL) for x in R]
    wm=sum(min(x['ret'],p90)*wt for x,wt in zip(R,wts))/sum(wts)
    ex2=r[:-2] if n>2 else r; mex2=st.mean(ex2); tot=sum(r)
    pos_sum=sum(x for x in r if x>0); top_share=(max(r)/pos_sum) if pos_sum>0 and max(r)>0 else 0
    pen=1-0.5*max(0,top_share-0.4); med=st.median(r)
    score=round(100*(0.4*med+0.4*wm+0.2*mex2)*min(1,n/15)*pen,2)
    hows={k:sum(x['how']==k for x in R) for k in ('leader','stop','time','open')}
    o.update(score=score,median_pct=round(med*100,1),win_rate=round(sum(x>0 for x in r)/n,2),weighted_winsor_mean_pct=round(wm*100,1),
        sum_units=round(tot,2),sum_ex_best=round(tot-max(r),2),sum_ex_top2=round(sum(ex2),2),mean_ex_top2_pct=round(mex2*100,1),
        top_trade_share=round(top_share,2),best_pct=round(max(r)*100,1),median_hold_min=st.median(x['hold_min'] for x in R),
        exits=hows,closed_or_timestopped=hows['leader']+hows['stop']+hows['time'],stop_hits=hows['stop'],last_copy_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(max(x['t'] for x in R))),
        last_tx_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(max(x['ts'] for x in L))) if L else None,copies=R)
    bad=set(json.dumps(json.load(open('/workspace/onchain-intel/known_ruggers.json'))).split('"'))|set(json.dumps(json.load(open('/workspace/onchain-intel/custodial_ignore.json'))).split('"'))
    fails=[]
    if med<=0: fails.append('median<=0')
    if tot-max(r)<=0: fails.append('ex-best<=0')
    if n<8: fails.append('copies<8')
    if o['closed_or_timestopped']<5: fails.append('closed<5')
    if o['median_hold_min']<1: fails.append('hold<1min')
    if w in bad: fails.append('ruggers/custodial list')
    o['fails']=fails; o['pass_']=not fails
    return o
if __name__=='__main__':
    out={}
    for w in sys.argv[1:]:
        try: o=run(w)
        except Exception as e: o=dict(wallet=w,error=repr(e))
        out[w]=o; json.dump(o,open(f'an/{w}.v2.json','w'),indent=1)
        print(json.dumps({k:v for k,v in o.items() if k!='copies'}),flush=True)
        json.dump(CCache,open(CC+'.tmp','w')); os.replace(CC+'.tmp',CC)
