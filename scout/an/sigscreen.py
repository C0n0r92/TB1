import json,time,sys,collections
sys.path.insert(0,'/workspace/scout'); from pub import rpc
from concurrent.futures import ThreadPoolExecutor
C=json.load(open('an/gt_cands.json'))[:int(sys.argv[1])]; now=time.time(); out={}
def f(w):
    r=rpc("getSignaturesForAddress",[w,{"limit":1000}])
    if r is None: return
    ts=[x['blockTime'] for x in r if x.get('blockTime') and not x.get('err')]
    if not ts: return
    span=(now-min(ts))/3600; h=collections.Counter(time.gmtime(t).tm_hour for t in ts if t>now-14*86400)
    tot=sum(h.values()); day=sum(v for k,v in h.items() if 7<=k<20)
    out[w]={'n':len(r),'span_h':round(span,1),'per_h':round(len(ts)/max(span,0.1),1),'err':sum(1 for x in r if x.get('err')),'day_share':round(day/tot,2) if tot else None,'peak':[k for k,_ in h.most_common(3)]}
with ThreadPoolExecutor(3) as ex: list(ex.map(f,C))
json.dump(out,open('an/sigscreen.json','w'))
for w,v in sorted(out.items(),key=lambda x:x[1]['per_h']): print(w,v)
