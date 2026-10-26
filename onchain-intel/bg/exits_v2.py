"""Exit-variant re-score on cached data (scorer_v2 cost model). Read-only. 1-min cached candles to t+2.5h; beyond that 5-min GT candles
fetched only for copies still holding, within a time budget; else remainder marked at current DexScreener price (path truncated)."""
import json,sys,os,time,statistics as st
sys.path.insert(0,'/workspace/onchain-intel/bg'); sys.path.insert(0,'/workspace/scout')
import scorer_v2 as S, analyze as A, fsim as F
from fetchlayer import get
C5F='an/v2_candles5.json'; C5=json.load(open(C5F)) if os.path.exists(C5F) else {}
T0=time.time(); BUDGET=float(os.environ.get('BUDGET','200')); stats=dict(ext_fetched=0,ext_cached=0,ext_skipped=0)
def cached1(m,t):
    p=f"{m}:{int(t)//60}:"; ks=[k for k in S.CCache if k.startswith(p)]
    return max((S.CCache[k] for k in ks),key=len) if ks else None
def ext5(m,t0,now):
    k=f"{m}:{int(t0)//300}"
    if k in C5: stats['ext_cached']+=1; return C5[k]
    if time.time()-T0>BUDGET or m not in S.PAIR: stats['ext_skipped']+=1; return None
    lim=min(1000,int((now-t0)/300)+2)
    d=get(f"{S.GT}pools/{S.PAIR[m]['pair']}/ohlcv/minute?aggregate=5&before_timestamp={int(now)}&limit={lim}&currency=usd&token=base")
    try: L=sorted(c for c in d['data']['attributes']['ohlcv_list'] if c[0]>=t0)
    except Exception: L=None
    if L is not None: C5[k]=L; stats['ext_fetched']+=1
    return L
def sim(c,cl,E,imp,P,mode,now):
    stop={'a':0.7,'b':0.5,'c':0.7,'cp':0.7,'d':0.7}[mode]; leader=mode in('a','b','cp','d'); tstop=mode=='d'
    rem=1.0; proc=0.0; t=c['t']; sells=c['sells'] if not tstop else [x for x in c['sells'] if x[0]<=t+S.CUT]; si=0
    tp=False; peak=None; how='open'; em=(t+5)//60*60
    for x in cl:
        if x[0]<=em: continue
        if leader:
            while si<len(sells) and sells[si][0]+5<x[0]+60 and rem>1e-9:
                _,fr,lp=sells[si]; px=S.guard(x[3],lp) or lp*0.99; q=rem*fr; proc+=q*px*(1-imp); rem-=q; si+=1
            if rem<=1e-6: return proc,'leader'
        o,h,l,cl_=x[1],x[2],x[3],x[4]
        if mode in('c','cp') and tp:
            if l<=0.6*peak: px=o if o<=0.6*peak else 0.6*peak; proc+=rem*px*(1-imp); return proc,'trail'
            peak=max(peak,h)
        elif l<=stop*E: px=o if o<=stop*E else stop*E; proc+=rem*px*(1-imp); return proc,'stop'
        if mode in('c','cp') and not tp and h>=2*E:
            px=max(o,2*E); q=rem*0.5; proc+=q*px*(1-imp); rem-=q; tp=True; peak=h
        if tstop and x[0]>=t+S.CUT-60: proc+=rem*cl_*(1-imp); return proc,'time'
    proc+=rem*P['px']*(1-imp); return proc,'open'
def run(w):
    now=time.time()
    L=[json.loads(l) for l in open(f'tx/{w}.jsonl')]; L=[x for x in L if 'err' not in x and x['ts']>=now-86400]
    L.sort(key=lambda x:(x['slot'],x['ts'])); sw=A.swaps(L); F.meta(sorted({s['mint'] for s in sw if s['side']=='buy'}))
    def ok(s):
        m=s['mint']; c=F.M.get(m,{}); cr=c.get('created') or (F.TC.get(m) or {}).get('created')
        sup=1e9 if (m.endswith('pump') or s.get('pump')) else c.get('supply')
        if s['usd']<F.MINUSD or cr is None or not sup or not s['tok']: return False
        return s['ts']-cr>=F.MINAGE and s['usd']/s['tok']*sup>=F.MINMCAP
    cps=[]; pos={}
    for s in sw:
        m=s['mint']; p=pos.setdefault(m,dict(tb=0,ts=0,c=[]))
        if s['side']=='buy':
            p['tb']+=s['tok']
            if ok(s): c=dict(m=m,t=s['ts'],fill=s['usd']/s['tok'],sells=[]); p['c'].append(c); cps.append(c)
        else:
            if p['tb']-p['ts']<=0: continue
            frac=min(1.0,s['tok']/max(p['tb']-p['ts'],1e-12)); p['ts']+=s['tok']; full=p['ts']>=0.95*p['tb']
            for c in p['c']: c['sells'].append((s['ts'],1.0 if full else frac,s['usd']/s['tok']))
            if full: p['c']=[]; p['tb']=p['ts']=0
    cps=cps[-25:]; S.pairs(sorted({c['m'] for c in cps}))
    R={k:[] for k in 'a b c cp d'.split()}; unp=0; trunc=0; hows={k:{} for k in R}
    for c in cps:
        P=S.PAIR.get(c['m']); cl=cached1(c['m'],c['t']) if P else None
        if not cl: unp+=1; continue
        rsol=max(P['liq']/2/P['solusd'],1e-9); imp=min(S.SIZE/rsol,0.5)
        em=(c['t']+5)//60*60; ec=[x for x in cl if x[0]==em]
        E=((S.guard(ec[0][2],c['fill']) if ec else None) or c['fill']*1.01)*(1+imp)
        full=cl
        if c['t']+S.CUT<now:
            e=ext5(c['m'],cl[-1][0]+60,now)
            if e: full=cl+[x for x in e if x[0]>cl[-1][0]]
            else: trunc+=1
        res={k:sim(c,full if k!='d' else cl,E,imp,P,k,now) for k in R}
        if any(pr/E-1-S.COST>20 for pr,_ in res.values()): unp+=1; continue
        for k,(pr,h) in res.items(): R[k].append(pr/E-1-S.COST); hows[k][h]=hows[k].get(h,0)+1
    out=dict(wallet=w,copies=len(R['a']),unpriced=unp,path_truncated_after_2_5h=trunc)
    for k,r in R.items():
        if not r: out[k]=None; continue
        s=sorted(r); out[k]=dict(median_pct=round(st.median(s)*100,1),total_sol=round(sum(s)*S.SIZE,3),ex_top2_sol=round(sum(s[:-2] if len(s)>2 else s)*S.SIZE,3),win_rate=round(sum(x>0 for x in s)/len(s),2),exits=hows[k],_r=r)
    return out
if __name__=='__main__':
    W=sys.argv[1:]; res=[]
    for w in W:
        o=run(w); res.append(o); print(w[:6],o['copies'],o['unpriced'],o['path_truncated_after_2_5h'],{k:(o[k]['median_pct'],o[k]['total_sol'],o[k]['ex_top2_sol']) if o[k] else None for k in 'a b c cp d'.split()},round(time.time()-T0),flush=True)
        json.dump(C5,open(C5F,'w'))
    json.dump(dict(res=res,stats=stats),open('/tmp/exits_raw.json','w'))
    print(stats)
