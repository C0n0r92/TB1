"""Quick prescreen for Zero's 11:34 bar (no network): closed7>=15, net/exbest>0 (5% costs, price-capped),
median capped trade >0 at 4% RT, median hold 1-30 min, swapped in last 24h, share of swaps 00-20 UTC."""
import json,sys,time,statistics as st,os
sys.path.insert(0,'/workspace/scout'); import analyze as A
now=time.time(); D=7*86400
ws=sys.argv[1:] or [f[:-5] for f in os.listdir('an/wg') if f.endswith('.json')]
rows=[]
for w in ws:
    try: o=json.load(open(f'an/wg/{w}.json'))
    except Exception: continue
    if not o['tx']: continue
    sw=A.swaps(o['tx']); Rall,_=A.rounds(sw); R=[x for x in Rall if x['exit_ts']>now-D]
    if not R or not sw: continue
    oldest=min(x['ts'] for x in o['tx'])
    cr=[]
    for x in R:
        sr=x['size_out_sol']/x['size_in_sol']-1
        pr=(x['exit_price_usd']/x['entry_price_usd']-1) if x['entry_price_usd'] and x['exit_price_usd'] else sr
        cr.append(min(sr,pr))
    cn=[x['size_in_sol']*(c-0.05) for x,c in zip(R,cr)]
    med=st.median(c-0.04 for c in cr)*100
    hold=st.median((x['exit_ts']-x['entry_ts'])/60 for x in R)
    sw7=[s for s in sw if s['ts']>now-D]; last=max(s['ts'] for s in sw)
    eu=sum(1 for s in sw7 if time.gmtime(s['ts']).tm_hour<20)/max(len(sw7),1)
    d=dict(w=w,cov7=(not o.get('truncated')) or oldest<now-D,closed7=len(R),cons=round(sum(cn),2),cexb=round(sum(cn)-max(cn),2),med4=round(med,1),hold=round(hold,1),idle_h=round((now-last)/3600,1),eu_share=round(eu,2))
    fails=[]
    if not d['cov7']: fails.append('coverage<7d')
    if d['closed7']<15: fails.append(f"closed {d['closed7']}<15")
    if d['cons']<=0: fails.append(f"net {d['cons']}")
    if d['cexb']<=0: fails.append(f"ex-best {d['cexb']}")
    if med<=0: fails.append(f"median {d['med4']}%")
    if not (1<=hold<=30): fails.append(f"hold {d['hold']}m")
    if d['idle_h']>24: fails.append(f"idle {d['idle_h']}h")
    if eu<0.5: fails.append(f"00-20UTC share {d['eu_share']}")
    d['fails']=fails; rows.append(d)
rows.sort(key=lambda d:len(d['fails']))
for d in rows: print('PRE-PASS' if not d['fails'] else len(d['fails']),d['w'],d['closed7'],d['cons'],d['cexb'],d['med4'],d['hold'],d['idle_h'],d['eu_share'],d['fails'])
