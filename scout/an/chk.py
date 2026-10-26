"""Free-only checks: exclusion lists, create-slot/early-buy, entry mcap (entry px * current supply). Public RPC only."""
import json,sys,os,statistics as st,re,time
sys.path.insert(0,'/workspace/scout'); import analyze as A; from pub import rpc
OI='/workspace/onchain-intel/'
txt=''.join(open(OI+f).read() for f in ['known_funders.csv','avoid.csv','known_ruggers.json','custodial_ignore.json'])
NMAX=int(os.environ.get('NMAX','12'))
cache=json.load(open('an/supply.json')) if os.path.exists('an/supply.json') else {}
def supply(m):
    if m not in cache:
        r=rpc('getTokenSupply',[m]); cache[m]=float(r['value']['uiAmount']) if r else None
    return cache[m]
for w in sys.argv[1:]:
    o=json.load(open(f'an/wg/{w}.json')); sw=A.swaps(o['tx']); R,_=A.rounds(sw)
    listed=w in txt
    # first buy per mint
    fb={}
    for s in sw:
        if s['side']=='buy' and s['mint'] not in fb: fb[s['mint']]=s
    mints=list(fb)[-NMAX:]
    early=[];mc=[];ok=0
    for m in mints:
        s=fb[m]
        tx=rpc('getTransaction',[s['sig'],{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}])
        if not tx: continue
        ok+=1
        logs=tx['meta'].get('logMessages') or []
        create=any('Instruction: Create' in l or 'InitializeMint' in l for l in logs)
        prior=rpc('getSignaturesForAddress',[m,{"before":s['sig'],"limit":1000}]) or []
        gap=tx['slot']-prior[-1]['slot'] if prior and len(prior)<1000 else None
        if create or (gap is not None and gap<=2): early.append((m[:6],create,gap,len(prior)))
        sp=supply(m)
        if sp: mc.append(s['usd']/s['tok']*sp)
    # entry mcap for closed rounds too
    for r in R:
        sp=supply(r['mint']) if r['mint'] in cache else None
        if sp: mc.append(r['entry_price_usd']*sp)
    json.dump(cache,open('an/supply.json','w'))
    res={'listed':listed,'checked_mints':len(mints),'tx_ok':ok,'create_or_slotgap<=2':early,'med_entry_mcap_usd':round(st.median(mc)) if mc else None,'share_mcap>100k':round(sum(x>1e5 for x in mc)/len(mc),2) if mc else None}
    print(w,res,flush=True)
