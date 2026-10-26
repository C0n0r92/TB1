"""First-funder check (read-only): page sigs back up to MAXP pages; if the oldest is reached, read that tx and take the SOL sender."""
import json,sys; sys.path.insert(0,'/workspace/onchain-intel/bg'); from fetchlayer import rpc
MAXP=6; out={}
for w in sys.argv[1:]:
    before=None; last=None; reached=False
    for p in range(MAXP):
        q={"limit":1000}; 
        if before: q["before"]=before
        r=rpc('getSignaturesForAddress',[w,q])
        if not r: reached = r==[] ; break
        last=r[-1]; before=last['signature']
        if len(r)<1000: reached=True; break
    f=None
    if reached and last:
        t=rpc('getTransaction',[last['signature'],{"encoding":"jsonParsed","maxSupportedTransactionVersion":0}])
        try:
            for ix in t['transaction']['message']['instructions']:
                pi=ix.get('parsed') or {}
                if isinstance(pi,dict) and pi.get('type') in ('transfer','createAccount') and (pi['info'].get('destination')==w or pi['info'].get('newAccount')==w):
                    f=dict(funder=pi['info'].get('source'),sol=(pi['info'].get('lamports') or 0)/1e9,ts=t['blockTime']); break
            if not f: f=dict(funder=t['transaction']['message']['accountKeys'][0]['pubkey'],note='fee payer of first tx',ts=t['blockTime'])
        except Exception as e: f=dict(error=repr(e))
    out[w]=dict(oldest_reached=reached,first=f)
    print(w[:6],out[w],flush=True)
json.dump(out,open('funders_v2.json','w'),indent=1)
