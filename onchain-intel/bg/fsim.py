"""Filtered copy sim with Chunk's Banana Gun filters: leader buy >= MINUSD ($20), token mcap at the leader's buy >= MINMCAP ($30k),
token age at the leader's buy >= MINAGE_S (300s). mcap at buy = leader fill price (USD/token) x supply; supply = 1e9 for pump.fun
mints (fixed), else DexScreener marketCap/priceUsd. Token creation = earliest DexScreener pairCreatedAt (tmeta cache).
Tokens with unknown age/supply are NOT copied (counted as unknown). Fills at the leader's own prices (optimistic, no latency).
Writes an/<w>.fsim.json. Read-only (DexScreener public API)."""
import json,sys,os,time,statistics as st,urllib.request
sys.path.insert(0,'/workspace/scout'); import analyze as A
from sim import sim
MINUSD=float(os.environ.get('MINUSD','20')); MINMCAP=float(os.environ.get('MINMCAP','30000')); MINAGE=float(os.environ.get('MINAGE_S','300'))
CF='an/fsim_meta.json'; M=json.load(open(CF)) if os.path.exists(CF) else {}
TC=json.load(open('an/tmeta_cache.json')) if os.path.exists('an/tmeta_cache.json') else {}
def meta(ms):
    need=[m for m in ms if m not in M]
    for i in range(0,len(need),30):
        ch=need[i:i+30]
        try: r=json.loads(urllib.request.urlopen(urllib.request.Request('https://api.dexscreener.com/tokens/v1/solana/'+','.join(ch),headers={'User-Agent':'scout-readonly/1.0'}),timeout=30).read())
        except Exception as e: r=[]; print('dexerr',e,flush=True)
        for m in ch: M[m]=dict(created=None,supply=None)
        for p in r:
            m=p.get('baseToken',{}).get('address')
            if m not in M: continue
            c=M[m]; pc=p.get('pairCreatedAt')
            if pc: c['created']=min(c['created'] or 9e15,pc/1000)
            try:
                px=float(p.get('priceUsd') or 0); mc=p.get('marketCap') or p.get('fdv')
                if px>0 and mc and not c['supply']: c['supply']=mc/px
            except: pass
        time.sleep(1.1)
    json.dump(M,open(CF+'.tmp','w')); os.replace(CF+'.tmp',CF)
def summ(C):
    if not C: return {}
    rets=[c['ret'] for c in C]; holds=[c['hold'] for c in C]
    return dict(copied_closed=len(C),win_rate=round(sum(x>0 for x in rets)/len(rets),2),med_ret_pct=round(st.median(rets)*100,1),
        sum_ret_units=round(sum(rets),2),sum_ex_best=round(sum(rets)-max(rets),2),best_ret_pct=round(max(rets)*100,1),
        sum_after_2pct_cost=round(sum(x-0.02 for x in rets),2),sum_ex_best_after_2pct=round(sum(x-0.02 for x in rets)-(max(rets)-0.02),2),
        med_hold_min=round(st.median(holds),1),share_lt60s=round(sum(h<1 for h in holds)/len(holds),2),med_leader_buy_usd=round(st.median(c['usd'] for c in C)))
if __name__=='__main__':
    now=time.time()
    for w in sys.argv[1:]:
        L=[json.loads(l) for l in open(f'tx/{w}.jsonl')]; L=[x for x in L if 'err' not in x and x['ts']>=now-86400]
        L.sort(key=lambda x:(x['slot'],x['ts'])); sw=A.swaps(L)
        meta(sorted({s['mint'] for s in sw if s['side']=='buy'}))
        unk=[0]; why={'usd':0,'mcap':0,'age':0,'unknown':0}
        def ok(s):
            m=s['mint']; c=M.get(m,{}); cr=c.get('created') or (TC.get(m) or {}).get('created')
            sup=1e9 if (m.endswith('pump') or s.get('pump')) else c.get('supply')
            if s['usd']<MINUSD: why['usd']+=1; return False
            if cr is None or not sup or not s['tok']: why['unknown']+=1; return False
            if s['ts']-cr<MINAGE: why['age']+=1; return False
            if s['usd']/s['tok']*sup<MINMCAP: why['mcap']+=1; return False
            return True
        # filtered: only buys passing filters trigger; sells copied proportionally (sim() uses MIN usd; emulate by zeroing usd of filtered buys)
        sw2=[dict(s,usd=(s['usd'] if (s['side']!='buy' or ok(s)) else 0.0)) for s in sw]
        import sim as S; S.MIN=0.000001
        # sim() checks s['usd']>=MIN: filtered buys have usd=0 -> not triggered but still count toward position size
        Cf,of=sim(sw2,now); S.MIN=MINUSD; Cu,ou=sim(sw,now)
        buys=[s for s in sw if s['side']=='buy']
        o=dict(wallet=w,filters=dict(min_leader_buy_usd=MINUSD,min_mcap_usd=MINMCAP,min_token_age_s=MINAGE),buys_24h=len(buys),
               triggers_passing=sum(1 for s in sw2 if s['side']=='buy' and s['usd']>0),blocked=why,filtered=summ(Cf),filtered_open=of,unfiltered_min20=summ(Cu),
               computed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ'),note='fills at leader prices, no latency/slippage (optimistic); 2% round-trip cost variant included')
        json.dump(o,open(f'an/{w}.fsim.json','w'),indent=1); print(w[:8],json.dumps({k:o[k] for k in ('triggers_passing','blocked','filtered','filtered_open')}),flush=True)
