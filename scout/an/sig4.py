import json,time,sys,collections,os
sys.path.insert(0,'/workspace/scout'); from pub import rpc
C=json.load(open('an/gt3_cands.json'))[:int(sys.argv[1])]; now=time.time()
fn='an/sig4.json'; out=json.load(open(fn)) if os.path.exists(fn) else {}
for i,w in enumerate(C):
    if w in out: continue
    r=rpc("getSignaturesForAddress",[w,{"limit":1000}])
    if r is None: continue
    ts=[x['blockTime'] for x in r if x.get('blockTime') and not x.get('err')]
    if not ts: continue
    span=(now-min(ts))/3600; h=collections.Counter(time.gmtime(t).tm_hour for t in ts if t>now-14*86400)
    tot=sum(h.values()); day=sum(v for k,v in h.items() if 7<=k<20)
    out[w]={'n':len(r),'span_h':round(span,1),'per_h':round(len(ts)/max(span,0.1),1),'n2h':sum(t>now-7200 for t in ts),'err':sum(1 for x in r if x.get('err')),'day_share':round(day/tot,2) if tot else None,'peak':[k for k,_ in h.most_common(3)]}
    if i%25==0: json.dump(out,open(fn,'w')); print(i,flush=True)
json.dump(out,open(fn,'w')); print('done',len(out))
