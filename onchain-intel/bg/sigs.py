"""Signature lists (public RPC, free) for candidates, 7d window. Cached to sig/<w>.json. Read-only."""
import json,sys,time,os
sys.path.insert(0,'/workspace/scout'); from pub import rpc
os.makedirs('sig',exist_ok=True)
C=json.load(open('cands.json')); now=time.time(); cut=now-7*86400
ws=sys.argv[1:] or [w for w in C if not os.path.exists(f'sig/{w}.json')]
for w in ws:
    fn=f'sig/{w}.json'
    out=[];before=None;spam=False
    while True:
        p={"limit":1000}
        if before:p["before"]=before
        r=rpc("getSignaturesForAddress",[w,p])
        if r is None: print('rpc fail',w); break
        out+=[{'s':x['signature'],'t':x.get('blockTime'),'e':x.get('err') is not None,'slot':x['slot']} for x in r]
        if not r or len(r)<1000 or (r[-1].get('blockTime') or 0)<cut: break
        if len(out)>=5000 and sum(1 for x in out if x['e'])>0.8*len(out): print('SPAM',w,flush=True); spam=True; break
        before=r[-1]['signature']
    ok=[x for x in out if not x['e'] and (x['t'] or 0)>=cut]
    json.dump({'fetched':now,'sigs':ok,'spam':spam,'oldest':min((x['t'] or now) for x in out) if out else now},open(fn,'w'))
    n24=sum(1 for x in ok if x['t']>=now-86400)
    last=max((x['t'] for x in ok),default=0)
    print(C.get(w,{}).get('name'),w[:6],'7d',len(ok),'24h',n24,'idle_h',round((now-last)/3600,1) if last else None,flush=True)
