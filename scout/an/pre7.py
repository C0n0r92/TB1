"""Quick 7d prescreen from cached an/wg/<w>.json (no network)."""
import json,sys,time,statistics as st,os
sys.path.insert(0,'/workspace/scout'); import analyze as A
now=time.time(); D=7*86400
ws=sys.argv[1:] or [f[:-5] for f in os.listdir('an/wg') if f.endswith('.json')]
for w in ws:
    try: o=json.load(open(f'an/wg/{w}.json'))
    except Exception as e: print(w[:6],'ERR',e); continue
    if not o['tx']: print(w[:6],'no tx'); continue
    sw=A.swaps(o['tx']); Rall,_=A.rounds(sw); R=[x for x in Rall if x['exit_ts']>now-D]
    oldest=min(x['ts'] for x in o['tx'])
    if not R: print(w[:6],'closed7=0'); continue
    net=[x['size_out_sol']-x['size_in_sol']*1.05 for x in R]
    cn=[]
    for x in R:
        sr=x['size_out_sol']/x['size_in_sol']-1
        pr=(x['exit_price_usd']/x['entry_price_usd']-1) if x['entry_price_usd'] and x['exit_price_usd'] else sr
        cn.append(x['size_in_sol']*(min(sr,pr)-0.05))
    hold=st.median((x['exit_ts']-x['entry_ts'])/60 for x in R)
    ok=len(R)>=15 and sum(net)>0 and sum(net)-max(net)>0 and sum(cn)>0 and sum(cn)-max(cn)>0 and hold>=30
    print('PRE-PASS' if ok else '        ',w,dict(cov_d=round((now-oldest)/86400,1),trunc=o.get('truncated'),closed7=len(R),net=round(sum(net),2),exb=round(sum(net)-max(net),2),cons=round(sum(cn),2),cexb=round(sum(cn)-max(cn),2),hold=round(hold,1)),flush=True)
