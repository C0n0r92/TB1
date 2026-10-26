"""Cheap activity triage: 1 getSignaturesForAddress(limit=200) per wallet via public RPC. Read-only. Writes triage.json."""
import json,sys,time,os
sys.path.insert(0,'/workspace/scout'); import pub; pub.RPC=os.environ.get("URL",pub.RPC); pub.GAP=float(os.environ.get("PGAP","0.3")); from pub import rpc
D=json.load(open('kolscan_directory.json')); C=json.load(open('cands.json'))
out=json.load(open('triage.json')) if os.path.exists('triage.json') else {}
now=time.time()
for w in D:
    if w in C or w in out or os.path.exists(f'sig/{w}.json'): continue
    r=rpc("getSignaturesForAddress",[w,{"limit":200}])
    if r is None: continue
    ok=[x.get('blockTime') or 0 for x in r if x.get('err') is None]
    out[w]=dict(name=D[w].get('name'),twitter=D[w].get('twitter'),n=len(r),ok=len(ok),ok_3h=sum(t>now-10800 for t in ok),ok_24h=sum(t>now-86400 for t in ok),last=max(ok) if ok else None)
    if len(out)%25==0: json.dump(out,open('triage.json.tmp','w')); os.replace('triage.json.tmp','triage.json')
json.dump(out,open('triage.json.tmp','w')); os.replace('triage.json.tmp','triage.json'); print('done',len(out))
