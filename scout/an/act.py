import json,time,sys
sys.path.insert(0,'/workspace/scout'); from pub import rpc
ws=json.load(open(sys.argv[1])); now=time.time(); out={}
for w in ws:
    r=rpc("getSignaturesForAddress",[w,{"limit":200}]) or []
    ts=[x['blockTime'] for x in r if x.get('blockTime') and not x.get('err')]
    out[w]={'n1h':sum(t>now-3600 for t in ts),'n2h':sum(t>now-7200 for t in ts),'last':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(max(ts))) if ts else None,'n200_span_h':round((now-min(ts))/3600,1) if ts else None}
    print(w,out[w],flush=True)
json.dump(out,open(sys.argv[2],'w'))
