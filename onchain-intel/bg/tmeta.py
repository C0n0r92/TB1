"""Token age-at-entry and current mcap/liquidity for a wallet's 24h $100+ entries (DexScreener public API tokens/v1). Writes an/<w>.tm.json. Read-only."""
import json,sys,time,statistics as st,urllib.request,os
sys.path.insert(0,'/workspace/scout'); import analyze as A
NOW=time.time(); CF='an/tmeta_cache.json'; cache=json.load(open(CF)) if os.path.exists(CF) else {}
def meta(ms):
    need=[m for m in ms if m not in cache]
    for i in range(0,len(need),30):
        ch=need[i:i+30]
        try: r=json.loads(urllib.request.urlopen(urllib.request.Request('https://api.dexscreener.com/tokens/v1/solana/'+','.join(ch),headers={'User-Agent':'scout-readonly/1.0'}),timeout=30).read())
        except Exception as e: r=[]; print('err',e)
        for m in ch: cache[m]=dict(created=None,mcap=None,liq=None)
        for p in r:
            m=p.get('baseToken',{}).get('address')
            if m not in cache: continue
            c=cache[m]; pc=p.get('pairCreatedAt')
            if pc: c['created']=min(c['created'] or 9e15,pc/1000)
            c['mcap']=max(c['mcap'] or 0,p.get('marketCap') or p.get('fdv') or 0)
            c['liq']=max(c['liq'] or 0,(p.get('liquidity') or {}).get('usd') or 0)
        time.sleep(1.1)
    json.dump(cache,open(CF,'w'))
for w in sys.argv[1:]:
    L=[json.loads(l) for l in open(f'tx/{w}.jsonl')]; L=[x for x in L if 'err' not in x]
    sw=[s for s in A.swaps(L) if s['ts']>NOW-86400]
    ent=[s for s in sw if s['side']=='buy' and s['usd']>=8]
    ms=sorted({s['mint'] for s in ent}); meta(ms)
    first={}
    for s in sorted(ent,key=lambda s:s['ts']): first.setdefault(s['mint'],s)
    ages=[(s['ts']-cache[m]['created'])/3600 for m,s in first.items() if cache[m]['created']]
    mc=[cache[m]['mcap'] for m in ms if cache[m]['mcap']]
    lq=[cache[m]['liq'] for m in ms if cache[m]['liq']]
    o=dict(tokens=len(ms),med_pair_age_h_at_entry=round(st.median(ages),2) if ages else None,share_pair_lt1h=round(sum(a<1 for a in ages)/len(ages),2) if ages else None,
           med_mcap_now_usd=round(st.median(mc)) if mc else None,share_mcap_lt100k=round(sum(x<1e5 for x in mc)/len(mc),2) if mc else None,med_liq_now_usd=round(st.median(lq)) if lq else None,med_entry_delay_min=round(st.median(ages)*60,1) if ages else None,share_entry_lt60s=round(sum(a*3600<60 for a in ages)/len(ages),2) if ages else None,share_entry_lt10s=round(sum(a*3600<10 for a in ages)/len(ages),2) if ages else None,share_mcap_ge1m=round(sum(x>=1e6 for x in mc)/len(mc),2) if mc else None,
           note='age = entry time minus earliest DexScreener pairCreatedAt (for pump.fun coins this is the bonding-curve/pool creation); mcap/liquidity are current, not at entry')
    json.dump(o,open(f'an/{w}.tm.json','w')); print(w[:6],o['med_entry_delay_min'],o['share_entry_lt60s'],o['share_entry_lt10s'],o['tokens'],o['med_pair_age_h_at_entry'],o['share_pair_lt1h'],o['med_mcap_now_usd'],o['share_mcap_lt100k'],o['med_liq_now_usd'])
