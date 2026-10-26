"""24h sig lists via public RPC (free), max 3 pages; marks busy wallets. Writes sig/<w>.json. Read-only."""
import json,sys,time,os
sys.path.insert(0,'/workspace/scout'); import pub; pub.RPC=os.environ.get("URL",pub.RPC); pub.GAP=float(os.environ.get("PGAP","0.3")); from pub import rpc
now=time.time(); cut=now-86400
for w in sys.argv[1:]:
    out=[];before=None;busy=False
    for page in range(3):
        p={"limit":1000}
        if before:p["before"]=before
        r=rpc("getSignaturesForAddress",[w,p])
        if not r: break
        out+=[{'s':x['signature'],'t':x.get('blockTime'),'e':x.get('err') is not None} for x in r]
        if len(r)<1000 or (r[-1].get('blockTime') or 0)<cut: break
        before=r[-1]['signature']
    else: busy=True
    ok=[x for x in out if not x['e'] and (x['t'] or 0)>=cut]
    json.dump({'fetched':now,'sigs':ok,'spam':busy,'oldest':min((x['t'] or now) for x in out) if out else now},open(f'sig/{w}.json','w'))
    print(w[:6],'ok24',len(ok),'err',sum(x['e'] for x in out),'busy',busy,flush=True)
