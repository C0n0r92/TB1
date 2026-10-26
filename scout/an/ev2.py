import json,sys,time,statistics as st,collections,os
sys.path.insert(0,'/workspace/scout'); import analyze as A
now=time.time(); res={}
for w in sys.argv[1:]:
    fn=f'an/wg/{w}.json'
    if not os.path.exists(fn): continue
    o=json.load(open(fn)); sw=A.swaps(o['tx'])
    if not sw: print(w[:8],'no swaps'); continue
    span=(now-min(x['ts'] for x in o['tx']))/86400
    R,op=A.rounds(sw); ts=[s['ts'] for s in sw]
    h=collections.Counter(time.gmtime(t).tm_hour for t in ts if t>now-14*86400); n14=sum(h.values())
    day=sum(v for k,v in h.items() if 7<=k<20)/max(n14,1)
    r={'span_d':round(span,1),'n_swaps':len(sw),'last':A.iso(max(ts)),'sw1h':sum(t>now-3600 for t in ts),'sw2h':sum(t>now-7200 for t in ts),'closed':len(R),'open':op,'day_share':round(day,2),'peak':[k for k,_ in h.most_common(3)],'pump_share':round(sum(1 for x in sw if x['pump'])/len(sw),2)}
    if R:
        net=[x['size_out_sol']-x['size_in_sol']*1.05 for x in R]; pct=[(x['size_out_sol']/x['size_in_sol']-1.05)*100 for x in R]
        r.update(win=round(sum(p>0 for p in pct)/len(R),2),med_pct=round(st.median(pct),1),sum_sol=round(sum(net),2),sum_ex_best=round(sum(net)-max(net),2),
          med_hold=round(st.median((x['exit_ts']-x['entry_ts'])/60 for x in R),1),med_size=round(st.median(x['size_in_sol'] for x in R),2),
          pct_ret=round(sum(net)/sum(x['size_in_sol'] for x in R)*100,1))
        for d in (7,30):
            RR=[(n,x) for n,x in zip(net,R) if x['exit_ts']>now-d*86400]
            r[f'pnl{d}d']=round(sum(n for n,_ in RR),2); r[f'pct{d}d']=round(sum(n for n,_ in RR)/max(sum(x['size_in_sol'] for _,x in RR),1e-9)*100,1)
    res[w]=r; print(w, r, flush=True)
json.dump(res,open('an/ev2_%s.json'%os.getpid(),'w'))
