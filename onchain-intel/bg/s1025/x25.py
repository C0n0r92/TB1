"""2.5h-exit variant of the BG-filtered copy sim (read-only). Each filtered copy exits at the first of: leader full exit, or entry+2.5h.
Partial leader sells before the cutoff are copied proportionally. Remainder at cutoff priced at GeckoTerminal 5-min candle close at cutoff
(top-liquidity DexScreener pair); if cutoff is in the future, marked at current DexScreener price. 2% cost applied in after-cost fields."""
import json,sys,os,time,statistics as st,urllib.request
sys.path.insert(0,'/workspace/onchain-intel/bg'); sys.path.insert(0,'/workspace/scout'); import analyze as A, fsim as F
CUT=9000
def get(u):
    try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'scout-readonly/1.0','Accept':'application/json'}),timeout=20))
    except Exception as e: return None
PAIR={}
def pairs(ms):
    for i in range(0,len(ms),30):
        d=get('https://api.dexscreener.com/tokens/v1/solana/'+','.join(ms[i:i+30])) or []
        for p in d:
            m=p['baseToken']['address']; liq=(p.get('liquidity') or {}).get('usd') or 0
            if m not in PAIR or liq>PAIR[m][2]: PAIR[m]=(p['pairAddress'],float(p.get('priceUsd') or 0),liq)
        time.sleep(1.1)
def px_at(m,t):
    if m not in PAIR: return 0.0
    d=get(f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{PAIR[m][0]}/ohlcv/minute?aggregate=5&before_timestamp={int(t)+300}&limit=3&currency=usd&token=base'); time.sleep(2.1)
    try:
        L=sorted(d['data']['attributes']['ohlcv_list']); L=[c for c in L if c[0]<=t+300]
        return float(L[-1][4]) if L else None
    except Exception: return None
def run(w,budget_calls=25):
    now=time.time()
    L=[json.loads(l) for l in open(f'tx/{w}.jsonl')]; L=[x for x in L if 'err' not in x and x['ts']>=now-86400]
    L.sort(key=lambda x:(x['slot'],x['ts'])); sw=A.swaps(L)
    F.meta(sorted({s['mint'] for s in sw if s['side']=='buy'}))
    def ok(s):
        m=s['mint']; c=F.M.get(m,{}); cr=c.get('created') or (F.TC.get(m) or {}).get('created')
        sup=1e9 if (m.endswith('pump') or s.get('pump')) else c.get('supply')
        if s['usd']<F.MINUSD or cr is None or not sup or not s['tok']: return False
        return s['ts']-cr>=F.MINAGE and s['usd']/s['tok']*sup>=F.MINMCAP
    pos={}; cps=[]
    for s in sw:
        m=s['mint']; p=pos.setdefault(m,dict(tb=0,ts=0,c=[]))
        if s['side']=='buy':
            p['tb']+=s['tok']
            if ok(s) and s['tok']>0: c=dict(m=m,t=s['ts'],px=s['usd']/s['tok'],sold=0.0,proc=0.0,done=False); p['c'].append(c); cps.append(c)
        else:
            if p['tb']-p['ts']<=0: continue
            frac=min(1.0,s['tok']/max(p['tb']-p['ts'],1e-12)); px=s['usd']/s['tok'] if s['tok'] else 0
            p['ts']+=s['tok']; full=p['ts']>=0.95*p['tb']
            for c in p['c']:
                if c['done'] or s['ts']>c['t']+CUT: continue
                q=(1-c['sold'])*(1 if full else frac); c['sold']+=q; c['proc']+=q*px
                if full: c['done']=True
            if full: p['c']=[]; p['tb']=p['ts']=0
    need=[c for c in cps if not c['done']]
    pairs(sorted({c['m'] for c in need})); calls=0; R=[]; unp=0
    for c in cps:
        if not c['done']:
            if c['t']+CUT>now: pe=PAIR.get(c['m'],(0,0,0))[1]
            elif calls<budget_calls: pe=px_at(c['m'],c['t']+CUT); calls+=1
            else: pe=None
            if pe is None: unp+=1; continue
            c['proc']+=(1-c['sold'])*pe
        R.append(c['proc']/c['px']-1)
    if not R: return dict(wallet=w,n=0)
    r=sorted(R)
    return dict(wallet=w,n=len(r),unpriced_skipped=unp,med_ret_pct=round(st.median(r)*100,1),med_after_2pct=round((st.median(r)-0.02)*100,1),win_rate=round(sum(x>0.02 for x in r)/len(r),2),
                sum_after_2pct=round(sum(x-0.02 for x in r),2),sum_ex_best_after_2pct=round(sum(x-0.02 for x in r)-(max(r)-0.02),2),computed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ'))
if __name__=='__main__':
    for w in sys.argv[1:]:
        o=run(w); json.dump(o,open(f'an/{w}.x25.json','w'),indent=1); print(o,flush=True)
