"""7d bar for selfcopy ask. Uses cached an/wg files (public RPC). Prints coverage flags."""
import json,sys,time,statistics as st,collections,os,glob
sys.path.insert(0,'/workspace/scout'); import analyze as A
now=time.time(); D=7*86400
ws=sys.argv[1:] or [os.path.basename(f)[:-5] for f in glob.glob('an/wg/*.json')]
out={}
for w in ws:
    fn=f'an/wg/{w}.json'
    if not os.path.exists(fn): continue
    o=json.load(open(fn)); sw=A.swaps(o['tx'])
    if not sw: continue
    oldest=min(x['ts'] for x in o['tx']); cov7=(not o.get('truncated')) or oldest<now-D
    R,_=A.rounds(sw); R=[x for x in R if x['exit_ts']>now-D]
    ts=[s['ts'] for s in sw if s['ts']>now-D]
    h=collections.Counter(time.gmtime(t).tm_hour for t in ts); n=sum(h.values())
    r={'cov7':cov7,'cover_d':round((now-oldest)/86400,1),'closed7':len(R),'last':A.iso(max(s['ts'] for s in sw)),
       'sw1h':sum(s['ts']>now-3600 for s in sw),'sw2h':sum(s['ts']>now-7200 for s in sw),
       'day_share':round(sum(v for k,v in h.items() if 7<=k<20)/max(n,1),2),'peak':[k for k,_ in h.most_common(3)]}
    if R:
        net=[x['size_out_sol']-x['size_in_sol']*1.05 for x in R]; pct=[(x['size_out_sol']/x['size_in_sol']-1.05)*100 for x in R]
        # sanity: SOL-return vs USD price-return
        bad=0
        for x in R:
            if x['entry_price_usd'] and x['exit_price_usd']:
                pr=x['exit_price_usd']/x['entry_price_usd']-1; sr=x['size_out_sol']/x['size_in_sol']-1
                if abs(sr-pr)>0.25 and abs(sr-pr)>0.5*abs(pr): bad+=1
        cr=[]
        for x in R:
            sr=x['size_out_sol']/x['size_in_sol']-1
            pr=(x['exit_price_usd']/x['entry_price_usd']-1) if x['entry_price_usd'] and x['exit_price_usd'] else sr
            cr.append(min(sr,pr))
        cn=[x['size_in_sol']*(c-0.05) for x,c in zip(R,cr)]
        r.update(net7c=round(sum(cn),2),ex_best7c=round(sum(cn)-max(cn),2),med_c=round(st.median(cr)*100-5,1))
        r.update(net7=round(sum(net),2),ex_best7=round(sum(net)-max(net),2),pct7=round(sum(net)/sum(x['size_in_sol'] for x in R)*100,1),
                 win=round(sum(p>0 for p in pct)/len(R),2),med_pct=round(st.median(pct),1),
                 med_hold=round(st.median((x['exit_ts']-x['entry_ts'])/60 for x in R),1),insane=bad)
    r['bar']=bool(R) and r['closed7']>=15 and r['net7']>0 and r['ex_best7']>0 and r['net7c']>0 and r['ex_best7c']>0 and r['med_hold']>=30
    out[w]=r
json.dump(out,open('an/ev7_out.json','w'))
for w,r in sorted(out.items(),key=lambda x:-x[1].get('net7',-1e9)):
    if r.get('closed7',0)>=15 and r.get('net7',-1)>0: print('BAR' if r['bar'] else '   ',w,r)
