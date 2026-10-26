import json,sys,time,statistics as st,collections
sys.path.insert(0,'/workspace/scout'); import analyze as A
now=time.time()
for w in sys.argv[1:]:
    o=json.load(open(f'data/w/{w}.json')); sw=A.swaps(o['tx'])
    if not sw: print(w[:8],'no swaps'); continue
    R,op=A.rounds(sw); ts=[s['ts'] for s in sw]
    h=collections.Counter(time.gmtime(t).tm_hour for t in ts); day=sum(v for k,v in h.items() if 7<=k<20)/len(ts)
    s=A.stats(R,1) if R else {}
    print(w[:8],'sw',len(sw),'span_h',round((now-min(ts))/3600,1),'last',A.iso(max(ts)),'1h',sum(t>now-3600 for t in ts),'2h',sum(t>now-7200 for t in ts),
      'closed',len(R),'open',op,{k:s.get(k) for k in ('win_5','med_pct_5','sum_sol_5','med_hold_min','med_size_sol')},'day',round(day,2),'pump',round(sum(1 for x in sw if x['pump'])/len(sw),2),'srcs',collections.Counter(x['src'] for x in o['tx']).most_common(2))
