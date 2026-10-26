"""Filtered copy sim INCLUDING open copies marked to market (Chunk's BG filters, same as fsim.py).
Closed copies: as sim.py (leader fills, proportional sells). Open copies (leader has not sold >=95% of the bought amount):
value = proceeds already realised from partial sells + remaining fraction x current DexScreener priceUsd (deepest-liquidity pair).
Returns in USD terms (entry px = leader fill USD/token at buy). Token with no DexScreener price -> valued at 0 (dead) and counted.
Writes an/<w>.mtm.json. Read-only (DexScreener public API)."""
import json,sys,os,time,statistics as st,urllib.request
sys.path.insert(0,'/workspace/scout'); import analyze as A
import fsim as F
def simo(sw):
    pos={}; out=[]
    for s in sw:
        m=s['mint']; p=pos.get(m)
        if s['side']=='buy':
            if p is None: p=pos[m]=dict(tb=0,ts=0,c=[])
            p['tb']+=s['tok']
            if s['usd']>0 and s['tok']>0: p['c'].append(dict(t=s['ts'],px=s['usd']/s['tok'],usd=s['usd'],sold=0.0,proc=0.0,t1=s['ts']))
        elif p:
            frac=min(1.0,s['tok']/max(p['tb']-p['ts'],1e-12)); px=s['usd']/s['tok'] if s['tok'] else 0
            p['ts']+=s['tok']
            for c in p['c']:
                q=(1-c['sold'])*frac; c['sold']+=q; c['proc']+=q*px; c['t1']=s['ts']
            if p['ts']>=0.95*p['tb']:
                for c in p['c']:
                    rem=1-c['sold']; c['proc']+=rem*px; c['sold']=1
                    out.append(dict(mint=m,ret=c['proc']/c['px']-1,hold=(c['t1']-c['t'])/60,usd=c['usd'],open=False))
                pos.pop(m)
    return out,pos
def prices(ms):
    P={}
    for i in range(0,len(ms),30):
        try: d=json.load(urllib.request.urlopen(urllib.request.Request('https://api.dexscreener.com/tokens/v1/solana/'+','.join(ms[i:i+30]),headers={'User-Agent':'scout-readonly/1.0'}),timeout=30))
        except Exception as e: print('dexerr',e); d=[]
        for p in d:
            m=p['baseToken']['address']; liq=(p.get('liquidity') or {}).get('usd') or 0
            if m not in P or liq>P[m][1]: P[m]=(float(p.get('priceUsd') or 0),liq)
        time.sleep(1.1)
    return P
def summ(R):
    if not R: return {}
    r=[x['ret'] for x in R]; h=[x['hold'] for x in R]
    return dict(n=len(R),win_rate=round(sum(x>0 for x in r)/len(r),2),med_ret_pct=round(st.median(r)*100,1),sum_ret_units=round(sum(r),2),
        sum_ex_best=round(sum(r)-max(r),2),best_ret_pct=round(max(r)*100,1),sum_ex_best_after_2pct=round(sum(x-0.02 for x in r)-(max(r)-0.02),2),
        med_hold_min=round(st.median(h),1),share_lt60s=round(sum(x<1 for x in h)/len(h),2))
if __name__=='__main__':
    now=time.time()
    for w in sys.argv[1:]:
        L=[json.loads(l) for l in open(f'tx/{w}.jsonl')]; L=[x for x in L if 'err' not in x and x['ts']>=now-86400]
        L.sort(key=lambda x:(x['slot'],x['ts'])); sw=A.swaps(L)
        F.meta(sorted({s['mint'] for s in sw if s['side']=='buy'}))
        def ok(s):
            m=s['mint']; c=F.M.get(m,{}); cr=c.get('created') or (F.TC.get(m) or {}).get('created')
            sup=1e9 if (m.endswith('pump') or s.get('pump')) else c.get('supply')
            if s['usd']<F.MINUSD or cr is None or not sup or not s['tok']: return False
            return s['ts']-cr>=F.MINAGE and s['usd']/s['tok']*sup>=F.MINMCAP
        sw2=[dict(s,usd=(s['usd'] if (s['side']!='buy' or ok(s)) else 0.0)) for s in sw]
        C,pos=simo(sw2)
        P=prices(sorted(pos))
        O=[]
        for m,p in pos.items():
            pn=P.get(m,(0,0))[0]
            for c in p['c']:
                O.append(dict(mint=m,ret=(c['proc']+(1-c['sold'])*pn)/c['px']-1,hold=(now-c['t'])/60,usd=c['usd'],open=True,priced=m in P))
        o=dict(wallet=w,filters=dict(min_leader_buy_usd=F.MINUSD,min_mcap_usd=F.MINMCAP,min_token_age_s=F.MINAGE),
               closed=summ(C),open=summ(O),open_unpriced=sum(1 for x in O if not x['priced']),combined=summ(C+O),
               computed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ'),
               note='open copies marked to market at DexScreener priceUsd at computed_utc (USD terms); open hold = minutes since entry; leader fills, no latency')
        json.dump(o,open(f'an/{w}.mtm.json','w'),indent=1)
        print(w[:8],'closed',o['closed'],'\n  open',o['open'],'unpriced',o['open_unpriced'],'\n  COMB',o['combined'],flush=True)
