"""Full 7d roster bar for one or more wallets (free: public RPC + DexScreener). Read-only."""
import json,sys,os,time,statistics as st,collections,urllib.request
sys.path.insert(0,'/workspace/scout'); import analyze as A; from pub import rpc
OI='/workspace/onchain-intel/'
txt=''.join(open(OI+f).read() for f in ['known_funders.csv','avoid.csv','known_ruggers.json','custodial_ignore.json'])
cache=json.load(open('an/supply.json')) if os.path.exists('an/supply.json') else {}
liqc=json.load(open('an/liq.json')) if os.path.exists('an/liq.json') else {}
def supply(m):
    if m not in cache:
        r=rpc('getTokenSupply',[m]); cache[m]=float(r['value']['uiAmount']) if r else None
    return cache[m]
def liq(mints):
    need=[m for m in mints if m not in liqc]
    for i in range(0,len(need),30):
        b=need[i:i+30]
        req=urllib.request.Request('https://api.dexscreener.com/tokens/v1/solana/'+','.join(b),headers={'User-Agent':'Mozilla/5.0'})
        d=json.load(urllib.request.urlopen(req,timeout=20))
        for m in b: liqc[m]=0.0
        for p in d:
            m=p['baseToken']['address']
            if m in liqc: liqc[m]=max(liqc[m],float((p.get('liquidity') or {}).get('usd') or 0))
        time.sleep(1)
    json.dump(liqc,open('an/liq.json','w'))
    return {m:liqc.get(m) for m in mints}
now=time.time(); D=7*86400
for w in sys.argv[1:]:
    o=json.load(open(f'an/wg/{w}.json')); sw=A.swaps(o['tx'])
    oldest=min(x['ts'] for x in o['tx']); cov7=(not o.get('truncated')) or oldest<now-D
    Rall,_=A.rounds(sw); R=[x for x in Rall if x['exit_ts']>now-D]
    res={'wallet':w,'cov7':cov7,'cover_d':round((now-oldest)/86400,2),'source':o.get('source'),'closed7':len(R)}
    if not R: print(json.dumps(res)); continue
    net=[x['size_out_sol']-x['size_in_sol']*1.05 for x in R]
    cr=[]
    for x in R:
        sr=x['size_out_sol']/x['size_in_sol']-1
        pr=(x['exit_price_usd']/x['entry_price_usd']-1) if x['entry_price_usd'] and x['exit_price_usd'] else sr
        cr.append(min(sr,pr))
    cn=[x['size_in_sol']*(c-0.05) for x,c in zip(R,cr)]
    pct=[(x['size_out_sol']/x['size_in_sol']-1.05)*100 for x in R]
    sw7=[s for s in sw if s['ts']>now-D]
    h=collections.Counter(time.gmtime(s['ts']).tm_hour for s in sw7)
    # MEV/arb pattern
    bysig=collections.defaultdict(set); byts=collections.Counter()
    for s in sw7: bysig[s['sig']].add((s['mint'],s['side'])); byts[s['ts']]+=1
    rt=sum(1 for v in bysig.values() if len({m for m,_ in v})<len(v))
    # sniper: first buy of each 7d-round mint
    early=[]; tx_ok=0
    for x in R:
        m=x['mint']
        if any(e[0]==m[:6] for e in early): continue
    seen=set()
    for x in R:
        m=x['mint']
        if m in seen: continue
        seen.add(m)
        tx=rpc('getTransaction',[x['entry_sig'],{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}])
        if not tx: continue
        tx_ok+=1
        prior=rpc('getSignaturesForAddress',[m,{"before":x['entry_sig'],"limit":1000}]) or []
        if len(prior)<1000:
            gap=tx['slot']-prior[-1]['slot'] if prior else 0
            if gap<=2: early.append((m[:6],gap,len(prior)))
    mc=[]
    for x in R:
        sp=supply(x['mint'])
        mc.append(x['entry_price_usd']*sp if sp and x['entry_price_usd'] else None)
    json.dump(cache,open('an/supply.json','w'))
    L=liq(sorted(seen))
    mcv=[v for v in mc if v is not None]
    res.update(net7=round(sum(net),2),ex_best7=round(sum(net)-max(net),2),net7_cons=round(sum(cn),2),ex_best7_cons=round(sum(cn)-max(cn),2),
        pct7=round(sum(net)/sum(x['size_in_sol'] for x in R)*100,1),win=round(sum(p>0 for p in pct)/len(R),2),med_pct=round(st.median(pct),1),
        med_hold=round(st.median((x['exit_ts']-x['entry_ts'])/60 for x in R),1),med_size=round(st.median(x['size_in_sol'] for x in R),2),
        last=A.iso(max(s['ts'] for s in sw)),sw1h=sum(s['ts']>now-3600 for s in sw),sw2h=sum(s['ts']>now-7200 for s in sw),
        day_share=round(sum(v for k,v in h.items() if 7<=k<20)/max(len(sw7),1),2),peak=[k for k,_ in h.most_common(3)],n_swaps7=len(sw7),
        listed=w in txt,same_tx_roundtrip=rt,max_swaps_same_second=max(byts.values()) if byts else 0,
        mints7=len(seen),entry_tx_checked=tx_ok,early_buys=early,
        med_entry_mcap=round(st.median(mcv)) if mcv else None,share_mcap300k=round(sum(v>=3e5 for v in mcv)/len(R),2),
        share_liq100k=round(sum(1 for x in R if (L.get(x['mint']) or 0)>=1e5)/len(R),2),
        med_liq_now=round(st.median([L.get(x['mint']) or 0 for x in R])))
    ok=res['cov7'] and res['closed7']>=15 and res['net7']>0 and res['ex_best7']>0 and res['net7_cons']>0 and res['ex_best7_cons']>0 \
       and res['med_hold']>=30 and res['share_mcap300k']>=0.7 and res['share_liq100k']>=0.7 and not res['listed'] \
       and rt==0 and res['max_swaps_same_second']<=2 and not early and tx_ok==len(seen)
    res['ALL_PASS']=bool(ok)
    print(json.dumps(res),flush=True)
    json.dump(res,open(f'an/bar7_{w[:6]}.json','w'))
